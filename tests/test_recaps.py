from datetime import datetime, timedelta

import pytest

from companion.companion import Companion
from companion.fake_provider import FakeProvider
from companion.provider import ProviderError
from companion.store import Store

START = datetime(2026, 11, 6, 22, 0)


class Clock:
    def __init__(self):
        self.now = START

    def __call__(self):
        return self.now

    def advance(self, **delta):
        self.now += timedelta(**delta)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def db(tmp_path):
    return tmp_path / "mochi.db"


def launch(db, provider, clock, interface="character", resume=False, **options):
    return Companion(Store(db), provider, "PERSONA", interface=interface, resume=resume, clock=clock, **options)


def finished_conversation(db, clock, recap_text="Unity kept crashing on build. Left unresolved.", **kw):
    """One Conversation that has ended, with its Recap written (so the DB already holds one)."""
    c = launch(db, FakeProvider(["hello", recap_text]), clock, **kw)
    c.send("my unity is broken")
    c.new_conversation()
    assert c.write_recaps() == 1
    c.store.close()


def system_of_last_call(provider):
    return provider.calls[-1][0]


def test_recap_is_written_when_a_conversation_ends_and_listed(db, clock):
    provider = FakeProvider(["hello", "Unity kept crashing on build. Left unresolved."])
    c = launch(db, provider, clock)
    c.send("my unity is broken")
    assert c.recaps() == []  # still going

    c.new_conversation()
    assert c.write_recaps() == 1

    [recap] = c.recaps()
    assert recap.text == "Unity kept crashing on build. Left unresolved."
    assert recap.interface == "character"
    assert recap.ended_at == START
    persona, messages = provider.calls[-1]
    assert "Recap" in persona
    assert "my unity is broken" in messages[0].content and "hello" in messages[0].content
    assert c.write_recaps() == 0  # nothing left to do, no extra model call
    assert len(provider.calls) == 2


def test_recap_never_becomes_a_memory(db, clock):
    finished_conversation(db, clock)
    c = launch(db, FakeProvider(), clock)
    assert c.memories() == []


def test_next_launch_recaps_a_conversation_that_never_ended_cleanly(db, clock):
    first = launch(db, FakeProvider(["hello"]), clock)
    first.send("my unity is broken")
    first.store.close()  # no clean exit

    clock.advance(hours=2)
    provider = FakeProvider(["Unity broke; left unresolved.", "yo"])
    second = launch(db, provider, clock)
    second.send("hi again")
    assert [r.text for r in second.recaps()] == ["Unity broke; left unresolved."]


def test_first_message_waits_for_the_recap_then_prompt_carries_it_with_its_age(db, clock):
    finished_conversation(db, clock)
    clock.advance(hours=5)
    provider = FakeProvider(["hey"])
    c = launch(db, provider, clock)
    c.send("hi")
    system = system_of_last_call(provider)
    assert "Left unresolved" in system
    assert "5 hours ago" in system


def test_recap_older_than_three_days_is_not_sent_but_stays_listed(db, clock):
    finished_conversation(db, clock)
    clock.advance(days=3, hours=1)
    provider = FakeProvider(["hey"])
    c = launch(db, provider, clock)
    c.send("hi")
    assert "Unity" not in system_of_last_call(provider)
    assert len(c.recaps()) == 1


def test_recap_within_three_days_is_sent(db, clock):
    finished_conversation(db, clock)
    clock.advance(days=2)
    provider = FakeProvider(["hey"])
    c = launch(db, provider, clock)
    c.send("hi")
    assert "2 days ago" in system_of_last_call(provider)


def test_cutoff_is_configurable(db, clock):
    finished_conversation(db, clock)
    clock.advance(days=2)
    provider = FakeProvider(["hey"])
    c = launch(db, provider, clock, recap_max_days=1)
    c.send("hi")
    assert "Unity" not in system_of_last_call(provider)


def test_fresh_and_older_recaps_are_labelled_so_the_persona_can_fade_them(db, clock):
    finished_conversation(db, clock)
    clock.advance(hours=3)
    fresh = FakeProvider(["hey"])
    launch(db, fresh, clock).send("hi")
    clock.advance(hours=30)
    older = FakeProvider(["hey"])
    launch(db, older, clock).send("hi")
    assert "fresh" in system_of_last_call(fresh)
    assert "fresh" not in system_of_last_call(older)


def test_a_second_conversation_the_same_day_sees_the_first_recap(db, clock):
    c = launch(db, FakeProvider(["a", "Fixed the crash: it was one line. Resolved.", "b"]), clock)
    c.send("crash")
    c.new_conversation()
    clock.advance(hours=1)
    c.send("new topic")  # recap is written first, then the reply
    system = system_of_last_call(c.provider)
    assert "Resolved" in system and "1 hour ago" in system
    assert "just before this one" in system


def test_sensitive_recap_is_flagged_for_the_persona(db, clock):
    finished_conversation(db, clock, recap_text="[sensitive]\nA bad night; user was low. Left open.")
    provider = FakeProvider(["hey"])
    c = launch(db, provider, clock)
    c.send("hi")
    system = system_of_last_call(provider)
    assert "never bring up first" in system
    assert "[sensitive]" not in system
    assert "A bad night" in system
    assert c.recaps()[0].sensitive is True


def test_recap_failure_never_blocks_the_reply_and_is_retried_later(db, clock):
    first = launch(db, FakeProvider(["hello"]), clock)
    first.send("my unity is broken")
    first.store.close()

    provider = FakeProvider([ProviderError("down"), "reply 1", "Unity broke. Unresolved.", "reply 2"])
    c = launch(db, provider, clock)
    assert c.send("hi") == "reply 1"
    assert c.recaps() == []
    assert "Unity" not in system_of_last_call(provider)

    clock.advance(minutes=30)
    assert c.send("hello?") == "reply 2"
    assert len(c.recaps()) == 1
    assert "Unity broke" in system_of_last_call(provider)


def test_failed_recap_is_not_retried_on_every_message(db, clock):
    first = launch(db, FakeProvider(["hello"]), clock)
    first.send("my unity is broken")
    first.store.close()

    provider = FakeProvider([ProviderError("down"), "r1", "r2"])
    c = launch(db, provider, clock)
    c.send("one")
    c.send("two")  # straight after: no second recap attempt
    assert len(provider.calls) == 3


def test_recap_failure_when_ending_a_conversation_is_swallowed(db, clock):
    provider = FakeProvider(["hello", ProviderError("down")])
    c = launch(db, provider, clock)
    c.send("hi")
    c.new_conversation()
    assert c.write_recaps() == 0
    assert c.recaps() == []


def test_recaps_are_one_pool_across_interfaces(db, clock):
    finished_conversation(db, clock, interface="terminal", resume=False)
    clock.advance(hours=1)
    provider = FakeProvider(["hey"])
    c = launch(db, provider, clock, interface="character")
    c.send("hi")
    assert "Unity" in system_of_last_call(provider)


def test_the_conversation_in_progress_is_not_recapped(db, clock):
    provider = FakeProvider(["hello"])
    c = launch(db, provider, clock, interface="terminal", resume=True)
    c.send("hi")
    clock.advance(hours=1)
    c.send("still here")
    assert c.recaps() == []
    assert len(provider.calls) == 2


def test_deleted_recap_stays_deleted(db, clock):
    finished_conversation(db, clock)
    provider = FakeProvider(["hey"])
    c = launch(db, provider, clock)
    c.delete_recap(c.recaps()[0].id)
    c.send("hi")
    assert c.recaps() == []
    assert len(provider.calls) == 1  # no regenerated recap
    assert "Unity" not in system_of_last_call(provider)


def test_prompt_states_the_time_and_the_gap_since_the_last_message(db, clock):
    finished_conversation(db, clock)
    clock.advance(days=3, hours=2)
    provider = FakeProvider(["hey"])
    c = launch(db, provider, clock)
    c.send("hi")
    system = system_of_last_call(provider)
    assert "Local time:" in system
    assert "Last Message before this one: 3 days ago" in system


def test_gap_covers_an_app_left_open_for_days(db, clock):
    provider = FakeProvider(["a", "b"])
    c = launch(db, provider, clock, interface="terminal", resume=True)
    c.send("hi")
    clock.advance(days=4)
    c.send("back")
    assert "Last Message before this one: 4 days ago" in system_of_last_call(provider)


def test_no_gap_line_for_the_very_first_message(db, clock):
    provider = FakeProvider(["a"])
    launch(db, provider, clock).send("hi")
    assert "Last Message" not in system_of_last_call(provider)
