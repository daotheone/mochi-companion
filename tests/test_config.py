import pytest

from companion.config import Config


def test_defaults():
    c = Config.load({})
    assert c.model == "deepseek-flash" and c.history_limit == 20 and c.api_key is None


@pytest.mark.parametrize("bad", ["0", "-3", "abc"])
def test_invalid_history_limit_is_rejected(bad):
    with pytest.raises(SystemExit):
        Config.load({"MOCHI_HISTORY_LIMIT": bad})


def test_memory_limit_defaults_to_five_and_can_be_set():
    assert Config.load({}).memory_limit == 5
    assert Config.load({"MOCHI_MEMORY_LIMIT": "8"}).memory_limit == 8


@pytest.mark.parametrize("bad", ["0", "abc"])
def test_invalid_memory_limit_is_rejected(bad):
    with pytest.raises(SystemExit):
        Config.load({"MOCHI_MEMORY_LIMIT": bad})


def test_recap_fading_thresholds_default_and_can_be_set():
    config = Config.load({})
    assert (config.recap_max_days, config.recap_fresh_hours) == (3, 24)
    config = Config.load({"MOCHI_RECAP_MAX_DAYS": "5", "MOCHI_RECAP_FRESH_HOURS": "12"})
    assert (config.recap_max_days, config.recap_fresh_hours) == (5, 12)
