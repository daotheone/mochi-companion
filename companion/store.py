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

    def add_message(self, conversation_id: int, role: str, content: str, at: datetime | None = None) -> int:
        with self._db:
            return self._db.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, _stamp(at)),
            ).lastrowid

    def recent_messages(self, conversation_id: int, limit: int) -> list[StoredMessage]:
        rows = self._db.execute(
            "SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
        return [StoredMessage(i, role, content, datetime.fromisoformat(at)) for i, role, content, at in reversed(rows)]

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
