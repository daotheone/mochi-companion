from companion.provider import ChatMessage, ProviderError


class FakeProvider:
    """Scripted provider for tests; never touches the network.

    A `ProviderError` instance in `replies` is raised for that call instead of returned.
    """

    def __init__(self, replies: list[str | ProviderError] | None = None):
        self.replies = list(replies or [])
        self.fail_with: str | None = None
        self.calls: list[tuple[str, list[ChatMessage]]] = []

    def complete(self, persona: str, messages: list[ChatMessage]) -> str:
        self.calls.append((persona, list(messages)))
        if self.fail_with is not None:
            raise ProviderError(self.fail_with)
        reply = self.replies.pop(0) if self.replies else "ok"
        if isinstance(reply, ProviderError):
            raise reply
        return reply
