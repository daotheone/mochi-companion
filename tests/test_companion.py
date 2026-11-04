import pytest

from companion.companion import Companion
from companion.fake_provider import FakeProvider
from companion.provider import ChatMessage, ProviderError
from companion.store import Store


@pytest.fixture
def db(tmp_path):
    return tmp_path / "mochi.db"


def launch(db, provider, limit=20):
    return Companion(Store(db), provider, "PERSONA", limit)


def test_conversation_survives_restart(db):
    first = launch(db, FakeProvider(["hello anh"]))
    first.send("hi")
    first.store.close()

    provider = FakeProvider(["still here"])
    second = launch(db, provider)
    assert [(m.role, m.content) for m in second.recent_messages()] == [
        ("user", "hi"),
        ("assistant", "hello anh"),
    ]
    second.send("again")
    assert provider.calls[0][1] == [
        ChatMessage("user", "hi"),
        ChatMessage("assistant", "hello anh"),
        ChatMessage("user", "again"),
    ]
    assert provider.calls[0][0] == "PERSONA"


def test_new_conversation_starts_empty_and_becomes_the_latest(db):
    c = launch(db, FakeProvider())
    c.send("old")
    c.new_conversation()
    assert c.recent_messages() == []
    c.send("fresh")
    c.store.close()
    assert [m.content for m in launch(db, FakeProvider()).recent_messages()] == ["fresh", "ok"]


def test_only_last_n_messages_are_sent_but_all_stay_stored(db):
    provider = FakeProvider()
    c = launch(db, provider, limit=3)
    for i in range(3):
        c.send(f"m{i}")
    sent = [m.content for m in provider.calls[-1][1]]
    assert sent == ["m1", "ok", "m2"]
    assert len(c.recent_messages(100)) == 6


def test_failure_keeps_user_message_and_retry_resends_without_duplicating(db):
    provider = FakeProvider(["finally"])
    c = launch(db, provider)
    provider.fail_with = "network down"
    with pytest.raises(ProviderError):
        c.send("hello")
    assert [m.content for m in c.recent_messages()] == ["hello"]
    assert c.has_unanswered_message()

    provider.fail_with = None
    assert c.retry() == "finally"
    assert [(m.role, m.content) for m in c.recent_messages()] == [
        ("user", "hello"),
        ("assistant", "finally"),
    ]
    assert not c.has_unanswered_message()


def test_typing_new_message_after_failure_keeps_old_one_in_history(db):
    provider = FakeProvider()
    c = launch(db, provider)
    provider.fail_with = "quota"
    with pytest.raises(ProviderError):
        c.send("first")
    provider.fail_with = None
    c.send("second")
    assert [m.content for m in provider.calls[-1][1]] == ["first", "second"]


def test_retry_with_nothing_unanswered_is_an_error(db):
    c = launch(db, FakeProvider())
    with pytest.raises(ProviderError):
        c.retry()
