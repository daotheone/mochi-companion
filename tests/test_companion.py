import pytest

from companion.companion import Companion, UnknownMemory
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


def test_history_limit_zero_is_honoured_not_defaulted(db):
    c = launch(db, FakeProvider())
    c.send("hi")
    assert c.recent_messages(0) == []


def test_saved_memory_is_listed_as_stated_and_survives_restart(db):
    c = launch(db, FakeProvider())
    saved = c.remember("likes less sugar", ["Food", "diet"])
    c.store.close()

    (m,) = launch(db, FakeProvider()).memories()
    assert (m.id, m.text, m.tags, m.kind) == (saved.id, "likes less sugar", ("food", "diet"), "stated")


def test_edit_retag_and_forget_are_honored_after_restart(db):
    c = launch(db, FakeProvider())
    keep = c.remember("likes tea")
    gone = c.remember("hates mornings")
    c.edit(keep.id, "likes green tea")
    c.set_tags(keep.id, ["#drinks"])
    c.forget(gone.id)
    c.store.close()

    (m,) = launch(db, FakeProvider()).memories()
    assert (m.text, m.tags, m.kind) == ("likes green tea", ("drinks",), "stated")


def test_memory_ids_are_never_reused(db):
    c = launch(db, FakeProvider())
    first = c.remember("a")
    c.forget(first.id)
    assert c.remember("b").id != first.id


def test_unknown_memory_id_raises(db):
    c = launch(db, FakeProvider())
    for action in (lambda: c.edit(9, "x"), lambda: c.forget(9), lambda: c.set_tags(9, []), lambda: c.confirm(9)):
        with pytest.raises(UnknownMemory):
            action()


def test_observe_line_is_stripped_and_saved_as_observed(db):
    reply = "ô tốt\nthấy a làm từng bước ok hơn thì phải?\n[observe: tags=study,habits | starts studying after picking a small first step]"
    c = launch(db, FakeProvider([reply]))
    shown = c.send("làm đc 2 câu r")

    assert shown == "ô tốt\nthấy a làm từng bước ok hơn thì phải?"
    assert c.recent_messages()[-1].content == shown
    (m,) = c.memories()
    assert (m.kind, m.tags, m.text) == ("observed", ("study", "habits"), "starts studying after picking a small first step")
    assert c.last_proposal == m


def test_malformed_observe_line_is_dropped_silently(db):
    c = launch(db, FakeProvider(["ok\n[observe: no separator here]"]))
    assert c.send("hi") == "ok"
    assert c.memories() == []
    assert c.last_proposal is None


def test_only_the_first_observe_line_counts_and_duplicates_are_skipped(db):
    c = launch(db, FakeProvider([
        "a\n[observe: tags=x | likes tea]\n[observe: tags=y | hates rain]",
        "b\n[observe:tags=x |  Likes   TEA ]",
    ]))
    c.send("one")
    assert [m.text for m in c.memories()] == ["likes tea"]
    c.send("two")
    assert [m.text for m in c.memories()] == ["likes tea"]
    assert c.last_proposal is None


def test_confirming_or_editing_an_observed_memory_makes_it_stated(db):
    c = launch(db, FakeProvider(["a\n[observe: tags=x | one]", "b\n[observe: tags=x | two]"]))
    c.send("1")
    c.send("2")
    first, second = c.memories()
    c.confirm(first.id)
    c.edit(second.id, "two, corrected")
    assert [(m.kind, m.text) for m in c.memories()] == [("stated", "one"), ("stated", "two, corrected")]


def system_sent(provider):
    return provider.calls[-1][0]


def test_all_memories_are_injected_while_they_fit_and_observed_ones_are_hedged(db):
    provider = FakeProvider(["a\n[observe: tags=study | studies best at night]", "ok"])
    c = launch(db, provider)
    c.remember("likes less sugar", ["food"])
    c.send("hello")
    c.send("unrelated")

    sent = system_sent(provider)
    assert sent.startswith("PERSONA")
    assert "likes less sugar" in sent
    assert "not yet confirmed" in sent and "studies best at night" in sent
    assert sent.index("likes less sugar") < sent.index("not yet confirmed")


def test_over_budget_memories_are_selected_by_tag_and_keyword_and_core_stays(db):
    provider = FakeProvider()
    c = Companion(Store(db), provider, "PERSONA", memory_limit=2, memory_budget=120)
    c.remember("likes less sugar in drinks", ["food"])
    c.remember("studies best at night", ["study"])
    c.remember("call him anh", ["core"])
    for i in range(6):
        c.remember(f"filler fact number {i}", ["misc"])

    c.send("i want something sweet, less sugar please")
    sent = system_sent(provider)
    assert "likes less sugar in drinks" in sent
    assert "call him anh" in sent
    assert "studies best at night" not in sent
    assert "filler" not in sent

    c.send("my study plan")
    assert "studies best at night" in system_sent(provider)
    assert "likes less sugar" not in system_sent(provider)


def test_forgotten_memory_is_no_longer_injected(db):
    provider = FakeProvider()
    c = launch(db, provider)
    m = c.remember("likes tea")
    c.forget(m.id)
    c.send("hi")
    assert system_sent(provider) == "PERSONA"


def test_inline_observe_marker_is_stripped_and_still_saved(db):
    c = launch(db, FakeProvider(["hi [observe: tags=a | likes tea] there"]))
    shown = c.send("x")
    assert "observe" not in shown and "observe" not in c.recent_messages()[-1].content
    assert [m.text for m in c.memories()] == ["likes tea"]


def test_reply_that_is_only_a_marker_is_an_error_and_can_be_retried(db):
    provider = FakeProvider(["[observe: tags=a | likes tea]", "real reply"])
    c = launch(db, provider)
    with pytest.raises(ProviderError):
        c.send("x")
    assert c.has_unanswered_message() and c.memories() == []
    assert c.retry() == "real reply"


def test_common_words_do_not_count_as_keyword_matches(db):
    provider = FakeProvider()
    c = Companion(Store(db), provider, "PERSONA", memory_limit=2, memory_budget=30)
    c.remember("he likes the beach", ["travel"])
    c.remember("studies best at night", ["study"])
    c.send("he said the")
    assert system_sent(provider) == "PERSONA"


def test_conversation_is_created_on_the_first_message_not_at_launch(db):
    c = launch(db, FakeProvider())
    assert c.store.latest_conversation("terminal") is None
    c.send("hi")
    assert c.store.latest_conversation("terminal") == c.conversation_id


def test_each_interface_resumes_only_its_own_latest_conversation(db):
    terminal = Companion(Store(db), FakeProvider(), "P", interface="terminal")
    terminal.send("from terminal")
    character = Companion(Store(db), FakeProvider(), "P", interface="character", resume=False)
    assert character.recent_messages() == []
    character.send("from character")

    again = Companion(Store(db), FakeProvider(), "P", interface="terminal")
    assert [m.content for m in again.recent_messages()] == ["from terminal", "ok"]


def test_character_starts_a_new_conversation_each_launch_without_empty_ones(db):
    first = Companion(Store(db), FakeProvider(), "P", interface="character", resume=False)
    first.send("one")
    Companion(Store(db), FakeProvider(), "P", interface="character", resume=False)  # never sends
    second = Companion(Store(db), FakeProvider(), "P", interface="character", resume=False)
    second.send("two")
    assert second.conversation_id != first.conversation_id
    count = second.store._db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    assert count == 2


def test_memories_are_shared_between_interfaces(db):
    Companion(Store(db), FakeProvider(), "P", interface="terminal").remember("likes tea")
    provider = FakeProvider()
    Companion(Store(db), provider, "P", interface="character", resume=False).send("hi")
    assert "likes tea" in provider.calls[0][0]


def test_existing_database_without_interface_column_is_migrated(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(
        "CREATE TABLE conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL DEFAULT 'x');"
        "INSERT INTO conversations DEFAULT VALUES;"
    )
    old.commit()
    old.close()
    assert Store(path).latest_conversation("terminal") == 1
    assert Store(path).latest_conversation("character") is None
