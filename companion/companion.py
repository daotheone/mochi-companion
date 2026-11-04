import re

from companion.config import DEFAULT_MEMORY_LIMIT
from companion.provider import ChatMessage, Provider, ProviderError
from companion.store import Memory, Store, StoredMessage


MEMORY_BUDGET_CHARS = 1600  # about 400 tokens
CORE_TAG = "core"


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
    ):
        self.store = store
        self.provider = provider
        self.persona = persona
        self.history_limit = history_limit
        self.memory_limit = memory_limit
        self.memory_budget = memory_budget
        self.conversation_id = store.latest_conversation() or store.new_conversation()
        self.last_proposal: Memory | None = None

    def recent_messages(self, limit: int | None = None) -> list[StoredMessage]:
        return self.store.recent_messages(self.conversation_id, self.history_limit if limit is None else limit)

    def new_conversation(self) -> None:
        self.conversation_id = self.store.new_conversation()

    def has_unanswered_message(self) -> bool:
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

    def memories(self) -> list[Memory]:
        return self.store.list_memories()

    def send(self, text: str) -> str:
        """Save the user's Message at once, then ask the provider. Raises ProviderError."""
        self.store.add_message(self.conversation_id, "user", text)
        return self._reply()

    def retry(self) -> str:
        """Resend the unanswered Message without saving it again."""
        if not self.has_unanswered_message():
            raise ProviderError("Nothing to retry: the last Message already has a reply.")
        return self._reply()

    def _reply(self) -> str:
        history = [ChatMessage(m.role, m.content) for m in self.recent_messages()]
        system = self.persona + self._memory_block(history[-1].content if history else "")
        reply, proposal = split_observation(self.provider.complete(system, history))
        if not reply:
            raise ProviderError("Mochi's reply was empty.")
        self.last_proposal = self._save_observation(proposal)
        self.store.add_message(self.conversation_id, "assistant", reply)
        return reply


def _clean_tags(tags: list[str]) -> list[str]:
    cleaned = [t.strip().lstrip("#").lower() for t in tags]
    return list(dict.fromkeys(t for t in cleaned if t))


OBSERVE_MARKER = re.compile(r"\[observe:([^\]]*)\]")
OBSERVE_BODY = re.compile(r"\s*tags=([^|]*)\|\s*(.+?)\s*$")


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
