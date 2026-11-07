import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interface TEXT NOT NULL DEFAULT 'terminal',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);
CREATE TABLE IF NOT EXISTS recaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    interface TEXT NOT NULL,
    text TEXT NOT NULL,
    sensitive INTEGER NOT NULL DEFAULT 0,
    ended_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    why TEXT,
    due TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'dropped')),
    conversation_id INTEGER,
    created_at TEXT NOT NULL,
    closed_at TEXT,
    reminded_for TEXT,
    snooze_until TEXT
);
CREATE TABLE IF NOT EXISTS focus_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    task_title TEXT NOT NULL,
    started_at TEXT NOT NULL,
    planned_minutes INTEGER NOT NULL,
    ends_at TEXT NOT NULL,
    ended_at TEXT,
    outcome TEXT CHECK (outcome IN ('finished', 'skipped')),
    answered INTEGER NOT NULL DEFAULT 0,
    early INTEGER NOT NULL DEFAULT 0,
    snoozes INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS messages_by_conversation ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL CHECK (kind IN ('stated', 'observed')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);
"""


@dataclass(frozen=True)
class StoredMessage:
    id: int
    role: str
    content: str
    at: datetime  # local time
    expression: str | None = None  # None on a user's Message and on replies older than Expressions


@dataclass(frozen=True)
class Recap:
    id: int
    conversation_id: int
    interface: str
    text: str
    sensitive: bool
    ended_at: datetime  # when the Conversation's last Message was sent
    created_at: datetime


@dataclass(frozen=True)
class EndedConversation:
    id: int
    interface: str
    ended_at: datetime


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    why: str | None
    due: datetime | None  # a date with no clock time sits at midnight; see `due_has_time`
    due_has_time: bool
    status: str  # "open", "done" or "dropped"
    conversation_id: int | None  # the Conversation that created it; None for a manual Task
    created_at: datetime
    closed_at: datetime | None
    reminded_for: str | None  # the stored due value a Reminder was last answered for
    snooze_until: datetime | None


@dataclass(frozen=True)
class FocusSession:
    id: int
    task_id: int
    task_title: str  # kept so history survives deleting the Task
    started_at: datetime
    planned_minutes: int
    ends_at: datetime  # when the Check-in is due; a Snooze or an early stop moves it
    ended_at: datetime | None  # None while running or waiting for its Check-in
    outcome: str | None  # "finished" or "skipped"
    answered: bool  # whether the Check-in was answered
    early: bool  # stopped before the planned end, so the Check-in offers Skip
    snoozes: int


_UNSET = object()


def _stamp(at: datetime | None) -> str:
    """Times are stored as naive local ISO strings, so they sort and compare with the clock."""
    return (at or datetime.now()).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class Memory:
    id: int
    text: str
    tags: tuple[str, ...]
    kind: str  # "stated" or "observed"


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(conversations)")}
        if "interface" not in columns:
            with self._db:
                self._db.execute("ALTER TABLE conversations ADD COLUMN interface TEXT NOT NULL DEFAULT 'terminal'")
        if "recapped" not in columns:
            with self._db:
                self._db.execute("ALTER TABLE conversations ADD COLUMN recapped INTEGER NOT NULL DEFAULT 0")
        if "expression" not in {row[1] for row in self._db.execute("PRAGMA table_info(messages)")}:
            with self._db:
                self._db.execute("ALTER TABLE messages ADD COLUMN expression TEXT")

    def close(self) -> None:
        self._db.close()

    def latest_conversation(self, interface: str) -> int | None:
        row = self._db.execute("SELECT MAX(id) FROM conversations WHERE interface = ?", (interface,)).fetchone()
        return row[0]

    def new_conversation(self, interface: str, at: datetime | None = None) -> int:
        with self._db:
            return self._db.execute(
                "INSERT INTO conversations (interface, created_at) VALUES (?, ?)", (interface, _stamp(at))
            ).lastrowid

    def add_message(
        self, conversation_id: int, role: str, content: str, at: datetime | None = None, expression: str | None = None
    ) -> int:
        with self._db:
            return self._db.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at, expression) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, role, content, _stamp(at), expression),
            ).lastrowid

    def recent_messages(self, conversation_id: int, limit: int) -> list[StoredMessage]:
        rows = self._db.execute(
            "SELECT id, role, content, created_at, expression FROM messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
        return [
            StoredMessage(i, role, content, datetime.fromisoformat(at), expression)
            for i, role, content, at, expression in reversed(rows)
        ]

    def latest_message_times(self, count: int) -> list[datetime]:
        """The send times of the newest Messages across every Conversation, newest first."""
        rows = self._db.execute("SELECT created_at FROM messages ORDER BY id DESC LIMIT ?", (count,)).fetchall()
        return [datetime.fromisoformat(r[0]) for r in rows]

    def ended_conversations(self, exclude: int | None, since: datetime) -> list[EndedConversation]:
        """Conversations with a reply, no Recap yet (nor a deleted one), last Message at or after `since`."""
        rows = self._db.execute(
            "SELECT c.id, c.interface, MAX(m.created_at) FROM conversations c "
            "JOIN messages m ON m.conversation_id = c.id "
            "WHERE c.recapped = 0 AND c.id IS NOT ? "
            "AND EXISTS (SELECT 1 FROM messages a WHERE a.conversation_id = c.id AND a.role = 'assistant') "
            "GROUP BY c.id HAVING MAX(m.created_at) >= ? ORDER BY c.id",
            (exclude, _stamp(since)),
        ).fetchall()
        return [EndedConversation(i, interface, datetime.fromisoformat(end)) for i, interface, end in rows]

    def add_recap(self, conversation_id: int, text: str, sensitive: bool, created_at: datetime | None = None) -> Recap:
        """Save a Recap of a Conversation and mark it recapped, so a deleted Recap is not rewritten."""
        interface, ended_at = self._db.execute(
            "SELECT c.interface, MAX(m.created_at) FROM conversations c JOIN messages m ON m.conversation_id = c.id "
            "WHERE c.id = ?", (conversation_id,)
        ).fetchone()
        with self._db:
            recap_id = self._db.execute(
                "INSERT INTO recaps (conversation_id, interface, text, sensitive, ended_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, interface, text, int(sensitive), ended_at, _stamp(created_at)),
            ).lastrowid
            self._db.execute("UPDATE conversations SET recapped = 1 WHERE id = ?", (conversation_id,))
        return self._recap(recap_id)

    def _recap(self, recap_id: int) -> Recap:
        return next(r for r in self.list_recaps() if r.id == recap_id)

    def list_recaps(self) -> list[Recap]:
        """Newest Conversation first."""
        rows = self._db.execute(
            "SELECT id, conversation_id, interface, text, sensitive, ended_at, created_at FROM recaps "
            "ORDER BY ended_at DESC, id DESC"
        ).fetchall()
        return [
            Recap(i, cid, interface, text, bool(sensitive), datetime.fromisoformat(end), datetime.fromisoformat(made))
            for i, cid, interface, text, sensitive, end, made in rows
        ]

    def delete_recap(self, recap_id: int) -> bool:
        with self._db:
            return self._db.execute("DELETE FROM recaps WHERE id = ?", (recap_id,)).rowcount > 0

    def add_memory(self, text: str, tags: list[str], kind: str) -> Memory:
        with self._db:
            memory_id = self._db.execute(
                "INSERT INTO memories (text, tags, kind) VALUES (?, ?, ?)",
                (text, ",".join(tags), kind),
            ).lastrowid
        return Memory(memory_id, text, tuple(tags), kind)

    def list_memories(self) -> list[Memory]:
        rows = self._db.execute("SELECT id, text, tags, kind FROM memories ORDER BY id").fetchall()
        return [Memory(i, text, tuple(t for t in tags.split(",") if t), kind) for i, text, tags, kind in rows]

    def update_memory(
        self, memory_id: int, *, text: str | None = None, tags: list[str] | None = None, kind: str | None = None
    ) -> bool:
        """Change the given fields; False if there is no such Memory."""
        fields = {"text": text, "tags": None if tags is None else ",".join(tags), "kind": kind}
        changes = {k: v for k, v in fields.items() if v is not None}
        if not changes:
            return any(m.id == memory_id for m in self.list_memories())
        assignments = ", ".join(f"{k} = ?" for k in changes)
        with self._db:
            cursor = self._db.execute(
                f"UPDATE memories SET {assignments} WHERE id = ?", (*changes.values(), memory_id)
            )
        return cursor.rowcount > 0

    def delete_memory(self, memory_id: int) -> bool:
        with self._db:
            return self._db.execute("DELETE FROM memories WHERE id = ?", (memory_id,)).rowcount > 0

    # --- Tasks ---
    _TASK_COLUMNS = "id, title, why, due, status, conversation_id, created_at, closed_at, reminded_for, snooze_until"

    @staticmethod
    def _task(row) -> Task:
        i, title, why, due, status, cid, created, closed, reminded, snooze = row
        return Task(
            i, title, why, datetime.fromisoformat(due) if due else None, bool(due and len(due) > 10), status, cid,
            datetime.fromisoformat(created), datetime.fromisoformat(closed) if closed else None, reminded,
            datetime.fromisoformat(snooze) if snooze else None,
        )

    def add_task(
        self, title: str, why: str | None = None, due: str | None = None,
        conversation_id: int | None = None, at: datetime | None = None,
    ) -> Task:
        """`due` is the stored text: `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM`."""
        with self._db:
            task_id = self._db.execute(
                "INSERT INTO tasks (title, why, due, conversation_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (title, why, due, conversation_id, _stamp(at)),
            ).lastrowid
        return self.get_task(task_id)

    def get_task(self, task_id: int) -> Task | None:
        row = self._db.execute(f"SELECT {self._TASK_COLUMNS} FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._task(row) if row else None

    def list_tasks(self, status: str | None = None) -> list[Task]:
        rows = self._db.execute(
            f"SELECT {self._TASK_COLUMNS} FROM tasks WHERE ? IS NULL OR status = ? ORDER BY id", (status, status)
        ).fetchall()
        return [self._task(r) for r in rows]

    def update_task(self, task_id: int, *, title=_UNSET, why=_UNSET, due=_UNSET) -> bool:
        """Change the given fields (`why` and `due` may be set to None); False if there is no such Task."""
        changes = {k: v for k, v in {"title": title, "why": why, "due": due}.items() if v is not _UNSET}
        current = self.get_task(task_id)
        if "due" in changes and current and changes["due"] != (
            (current.due.isoformat(timespec="minutes") if current.due_has_time else current.due.date().isoformat())
            if current.due else None
        ):
            changes["snooze_until"] = None  # a new due time starts afresh; the same one keeps its Snooze
        elif "due" in changes:
            del changes["due"]
        if not changes:
            return self.get_task(task_id) is not None
        assignments = ", ".join(f"{k} = ?" for k in changes)
        with self._db:
            return self._db.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ?", (*changes.values(), task_id)
            ).rowcount > 0

    def set_task_status(self, task_id: int, status: str, at: datetime | None = None) -> bool:
        closed = None if status == "open" else _stamp(at)
        with self._db:
            return self._db.execute(
                "UPDATE tasks SET status = ?, closed_at = ? WHERE id = ?", (status, closed, task_id)
            ).rowcount > 0

    def delete_task(self, task_id: int) -> bool:
        with self._db:
            return self._db.execute("DELETE FROM tasks WHERE id = ?", (task_id,)).rowcount > 0

    def answer_reminder(self, task_ids: list[int], snooze_until: datetime | None = None) -> None:
        """Record that a Reminder was answered: its due value will not fire again, unless snoozed."""
        with self._db:
            for task_id in task_ids:
                self._db.execute(
                    "UPDATE tasks SET reminded_for = due, snooze_until = ? WHERE id = ?",
                    (_stamp(snooze_until) if snooze_until else None, task_id),
                )

    # --- Focus Sessions ---
    _FOCUS_COLUMNS = (
        "id, task_id, task_title, started_at, planned_minutes, ends_at, ended_at, outcome, answered, early, snoozes"
    )

    @staticmethod
    def _focus(row) -> FocusSession:
        i, task_id, title, started, planned, ends, ended, outcome, answered, early, snoozes = row
        return FocusSession(
            i, task_id, title, datetime.fromisoformat(started), planned, datetime.fromisoformat(ends),
            datetime.fromisoformat(ended) if ended else None, outcome, bool(answered), bool(early), snoozes,
        )

    def add_focus_session(self, task: Task, planned_minutes: int, started: datetime, ends_at: datetime) -> FocusSession:
        with self._db:
            session_id = self._db.execute(
                "INSERT INTO focus_sessions (task_id, task_title, started_at, planned_minutes, ends_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (task.id, task.title, _stamp(started), planned_minutes, _stamp(ends_at)),
            ).lastrowid
        return self.get_focus_session(session_id)

    def get_focus_session(self, session_id: int) -> FocusSession | None:
        row = self._db.execute(
            f"SELECT {self._FOCUS_COLUMNS} FROM focus_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return self._focus(row) if row else None

    def running_focus_session(self) -> FocusSession | None:
        """The Focus Session that has not ended yet, whether it is still counting or waiting for its Check-in."""
        row = self._db.execute(
            f"SELECT {self._FOCUS_COLUMNS} FROM focus_sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return self._focus(row) if row else None

    def list_focus_sessions(self, task_id: int | None = None) -> list[FocusSession]:
        """Newest first."""
        rows = self._db.execute(
            f"SELECT {self._FOCUS_COLUMNS} FROM focus_sessions WHERE ? IS NULL OR task_id = ? ORDER BY id DESC",
            (task_id, task_id),
        ).fetchall()
        return [self._focus(r) for r in rows]

    def update_focus_session(self, session_id: int, **fields) -> None:
        """Columns by name; datetimes are stamped, booleans stored as integers."""
        values = []
        for key, value in fields.items():
            values.append(_stamp(value) if isinstance(value, datetime) else int(value) if isinstance(value, bool) else value)
        assignments = ", ".join(f"{k} = ?" for k in fields)
        with self._db:
            self._db.execute(f"UPDATE focus_sessions SET {assignments} WHERE id = ?", (*values, session_id))
