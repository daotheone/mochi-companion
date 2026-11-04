import sys

from companion.companion import Companion
from companion.config import Config
from companion.groq_provider import GroqProvider
from companion.provider import ProviderError
from companion.store import Store

SHOWN_ON_LAUNCH = 10
HELP = "Commands: /new  start a new Conversation, /retry  resend unanswered Message, /quit"


def run(companion: Companion, input_fn=input, print_fn=print) -> None:
    history = companion.recent_messages(SHOWN_ON_LAUNCH)
    if history:
        print_fn("--- earlier in this Conversation ---")
        for m in history:
            print_fn(f"{'you' if m.role == 'user' else 'mochi'}: {m.content}")
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
            else:
                reply = companion.send(line)
        except ProviderError as e:
            print_fn(f"[error] {e}\nYour Message is saved. Use /retry to try again.")
            continue
        print_fn(f"mochi: {reply}")


def main() -> None:
    config = Config.load()
    if not config.persona_path.is_file():
        sys.exit(f"Persona file not found: {config.persona_path}")
    store = Store(config.db_path)
    provider = GroqProvider(config.api_key, config.model)
    companion = Companion(
        store, provider, config.persona_path.read_text(), config.history_limit
    )
    try:
        run(companion)
    finally:
        store.close()


if __name__ == "__main__":
    main()
