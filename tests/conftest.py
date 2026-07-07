"""Test-Setup.

Das HA-Test-Plugin nur laden, wenn Home Assistant installiert ist –
so laufen die reinen Parser-Tests (nur httpx) auch ohne HA/HA-Plugin,
während die Config-Flow-/Coordinator-Tests in CI mit HA laufen.
"""

try:  # pragma: no cover - abhängig von der Umgebung
    import homeassistant  # noqa: F401

    _HA_AVAILABLE = True
    pytest_plugins = "pytest_homeassistant_custom_component"
except ImportError:  # pragma: no cover
    _HA_AVAILABLE = False


if _HA_AVAILABLE:  # pragma: no cover - läuft nur in CI mit HA
    import pytest

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations):
        """Custom Component in HA-Tests ladbar machen."""
        yield
