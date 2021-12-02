import logging

from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_CONNECTIVITY,
)

from .vehicle import Vehicle
from .kia_uvo_entity import KiaUvoEntity, DeviceInfoMixin
from .const import DOMAIN, DATA_VEHICLE_INSTANCE

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES: int = 1


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigType, async_add_entities
):
    vehicle: Vehicle = hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]

    binary_instruments = [
        (
            "Hood",
            "door_hood_open",
            "mdi:car",
            "mdi:car",
            DEVICE_CLASS_DOOR,
        ),
        (
            "Trunk",
            "door_trunk_open",
            "mdi:car-back",
            "mdi:car-back",
            DEVICE_CLASS_DOOR,
        ),
        (
            "Door - Front Left",
            "door_front_left_open",
            "mdi:car-door",
            "mdi:car-door",
            DEVICE_CLASS_DOOR,
        ),
        (
            "Door - Front Right",
            "door_front_right_open",
            "mdi:car-door",
            "mdi:car-door",
            DEVICE_CLASS_DOOR,
        ),
        (
            "Door - Rear Left",
            "door_back_left_open",
            "mdi:car-door",
            "mdi:car-door",
            DEVICE_CLASS_DOOR,
        ),
        (
            "Door - Rear Right",
            "door_back_right_open",
            "mdi:car-door",
            "mdi:car-door",
            DEVICE_CLASS_DOOR,
        ),
        (
            "Engine",
            "engine_on",
            "mdi:engine",
            "mdi:engine-off",
            DEVICE_CLASS_POWER,
        ),
        (
            "Tire Pressure - All",
            "tire_all_on",
            "mdi:car-tire-alert",
            "mdi:tire",
            DEVICE_CLASS_PROBLEM,
        ),
        (
            "HVAC",
            "climate_hvac_on",
            "mdi:air-conditioner",
            "mdi:air-conditioner",
            DEVICE_CLASS_POWER,
        ),
        (
            "Defroster",
            "climate_defrost_on",
            "mdi:car-defrost-front",
            "mdi:car-defrost-front",
            DEVICE_CLASS_POWER,
        ),
        (
            "Rear Window Heater",
            "climate_heated_rear_window_on",
            "mdi:car-defrost-rear",
            "mdi:car-defrost-rear",
            DEVICE_CLASS_POWER,
        ),
        (
            "Side Mirror Heater",
            "climate_heated_side_mirror_on",
            "mdi:car-side",
            "mdi:car-side",
            DEVICE_CLASS_POWER,
        ),
        (
            "Steering Wheel Heater",
            "climate_heated_steering_wheel_on",
            "mdi:steering",
            "mdi:steering",
            DEVICE_CLASS_POWER,
        ),
        (
            "Low Fuel Light",
            "low_fuel_light_on",
            "mdi:gas-station-off",
            "mdi:gas-station",
            DEVICE_CLASS_PROBLEM,
        ),
        (
            "Charging",
            "ev_battery_charging",
            "mdi:battery-charging",
            "mdi:battery",
            DEVICE_CLASS_BATTERY_CHARGING,
        ),
        (
            "Plugged In",
            "ev_plugged_in",
            "mdi:power-plug",
            "mdi:power-plug-off",
            DEVICE_CLASS_PLUG,
        ),
    ]

    binary_sensors = []

    for description, key, on_icon, off_icon, device_class in binary_instruments:
        binary_sensors.append(
            InstrumentSensor(
                vehicle,
                description,
                key,
                on_icon,
                off_icon,
                device_class,
            )
        )

    async_add_entities(binary_sensors, True)
    async_add_entities([VehicleEntity(vehicle)], True)
    async_add_entities([APIActionInProgress(vehicle)], True)


class InstrumentSensor(KiaUvoEntity):
    def __init__(
        self,
        vehicle: Vehicle,
        description,
        key,
        on_icon,
        off_icon,
        device_class,
    ):
        super().__init__(vehicle)
        self._attr_unique_id = f"{DOMAIN}-{vehicle.identifier}-{key}"
        self._attr_device_class = device_class
        self._attr_name = f"{vehicle.name} {description}"

        self._key = key
        self._on_icon = on_icon
        self._off_icon = off_icon

    @property
    def icon(self):
        return self._on_icon if self.is_on else self._off_icon

    @property
    def is_on(self) -> bool:
        return getattr(self._vehicle, self._key)

    @property
    def state(self):
        if self._attr_device_class == DEVICE_CLASS_LOCK:
            return "off" if self.is_on else "on"
        return "on" if self.is_on else "off"

    @property
    def available(self) -> bool:
        return super() and getattr(self._vehicle, self._key) is not None


class VehicleEntity(KiaUvoEntity):
    def __init__(self, vehicle: Vehicle):
        super().__init__(vehicle)
        self._attr_unique_id = f"{DOMAIN}-{vehicle.identifier}-all-data"
        self._attr_name = f"{vehicle.name} Data"

    @property
    def state(self):
        return "on"

    @property
    def is_on(self) -> bool:
        return True

    @property
    def state_attributes(self):
        return {
            "vehicle_data": self._vehicle.__repr__(),
            "vehicle_name": self._vehicle.name,
        }


class APIActionInProgress(DeviceInfoMixin, Entity):
    _attr_should_poll = False

    def __init__(self, vehicle: Vehicle):
        self._vehicle = vehicle
        self._attr_unique_id = f"{DOMAIN}-API-action-in-progress"
        self._attr_device_class = DEVICE_CLASS_CONNECTIVITY
        self._attr_available = False
        self._attr_name = None

        self._is_on = False

    async def async_added_to_hass(self) -> None:
        self._vehicle.api_cloud.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        self._vehicle.api_cloud.remove_callback(self.async_write_ha_state)

    @property
    def name(self) -> str:
        return f"API Action ({self._vehicle.api_cloud.current_action_name()})"

    @property
    def available(self) -> bool:
        return not not self._vehicle

    @property
    def icon(self):
        return "mdi:api" if self.is_on else "mdi:api-off"

    @property
    def state(self):
        return "on" if self.is_on else "off"

    @property
    def is_on(self) -> bool:
        return not not self._vehicle and self._vehicle.api_cloud.action_in_progress()
