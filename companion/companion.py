import re
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Callable

from companion.config import (
    DEFAULT_FOCUS_MINUTES, DEFAULT_MEMORY_LIMIT, DEFAULT_RECAP_FRESH_HOURS, DEFAULT_RECAP_MAX_DAYS,
    DEFAULT_REMINDER_HOUR, DEFAULT_SNOOZE_MINUTES,
)
from companion.provider import ChatMessage, Provider, ProviderError
from companion.store import FocusSession, Memory, Recap, Store, StoredMessage, Task, _UNSET
from companion.tasks import DEFAULT_LINES, TaskProposal, format_due, pick_line, split_task, stamp_due


EXPRESSIONS = ("neutral", "happy", "sad", "smirk", "blush", "angry", "surprised", "laugh")
NEUTRAL = "neutral"
MEMORY_BUDGET_CHARS = 1600  # about 400 tokens
CORE_TAG = "core"
TASK_BUDGET_CHARS = 1600
TASK_RECENT_HOURS = 24
LATE_CHECKIN_HOURS = 3  # a Check-in this late is closed as finished, unanswered, instead of asked
RECAP_RETRY_AFTER = timedelta(minutes=10)
RECAPS_PER_PASS = 3  # a long absence does not trigger a pile of model calls
RECAP_TRANSCRIPT_MESSAGES = 60
SENSITIVE_MARKER = "[sensitive]"
RECAP_INSTRUCTIONS = f"""You write a Recap: a brief note that Mochi, a companion, keeps about a finished Conversation with the user.
Write 1-3 plain sentences, in the language the user mostly used. Say what happened and whether anything was left unresolved.
If a problem was fixed or a question answered, say so plainly (for example "Fixed: ...") so it is not mistaken for an open problem.
If something is still open, say what. Do not add advice, quotes or opinions, and invent nothing.
If the Conversation touched something vulnerable (a bad night, grief, distress, self-harm), start with the line {SENSITIVE_MARKER} on its own, then the Recap.
Output only the Recap."""


class UnknownMemory(LookupError):
    """No Memory has the given id."""


class UnknownTask(LookupError):
    """No Task has the given id."""


class FocusError(ValueError):
    """A Focus Session cannot be started or changed that way."""


@dataclass(frozen=True)
class Notice:
    """A Reminder or Check-in: an app event in Mochi's voice, not a Message, and never a model call."""

    key: str  # changes whenever the Notice changes, so a UI can tell a new one from a redraw
    kind: str  # "checkin" or "reminder"
    text: str
    expression: str
    actions: tuple[tuple[str, str], ...]  # (action id, button caption)
    session_id: int | None = None
    task_ids: tuple[int, ...] = ()


class Companion:
    """Core Conversation logic: no UI dependency. A Conversation is reopened from the Store."""

    def __init__(
        self,
        store: Store,
        provider: Provider,
        persona: str,
        history_limit: int = 20,
        memory_limit: int = DEFAULT_MEMORY_LIMIT,
        memory_budget: int = MEMORY_BUDGET_CHARS,
        interface: str = "terminal",
        resume: bool = True,
        clock: Callable[[], datetime] | None = None,
        recap_max_days: float = DEFAULT_RECAP_MAX_DAYS,
        recap_fresh_hours: float = DEFAULT_RECAP_FRESH_HOURS,
        focus_minutes: int = DEFAULT_FOCUS_MINUTES,
        snooze_minutes: int = DEFAULT_SNOOZE_MINUTES,
        reminder_hour: int = DEFAULT_REMINDER_HOUR,
        notice_lines: dict[str, list[str]] | None = None,
    ):
        self.store = store
        self.provider = provider
        self.persona = persona
        self.history_limit = history_limit
        self.memory_limit = memory_limit
        self.memory_budget = memory_budget
        self.interface = interface
        self.clock = clock  # when set, the Persona is told the local time and the gap since the last Message
        self.recap_max_days = recap_max_days  # older Recaps stay listed but are not sent to the model
        self.recap_fresh_hours = recap_fresh_hours
        self.focus_minutes = focus_minutes
        self.snooze_minutes = snooze_minutes
        self.reminder_hour = reminder_hour
        self.notice_lines = notice_lines or DEFAULT_LINES
        self._recap_retry_at: datetime | None = None
        # A Conversation is only created by the first Message, so there are no empty ones.
        self.conversation_id: int | None = store.latest_conversation(interface) if resume else None
        self.last_proposal: Memory | None = None
        self.last_task_proposal: TaskProposal | None = None
        self.last_expression = NEUTRAL

    def recent_messages(self, limit: int | None = None) -> list[StoredMessage]:
        if self.conversation_id is None:
            return []
        return self.store.recent_messages(self.conversation_id, self.history_limit if limit is None else limit)

    def new_conversation(self) -> None:
        """Leave the current Conversation; the next Message starts a fresh one.

        Its Recap is written by `write_recaps`, which the caller runs when it can afford a model call.
        """
        self.conversation_id = None

    def _now(self) -> datetime:
        return self.clock() if self.clock else datetime.now()

    def recaps(self) -> list[Recap]:
        return self.store.list_recaps()

    def delete_recap(self, recap_id: int) -> None:
        self.store.delete_recap(recap_id)

    def write_recaps(self) -> int:
        """Recap every ended Conversation that lacks one; returns how many were written.

        A failing provider is never an error here: the Recap is simply tried again later.
        """
        now = self._now()
        ended = self.store.ended_conversations(self.conversation_id, now - timedelta(days=self.recap_max_days))
        written = 0
        for conversation in ended[-RECAPS_PER_PASS:]:
            try:
                text, sensitive = self._summarise(conversation.id)
            except ProviderError:
                self._recap_retry_at = now + RECAP_RETRY_AFTER
                break
            self.store.add_recap(conversation.id, text, sensitive, now)
            written += 1
        return written

    def _summarise(self, conversation_id: int) -> tuple[str, bool]:
        messages = self.store.recent_messages(conversation_id, RECAP_TRANSCRIPT_MESSAGES)
        transcript = "\n".join(f"{'user' if m.role == 'user' else 'Mochi'}: {m.content}" for m in messages)
        text = self.provider.complete(RECAP_INSTRUCTIONS, [ChatMessage("user", transcript)]).strip()
        sensitive = text.casefold().startswith(SENSITIVE_MARKER)
        if sensitive:
            text = text[len(SENSITIVE_MARKER):].strip()
        if not text:
            raise ProviderError("The Recap came back empty.")
        return text, sensitive

    def ensure_conversation(self) -> int:
        if self.conversation_id is None:
            self.conversation_id = self.store.new_conversation(self.interface)
        return self.conversation_id

    def has_unanswered_message(self) -> bool:
        if self.conversation_id is None:
            return False
        last = self.store.recent_messages(self.conversation_id, 1)
        return bool(last) and last[0].role == "user"

    def remember(self, text: str, tags: list[str] | None = None) -> Memory:
        """Save a Stated Memory."""
        return self.store.add_memory(text, _clean_tags(tags or []), "stated")

    def edit(self, memory_id: int, text: str) -> None:
        """Rewrite a Memory's text. Editing an Observed Memory confirms it."""
        self._require(self.store.update_memory(memory_id, text=text, kind="stated"))

    def set_tags(self, memory_id: int, tags: list[str]) -> None:
        self._require(self.store.update_memory(memory_id, tags=_clean_tags(tags)))

    def confirm(self, memory_id: int) -> None:
        self._require(self.store.update_memory(memory_id, kind="stated"))

    def forget(self, memory_id: int) -> None:
        self._require(self.store.delete_memory(memory_id))

    @staticmethod
    def _require(found: bool) -> None:
        if not found:
            raise UnknownMemory("No such Memory.")

    def _memory_block(self, message: str) -> str:
        chosen = select_memories(
            self.memories(), message, self.memory_limit, self.memory_budget
        )
        if not chosen:
            return ""
        lines = [_memory_line(m) for m in chosen]
        return "\n\n## What you remember about the user\n" + "\n".join(lines)

    def _save_observation(self, proposal: tuple[list[str], str] | None) -> Memory | None:
        if proposal is None:
            return None
        tags, text = proposal
        if _normalize(text) in {_normalize(m.text) for m in self.memories()}:
            return None
        return self.store.add_memory(text, _clean_tags(tags), "observed")

    def _now_block(self) -> str:
        if self.clock is None:
            return ""
        now = self.clock()
        lines = [f"Local time: {now:%A %Y-%m-%d %H:%M}"]
        times = self.store.latest_message_times(2)  # the newest is the Message being answered
        if len(times) == 2:
            lines.append(f"Last Message before this one: {format_age(now - times[1])}")
        return "\n\n## Now\n" + "\n".join(lines)

    def _recap_block(self) -> str:
        now = self._now()
        recent = [r for r in self.recaps() if now - r.ended_at <= timedelta(days=self.recap_max_days)]
        if not recent:
            return ""
        lines = []
        for position, recap in enumerate(recent):
            age = now - recap.ended_at
            labels = []
            if position == 0:
                labels.append("the Conversation just before this one")
            if age < timedelta(hours=self.recap_fresh_hours):
                labels.append("fresh")
            if recap.sensitive:
                labels.append("sensitive: never bring up first")
            note = f" ({'; '.join(labels)})" if labels else ""
            lines.append(f"- {format_age(age)}{note}: {recap.text}")
        return "\n\n## Recaps of earlier Conversations\n" + "\n".join(lines)

    def memories(self) -> list[Memory]:
        return self.store.list_memories()

    # --- Tasks ---
    def add_task(
        self, title: str, why: str | None = None, due: datetime | None = None, has_time: bool = True,
        conversation_id: int | None = None,
    ) -> Task:
        title = " ".join(title.split())
        if not title:
            raise ValueError("A Task needs a title.")
        due = self._due(due, has_time)
        return self.store.add_task(title, (why or "").strip() or None, due, conversation_id, self._now())

    def accept_task(self, proposal: TaskProposal) -> Task:
        """Save what Mochi proposed, linked to the Conversation it came from."""
        return self.add_task(proposal.title, proposal.why, proposal.due, proposal.has_time, proposal.conversation_id)

    @staticmethod
    def _due(due: datetime | None, has_time: bool) -> str | None:
        return stamp_due(due, has_time)

    def tasks(self, status: str | None = None) -> list[Task]:
        return self.store.list_tasks(status)

    def edit_task(self, task_id: int, title=_UNSET, why=_UNSET, due=_UNSET, has_time: bool = True) -> None:
        """Change the given fields; `why` and `due` may be None to clear them."""
        fields = {}
        if title is not _UNSET:
            title = " ".join(title.split())
            if not title:
                raise ValueError("A Task needs a title.")
            fields["title"] = title
        if why is not _UNSET:
            fields["why"] = (why or "").strip() or None
        if due is not _UNSET:
            fields["due"] = self._due(due, has_time)
        self._require_task(self.store.update_task(task_id, **fields))

    def complete_task(self, task_id: int) -> None:
        self._require_task(self.store.set_task_status(task_id, "done", self._now()))

    def drop_task(self, task_id: int) -> None:
        self._require_task(self.store.set_task_status(task_id, "dropped", self._now()))

    def delete_task(self, task_id: int) -> None:
        self._require_task(self.store.delete_task(task_id))

    @staticmethod
    def _require_task(found: bool) -> None:
        if not found:
            raise UnknownTask("No such Task.")

    def due_at(self, task: Task) -> datetime | None:
        """When a Task is due for Reminders: a date with no clock time counts as the configured hour."""
        if task.due is None:
            return None
        return task.due if task.due_has_time else task.due.replace(hour=self.reminder_hour, minute=0)

    def overdue_tasks(self) -> list[Task]:
        now = self._now()
        return [t for t in self.tasks("open") if (due := self.due_at(t)) and due <= now]

    def _urgency(self, task: Task):
        due = self.due_at(task)
        return (due is None, due or datetime.max, task.id)

    def _task_block(self) -> str:
        now = self._now()
        lines, used, left_out = [], 0, 0
        for task in sorted(self.tasks("open"), key=self._urgency):
            line = self._task_line(task, now)
            if used + len(line) > TASK_BUDGET_CHARS:
                left_out += 1
                continue
            used += len(line)
            lines.append(line)
        if left_out:
            lines.append(f"- (and {left_out} more open Task{'s' if left_out != 1 else ''} not shown)")
        recent = [
            f"- {t.status}, {format_age(now - t.closed_at)}: {t.title}"
            for t in self.tasks()
            if t.status != "open" and t.closed_at and now - t.closed_at <= timedelta(hours=TASK_RECENT_HOURS)
        ]
        running = self.running_focus()
        parts = []
        if lines:
            parts.append("## Tasks (open, most urgent first)\n" + "\n".join(lines))
        if recent:
            parts.append("## Tasks finished or dropped in the last 24 hours\n" + "\n".join(recent))
        if running:
            state = "waiting for its Check-in" if running.ends_at <= now else f"ends {format_age(running.ends_at - now)}"
            parts.append(
                f"## Focus Session running\n- on \"{running.task_title}\", started {format_age(now - running.started_at)}, "
                f"{running.planned_minutes} minutes planned, {state}"
            )
        return "\n\n" + "\n\n".join(parts) if parts else ""

    def _task_line(self, task: Task, now: datetime) -> str:
        due = self.due_at(task)
        when = format_due(task.due, task.due_has_time)
        status = f"{when}, overdue" if due and due <= now else when
        why = f" (why: {task.why})" if task.why else ""
        return f"- {task.title} [{status}]{why}"

    # --- Focus Sessions ---
    def running_focus(self) -> FocusSession | None:
        self._close_stale_focus()
        return self.store.running_focus_session()

    def focus_history(self, task_id: int | None = None) -> list[FocusSession]:
        return self.store.list_focus_sessions(task_id)

    def start_focus(self, task_id: int) -> FocusSession:
        """Start the one Focus Session on an open Task."""
        task = self.store.get_task(task_id)
        if task is None:
            raise UnknownTask("No such Task.")
        if task.status != "open":
            raise FocusError("A Focus Session needs an open Task.")
        if self.running_focus() is not None:
            raise FocusError("A Focus Session is already running.")
        now = self._now()
        return self.store.add_focus_session(task, self.focus_minutes, now, now + timedelta(minutes=self.focus_minutes))

    def stop_focus(self) -> None:
        """Stop early: the Check-in comes at once, with Skip as an extra choice."""
        session = self.running_focus()
        if session is None or session.ends_at <= self._now():
            return
        self.store.update_focus_session(session.id, ends_at=self._now(), early=True)

    def _close_stale_focus(self) -> None:
        session = self.store.running_focus_session()
        if session and self._now() - session.ends_at >= timedelta(hours=LATE_CHECKIN_HOURS):
            self.store.update_focus_session(session.id, ended_at=session.ends_at, outcome="finished")

    def answer_checkin(self, session_id: int, answer: str) -> None:
        """`done`, `not_yet`, `snooze` or `skip`."""
        session = self.store.get_focus_session(session_id)
        if session is None or session.ended_at is not None:
            return
        now = self._now()
        if answer == "snooze":
            self.store.update_focus_session(
                session.id, ends_at=now + timedelta(minutes=self.snooze_minutes), snoozes=session.snoozes + 1,
                early=False,
            )
            return
        if answer == "done":
            self.store.set_task_status(session.task_id, "done", now)
        outcome = "skipped" if answer == "skip" else "finished"
        self.store.update_focus_session(session.id, ended_at=now, outcome=outcome, answered=True)

    # --- Reminders and Check-ins ---
    def pending_notice(self) -> Notice | None:
        """What Mochi should say now, if anything: Check-ins before Reminders, several Reminders merged into one."""
        now = self._now()
        session = self.running_focus()
        if session and session.ends_at <= now:
            actions = [("done", "Task done"), ("not_yet", "Not done yet"), ("snooze", f"Snooze {self.snooze_minutes} min")]
            if session.early:
                actions.append(("skip", "Skip"))
            text = pick_line(self.notice_lines["checkin"], session.id, title=session.task_title)
            return Notice(
                f"checkin:{session.id}:{session.ends_at.isoformat()}:{int(session.early)}", "checkin", text,
                NEUTRAL, tuple(actions), session_id=session.id,
            )
        due, snoozed = [], False
        for task in self.tasks("open"):
            at = self.due_at(task)
            if task.snooze_until is not None:
                if task.snooze_until <= now:
                    due.append(task)
                    snoozed = True
            elif at is not None and at <= now and task.reminded_for != stamp_due(task.due, task.due_has_time):
                due.append(task)
        if not due:
            return None
        due.sort(key=self._urgency)
        ids = tuple(t.id for t in due)
        actions = [("got_it", "Got it"), ("snooze", f"Snooze {self.snooze_minutes} min")]
        if len(due) == 1:
            if self.store.running_focus_session() is None:
                actions.insert(0, ("focus", "Start focus"))
            pool = self.notice_lines["reminder_snoozed" if snoozed else "reminder"]
            text = pick_line(pool, due[0].id, title=due[0].title)
        else:
            shown = ", ".join(t.title for t in due[:3]) + ("…" if len(due) > 3 else "")
            text = pick_line(self.notice_lines["reminder_group"], sum(ids), count=str(len(due)), titles=shown)
        return Notice(
            f"reminder:{','.join(map(str, ids))}:{int(snoozed)}", "reminder", text,
            "angry" if snoozed else "surprised", tuple(actions), task_ids=ids,
        )

    def answer_notice(self, notice: Notice, action: str) -> None:
        if notice.kind == "checkin":
            if notice.session_id is not None:
                self.answer_checkin(notice.session_id, action)
            return
        if action == "snooze":
            until = self._now() + timedelta(minutes=self.snooze_minutes)
            self.store.answer_reminder(list(notice.task_ids), until)
            return
        self.store.answer_reminder(list(notice.task_ids))
        if action == "focus" and len(notice.task_ids) == 1:
            try:
                self.start_focus(notice.task_ids[0])
            except (FocusError, UnknownTask):
                pass

    def send(self, text: str) -> str:
        """Save the user's Message at once, then ask the provider. Raises ProviderError."""
        self.store.add_message(self.ensure_conversation(), "user", text, self._now())
        if self._recap_retry_at is None or self._now() >= self._recap_retry_at:
            self.write_recaps()  # the reply waits for it; a failure only means a reply without it
        return self._reply()

    def retry(self) -> str:
        """Resend the unanswered Message without saving it again."""
        if not self.has_unanswered_message():
            raise ProviderError("Nothing to retry: the last Message already has a reply.")
        return self._reply()

    def _reply(self) -> str:
        history = [ChatMessage(m.role, _with_marker(m)) for m in self.recent_messages()]
        system = (
            self.persona + self._memory_block(history[-1].content if history else "")
            + self._now_block() + self._recap_block() + self._task_block()
        )
        started = time.monotonic()
        raw = self.provider.complete(system, history)
        print(
            f"[timing] model call {time.monotonic() - started:.1f}s, prompt ~{len(system) + sum(len(m.content) for m in history)} chars",
            file=sys.stderr,
        )
        text, expression = split_expression(strip_script_leak(raw))
        text, task_proposal = split_task(text)
        reply, proposal = split_observation(text)
        if not reply:
            raise ProviderError("Mochi's reply was empty.")
        self.last_proposal = self._save_observation(proposal)
        self.last_task_proposal = replace(task_proposal, conversation_id=self.ensure_conversation()) if task_proposal else None
        self.last_expression = expression
        self.store.add_message(self.ensure_conversation(), "assistant", reply, self._now(), expression)
        return reply


def format_age(age: timedelta) -> str:
    seconds = max(0, int(age.total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 48 * 3600:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    return f"{age.days} days ago"


def _clean_tags(tags: list[str]) -> list[str]:
    cleaned = [t.strip().lstrip("#").lower() for t in tags]
    return list(dict.fromkeys(t for t in cleaned if t))


OBSERVE_MARKER = re.compile(r"\[observe:([^\]]*)\]")
OBSERVE_BODY = re.compile(r"\s*tags=([^|]*)\|\s*(.+?)\s*$")


FEEL_MARKER = re.compile(r"\[feel:([^\]]*)\]", re.IGNORECASE)
SCRIPT_LEAK = re.compile(r"^[ \t]*user[ \t]*:", re.IGNORECASE | re.MULTILINE)


def strip_script_leak(reply: str) -> str:
    """Cut a reply at the first `User:` line: the model has started writing the user's side of the script."""
    match = SCRIPT_LEAK.search(reply)
    return reply[: match.start()].strip() if match else reply


def split_expression(reply: str) -> tuple[str, str]:
    """Strip every `[feel: ...]` marker from a reply; return the first valid Expression, else neutral."""
    named = (body.strip().casefold() for body in FEEL_MARKER.findall(reply))
    return FEEL_MARKER.sub("", reply), next((e for e in named if e in EXPRESSIONS), NEUTRAL)


def _with_marker(message: StoredMessage) -> str:
    """A Message as the model should see it: its own replies keep their marker, or it stops writing one."""
    return f"[feel: {message.expression}]\n{message.content}" if message.expression else message.content


def split_observation(reply: str) -> tuple[str, tuple[list[str], str] | None]:
    """Strip every `[observe: ...]` marker from a reply; return the first well-formed one."""
    proposal = None
    for body in OBSERVE_MARKER.findall(reply):
        match = OBSERVE_BODY.match(body)
        if match and proposal is None:
            proposal = (match.group(1).split(","), match.group(2))
    stripped = OBSERVE_MARKER.sub("", reply)
    lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in stripped.splitlines()]
    return "\n".join(line for line in lines if line), proposal


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _memory_line(memory: Memory) -> str:
    if memory.kind == "observed":
        return f"- (not yet confirmed; ask before relying on it) {memory.text}"
    return f"- {memory.text}"


STOPWORDS = frozenset("the an and but for with that this you not are was has have she him her his they them its our he is it of in on at we my me".split())


def _words(text: str) -> set[str]:
    """Lowercase words worth matching on: single letters and common English words are skipped."""
    return {w for w in re.findall(r"\w+", text.casefold()) if len(w) > 1 and w not in STOPWORDS}


def select_memories(memories: list[Memory], message: str, limit: int, budget: int) -> list[Memory]:
    """All Memories while they fit the budget; otherwise #core plus the best Tag/keyword matches."""
    if sum(len(_memory_line(m)) for m in memories) <= budget:
        return memories
    words = _words(message)

    def score(m: Memory) -> int:
        return 3 * len(words & set(m.tags)) + len(words & _words(m.text))

    core = [m for m in memories if CORE_TAG in m.tags]
    ranked = sorted((m for m in memories if CORE_TAG not in m.tags and score(m) > 0), key=lambda m: (-score(m), -m.id))
    chosen, used = [], 0
    for m in core + ranked[:limit]:
        used += len(_memory_line(m))
        if used <= budget:
            chosen.append(m)
    return sorted(chosen, key=lambda m: m.id)
