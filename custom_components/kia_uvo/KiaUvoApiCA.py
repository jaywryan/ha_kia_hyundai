import logging

from datetime import timedelta, datetime
import json
from aiohttp import ClientSession

from .const import (
    DOMAIN,
    BRANDS,
    BRAND_HYUNDAI,
    BRAND_KIA,
    DATE_FORMAT,
)
from .KiaUvoApiImpl import KiaUvoApiImpl
from .Token import Token

_LOGGER = logging.getLogger(__name__)


class KiaUvoApiCA(KiaUvoApiImpl):
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
        super().__init__(
            hass, username, password, region, brand, use_email_with_geocode_api, pin
        )

        self.last_action_tracked = True
        self.last_action_xid = None
        self.last_action_completed = False
        self.last_action_pin_auth = None

        if BRANDS[brand] == BRAND_KIA:
            self.BASE_URL: str = "kiaconnect.ca"
        elif BRANDS[brand] == BRAND_HYUNDAI:
            self.BASE_URL: str = "www.mybluelink.ca"
        self.old_vehicle_status = {}
        self.API_URL: str = "https://" + self.BASE_URL + "/tods/api/"
        self.API_HEADERS = {
            "content-type": "application/json;charset=UTF-8",
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36",
            "host": self.BASE_URL,
            "origin": "https://" + self.BASE_URL,
            "referer": "https://" + self.BASE_URL + "/login",
            "from": "SPA",
            "language": "0",
            "offset": "0",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
        self.api_session = ClientSession(raise_for_status=True)

    async def login(self) -> Token:
        username = self.username
        password = self.password

        # Sign In with Email and Password and Get Authorization Code

        url = self.API_URL + "lgn"
        data = {"loginId": username, "password": password}
        headers = self.API_HEADERS
        response = await self.api_session.post(url=url, json=data, headers=headers)
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {await response.text()}")
        response = await response.json()
        response = response["result"]
        access_token = response["accessToken"]
        refresh_token = response["refreshToken"]
        _LOGGER.debug(f"{DOMAIN} - Access Token Value {access_token}")
        _LOGGER.debug(f"{DOMAIN} - Refresh Token Value {refresh_token}")

        # Get Vehicles
        url = self.API_URL + "vhcllst"
        headers = self.API_HEADERS
        headers["accessToken"] = access_token
        response = await self.api_session.post(url=url, headers=headers)
        _LOGGER.debug(f"{DOMAIN} - Get Vehicles Response {await response.text()}")
        response = await response.json()
        response = response["result"]
        vehicle_name = response["vehicles"][0]["nickName"]
        vehicle_id = response["vehicles"][0]["vehicleId"]
        vehicle_model = response["vehicles"][0]["nickName"]
        vehicle_registration_date = response["vehicles"][0].get(
            "enrollmentDate", "missing"
        )

        valid_until = (datetime.now() + timedelta(hours=23)).strftime(DATE_FORMAT)

        token = Token({})
        token.set(
            access_token,
            refresh_token,
            None,
            vehicle_name,
            vehicle_id,
            None,
            vehicle_model,
            vehicle_registration_date,
            valid_until,
            "NoStamp",
        )

        return token

    async def get_cached_vehicle_status(self, token: Token):
        # Vehicle Status Call
        url = self.API_URL + "lstvhclsts"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id

        response = await self.api_session.post(url=url, headers=headers)
        response = await response.json()
        _LOGGER.debug(f"{DOMAIN} - get_cached_vehicle_status response {await response.text()}")
        response = response["result"]["status"]

        vehicle_status = {}
        vehicle_status["vehicleStatus"] = response
        vehicle_status["vehicleStatus"]["time"] = response["lastStatusDate"]

        # Service Status Call
        url = self.API_URL + "nxtsvc"
        response = await self.api_session.post(url=url, headers=headers)
        response = await response.json()
        _LOGGER.debug(f"{DOMAIN} - Get Service status data {await response.text()}")
        response = response["result"]["maintenanceInfo"]

        vehicle_status["odometer"] = {}
        vehicle_status["odometer"]["unit"] = response["currentOdometerUnit"]
        vehicle_status["odometer"]["value"] = response["currentOdometer"]

        vehicle_status["nextService"] = {}
        vehicle_status["nextService"]["unit"] = response["imatServiceOdometerUnit"]
        vehicle_status["nextService"]["value"] = response["imatServiceOdometer"]

        # Handles cars that have never had service
        if response.get("msopServiceOdometer"):
            vehicle_status["lastService"] = {}
            vehicle_status["lastService"]["unit"] = response["msopServiceOdometerUnit"]
            vehicle_status["lastService"]["value"] = response["msopServiceOdometer"]

        if not self.old_vehicle_status == {}:
            if (
                vehicle_status["odometer"]["value"]
                > self.old_vehicle_status["odometer"]["value"]
            ):
                vehicle_status["vehicleLocation"] = await self.get_location(token)
            else:
                vehicle_status["vehicleLocation"] = self.old_vehicle_status[
                    "vehicleLocation"
                ]
        else:
            vehicle_status["vehicleLocation"] = await self.get_location(token)

        self.old_vehicle_status = vehicle_status
        return vehicle_status

    async def get_location(self, token: Token):
        url = self.API_URL + "fndmcr"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        try:
            headers["pAuth"] = await self.get_pin_token(token)

            response = await self.api_session.post(
                url=url, headers=headers, data=json.dumps({"pin": self.pin})
            )
            response = await response.json()
            _LOGGER.debug(f"{DOMAIN} - Get Vehicle Location {await response.text()}")
            if response["responseHeader"]["responseCode"] != 0:
                raise Exception("No Location Located")

        except:
            _LOGGER.warning(f"{DOMAIN} - Get vehicle location failed")
            response = None
            return response
        else:
            return response["result"]

    async def get_pin_token(self, token: Token):
        url = self.API_URL + "vrfypin"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id

        response = await self.api_session.post(
            url=url, headers=headers, data=json.dumps({"pin": self.pin})
        )
        _LOGGER.debug(f"{DOMAIN} - Received Pin validation response {await response.text()}")
        response_json = await response.json()

        return response_json["result"]["pAuth"]

    async def update_vehicle_status(self, token: Token):
        url = self.API_URL + "rltmvhclsts"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id

        response = await self.api_session.post(url=url, headers=headers)
        response = await response.json()
        _LOGGER.debug(f"{DOMAIN} - Received forced vehicle data {await response.text()}")

    async def lock_action(self, token: Token, action):
        _LOGGER.debug(f"{DOMAIN} - Action for lock is: {action}")
        if action == "close":
            url = self.API_URL + "drlck"
            _LOGGER.debug(f"{DOMAIN} - Calling Lock")
        else:
            url = self.API_URL + "drulck"
            _LOGGER.debug(f"{DOMAIN} - Calling unlock")
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = await self.get_pin_token(token)

        response = await self.api_session.post(
            url, headers=headers, data=json.dumps({"pin": self.pin})
        )
        response_headers = response.headers
        self.last_action_xid = response_headers["transactionId"]
        self.last_action_pin_auth = headers["pAuth"]

        _LOGGER.debug(f"{DOMAIN} - Received lock_action response")

    async def start_climate(
        self, token: Token, set_temp, duration, defrost, climate, heating
    ):
        url = self.API_URL + "rmtstrt"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = await self.get_pin_token(token)

        set_temp = self.get_temperature_range_by_region().index(set_temp)
        set_temp = hex(set_temp).split("x")
        set_temp = set_temp[1] + "H"
        set_temp = set_temp.zfill(3).upper()

        payload = {
            "setting": {
                "airCtrl": int(climate),
                "defrost": defrost,
                "heating1": int(heating),
                "igniOnDuration": duration,
                "ims": 0,
                "airTemp": {"value": set_temp, "unit": 0, "hvacTempType": 0},
            },
            "pin": self.pin,
        }
        # _LOGGER.debug(f"{DOMAIN} - Planned start_climate payload {payload}")

        response = await self.api_session.post(url=url, headers=headers, data=json.dumps(payload))
        response_headers = response.headers

        self.last_action_xid = response_headers["transactionId"]
        self.last_action_pin_auth = headers["pAuth"]

        _LOGGER.debug(f"{DOMAIN} - Received start_climate response {await response.text()}")

    async def start_climate_ev(
        self, token: Token, set_temp, duration, defrost, climate, heating
    ):
        url = self.API_URL + "evc/rfon"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = await self.get_pin_token(token)

        set_temp = self.get_temperature_range_by_region().index(set_temp)
        set_temp = hex(set_temp).split("x")
        set_temp = set_temp[1] + "H"
        set_temp = set_temp.zfill(3).upper()

        payload = {
            "hvacInfo": {
                "airCtrl": int(climate),
                "defrost": defrost,
                "heating1": int(heating),
                "airTemp": {
                    "value": set_temp,
                    "unit": 0,
                    "hvacTempType": 1,
                },
            },
            "pin": self.pin,
        }

        # _LOGGER.debug(f"{DOMAIN} - Planned start_climate_ev payload {payload}")

        response = self.api_session.post(url=url, headers=headers, data=json.dumps(payload))
        response_headers = response.headers

        self.last_action_xid = response_headers["transactionId"]
        self.last_action_pin_auth = headers["pAuth"]
        _LOGGER.debug(f"{DOMAIN} - Received start_climate_ev response {await response.text()}")

    async def stop_climate(self, token: Token):
        url = self.API_URL + "rmtstp"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = await self.get_pin_token(token)

        response = await self.api_session.post(
            url, headers=headers, data=json.dumps({"pin": self.pin})
        )
        response_headers = response.headers

        self.last_action_xid = response_headers["transactionId"]
        self.last_action_pin_auth = headers["pAuth"]

        _LOGGER.debug(f"{DOMAIN} - Received stop_climate response")

    async def stop_climate_ev(self, token: Token):
        url = self.API_URL + "evc/rfoff"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = await self.get_pin_token(token)

        response = await self.api_session.post(
            url=url, headers=headers, data=json.dumps({"pin": self.pin})
        )
        response_headers = response.headers

        self.last_action_xid = response_headers["transactionId"]
        self.last_action_pin_auth = headers["pAuth"]

        _LOGGER.debug(f"{DOMAIN} - Received stop_climate response")

    async def check_last_action_status(self, token: Token):
        url = self.API_URL + "rmtsts"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["transactionId"] = self.last_action_xid
        headers["pAuth"] = self.last_action_pin_auth
        response = await self.api_session.post(url=url, headers=headers)
        response = await response.json()

        self.last_action_completed = (
            response["result"]["transaction"]["apiStatusCode"] != "null"
        )
        if self.last_action_completed:
            action_status = response["result"]["transaction"]["apiStatusCode"]
            _LOGGER.debug(f"{DOMAIN} - Last action_status: {action_status}")
        return self.last_action_completed

    async def start_charge(self, token: Token):
        url = self.API_URL + "evc/rcstrt"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = await self.get_pin_token(token)

        response = await self.api_session.post(
            url=url, headers=headers, data=json.dumps({"pin": self.pin})
        )
        response_headers = response.headers

        self.last_action_xid = response_headers["transactionId"]
        self.last_action_pin_auth = headers["pAuth"]

        _LOGGER.debug(f"{DOMAIN} - Received start_charge response {await response.text()}")

    async def stop_charge(self, token: Token):
        url = self.API_URL + "evc/rcstp"
        headers = self.API_HEADERS
        headers["accessToken"] = token.access_token
        headers["vehicleId"] = token.vehicle_id
        headers["pAuth"] = await self.get_pin_token(token)

        response = await self.api_session.post(
            url=url, headers=headers, data=json.dumps({"pin": self.pin})
        )
        response_headers = response.headers
        self.last_action_xid = response_headers["transactionId"]
        self.last_action_pin_auth = headers["pAuth"]

        _LOGGER.debug(f"{DOMAIN} - Received start_charge response {await response.text()}")
