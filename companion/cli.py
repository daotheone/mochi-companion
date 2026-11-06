from companion.app import bubbles as split_bubbles, build_companion
from companion.companion import Companion, UnknownMemory, UnknownTask
from companion.provider import ProviderError
from companion.store import Memory, Store, Task
from companion.tasks import format_due, parse_due, stamp_due

SHOWN_ON_LAUNCH = 10
HELP = (
    "Commands: /new  start a new Conversation, /recaps  list Recaps, /retry  resend unanswered Message, /quit\n"
    "Memories: /remember [#tag ...] text, /memories, /edit id text, /tag id [#tag ...], "
    "/forget id, /confirm id\n"
    "Tasks: /task [due=YYYY-MM-DD[THH:MM]] title [| why], /tasks [all], /done id, /drop id"
)
USAGE = {
    "/remember": "Usage: /remember [#tag ...] text",
    "/edit": "Usage: /edit id text",
    "/tag": "Usage: /tag id [#tag ...]",
    "/forget": "Usage: /forget id",
    "/confirm": "Usage: /confirm id",
    "/task": "Usage: /task [due=YYYY-MM-DD[THH:MM]] title [| why]",
    "/done": "Usage: /done id",
    "/drop": "Usage: /drop id",
}


MEMORY_COMMANDS = ("/remember", "/edit", "/tag", "/forget", "/confirm")


def bubbles(speaker: str, text: str) -> list[str]:
    return [f"{speaker}: {line}" for line in split_bubbles(text)]


def format_memory(m: Memory) -> str:
    tags = "".join(f" #{t}" for t in m.tags)
    return f"[{m.id}] {m.kind}{tags}: {m.text}"


def show_recaps(companion: Companion, print_fn) -> None:
    recaps = companion.recaps()
    for r in recaps:
        print_fn(f"[{r.id}] {r.ended_at:%Y-%m-%d %H:%M} ({r.interface}){' [sensitive]' if r.sensitive else ''}: {r.text}")
    if not recaps:
        print_fn("No Recaps yet. One is written when a Conversation ends.")


def format_task(c: Companion, t: Task) -> str:
    status = "" if t.status == "open" else f" ({t.status})"
    due = c.due_at(t)
    overdue = " OVERDUE" if t.status == "open" and due and due <= c._now() else ""
    why = f"  why: {t.why}" if t.why else ""
    return f"[{t.id}] {t.title}{status}  {format_due(t.due, t.due_has_time)}{overdue}{why}"


def task_command(companion: Companion, line: str, print_fn) -> bool:
    """Run a Task command; False if the line is not one. The terminal never fires Reminders (ADR 0003)."""
    command, _, rest = line.partition(" ")
    rest = rest.strip()
    if command == "/tasks":
        found = companion.tasks(None if rest == "all" else "open")
        for t in found:
            print_fn(format_task(companion, t))
        if not found:
            print_fn("No open Tasks. Use /task to add one.")
        return True
    if command == "/task":
        due, has_time = None, False
        if rest.startswith("due="):
            raw, _, rest = rest[4:].partition(" ")
            parsed = parse_due(raw)
            if parsed is None:
                print_fn("Could not read that time. Use due=YYYY-MM-DD or due=YYYY-MM-DDTHH:MM.")
                return True
            due, has_time = parsed
        title, _, why = rest.partition("|")
        if not title.strip():
            print_fn(USAGE[command])
            return True
        print_fn(format_task(companion, companion.add_task(title, why, due, has_time)))
        return True
    if command in ("/done", "/drop"):
        if not rest.isdigit():
            print_fn(USAGE[command])
            return True
        try:
            (companion.complete_task if command == "/done" else companion.drop_task)(int(rest))
        except UnknownTask:
            print_fn(f"No Task with id {rest}.")
            return True
        print_fn(f"Task {rest} marked {'done' if command == '/done' else 'dropped'}.")
        return True
    return False


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
    if command not in MEMORY_COMMANDS:
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
    overdue = companion.overdue_tasks()
    if overdue:
        print_fn("--- overdue Tasks ---")
        for t in overdue:
            print_fn(format_task(companion, t))
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
                companion.write_recaps()
                continue
            elif line == "/recaps":
                show_recaps(companion, print_fn)
                continue
            elif line == "/retry":
                reply = companion.retry()
            elif line.startswith("/") and (task_command(companion, line, print_fn) or memory_command(companion, line, print_fn)):
                continue
            else:
                reply = companion.send(line)
        except ProviderError as e:
            print_fn(f"[error] {e}\nYour Message is saved. Use /retry to try again.")
            continue
        for shown in bubbles("mochi", reply):
            print_fn(shown)
        proposed = companion.last_task_proposal
        if proposed:
            due = f" due={stamp_due(proposed.due, proposed.has_time)}" if proposed.due else ""
            print_fn(f"(mochi suggests a Task: /task{due} {proposed.title}{' | ' + proposed.why if proposed.why else ''})")
        noticed = companion.last_proposal
        if noticed:
            print_fn(
                f"(mochi noticed: {noticed.text}  /confirm {noticed.id} to keep it, "
                f"/forget {noticed.id} to drop it)"
            )


def main() -> None:
    companion, store = build_companion("terminal", resume=True)
    try:
        run(companion)
    finally:
        store.close()


if __name__ == "__main__":
    main()
