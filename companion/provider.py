from dataclasses import dataclass
from typing import Protocol


class ProviderError(Exception):
    """A readable failure from the hosted model (missing key, network, quota)."""


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "user" or "assistant"
    content: str


class Provider(Protocol):
    def complete(self, persona: str, messages: list[ChatMessage]) -> str: ...
