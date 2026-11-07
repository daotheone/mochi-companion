from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from companion.companion import Companion
from companion.desktop.worker import Worker
from companion.fake_provider import FakeProvider
from companion.store import Store


def make_worker(qapp, tmp_path, provider):
    def factory():
        store = Store(tmp_path / "m.db")
        return Companion(store, provider, "P", interface="character", resume=False), store

    worker = Worker(factory)
    events: list[tuple] = []
    worker.state_changed.connect(lambda s: events.append(("state", s)))
    worker.replied.connect(lambda lines, noticed, expression, task: events.append(("reply", lines, noticed, expression)))
    worker.task_proposals = []
    worker.replied.connect(lambda *args: worker.task_proposals.append(args[3]))
    worker.failed.connect(lambda m: events.append(("failed", m)))
    worker.memories_changed.connect(lambda ms: events.append(("memories", len(ms))))
    worker.conversation_changed.connect(lambda ms: events.append(("conversation", [m.content for m in ms])))
    worker.recaps_changed.connect(lambda rs: events.append(("recaps", [r.text for r in rs])))
    worker.start()
    events.clear()
    return worker, events


def test_send_goes_thinking_then_replies_in_bubbles(qapp, tmp_path):
    worker, events = make_worker(qapp, tmp_path, FakeProvider(["one\ntwo"]))
    worker.send("hi")
    assert events[0] == ("state", "thinking")
    assert ("reply", ["one", "two"], None, "neutral") in events
    assert ("conversation", ["hi", "one\ntwo"]) in events


def test_reply_carries_the_expression(qapp, tmp_path):
    worker, events = make_worker(qapp, tmp_path, FakeProvider(["[feel: smirk]\none"]))
    worker.send("hi")
    assert ("reply", ["one"], None, "smirk") in events


def test_failure_reports_message_and_retry_recovers(qapp, tmp_path):
    provider = FakeProvider(["back"])
    provider.fail_with = "network down"
    worker, events = make_worker(qapp, tmp_path, provider)
    worker.send("hi")
    assert ("failed", "network down") in events
    assert events[-1][0] != "reply"
    provider.fail_with = None
    worker.retry()
    assert ("reply", ["back"], None, "neutral") in events


def test_observed_memory_is_passed_with_the_reply_and_can_be_confirmed(qapp, tmp_path):
    reply = "nice\n[observe: tags=study | likes small steps]"
    worker, events = make_worker(qapp, tmp_path, FakeProvider([reply]))
    worker.send("did two")
    noticed = next(e[2] for e in events if e[0] == "reply")
    assert noticed.kind == "observed"
    worker.confirm_memory(noticed.id)
    assert worker.companion.memories()[0].kind == "stated"


def test_memory_editing_round_trip(qapp, tmp_path):
    worker, events = make_worker(qapp, tmp_path, FakeProvider())
    worker.add_memory("likes tea", ["drink"])
    worker.edit_memory(1, "likes green tea")
    worker.set_memory_tags(1, ["tea"])
    worker.forget_memory(1)
    worker.forget_memory(1)  # already gone: no crash, just a refresh
    assert [e for e in events if e[0] == "memories"][-1] == ("memories", 0)


def test_new_conversation_writes_a_recap_and_it_can_be_deleted(qapp, tmp_path):
    worker, events = make_worker(qapp, tmp_path, FakeProvider(["hello", "Said hi. Nothing open."]))
    worker.send("hi")
    worker.new_conversation()
    assert ("recaps", ["Said hi. Nothing open."]) in events
    worker.delete_recap(worker.companion.recaps()[0].id)
    assert events[-1] == ("recaps", [])


def test_a_conversation_left_open_is_recapped_on_the_next_launch(qapp, tmp_path):
    first, _ = make_worker(qapp, tmp_path, FakeProvider(["hello"]))
    first.send("hi")
    first.shutdown()
    second, events = make_worker(qapp, tmp_path, FakeProvider(["Said hi."]))
    assert second.companion.recaps()[0].text == "Said hi."


def test_a_task_proposal_travels_with_the_reply_and_is_saved_only_on_accept(qapp, tmp_path):
    worker, events = make_worker(qapp, tmp_path, FakeProvider(["ok\n[task: due=2026-11-07T19:00 | gọi mẹ | mẹ dặn]"]))
    tasks = []
    worker.tasks_changed.connect(lambda ts, sessions: tasks.append([t.title for t in ts]))
    worker.send("nhớ gọi mẹ")
    proposal = worker.task_proposals[-1]
    assert proposal.title == "gọi mẹ" and tasks[-1] == []
    worker.accept_task(proposal)
    assert tasks[-1] == ["gọi mẹ"]


def test_check_ins_are_polled_and_answered(qapp, tmp_path):
    worker, events = make_worker(qapp, tmp_path, FakeProvider())
    notices = []
    worker.notice_changed.connect(notices.append)
    clock = [datetime(2026, 11, 7, 12)]
    worker.companion.clock = lambda: clock[0]
    worker.add_task("study", "", None, False)
    worker.start_focus(worker.companion.tasks()[0].id)
    worker.check_notices()
    assert notices == []
    clock[0] += timedelta(minutes=30)
    worker.check_notices()
    worker.check_notices()  # unchanged: reported once
    assert [n.kind for n in notices] == ["checkin"]
    worker.answer_notice(notices[-1], "done")
    assert notices[-1] is None and worker.companion.tasks()[0].status == "done"
