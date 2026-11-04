from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot

from companion.app import bubbles
from companion.companion import Companion, UnknownMemory
from companion.provider import ProviderError
from companion.store import Memory, Store


class Worker(QObject):
    """Owns the Store and Companion on one thread; the UI only talks to it through signals.

    `factory` runs inside `start`, so the SQLite connection is made on the worker's own thread.
    """

    state_changed = Signal(str)  # "thinking" | "idle"
    replied = Signal(list, object)  # Bubbles, Memory | None (what Mochi noticed)
    failed = Signal(str)
    memories_changed = Signal(list)
    conversation_changed = Signal(list)

    def __init__(self, factory: Callable[[], tuple[Companion, Store]]):
        super().__init__()
        self._factory = factory
        self.companion: Companion
        self._store: Store

    @Slot()
    def start(self) -> None:
        self.companion, self._store = self._factory()
        self.refresh()

    @Slot()
    def shutdown(self) -> None:
        self._store.close()

    @Slot()
    def refresh(self) -> None:
        self.memories_changed.emit(self.companion.memories())
        self.conversation_changed.emit(self.companion.recent_messages(500))

    @Slot(str)
    def send(self, text: str) -> None:
        self._ask(lambda: self.companion.send(text))

    @Slot()
    def retry(self) -> None:
        self._ask(self.companion.retry)

    def _ask(self, call: Callable[[], str]) -> None:
        self.state_changed.emit("thinking")
        try:
            reply = call()
        except ProviderError as e:
            self.state_changed.emit("idle")
            self.conversation_changed.emit(self.companion.recent_messages(500))
            self.failed.emit(str(e))
            return
        noticed: Memory | None = self.companion.last_proposal
        self.conversation_changed.emit(self.companion.recent_messages(500))
        self.memories_changed.emit(self.companion.memories())
        self.replied.emit(bubbles(reply), noticed)

    @Slot()
    def new_conversation(self) -> None:
        self.companion.new_conversation()
        self.conversation_changed.emit([])

    @Slot(str, list)
    def add_memory(self, text: str, tags: list) -> None:
        self.companion.remember(text, tags)
        self.memories_changed.emit(self.companion.memories())

    @Slot(int, str)
    def edit_memory(self, memory_id: int, text: str) -> None:
        self._change(self.companion.edit, memory_id, text)

    @Slot(int, list)
    def set_memory_tags(self, memory_id: int, tags: list) -> None:
        self._change(self.companion.set_tags, memory_id, tags)

    @Slot(int)
    def confirm_memory(self, memory_id: int) -> None:
        self._change(self.companion.confirm, memory_id)

    @Slot(int)
    def forget_memory(self, memory_id: int) -> None:
        self._change(self.companion.forget, memory_id)

    def _change(self, action: Callable, *args) -> None:
        try:
            action(*args)
        except UnknownMemory:
            pass  # gone already (e.g. forgotten from the other window); the refresh shows the truth
        self.memories_changed.emit(self.companion.memories())
