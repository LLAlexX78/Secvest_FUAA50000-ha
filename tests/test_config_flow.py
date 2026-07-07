"""Config-Flow-Tests (benötigen Home Assistant / pytest-HA-Plugin)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.const import (  # noqa: E402
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402

from custom_components.secvest.api import SecvestAuthError  # noqa: E402
from custom_components.secvest.const import CONF_VERIFY_SSL, DOMAIN  # noqa: E402

USER_INPUT = {
    CONF_HOST: "192.0.2.10",
    CONF_PORT: 4433,
    CONF_USERNAME: "tester",
    CONF_PASSWORD: "geheim",
    CONF_VERIFY_SSL: False,
}


async def test_user_flow_success(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.secvest.config_flow.SecvestClient.async_validate",
        new=AsyncMock(),
    ), patch(
        "custom_components.secvest.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.10"


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "custom_components.secvest.config_flow.SecvestClient.async_validate",
        new=AsyncMock(side_effect=SecvestAuthError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
