from unittest.mock import patch

from src.config import (
    get_config,
    get_data_retention_days,
    reload_config,
)


def test_reload_config_refreshes_cached_yaml():
    with patch("src.config.load_config", side_effect=[{"version": 1}, {"version": 2}]):
        reload_config()
        first = get_config()
        second = get_config()

        assert first == {"version": 1}
        assert second is first

        reloaded = reload_config()

    assert reloaded == {"version": 2}
    assert get_config() == {"version": 2}


def test_get_data_retention_days_alias_reads_storage_setting():
    with patch("src.config.load_config", return_value={"storage": {"inactive_user_retention_days": 45}}):
        reload_config()

    assert get_data_retention_days() == 45
