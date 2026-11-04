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
"""


@dataclass(frozen=True)
class StoredMessage:
    id: int
    role: str
    content: str


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
