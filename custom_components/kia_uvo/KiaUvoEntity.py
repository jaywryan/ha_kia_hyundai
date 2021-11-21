import logging
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .Vehicle import Vehicle
from .const import DOMAIN, DATA_VEHICLE_INSTANCE, TOPIC_UPDATE, BRANDS, ENTITIES

_LOGGER = logging.getLogger(__name__)

class KiaUvoEntity(Entity):
    def __init__(self, hass, config_entry, vehicle: Vehicle):
        self.hass = hass
        self.config_entry = config_entry
        self.vehicle = vehicle
        self.topic_update = TOPIC_UPDATE.format(vehicle.id)
        self.topic_update_listener = None
        self.update_method = None
        ENTITIES.append(self)

    async def async_added_to_hass(self):
        @callback
        def update():
            _LOGGER.debug(f"updates on main ...")
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.update_method = update

        await super().async_added_to_hass()
#        self.topic_update_listener = async_dispatcher_connect(
#            self.hass, self.topic_update, update
#        )
        @callback
        def cleanup():
            self.update_method = None
        self.async_on_remove(cleanup)
        self.update_from_latest_data()

    @property
    def available(self) -> bool:
        return not not self.vehicle

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.vehicle.id)},
            "name": self.vehicle.name,
            "manufacturer": BRANDS[self.vehicle.kia_uvo_api.brand],
            "model": self.vehicle.model,
            "engine_type": self.vehicle.engine_type,
            "sw_version": self.vehicle.registration_date,
            "via_device": (DOMAIN, self.vehicle.id),
        }

    @callback
    def update_from_latest_data(self):
        self.vehicle = self.hass.data[DOMAIN][DATA_VEHICLE_INSTANCE]
