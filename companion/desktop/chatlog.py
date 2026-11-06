from datetime import datetime
from pathlib import Path

from companion.config import PROJECT_ROOT
from companion.store import StoredMessage

LOG_DIR = PROJECT_ROOT / "chat_logs"  # gitignored; kept for tuning the Persona


def render(messages: list[StoredMessage]) -> str:
    parts = []
    for m in messages:
        who = "User" if m.role == "user" else "Mochi"
        parts.append(f"**{who}:**\n{m.content.strip()}")
    return "# Chat log\n\n" + "\n\n".join(parts) + "\n"


def save(messages: list[StoredMessage], directory: Path = LOG_DIR, now: datetime | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{(now or datetime.now()):%Y-%m-%d_%H-%M-%S}.md"
    path.write_text(render(messages), encoding="utf-8")
    return path
