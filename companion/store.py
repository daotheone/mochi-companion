import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
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

    def close(self) -> None:
        self._db.close()

    def latest_conversation(self) -> int | None:
        row = self._db.execute("SELECT MAX(id) FROM conversations").fetchone()
        return row[0]

    def new_conversation(self) -> int:
        with self._db:
            return self._db.execute("INSERT INTO conversations DEFAULT VALUES").lastrowid

    def add_message(self, conversation_id: int, role: str, content: str) -> int:
        with self._db:
            return self._db.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, role, content),
            ).lastrowid

    def recent_messages(self, conversation_id: int, limit: int) -> list[StoredMessage]:
        rows = self._db.execute(
            "SELECT id, role, content FROM messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
        return [StoredMessage(*r) for r in reversed(rows)]

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
