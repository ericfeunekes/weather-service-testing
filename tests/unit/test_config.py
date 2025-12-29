import sys
from pathlib import Path

import pytest

# Ensure src is importable without installation
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src"))

from wxbench.config import ConfigError, WxConfig, load_config


def test_load_config_valid_environment():
    env = {
        "WX_LAT": "51.5",
        "WX_LON": "-0.12",
        "WX_TZ": "UTC",
        "WX_PROVIDER_ALPHA_KEY": "abc123",
        "WX_SECONDARY": "token",
    }

    config = load_config(env)

    assert isinstance(config, WxConfig)
    assert config.latitude == pytest.approx(51.5)
    assert config.longitude == pytest.approx(-0.12)
    assert config.timezone == "UTC"
    assert config.provider_keys == {
        "WX_PROVIDER_ALPHA_KEY": "abc123",
        "WX_SECONDARY": "token",
    }


def test_load_config_strips_whitespace():
    env = {
        "WX_LAT": " 51.5 ",
        "WX_LON": " -0.12 ",
        "WX_TZ": " UTC ",
        "WX_PROVIDER_ALPHA_KEY": " abc123\n",
        "WX_SECONDARY": "  ",
    }

    config = load_config(env)

    assert config.latitude == pytest.approx(51.5)
    assert config.longitude == pytest.approx(-0.12)
    assert config.timezone == "UTC"
    assert config.provider_keys == {"WX_PROVIDER_ALPHA_KEY": "abc123"}


def test_missing_required_values_raise_errors():
    env = {"WX_LAT": "", "WX_LON": "10", "WX_TZ": "UTC"}

    with pytest.raises(ConfigError):
        load_config(env)


def test_coordinate_bounds_are_enforced():
    env = {"WX_LAT": "-91", "WX_LON": "10", "WX_TZ": "UTC"}

    with pytest.raises(ConfigError):
        load_config(env)


def test_timezone_must_be_valid_iana_label():
    env = {"WX_LAT": "10", "WX_LON": "10", "WX_TZ": "Mars/Phobos"}

    with pytest.raises(ConfigError):
        load_config(env)
