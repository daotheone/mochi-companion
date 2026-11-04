import sys

from companion.companion import Companion
from companion.config import Config
from companion.deepseek_provider import DeepSeekProvider
from companion.persona import persona_warning
from companion.store import Store


def bubbles(text: str) -> list[str]:
    """The Bubbles of a Message: one per non-blank line."""
    return [line for line in text.splitlines() if line.strip()]


def build_companion(interface: str, resume: bool) -> tuple[Companion, Store]:
    """Startup wiring shared by every Interface. Exits with a readable message on a bad setup."""
    config = Config.load()
    if not config.persona_path.is_file():
        sys.exit(f"Persona file not found: {config.persona_path}")
    persona = config.persona_path.read_text()
    if warning := persona_warning(persona):
        print(f"[warning] {warning}", file=sys.stderr)
    store = Store(config.db_path)
    provider = DeepSeekProvider(config.api_key, config.model, log_usage=True)
    companion = Companion(
        store, provider, persona, config.history_limit, config.memory_limit,
        interface=interface, resume=resume,
    )
    return companion, store
