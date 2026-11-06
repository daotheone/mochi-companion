from datetime import datetime, timedelta

import pytest

from companion.companion import Companion, FocusError, UnknownTask
from companion.fake_provider import FakeProvider
from companion.store import Store
from companion.tasks import load_lines, split_task

T0 = datetime(2026, 11, 7, 12, 0)


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


def make(db, replies=None, clock=None, **kwargs):
    clock = clock or Clock()
    return Companion(Store(db), FakeProvider(replies), "PERSONA", clock=clock, **kwargs), clock


@pytest.fixture
def db(tmp_path):
    return tmp_path / "mochi.db"


# --- the [task:] marker ---
def test_marker_with_due_title_and_why():
    text, p = split_task("ok\n[task: due=2026-11-07T19:00 | gọi mẹ | mẹ dặn]")
    assert text.strip() == "ok"
    assert (p.title, p.why, p.due, p.has_time) == ("gọi mẹ", "mẹ dặn", datetime(2026, 11, 7, 19), True)


def test_marker_without_due_or_why():
    _, p = split_task("[task: nộp bài]")
    assert (p.title, p.why, p.due, p.due_unreadable) == ("nộp bài", None, None, False)


def test_date_only_due_has_no_clock_time():
    _, p = split_task("[task: due=2026-11-08 | nộp bài]")
    assert (p.due, p.has_time) == (datetime(2026, 11, 8), False)


def test_unreadable_due_keeps_the_task_without_a_time():
    _, p = split_task("[task: due=tối mai | nộp bài | gấp]")
    assert (p.title, p.why, p.due, p.due_unreadable) == ("nộp bài", "gấp", None, True)


def test_marker_without_a_title_is_dropped_but_still_stripped():
    text, p = split_task("hi [task: due=2026-11-07T19:00 | ]")
    assert p is None and "task" not in text


def test_a_reply_with_a_marker_proposes_but_saves_nothing(db):
    c, _ = make(db, ["[feel: neutral]\nok\n[task: due=2026-11-07T19:00 | gọi mẹ | mẹ dặn]"])
    assert c.send("nhớ gọi mẹ 7h tối") == "ok"
    assert c.last_task_proposal.title == "gọi mẹ"
    assert c.tasks() == []
    c.send("again")  # the next reply carries none
    assert c.last_task_proposal is None


def test_accepting_links_the_task_to_its_conversation(db):
    c, _ = make(db, ["ok\n[task: due=2026-11-07T19:00 | gọi mẹ | mẹ dặn]"])
    c.send("hi")
    task = c.accept_task(c.last_task_proposal)
    assert (task.title, task.why, task.status, task.due_has_time) == ("gọi mẹ", "mẹ dặn", "open", True)
    assert task.conversation_id == c.conversation_id
    assert c.add_task("manual").conversation_id is None


# --- Task CRUD ---
def test_status_edit_and_delete(db):
    c, _ = make(db)
    t = c.add_task("a", "because", datetime(2026, 11, 9), False)
    c.edit_task(t.id, title="b", why=None, due=None)
    edited = c.tasks()[0]
    assert (edited.title, edited.why, edited.due) == ("b", None, None)
    c.complete_task(t.id)
    assert c.tasks("done")[0].closed_at == T0 and c.tasks("open") == []
    c.drop_task(t.id)
    assert c.tasks("dropped")
    c.delete_task(t.id)
    assert c.tasks() == []
    with pytest.raises(UnknownTask):
        c.complete_task(t.id)


def test_blank_title_is_rejected(db):
    c, _ = make(db)
    with pytest.raises(ValueError):
        c.add_task("   ")


# --- the prompt ---
def test_a_task_from_an_earlier_conversation_is_in_a_fresh_ones_prompt(db):
    c, _ = make(db, ["ok\n[task: due=2026-11-07T19:00 | gọi mẹ | mẹ dặn]"])
    c.send("hi")
    c.accept_task(c.last_task_proposal)
    c.new_conversation()
    c.send("hello")
    system = c.provider.calls[-1][0]
    assert "gọi mẹ" in system and "mẹ dặn" in system


def test_open_tasks_are_listed_most_urgent_first_and_do_not_fade(db):
    c, clock = make(db)
    c.add_task("no time")
    c.add_task("later", due=datetime(2026, 11, 20), has_time=False)
    c.add_task("soon", due=datetime(2026, 11, 7, 18), has_time=True)
    clock.advance(days=60)
    c.send("hi")
    block = c.provider.calls[-1][0].split("## Tasks")[1]
    assert block.index("soon") < block.index("later") < block.index("no time")
    assert "overdue" in block


def test_task_block_respects_its_budget(db, monkeypatch):
    monkeypatch.setattr("companion.companion.TASK_BUDGET_CHARS", 100)
    c, _ = make(db)
    for i in range(10):
        c.add_task(f"task number {i}")
    c.send("hi")
    block = c.provider.calls[-1][0]
    assert "more open Tasks not shown" in block and "task number 9" not in block


def test_recently_closed_tasks_and_a_running_focus_session_are_in_the_prompt(db):
    c, clock = make(db)
    done, old, running = c.add_task("done one"), c.add_task("old one"), c.add_task("running one")
    c.complete_task(old.id)
    clock.advance(hours=30)
    c.complete_task(done.id)
    c.start_focus(running.id)
    c.send("hi")
    system = c.provider.calls[-1][0]
    assert "done, just now: done one" in system and "old one" not in system
    assert "Focus Session running" in system and "running one" in system


def test_no_tasks_adds_nothing(db):
    c, _ = make(db)
    c.send("hi")
    assert "Tasks" not in c.provider.calls[-1][0]


# --- Reminders ---
def test_a_date_only_task_is_due_at_nine(db):
    c, clock = make(db)
    clock.now = datetime(2026, 11, 7, 8, 59)
    c.add_task("write", due=datetime(2026, 11, 7), has_time=False)
    assert c.pending_notice() is None
    clock.now = datetime(2026, 11, 7, 9, 0)
    assert "write" in c.pending_notice().text


def test_reminder_hour_is_configurable(db):
    c, clock = make(db, reminder_hour=14)
    c.add_task("write", due=datetime(2026, 11, 7), has_time=False)
    assert c.pending_notice() is None
    clock.now = datetime(2026, 11, 7, 14, 0)
    assert c.pending_notice()


def test_reminder_fires_once_per_due_time_and_survives_restart_until_answered(db):
    c, clock = make(db)
    c.add_task("call", due=datetime(2026, 11, 7, 11), has_time=True)
    notice = c.pending_notice()
    assert (notice.kind, notice.expression) == ("reminder", "surprised")
    c.store.close()
    c, _ = make(db, clock=clock)
    notice = c.pending_notice()  # unanswered, so it is still there
    c.answer_notice(notice, "got_it")
    assert c.pending_notice() is None
    c.store.close()
    c, _ = make(db, clock=clock)
    assert c.pending_notice() is None
    assert [t.status for t in c.overdue_tasks()] == ["open"]  # overdue, never "missed"


def test_editing_the_due_time_arms_a_new_reminder(db):
    c, _ = make(db)
    t = c.add_task("call", due=datetime(2026, 11, 7, 11), has_time=True)
    c.answer_notice(c.pending_notice(), "got_it")
    c.edit_task(t.id, due=datetime(2026, 11, 7, 11, 30))
    assert c.pending_notice()


def test_snooze_comes_back_angry_after_the_snooze_and_is_uncapped(db):
    c, clock = make(db)
    c.add_task("call", due=datetime(2026, 11, 7, 11), has_time=True)
    for _ in range(3):
        c.answer_notice(c.pending_notice(), "snooze")
        assert c.pending_notice() is None
        clock.advance(minutes=9)
        assert c.pending_notice() is None
        clock.advance(minutes=1)
        again = c.pending_notice()
        assert again.expression == "angry"
        assert "call" in again.text


def test_several_overdue_tasks_merge_into_one_grouped_reminder(db):
    c, _ = make(db)
    for title in ("a", "b", "c"):
        c.add_task(title, due=datetime(2026, 11, 7, 10), has_time=True)
    notice = c.pending_notice()
    assert notice.kind == "reminder" and len(notice.task_ids) == 3
    assert "3" in notice.text and "focus" not in dict(notice.actions)
    c.answer_notice(notice, "got_it")
    assert c.pending_notice() is None


def test_reminder_text_never_shows_the_why_and_done_tasks_do_not_fire(db):
    c, _ = make(db)
    t = c.add_task("call", "secret reason", datetime(2026, 11, 7, 10), True)
    assert "secret" not in c.pending_notice().text
    c.complete_task(t.id)
    assert c.pending_notice() is None


def test_reminder_wording_is_stable_between_polls(db):
    c, _ = make(db)
    c.add_task("call", due=datetime(2026, 11, 7, 10), has_time=True)
    assert c.pending_notice() == c.pending_notice()


def test_notice_lines_come_from_the_editable_file(db, tmp_path):
    path = tmp_path / "notices.json"
    path.write_text('{"reminder": ["custom {title}"], "nonsense": 3}')
    c, _ = make(db, notice_lines=load_lines(path))
    c.add_task("call", due=datetime(2026, 11, 7, 10), has_time=True)
    assert c.pending_notice().text == "custom call"
    assert load_lines(tmp_path / "missing.json")["checkin"]


# --- Focus Sessions ---
def test_focus_session_runs_then_checks_in_and_marks_the_task_done(db):
    c, clock = make(db, focus_minutes=25)
    t = c.add_task("study")
    session = c.start_focus(t.id)
    assert session.planned_minutes == 25 and c.pending_notice() is None
    clock.advance(minutes=25)
    notice = c.pending_notice()
    assert (notice.kind, notice.expression) == ("checkin", "neutral")
    assert [a for a, _ in notice.actions] == ["done", "not_yet", "snooze"]
    c.answer_notice(notice, "done")
    saved = c.focus_history(t.id)[0]
    assert (saved.outcome, saved.answered, saved.ended_at) == ("finished", True, clock.now)
    assert c.tasks()[0].status == "done" and c.running_focus() is None


def test_not_done_yet_finishes_the_session_but_not_the_task(db):
    c, clock = make(db)
    t = c.add_task("study")
    c.start_focus(t.id)
    clock.advance(minutes=25)
    c.answer_notice(c.pending_notice(), "not_yet")
    assert c.focus_history()[0].outcome == "finished" and c.tasks()[0].status == "open"


def test_snooze_extends_the_same_focus_session(db):
    c, clock = make(db)
    t = c.add_task("study")
    first = c.start_focus(t.id)
    clock.advance(minutes=25)
    c.answer_notice(c.pending_notice(), "snooze")
    assert c.pending_notice() is None and c.running_focus().id == first.id
    clock.advance(minutes=10)
    assert c.pending_notice().kind == "checkin"
    assert len(c.focus_history()) == 1 and c.running_focus().snoozes == 1


def test_stopping_early_opens_the_checkin_with_skip(db):
    c, clock = make(db)
    t = c.add_task("study")
    c.start_focus(t.id)
    clock.advance(minutes=5)
    c.stop_focus()
    notice = c.pending_notice()
    assert "skip" in dict(notice.actions)
    c.answer_notice(notice, "skip")
    saved = c.focus_history()[0]
    assert (saved.outcome, saved.answered) == ("skipped", True) and c.tasks()[0].status == "open"


def test_only_one_focus_session_at_a_time_and_only_on_open_tasks(db):
    c, _ = make(db)
    a, b = c.add_task("a"), c.add_task("b")
    c.start_focus(a.id)
    with pytest.raises(FocusError):
        c.start_focus(b.id)
    c.complete_task(b.id)
    c.stop_focus()
    c.answer_notice(c.pending_notice(), "not_yet")
    with pytest.raises(FocusError):
        c.start_focus(b.id)
    with pytest.raises(UnknownTask):
        c.start_focus(999)


def test_checkin_that_came_due_during_a_restart_is_asked_late_once(db):
    c, clock = make(db)
    c.start_focus(c.add_task("study").id)
    c.store.close()
    clock.advance(minutes=90)
    c, _ = make(db, clock=clock)
    c.answer_notice(c.pending_notice(), "not_yet")
    assert c.pending_notice() is None


def test_checkin_hours_late_closes_finished_and_unanswered(db):
    c, clock = make(db)
    c.start_focus(c.add_task("study").id)
    clock.advance(hours=8)
    assert c.pending_notice() is None
    saved = c.focus_history()[0]
    assert (saved.outcome, saved.answered) == ("finished", False)


def test_checkins_come_before_reminders(db):
    c, clock = make(db)
    c.start_focus(c.add_task("study").id)
    c.add_task("call", due=datetime(2026, 11, 7, 12, 10), has_time=True)
    clock.advance(minutes=30)
    assert c.pending_notice().kind == "checkin"
    c.answer_notice(c.pending_notice(), "not_yet")
    assert c.pending_notice().kind == "reminder"


def test_reminder_can_start_a_focus_session(db):
    c, _ = make(db)
    t = c.add_task("call", due=datetime(2026, 11, 7, 10), has_time=True)
    notice = c.pending_notice()
    assert "focus" in dict(notice.actions)
    c.answer_notice(notice, "focus")
    assert c.running_focus().task_id == t.id and c.pending_notice() is None


def test_history_survives_deleting_the_task_and_ids_stay(db):
    c, clock = make(db)
    t = c.add_task("study")
    s = c.start_focus(t.id)
    clock.advance(minutes=25)
    c.answer_notice(c.pending_notice(), "not_yet")
    c.delete_task(t.id)
    assert [(h.id, h.task_title) for h in c.focus_history()] == [(s.id, "study")]


def test_editing_the_title_keeps_a_snooze_but_a_new_due_time_clears_it(db):
    c, _ = make(db)
    t = c.add_task("call", due=datetime(2026, 11, 7, 11), has_time=True)
    c.answer_notice(c.pending_notice(), "snooze")
    c.edit_task(t.id, title="call mum", due=datetime(2026, 11, 7, 11), has_time=True)
    assert c.tasks()[0].snooze_until is not None
    c.edit_task(t.id, due=datetime(2026, 11, 7, 11, 30), has_time=True)
    assert c.tasks()[0].snooze_until is None


def test_a_proposal_keeps_the_conversation_that_made_it(db):
    c, _ = make(db, ["ok\n[task: gọi mẹ]"])
    c.send("hi")
    first = c.conversation_id
    proposal = c.last_task_proposal
    c.new_conversation()
    assert c.accept_task(proposal).conversation_id == first
