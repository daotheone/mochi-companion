import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_HISTORY_LIMIT = 20
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


@dataclass(frozen=True)
class Config:
    api_key: str | None
    model: str
    history_limit: int
    db_path: Path
    persona_path: Path

    @classmethod
    def load(cls, environ: dict[str, str] | None = None) -> "Config":
        if environ is None:
            environ = os.environ  # type: ignore[assignment]
            load_dotenv(PROJECT_ROOT / ".env", environ)
        data_dir = Path(
            environ.get("MOCHI_DATA_DIR", Path.home() / ".local/share/mochi-companion")
        )
        return cls(
            api_key=environ.get("GROQ_API_KEY") or None,
            model=environ.get("MOCHI_MODEL", DEFAULT_MODEL),
            history_limit=_positive_int(environ, "MOCHI_HISTORY_LIMIT", DEFAULT_HISTORY_LIMIT),
            db_path=data_dir / "mochi.db",
            persona_path=Path(environ.get("MOCHI_PERSONA", PROJECT_ROOT / "persona/mochi.md")),
        )
