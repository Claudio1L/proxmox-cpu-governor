from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PRIVATE_KEY,
    CONF_USERNAME,
    DOMAIN,
)

UPDATE_INTERVAL = timedelta(seconds=30)


class ProxmoxCpuGovernorCoordinator(DataUpdateCoordinator[str]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        self.host = entry.data[CONF_HOST]
        self.port = entry.data[CONF_PORT]
        self.username = entry.data[CONF_USERNAME]
        self.private_key = entry.data[CONF_PRIVATE_KEY]

    async def _run_ssh(self, remote_command: str) -> str:
        process = await asyncio.create_subprocess_exec(
            "ssh",
            "-i",
            self.private_key,
            "-p",
            str(self.port),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            f"{self.username}@{self.host}",
            remote_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error = stderr.decode().strip() or "SSH command failed"
            raise UpdateFailed(error)

        return stdout.decode().strip()

    async def _async_update_data(self) -> str:
        return await self._run_ssh(
            "cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor"
        )

    async def async_set_governor(self, governor: str) -> None:
        await self._run_ssh(
            f"sudo -n /usr/local/sbin/ha-cpu-governor {governor}"
        )

        await self.async_request_refresh()
