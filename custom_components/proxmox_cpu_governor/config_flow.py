from __future__ import annotations

import asyncio

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PRIVATE_KEY,
    CONF_USERNAME,
    DEFAULT_PORT,
    DEFAULT_PRIVATE_KEY,
    DEFAULT_USERNAME,
    DOMAIN,
)


class ProxmoxCpuGovernorConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
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

            try:
                process = await asyncio.create_subprocess_exec(
                    "ssh",
                    "-i",
                    private_key,
                    "-p",
                    str(port),
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=10",
                    f"{username}@{host}",
                    "cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    raise RuntimeError(stderr.decode().strip())

                governor = stdout.decode().strip()

                if governor not in ("performance", "powersave"):
                    errors["base"] = "unsupported_governor"
                else:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"Proxmox {host}",
                        data=user_input,
                    )

            except Exception:
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
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
