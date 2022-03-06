"""Config flow for Remootio integration."""
from __future__ import annotations

import logging
from typing import Any

from aioremootio import (
    ConnectionOptions,
    RemootioClientAuthenticationError,
    RemootioClientConnectionEstablishmentError,
)
from aioremootio.constants import (
    CONNECTION_OPTION_REGEX_API_AUTH_KEY,
    CONNECTION_OPTION_REGEX_API_SECRET_KEY,
    CONNECTION_OPTION_REGEX_HOST,
)
import voluptuous as vol
from voluptuous.error import RequiredFieldInvalid
from voluptuous.schema_builder import REMOVE_EXTRA

from homeassistant import config_entries
from homeassistant.components.cover import DEVICE_CLASS_GARAGE, DEVICE_CLASS_GATE
from homeassistant.const import CONF_DEVICE_CLASS, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_API_AUTH_KEY,
    CONF_API_SECRET_KEY,
    CONF_SERIAL_NUMBER,
    CONF_TITLE,
    DOMAIN,
)
from .exceptions import UnsupportedRemootioDeviceError
from .utils import get_serial_number

_LOGGER = logging.getLogger(__name__)

INPUT_VALIDATION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, msg="Host is required"): vol.All(
            vol.Coerce(str),
            vol.Match(CONNECTION_OPTION_REGEX_HOST),
            msg="Host appears to be invalid; it can be an IP address or a host name that complies with RFC-1123",
        ),
        vol.Required(CONF_API_SECRET_KEY, msg="API Secret Key is required"): vol.All(
            vol.Coerce(str),
            vol.Upper,
            vol.Match(CONNECTION_OPTION_REGEX_API_SECRET_KEY),
            msg="API Secret Key appears to be invalid; it must be a sequence of 64 characters and can contain only numbers and english letters",
        ),
        vol.Required(CONF_API_AUTH_KEY, msg="API Auth Key is required"): vol.All(
            vol.Coerce(str),
            vol.Upper,
            vol.Match(CONNECTION_OPTION_REGEX_API_AUTH_KEY),
            msg="API Auth Key appears to be invalid; it must be a sequence of 64 characters and can contain only numbers and english letters",
        ),
        vol.Required(
            CONF_DEVICE_CLASS,
            default=DEVICE_CLASS_GARAGE,
            msg="Controlled device's class is required",
        ): vol.All(
            vol.Coerce(str),
            vol.In([DEVICE_CLASS_GARAGE, DEVICE_CLASS_GATE]),
            msg="Controlled device's class appears to be invalid",
        ),
    },
    extra=REMOVE_EXTRA,
)

DEVICE_NAME = "Remootio Device"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""

    _LOGGER.debug("Validating input... Input [%s]", data)

    INPUT_VALIDATION_SCHEMA(data)

    connection_options: ConnectionOptions = ConnectionOptions(
        data[CONF_HOST], data[CONF_API_SECRET_KEY], data[CONF_API_AUTH_KEY]
    )

    device_serial_number: str = await get_serial_number(
        hass, connection_options, _LOGGER
    )

    return {
        CONF_TITLE: f"{DEVICE_NAME} (Host: {data[CONF_HOST]}, S/N: {device_serial_number})",
        CONF_SERIAL_NUMBER: device_serial_number,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remootio."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the class."""
        super().__init__()

        self.form_displayed = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        user_input = user_input or {}
        errors = {}

        if len(user_input) != 0:
            try:
                info = await validate_input(self.hass, user_input)
            except UnsupportedRemootioDeviceError:
                _LOGGER.debug("Remootio device isn't supported.", exc_info=True)
                return self.async_abort(reason="unsupported_device")
            except vol.MultipleInvalid as e:
                _LOGGER.error(
                    f"Invalid user input. MultipleInvalid.Errors [{e.errors}]"
                )
                for error in e.errors:
                    _LOGGER.debug(
                        f"Error [{error.__class__.__name__}] Path [{error.path[0]}]"
                    )
                    if isinstance(error, RequiredFieldInvalid):
                        errors[str(error.path[0])] = f"{error.path[0]}_required"
                    else:
                        errors[str(error.path[0])] = f"{error.path[0]}_invalid"
            except RemootioClientConnectionEstablishmentError:
                _LOGGER.error("Can't connect to Remootio device.")
                errors["base"] = "cannot_connect"
            except RemootioClientAuthenticationError:
                _LOGGER.error("Can't authenticate by the Remootio device.")
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception/error.")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info[CONF_SERIAL_NUMBER])
                self._abort_if_unique_id_configured(user_input)

                user_input[CONF_SERIAL_NUMBER] = info[CONF_SERIAL_NUMBER]

                return self.async_create_entry(title=info[CONF_TITLE], data=user_input)

        self.form_displayed = True

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_HOST,
                        default=user_input.get(CONF_HOST, vol.UNDEFINED),
                    ): vol.Coerce(str),
                    vol.Optional(
                        CONF_API_SECRET_KEY,
                        default=user_input.get(CONF_API_SECRET_KEY, vol.UNDEFINED),
                    ): vol.Coerce(str),
                    vol.Optional(
                        CONF_API_AUTH_KEY,
                        default=user_input.get(CONF_API_AUTH_KEY, vol.UNDEFINED),
                    ): vol.Coerce(str),
                    vol.Optional(
                        CONF_DEVICE_CLASS,
                        default=user_input.get(CONF_DEVICE_CLASS, DEVICE_CLASS_GARAGE),
                    ): vol.All(
                        vol.Coerce(str),
                        vol.In([DEVICE_CLASS_GARAGE, DEVICE_CLASS_GATE]),
                    ),
                },
                extra=REMOVE_EXTRA,
            ),
            errors=errors,
        )
