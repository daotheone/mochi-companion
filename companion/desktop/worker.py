from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from companion.app import bubbles
from companion.companion import Companion, FocusError, Notice, UnknownMemory, UnknownTask
from companion.provider import ProviderError
from companion.store import Memory, Store
from companion.tasks import TaskProposal

NOTICE_POLL_MS = 10_000  # compares stored wall-clock times, so it survives suspend (no long timers)


class Worker(QObject):
    """Owns the Store and Companion on one thread; the UI only talks to it through signals.

    `factory` runs inside `start`, so the SQLite connection is made on the worker's own thread.
    """

    state_changed = Signal(str)  # "thinking" | "idle"
    replied = Signal(list, object, str, object)  # Bubbles, Memory | None (noticed), Expression, TaskProposal | None
    failed = Signal(str)
    memories_changed = Signal(list)
    conversation_changed = Signal(list)
    recaps_changed = Signal(list)
    tasks_changed = Signal(list, list)  # every Task, every Focus Session (newest first)
    notice_changed = Signal(object)  # the Reminder or Check-in to show now, or None

    def __init__(self, factory: Callable[[], tuple[Companion, Store]]):
        super().__init__()
        self._factory = factory
        self.companion: Companion
        self._store: Store
        self._notice_key: str | None = None
        self._poll: QTimer | None = None

    @Slot()
    def start(self) -> None:
        self.companion, self._store = self._factory()
        self.refresh()
        self._poll = QTimer(self, interval=NOTICE_POLL_MS, timeout=self.check_notices)
        self._poll.start()
        self.check_notices()
        self._recap()  # a Conversation that ended without a clean exit; a first Message queues behind this

    @Slot()
    def shutdown(self) -> None:
        if self._poll:
            self._poll.stop()
        self._store.close()

    @Slot()
    def refresh(self) -> None:
        self.memories_changed.emit(self.companion.memories())
        self.conversation_changed.emit(self.companion.recent_messages(500))
        self.recaps_changed.emit(self.companion.recaps())
        self._emit_tasks()

    def _emit_tasks(self) -> None:
        self.tasks_changed.emit(self.companion.tasks(), self.companion.focus_history())

    @Slot()
    def check_notices(self, force: bool = False) -> None:
        """Poll for a due Reminder or Check-in; only a change is reported, unless `force`d."""
        notice = self.companion.pending_notice()
        key = notice.key if notice else None
        if key != self._notice_key or force:
            self._notice_key = key
            self.notice_changed.emit(notice)
            self._emit_tasks()

    def _recap(self) -> None:
        self.companion.write_recaps()  # never raises: a failure is retried later
        self.recaps_changed.emit(self.companion.recaps())

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
        self.recaps_changed.emit(self.companion.recaps())
        self._emit_tasks()
        self.replied.emit(bubbles(reply), noticed, self.companion.last_expression, self.companion.last_task_proposal)

    @Slot()
    def new_conversation(self) -> None:
        self.companion.new_conversation()
        self.conversation_changed.emit([])
        self._recap()

    @Slot(int)
    def delete_recap(self, recap_id: int) -> None:
        self.companion.delete_recap(recap_id)
        self.recaps_changed.emit(self.companion.recaps())

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

    # --- Tasks and Focus Sessions ---
    @Slot(object)
    def accept_task(self, proposal: TaskProposal) -> None:
        self.companion.accept_task(proposal)
        self._after_task_change()

    @Slot(str, str, object, bool)
    def add_task(self, title: str, why: str, due, has_time: bool) -> None:
        try:
            self.companion.add_task(title, why, due, has_time)
        except ValueError:
            pass  # the view does not send a blank title
        self._after_task_change()

    @Slot(int, str, str, object, bool)
    def edit_task(self, task_id: int, title: str, why: str, due, has_time: bool) -> None:
        self._task_change(self.companion.edit_task, task_id, title, why, due, has_time)

    @Slot(int)
    def complete_task(self, task_id: int) -> None:
        self._task_change(self.companion.complete_task, task_id)

    @Slot(int)
    def drop_task(self, task_id: int) -> None:
        self._task_change(self.companion.drop_task, task_id)

    @Slot(int)
    def delete_task(self, task_id: int) -> None:
        self._task_change(self.companion.delete_task, task_id)

    @Slot(int)
    def start_focus(self, task_id: int) -> None:
        self._task_change(self.companion.start_focus, task_id)

    @Slot()
    def stop_focus(self) -> None:
        self._task_change(self.companion.stop_focus)

    @Slot(object, str)
    def answer_notice(self, notice: Notice, action: str) -> None:
        self._task_change(self.companion.answer_notice, notice, action, force_notice=True)

    def _task_change(self, action: Callable, *args, force_notice: bool = False) -> None:
        try:
            action(*args)
        except (UnknownTask, FocusError, ValueError):
            pass  # gone or no longer possible (e.g. changed from the terminal); the refresh shows the truth
        self._after_task_change(force_notice)

    def _after_task_change(self, force_notice: bool = False) -> None:
        self._emit_tasks()
        self.check_notices(force_notice)
