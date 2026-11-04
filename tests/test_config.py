import pytest

from companion.config import Config


def test_defaults():
    c = Config.load({})
    assert c.model == "openai/gpt-oss-20b" and c.history_limit == 20 and c.api_key is None


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
