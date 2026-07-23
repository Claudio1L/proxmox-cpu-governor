from __future__ import annotations

import asyncio
import base64
import re
import shlex
import logging

import asyncssh
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PRIVATE_KEY,
    CONF_ROOT_PASSWORD,
    CONF_USERNAME,
    DEFAULT_PORT,
    DEFAULT_PRIVATE_KEY,
    DEFAULT_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

GOVERNOR_SCRIPT_PATH = "/usr/local/sbin/ha-cpu-governor"
SUDOERS_PATH = "/etc/sudoers.d/homeassistant-cpu-governor"

GOVERNOR_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 performance|powersave" >&2
    exit 2
fi

governor="$1"

case "$governor" in
    performance|powersave)
        ;;
    *)
        echo "Unsupported governor: $governor" >&2
        exit 2
        ;;
esac

found=0

for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    governor_file="${policy}/scaling_governor"
    available_file="${policy}/scaling_available_governors"

    [[ -f "$governor_file" ]] || continue

    if [[ -f "$available_file" ]] && ! grep -qw "$governor" "$available_file"; then
        echo "$governor is not supported by $policy" >&2
        exit 1
    fi

    printf '%s\\n' "$governor" > "$governor_file"
    found=1
done

if [[ "$found" -ne 1 ]]; then
    echo "No CPU frequency policies found" >&2
    exit 1
fi
"""


async def _read_public_key(private_key: str) -> str:
    """Extract the OpenSSH public key from the configured private key."""
    process = await asyncio.create_subprocess_exec(
        "ssh-keygen",
        "-y",
        "-f",
        private_key,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(stderr.decode().strip())

    public_key = stdout.decode().strip()

    if not public_key:
        raise RuntimeError("Unable to extract the SSH public key")

    return public_key


def _build_bootstrap_command(username: str, public_key: str) -> str:
    """Build the root command which prepares the Proxmox host."""
    encoded_script = base64.b64encode(
        GOVERNOR_SCRIPT.encode()
    ).decode()

    sudoers_content = (
        f"{username} ALL=(root) NOPASSWD: "
        f"{GOVERNOR_SCRIPT_PATH}\n"
    )
    encoded_sudoers = base64.b64encode(
        sudoers_content.encode()
    ).decode()

    quoted_username = shlex.quote(username)
    quoted_public_key = shlex.quote(public_key)

    return f"""
set -eu

if ! id -u {quoted_username} >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash {quoted_username}
fi

home_dir="$(getent passwd {quoted_username} | cut -d: -f6)"

test -n "$home_dir"

install -d -m 700 -o {quoted_username} -g {quoted_username} "$home_dir/.ssh"
touch "$home_dir/.ssh/authorized_keys"
chown {quoted_username}:{quoted_username} "$home_dir/.ssh/authorized_keys"
chmod 600 "$home_dir/.ssh/authorized_keys"

public_key={quoted_public_key}

if ! grep -qxF "$public_key" "$home_dir/.ssh/authorized_keys"; then
    printf '%s\\n' "$public_key" >> "$home_dir/.ssh/authorized_keys"
fi

printf '%s' {shlex.quote(encoded_script)} |
    base64 -d > {GOVERNOR_SCRIPT_PATH}

chown root:root {GOVERNOR_SCRIPT_PATH}
chmod 755 {GOVERNOR_SCRIPT_PATH}

printf '%s' {shlex.quote(encoded_sudoers)} |
    base64 -d > {SUDOERS_PATH}

chown root:root {SUDOERS_PATH}
chmod 440 {SUDOERS_PATH}

visudo -cf {SUDOERS_PATH}

test -r /sys/devices/system/cpu/cpufreq/policy0/scaling_governor

echo bootstrap_ok
"""


class ProxmoxCpuGovernorConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Configure Proxmox CPU Governor."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            username = user_input[CONF_USERNAME]
            private_key = user_input[CONF_PRIVATE_KEY]
            root_password = user_input[CONF_ROOT_PASSWORD]

            try:
                if not re.fullmatch(
                    r"[a-z_][a-z0-9_-]*[$]?",
                    username,
                ):
                    raise ValueError("Invalid Linux username")

                public_key = await _read_public_key(private_key)
                bootstrap_command = _build_bootstrap_command(
                    username,
                    public_key,
                )

                async with asyncssh.connect(
                    host,
                    port=port,
                    username="root",
                    password=root_password,
                    known_hosts=None,
                ) as connection:
                    result = await connection.run(
                        bootstrap_command,
                        check=True,
                    )

                    if "bootstrap_ok" not in result.stdout:
                        raise RuntimeError(
                            "Bootstrap did not complete"
                        )

                async with asyncssh.connect(
                    host,
                    port=port,
                    username=username,
                    client_keys=[private_key],
                    known_hosts=None,
                ) as connection:
                    result = await connection.run(
                        "cat "
                        "/sys/devices/system/cpu/cpufreq/"
                        "policy0/scaling_governor",
                        check=True,
                    )

                    governor = result.stdout.strip()

                    if governor not in (
                        "performance",
                        "powersave",
                    ):
                        errors["base"] = "unsupported_governor"
                    else:
                        await self.async_set_unique_id(host)
                        self._abort_if_unique_id_configured()

                        entry_data = {
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_USERNAME: username,
                            CONF_PRIVATE_KEY: private_key,
                        }

                        return self.async_create_entry(
                            title=f"Proxmox {host}",
                            data=entry_data,
                        )

            except Exception as ex:
                _LOGGER.exception("Bootstrap failed")
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(
                    CONF_PORT,
                    default=DEFAULT_PORT,
                ): int,
                vol.Required(
                    CONF_USERNAME,
                    default=DEFAULT_USERNAME,
                ): str,
                vol.Required(
                    CONF_PRIVATE_KEY,
                    default=DEFAULT_PRIVATE_KEY,
                ): str,
                vol.Required(CONF_ROOT_PASSWORD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD,
                        autocomplete="current-password",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
