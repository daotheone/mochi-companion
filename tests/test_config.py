import pytest

from companion.config import Config


def test_defaults():
    c = Config.load({})
    assert c.model == "openai/gpt-oss-20b" and c.history_limit == 20 and c.api_key is None


@pytest.mark.parametrize("bad", ["0", "-3", "abc"])
def test_invalid_history_limit_is_rejected(bad):
    with pytest.raises(SystemExit):
        Config.load({"MOCHI_HISTORY_LIMIT": bad})
