"""Coordinator-Test mit Mock-Client (benötigt Home Assistant)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.const import (  # noqa: E402
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant  # noqa: E402
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,
)

from custom_components.secvest.api import SecvestData  # noqa: E402
from custom_components.secvest.const import CONF_VERIFY_SSL, DOMAIN  # noqa: E402
from custom_components.secvest.coordinator import SecvestCoordinator  # noqa: E402


async def test_coordinator_updates(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 4433,
            CONF_USERNAME: "tester",
            CONF_PASSWORD: "geheim",
            CONF_VERIFY_SSL: False,
        },
        options={},
    )
    entry.add_to_hass(hass)

    client = AsyncMock()
    client.async_get_data = AsyncMock(
        return_value=SecvestData(
            partitions={
                1: {"name": "EG", "state": "unset", "zones": ["301"]}
            }
        )
    )

    coordinator = SecvestCoordinator(hass, entry, client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data.partitions[1]["name"] == "EG"
    client.async_get_data.assert_awaited()
