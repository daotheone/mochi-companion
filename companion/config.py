import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "deepseek-flash"
DEFAULT_HISTORY_LIMIT = 20
DEFAULT_MEMORY_LIMIT = 5
DEFAULT_RECAP_MAX_DAYS = 3
DEFAULT_RECAP_FRESH_HOURS = 24
DEFAULT_FOCUS_MINUTES = 25
DEFAULT_SNOOZE_MINUTES = 10
DEFAULT_REMINDER_HOUR = 9  # a due date with no clock time counts as due at this hour
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path, environ: dict[str, str]) -> None:
    """Minimal .env reader; real environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        environ.setdefault(key.strip(), value.strip().strip("'\""))


def _positive_int(environ: dict[str, str], key: str, default: int) -> int:
    raw = environ.get(key, str(default))
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise SystemExit(f"{key} must be a positive integer, got {raw!r}")
    return value


def _hour(environ: dict[str, str], key: str, default: int) -> int:
    raw = environ.get(key, str(default))
    try:
        value = int(raw)
    except ValueError:
        value = -1
    if not 0 <= value <= 23:
        raise SystemExit(f"{key} must be an hour from 0 to 23, got {raw!r}")
    return value


@dataclass(frozen=True)
class Config:
    api_key: str | None
    model: str
    history_limit: int
    memory_limit: int
    recap_max_days: int
    recap_fresh_hours: int
    focus_minutes: int
    snooze_minutes: int
    reminder_hour: int
    db_path: Path
    persona_path: Path
    notices_path: Path

    @classmethod
    def load(cls, environ: dict[str, str] | None = None) -> "Config":
        if environ is None:
            environ = os.environ  # type: ignore[assignment]
            load_dotenv(PROJECT_ROOT / ".env", environ)
        data_dir = Path(
            environ.get("MOCHI_DATA_DIR", Path.home() / ".local/share/mochi-companion")
        )
        return cls(
            api_key=environ.get("DEEPSEEK_API_KEY") or None,
            model=environ.get("MOCHI_MODEL", DEFAULT_MODEL),
            history_limit=_positive_int(environ, "MOCHI_HISTORY_LIMIT", DEFAULT_HISTORY_LIMIT),
            memory_limit=_positive_int(environ, "MOCHI_MEMORY_LIMIT", DEFAULT_MEMORY_LIMIT),
            recap_max_days=_positive_int(environ, "MOCHI_RECAP_MAX_DAYS", DEFAULT_RECAP_MAX_DAYS),
            recap_fresh_hours=_positive_int(environ, "MOCHI_RECAP_FRESH_HOURS", DEFAULT_RECAP_FRESH_HOURS),
            focus_minutes=_positive_int(environ, "MOCHI_FOCUS_MINUTES", DEFAULT_FOCUS_MINUTES),
            snooze_minutes=_positive_int(environ, "MOCHI_SNOOZE_MINUTES", DEFAULT_SNOOZE_MINUTES),
            reminder_hour=_hour(environ, "MOCHI_REMINDER_HOUR", DEFAULT_REMINDER_HOUR),
            db_path=data_dir / "mochi.db",
            persona_path=Path(environ.get("MOCHI_PERSONA", PROJECT_ROOT / "persona/mochi.md")),
            notices_path=Path(environ.get("MOCHI_NOTICES", PROJECT_ROOT / "persona/notices.json")),
        )
