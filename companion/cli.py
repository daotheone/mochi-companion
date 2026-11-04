import sys

from companion.companion import Companion, UnknownMemory
from companion.config import Config
from companion.deepseek_provider import DeepSeekProvider
from companion.persona import persona_warning
from companion.provider import ProviderError
from companion.store import Memory, Store

SHOWN_ON_LAUNCH = 10
HELP = (
    "Commands: /new  start a new Conversation, /retry  resend unanswered Message, /quit\n"
    "Memories: /remember [#tag ...] text, /memories, /edit id text, /tag id [#tag ...], "
    "/forget id, /confirm id"
)
USAGE = {
    "/remember": "Usage: /remember [#tag ...] text",
    "/edit": "Usage: /edit id text",
    "/tag": "Usage: /tag id [#tag ...]",
    "/forget": "Usage: /forget id",
    "/confirm": "Usage: /confirm id",
}


def bubbles(speaker: str, text: str) -> list[str]:
    return [f"{speaker}: {line}" for line in text.splitlines() if line.strip()]


def format_memory(m: Memory) -> str:
    tags = "".join(f" #{t}" for t in m.tags)
    return f"[{m.id}] {m.kind}{tags}: {m.text}"


def split_tags(words: list[str]) -> tuple[list[str], str]:
    """Leading #tags, then the rest as text."""
    n = 0
    while n < len(words) and words[n].startswith("#") and len(words[n]) > 1:
        n += 1
    return words[:n], " ".join(words[n:])


def memory_command(companion: Companion, line: str, print_fn) -> bool:
    """Run a Memory command; False if the line is not one."""
    command, *words = line.split()
    if command == "/memories":
        found = companion.memories()
        for m in found:
            print_fn(format_memory(m))
        if not found:
            print_fn("No Memories yet. Use /remember to add one.")
        return True
    if command not in USAGE:
        return False
    try:
        if command == "/remember":
            tags, text = split_tags(words)
            if not text:
                print_fn(USAGE[command])
                return True
            print_fn(format_memory(companion.remember(text, tags)))
            return True
        if not words or not words[0].isdigit():
            print_fn(USAGE[command])
            return True
        memory_id, rest = int(words[0]), words[1:]
        if command == "/edit":
            if not rest:
                print_fn(USAGE[command])
                return True
            companion.edit(memory_id, " ".join(rest))
        elif command == "/tag":
            tags, text = split_tags(rest)
            if text:
                print_fn(USAGE[command])
                return True
            companion.set_tags(memory_id, tags)
        elif command == "/forget":
            companion.forget(memory_id)
        else:
            companion.confirm(memory_id)
    except UnknownMemory:
        print_fn(f"No Memory with id {words[0]}.")
        return True
    print_fn(f"{command[1:].capitalize()}: done.")
    return True


def run(companion: Companion, input_fn=input, print_fn=print) -> None:
    history = companion.recent_messages(SHOWN_ON_LAUNCH)
    if history:
        print_fn("--- earlier in this Conversation ---")
        for m in history:
            for shown in bubbles("you" if m.role == "user" else "mochi", m.content):
                print_fn(shown)
        print_fn("------------------------------------")
    print_fn(HELP)
    if companion.has_unanswered_message():
        print_fn("(Your last Message has no reply yet. Use /retry to resend it.)")

    while True:
        try:
            line = input_fn("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print_fn("")
            return
        if not line:
            continue
        try:
            if line in ("/quit", "/exit"):
                return
            elif line == "/new":
                companion.new_conversation()
                print_fn("Started a new Conversation.")
                continue
            elif line == "/retry":
                reply = companion.retry()
            elif line.startswith("/") and memory_command(companion, line, print_fn):
                continue
            else:
                reply = companion.send(line)
        except ProviderError as e:
            print_fn(f"[error] {e}\nYour Message is saved. Use /retry to try again.")
            continue
        for shown in bubbles("mochi", reply):
            print_fn(shown)
        noticed = companion.last_proposal
        if noticed:
            print_fn(
                f"(mochi noticed: {noticed.text}  /confirm {noticed.id} to keep it, "
                f"/forget {noticed.id} to drop it)"
            )


def main() -> None:
    config = Config.load()
    if not config.persona_path.is_file():
        sys.exit(f"Persona file not found: {config.persona_path}")
    persona = config.persona_path.read_text()
    if warning := persona_warning(persona):
        print(f"[warning] {warning}", file=sys.stderr)
    store = Store(config.db_path)
    provider = DeepSeekProvider(config.api_key, config.model, log_usage=True)
    companion = Companion(
        store, provider, persona, config.history_limit,
        config.memory_limit,
    )
    try:
        run(companion)
    finally:
        store.close()


if __name__ == "__main__":
    main()
