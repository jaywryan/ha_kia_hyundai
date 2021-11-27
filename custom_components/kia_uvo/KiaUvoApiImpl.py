import logging

import requests

from homeassistant.util import dt as dt_util

from .const import *
from .Token import Token

_LOGGER = logging.getLogger(__name__)


class KiaUvoApiImpl:
    def __init__(
        self,
        hass,
        username: str,
        password: str,
        region: int,
        brand: int,
        use_email_with_geocode_api: bool = False,
        pin: str = "",
    ):
        self.hass = hass
        self.username = username
        self.password = password
        self.pin = pin
        self.use_email_with_geocode_api = use_email_with_geocode_api
        self.stamps = None
        self.region = region
        self.brand = brand
        self.last_action_tracked = False
        self.supports_soc_range = True

    async def login(self) -> Token:
        pass

    async def get_cached_vehicle_status(self, token: Token):
        pass

    async def check_last_action_status(self, token: Token):
        pass

    async def get_geocoded_location(self, lat, lon):
        email_parameter = ""
        if self.use_email_with_geocode_api:
            email_parameter = "&email=" + self.username

        url = (
            "https://nominatim.openstreetmap.org/reverse?lat="
            + str(lat)
            + "&lon="
            + str(lon)
            + "&format=json&addressdetails=1&zoom=18"
            + email_parameter
        )
        response = requests.get(url)
        response = response.json()
        return response

    async def update_vehicle_status(self, token: Token):
        pass

    async def lock_action(self, token: Token, action):
        pass

    async def start_climate(
        self, token: Token, set_temp, duration, defrost, climate, heating
    ):
        pass

    async def stop_climate(self, token: Token):
        pass

    async def start_charge(self, token: Token):
        pass

    async def stop_charge(self, token: Token):
        pass

    async def set_charge_limits(self, token: Token, ac_limit: int, dc_limit: int):
        pass

    def get_timezone_by_region(self) -> tzinfo:
        if REGIONS[self.region] == REGION_CANADA:
            return dt_util.UTC
        elif REGIONS[self.region] == REGION_EUROPE:
            return TIME_ZONE_EUROPE
        elif REGIONS[self.region] == REGION_USA:
            return dt_util.UTC

    def get_temperature_range_by_region(self):
        if REGIONS[self.region] == REGION_CANADA:
            return CA_TEMP_RANGE
        elif REGIONS[self.region] == REGION_EUROPE:
            return EU_TEMP_RANGE
        elif REGIONS[self.region] == REGION_USA:
            return USA_TEMP_RANGE
