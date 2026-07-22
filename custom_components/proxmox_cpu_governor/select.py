from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SUPPORTED_GOVERNORS
from .coordinator import ProxmoxCpuGovernorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = ProxmoxCpuGovernorCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    async_add_entities(
        [ProxmoxCpuGovernorSelect(coordinator, entry)],
    )


class ProxmoxCpuGovernorSelect(
    CoordinatorEntity[ProxmoxCpuGovernorCoordinator],
    SelectEntity,
):
    _attr_has_entity_name = True
    _attr_name = "CPU governor"
    _attr_icon = "mdi:speedometer"
    _attr_options = SUPPORTED_GOVERNORS

    def __init__(
        self,
        coordinator: ProxmoxCpuGovernorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)

        self._attr_unique_id = f"{entry.entry_id}_cpu_governor"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Proxmox",
            "model": "CPU Governor",
        }

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data

    async def async_select_option(self, option: str) -> None:
        if option not in SUPPORTED_GOVERNORS:
            raise ValueError(f"Governor non supportato: {option}")

        await self.coordinator.async_set_governor(option)
