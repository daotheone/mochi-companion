import re
import sys
import time
from datetime import datetime, timedelta
from typing import Callable

from companion.config import DEFAULT_MEMORY_LIMIT, DEFAULT_RECAP_FRESH_HOURS, DEFAULT_RECAP_MAX_DAYS
from companion.provider import ChatMessage, Provider, ProviderError
from companion.store import Memory, Recap, Store, StoredMessage


EXPRESSIONS = ("neutral", "happy", "sad", "smirk", "blush", "angry", "surprised", "laugh")
NEUTRAL = "neutral"
MEMORY_BUDGET_CHARS = 1600  # about 400 tokens
CORE_TAG = "core"
RECAP_RETRY_AFTER = timedelta(minutes=10)
RECAPS_PER_PASS = 3  # a long absence does not trigger a pile of model calls
RECAP_TRANSCRIPT_MESSAGES = 60
SENSITIVE_MARKER = "[sensitive]"
RECAP_INSTRUCTIONS = f"""You write a Recap: a brief note that Mochi, a companion, keeps about a finished Conversation with the user.
Write 1-3 plain sentences, in the language the user mostly used. Say what happened and whether anything was left unresolved.
If a problem was fixed or a question answered, say so plainly (for example "Fixed: ...") so it is not mistaken for an open problem.
If something is still open, say what. Do not add advice, quotes or opinions, and invent nothing.
If the Conversation touched something vulnerable (a bad night, grief, distress, self-harm), start with the line {SENSITIVE_MARKER} on its own, then the Recap.
Output only the Recap."""


class UnknownMemory(LookupError):
    """No Memory has the given id."""


class Companion:
    """Core Conversation logic: no UI dependency. A Conversation is reopened from the Store."""

    def __init__(
        self,
        store: Store,
        provider: Provider,
        persona: str,
        history_limit: int = 20,
        memory_limit: int = DEFAULT_MEMORY_LIMIT,
        memory_budget: int = MEMORY_BUDGET_CHARS,
        interface: str = "terminal",
        resume: bool = True,
        clock: Callable[[], datetime] | None = None,
        recap_max_days: float = DEFAULT_RECAP_MAX_DAYS,
        recap_fresh_hours: float = DEFAULT_RECAP_FRESH_HOURS,
    ):
        self.store = store
        self.provider = provider
        self.persona = persona
        self.history_limit = history_limit
        self.memory_limit = memory_limit
        self.memory_budget = memory_budget
        self.interface = interface
        self.clock = clock  # when set, the Persona is told the local time and the gap since the last Message
        self.recap_max_days = recap_max_days  # older Recaps stay listed but are not sent to the model
        self.recap_fresh_hours = recap_fresh_hours
        self._recap_retry_at: datetime | None = None
        # A Conversation is only created by the first Message, so there are no empty ones.
        self.conversation_id: int | None = store.latest_conversation(interface) if resume else None
        self.last_proposal: Memory | None = None
        self.last_expression = NEUTRAL

    def recent_messages(self, limit: int | None = None) -> list[StoredMessage]:
        if self.conversation_id is None:
            return []
        return self.store.recent_messages(self.conversation_id, self.history_limit if limit is None else limit)

    def new_conversation(self) -> None:
        """Leave the current Conversation; the next Message starts a fresh one.

        Its Recap is written by `write_recaps`, which the caller runs when it can afford a model call.
        """
        self.conversation_id = None

    def _now(self) -> datetime:
        return self.clock() if self.clock else datetime.now()

    def recaps(self) -> list[Recap]:
        return self.store.list_recaps()

    def delete_recap(self, recap_id: int) -> None:
        self.store.delete_recap(recap_id)

    def write_recaps(self) -> int:
        """Recap every ended Conversation that lacks one; returns how many were written.

        A failing provider is never an error here: the Recap is simply tried again later.
        """
        now = self._now()
        ended = self.store.ended_conversations(self.conversation_id, now - timedelta(days=self.recap_max_days))
        written = 0
        for conversation in ended[-RECAPS_PER_PASS:]:
            try:
                text, sensitive = self._summarise(conversation.id)
            except ProviderError:
                self._recap_retry_at = now + RECAP_RETRY_AFTER
                break
            self.store.add_recap(conversation.id, text, sensitive, now)
            written += 1
        return written

    def _summarise(self, conversation_id: int) -> tuple[str, bool]:
        messages = self.store.recent_messages(conversation_id, RECAP_TRANSCRIPT_MESSAGES)
        transcript = "\n".join(f"{'user' if m.role == 'user' else 'Mochi'}: {m.content}" for m in messages)
        text = self.provider.complete(RECAP_INSTRUCTIONS, [ChatMessage("user", transcript)]).strip()
        sensitive = text.casefold().startswith(SENSITIVE_MARKER)
        if sensitive:
            text = text[len(SENSITIVE_MARKER):].strip()
        if not text:
            raise ProviderError("The Recap came back empty.")
        return text, sensitive

    def ensure_conversation(self) -> int:
        if self.conversation_id is None:
            self.conversation_id = self.store.new_conversation(self.interface)
        return self.conversation_id

    def has_unanswered_message(self) -> bool:
        if self.conversation_id is None:
            return False
        last = self.store.recent_messages(self.conversation_id, 1)
        return bool(last) and last[0].role == "user"

    def remember(self, text: str, tags: list[str] | None = None) -> Memory:
        """Save a Stated Memory."""
        return self.store.add_memory(text, _clean_tags(tags or []), "stated")

    def edit(self, memory_id: int, text: str) -> None:
        """Rewrite a Memory's text. Editing an Observed Memory confirms it."""
        self._require(self.store.update_memory(memory_id, text=text, kind="stated"))

    def set_tags(self, memory_id: int, tags: list[str]) -> None:
        self._require(self.store.update_memory(memory_id, tags=_clean_tags(tags)))

    def confirm(self, memory_id: int) -> None:
        self._require(self.store.update_memory(memory_id, kind="stated"))

    def forget(self, memory_id: int) -> None:
        self._require(self.store.delete_memory(memory_id))

    @staticmethod
    def _require(found: bool) -> None:
        if not found:
            raise UnknownMemory("No such Memory.")

    def _memory_block(self, message: str) -> str:
        chosen = select_memories(
            self.memories(), message, self.memory_limit, self.memory_budget
        )
        if not chosen:
            return ""
        lines = [_memory_line(m) for m in chosen]
        return "\n\n## What you remember about the user\n" + "\n".join(lines)

    def _save_observation(self, proposal: tuple[list[str], str] | None) -> Memory | None:
        if proposal is None:
            return None
        tags, text = proposal
        if _normalize(text) in {_normalize(m.text) for m in self.memories()}:
            return None
        return self.store.add_memory(text, _clean_tags(tags), "observed")

    def _now_block(self) -> str:
        if self.clock is None:
            return ""
        now = self.clock()
        lines = [f"Local time: {now:%A %Y-%m-%d %H:%M}"]
        times = self.store.latest_message_times(2)  # the newest is the Message being answered
        if len(times) == 2:
            lines.append(f"Last Message before this one: {format_age(now - times[1])}")
        return "\n\n## Now\n" + "\n".join(lines)

    def _recap_block(self) -> str:
        now = self._now()
        recent = [r for r in self.recaps() if now - r.ended_at <= timedelta(days=self.recap_max_days)]
        if not recent:
            return ""
        lines = []
        for position, recap in enumerate(recent):
            age = now - recap.ended_at
            labels = []
            if position == 0:
                labels.append("the Conversation just before this one")
            if age < timedelta(hours=self.recap_fresh_hours):
                labels.append("fresh")
            if recap.sensitive:
                labels.append("sensitive: never bring up first")
            note = f" ({'; '.join(labels)})" if labels else ""
            lines.append(f"- {format_age(age)}{note}: {recap.text}")
        return "\n\n## Recaps of earlier Conversations\n" + "\n".join(lines)

    def memories(self) -> list[Memory]:
        return self.store.list_memories()

    def send(self, text: str) -> str:
        """Save the user's Message at once, then ask the provider. Raises ProviderError."""
        self.store.add_message(self.ensure_conversation(), "user", text, self._now())
        if self._recap_retry_at is None or self._now() >= self._recap_retry_at:
            self.write_recaps()  # the reply waits for it; a failure only means a reply without it
        return self._reply()

    def retry(self) -> str:
        """Resend the unanswered Message without saving it again."""
        if not self.has_unanswered_message():
            raise ProviderError("Nothing to retry: the last Message already has a reply.")
        return self._reply()

    def _reply(self) -> str:
        history = [ChatMessage(m.role, _with_marker(m)) for m in self.recent_messages()]
        system = (
            self.persona + self._memory_block(history[-1].content if history else "")
            + self._now_block() + self._recap_block()
        )
        started = time.monotonic()
        raw = self.provider.complete(system, history)
        print(
            f"[timing] model call {time.monotonic() - started:.1f}s, prompt ~{len(system) + sum(len(m.content) for m in history)} chars",
            file=sys.stderr,
        )
        text, expression = split_expression(strip_script_leak(raw))
        reply, proposal = split_observation(text)
        if not reply:
            raise ProviderError("Mochi's reply was empty.")
        self.last_proposal = self._save_observation(proposal)
        self.last_expression = expression
        self.store.add_message(self.ensure_conversation(), "assistant", reply, self._now(), expression)
        return reply


def format_age(age: timedelta) -> str:
    seconds = max(0, int(age.total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 48 * 3600:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    return f"{age.days} days ago"


def _clean_tags(tags: list[str]) -> list[str]:
    cleaned = [t.strip().lstrip("#").lower() for t in tags]
    return list(dict.fromkeys(t for t in cleaned if t))


OBSERVE_MARKER = re.compile(r"\[observe:([^\]]*)\]")
OBSERVE_BODY = re.compile(r"\s*tags=([^|]*)\|\s*(.+?)\s*$")


FEEL_MARKER = re.compile(r"\[feel:([^\]]*)\]", re.IGNORECASE)
SCRIPT_LEAK = re.compile(r"^[ \t]*user[ \t]*:", re.IGNORECASE | re.MULTILINE)


def strip_script_leak(reply: str) -> str:
    """Cut a reply at the first `User:` line: the model has started writing the user's side of the script."""
    match = SCRIPT_LEAK.search(reply)
    return reply[: match.start()].strip() if match else reply


def split_expression(reply: str) -> tuple[str, str]:
    """Strip every `[feel: ...]` marker from a reply; return the first valid Expression, else neutral."""
    named = (body.strip().casefold() for body in FEEL_MARKER.findall(reply))
    return FEEL_MARKER.sub("", reply), next((e for e in named if e in EXPRESSIONS), NEUTRAL)


def _with_marker(message: StoredMessage) -> str:
    """A Message as the model should see it: its own replies keep their marker, or it stops writing one."""
    return f"[feel: {message.expression}]\n{message.content}" if message.expression else message.content


def split_observation(reply: str) -> tuple[str, tuple[list[str], str] | None]:
    """Strip every `[observe: ...]` marker from a reply; return the first well-formed one."""
    proposal = None
    for body in OBSERVE_MARKER.findall(reply):
        match = OBSERVE_BODY.match(body)
        if match and proposal is None:
            proposal = (match.group(1).split(","), match.group(2))
    stripped = OBSERVE_MARKER.sub("", reply)
    lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in stripped.splitlines()]
    return "\n".join(line for line in lines if line), proposal


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _memory_line(memory: Memory) -> str:
    if memory.kind == "observed":
        return f"- (not yet confirmed; ask before relying on it) {memory.text}"
    return f"- {memory.text}"


STOPWORDS = frozenset("the an and but for with that this you not are was has have she him her his they them its our he is it of in on at we my me".split())


def _words(text: str) -> set[str]:
    """Lowercase words worth matching on: single letters and common English words are skipped."""
    return {w for w in re.findall(r"\w+", text.casefold()) if len(w) > 1 and w not in STOPWORDS}


def select_memories(memories: list[Memory], message: str, limit: int, budget: int) -> list[Memory]:
    """All Memories while they fit the budget; otherwise #core plus the best Tag/keyword matches."""
    if sum(len(_memory_line(m)) for m in memories) <= budget:
        return memories
    words = _words(message)

    def score(m: Memory) -> int:
        return 3 * len(words & set(m.tags)) + len(words & _words(m.text))

    core = [m for m in memories if CORE_TAG in m.tags]
    ranked = sorted((m for m in memories if CORE_TAG not in m.tags and score(m) > 0), key=lambda m: (-score(m), -m.id))
    chosen, used = [], 0
    for m in core + ranked[:limit]:
        used += len(_memory_line(m))
        if used <= budget:
            chosen.append(m)
    return sorted(chosen, key=lambda m: m.id)
