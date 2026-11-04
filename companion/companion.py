from companion.provider import ChatMessage, Provider, ProviderError
from companion.store import Store, StoredMessage


class Companion:
    """Core Conversation logic: no UI dependency. A Conversation is reopened from the Store."""

    def __init__(self, store: Store, provider: Provider, persona: str, history_limit: int = 20):
        self.store = store
        self.provider = provider
        self.persona = persona
        self.history_limit = history_limit
        self.conversation_id = store.latest_conversation() or store.new_conversation()

    def recent_messages(self, limit: int | None = None) -> list[StoredMessage]:
        return self.store.recent_messages(self.conversation_id, self.history_limit if limit is None else limit)

    def new_conversation(self) -> None:
        self.conversation_id = self.store.new_conversation()

    def has_unanswered_message(self) -> bool:
        last = self.store.recent_messages(self.conversation_id, 1)
        return bool(last) and last[0].role == "user"

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
        reply = self.provider.complete(self.persona, history)
        self.store.add_message(self.conversation_id, "assistant", reply)
        return reply
