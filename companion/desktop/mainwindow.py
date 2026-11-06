from datetime import date, datetime, time

from PySide6.QtCore import QDate, QEvent, QTime, QTimer, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QDateEdit, QTimeEdit, QFrame, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from companion.desktop import chatlog, theme
from companion.desktop.face import Face
from companion.store import FocusSession, Memory, Recap, StoredMessage, Task
from companion.tasks import TaskProposal, format_due


SIDEBAR_WIDTH = 170
SIDEBAR_COLLAPSED_WIDTH = 60


def _split_tags(raw: str) -> list[str]:
    return [t for t in raw.replace(",", " ").split() if t.strip("#")]


def _button(text: str, name: str = "", tip: str = "") -> QPushButton:
    b = QPushButton(text, objectName=name)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if tip:
        b.setToolTip(tip)
    return b


def _wrapping_list() -> QListWidget:
    """A list whose long items wrap to its width, and wrap again when the window is resized."""
    view = QListWidget(wordWrap=True)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    view.setResizeMode(QListView.ResizeMode.Adjust)
    return view


def _header(title: str, hint: str = "") -> QHBoxLayout:
    row = QHBoxLayout()
    column = QVBoxLayout()
    column.setSpacing(0)
    column.addWidget(QLabel(title, objectName="title"))
    if hint:
        column.addWidget(QLabel(hint, objectName="hint"))
    row.addLayout(column)
    row.addStretch()
    return row


def strip_text(tasks: list[Task], sessions: list[FocusSession], now: datetime) -> str:
    """The Chat view's slim strip: the running Focus Session and how many open Tasks are due today."""
    parts = []
    running = next((s for s in sessions if s.ended_at is None), None)
    if running:
        left = (running.ends_at - now).total_seconds()
        parts.append(
            f"Focus: {running.task_title} · {int(left // 60):d}:{int(left % 60):02d} left" if left > 0
            else f"Focus: {running.task_title} · time is up"
        )
    today = sum(1 for t in tasks if t.status == "open" and t.due is not None and t.due.date() <= now.date())
    if today:
        parts.append(f"{today} Task{'s' if today != 1 else ''} due today or overdue")
    return "   ·   ".join(parts)


class Portrait(QWidget):
    """Mochi's face in the Main Window, at the art's native size and direction."""

    SIZE = 128

    def __init__(self, face: Face):
        super().__init__()
        self.setFixedSize(self.SIZE, self.SIZE)
        self._face = face
        face.changed.connect(self.update)

    def paintEvent(self, _event) -> None:
        QPainter(self).drawPixmap(0, 0, self._face.pixmap(self.size(), False))


class ConversationView(QWidget):
    send_requested = Signal(str)
    new_requested = Signal()
    save_log_requested = Signal()
    retry_requested = Signal()
    confirm_requested = Signal(int)
    forget_requested = Signal(int)
    task_add_requested = Signal(object)
    notice_answered = Signal(object, str)

    def __init__(self, face: Face):
        super().__init__(objectName="page")
        self._messages: list[StoredMessage] = []
        self._busy = False
        self._notices: dict[str, QWidget] = {}  # by slot: a reply can carry several, answered independently
        self._strip = QLabel(objectName="hint", wordWrap=True)
        self._strip.hide()
        self.portrait = Portrait(face)

        self._column = QVBoxLayout()
        self._column.setSpacing(8)
        self._column.setContentsMargins(0, 0, 8, 0)
        holder = QWidget(objectName="page")
        self._holder_layout = QVBoxLayout(holder)
        self._holder_layout.setContentsMargins(0, 0, 0, 0)
        self._holder_layout.addLayout(self._column)
        self._holder_layout.addStretch()
        self._scroll = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
        self._scroll.setWidget(holder)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # The range only grows once the layout has run, so follow it instead of scrolling at a guessed moment.
        self._at_bottom = True
        bar = self._scroll.verticalScrollBar()
        bar.rangeChanged.connect(self._follow)
        bar.valueChanged.connect(lambda value: setattr(self, "_at_bottom", value == bar.maximum()))
        self._empty = QLabel("Chưa có tin nhắn nào.\nSay hi to Mochi", objectName="hint")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._input = QLineEdit(placeholderText="Nói với Mochi…")
        self._send = _button("Send", "primary")
        mic = _button("Voice", "icon", "Voice: coming soon")
        mic.setEnabled(False)
        self._input.returnPressed.connect(self._submit)
        self._send.clicked.connect(self._submit)

        header = _header("Chat", "Your current Conversation")
        history = _button("History", tip="Continue a past Conversation: coming soon")
        history.setEnabled(False)
        save = _button("Save log", tip="Save this Conversation as Markdown in chat_logs/")
        new = _button("New", tip="Start a new Conversation")
        save.clicked.connect(self.save_log_requested.emit)
        new.clicked.connect(self.new_requested.emit)
        for b in (history, save, new):
            header.addWidget(b)

        row = QHBoxLayout()
        row.addWidget(mic)
        row.addWidget(self._input, 1)
        row.addWidget(self._send)
        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        bottom.addWidget(self.portrait)
        beside = QVBoxLayout()
        beside.addStretch()
        beside.addLayout(row)
        bottom.addLayout(beside, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addWidget(self._strip)
        layout.addWidget(self._empty, 1)
        layout.addWidget(self._scroll, 1)
        layout.addLayout(bottom)
        self._empty.show()
        self._scroll.hide()

    def messages(self) -> list[StoredMessage]:
        return self._messages

    def _bubble(self, m: StoredMessage) -> QWidget:
        mine = m.role == "user"
        label = QLabel("\n".join(line for line in m.content.splitlines() if line.strip()), wordWrap=True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setMaximumWidth(460)
        label.setStyleSheet(
            f"background: {theme.ACCENT if mine else theme.PANEL}; color: {'white' if mine else theme.INK};"
            f"border: 1.5px solid {theme.ACCENT if mine else theme.BORDER}; border-radius: 16px; padding: 9px 14px;"
        )
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        if mine:
            layout.addStretch()
        layout.addWidget(label)
        if not mine:
            layout.addStretch()
        return row

    def show_messages(self, messages: list[StoredMessage]) -> None:
        self._messages = messages
        while self._column.count():
            item = self._column.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for m in messages:
            self._column.addWidget(self._bubble(m))
        self._empty.setVisible(not messages)
        self._scroll.setVisible(bool(messages))
        self._at_bottom = True

    def set_strip(self, text: str) -> None:
        """One line about the running Focus Session and what is due today; hidden when there is nothing."""
        self._strip.setText(text)
        self._strip.setVisible(bool(text))

    def show_error(self, message: str) -> None:
        self._show_notice("error", message, [("Retry", self.retry_requested.emit)])

    def show_noticed(self, memory: Memory) -> None:
        self._show_notice("noticed", f"mochi noticed: {memory.text}", [
            ("Confirm", lambda: self.confirm_requested.emit(memory.id)),
            ("Forget", lambda: self.forget_requested.emit(memory.id)),
        ])

    def show_proposal(self, proposal: TaskProposal) -> None:
        self._show_notice("proposal", f"task: {proposal.title} ({format_due(proposal.due, proposal.has_time)})", [
            ("Add", lambda: self.task_add_requested.emit(proposal)),
            ("Dismiss", lambda: None),
        ])

    def show_alert(self, notice) -> None:
        """A Reminder or Check-in, in place of the Speech Balloon while the Main Window is open."""
        self._show_notice("alert", notice.text, [
            (caption, lambda action=action: self.notice_answered.emit(notice, action))
            for action, caption in notice.actions
        ])

    def _show_notice(self, slot: str, text: str, actions: list) -> None:
        """A note at the bottom of the history, with buttons; using one dismisses only it."""
        self.clear_notice(slot)
        notice = QWidget()
        column = QVBoxLayout(notice)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(QLabel(text, objectName="hint", wordWrap=True))
        row = QHBoxLayout()
        for caption, action in actions:
            button = _button(caption)
            button.clicked.connect(lambda _=False, action=action: (self.clear_notice(slot), action()))
            row.addWidget(button)
        row.addStretch()
        column.addLayout(row)
        self._notices[slot] = notice
        self._holder_layout.insertWidget(len(self._notices), notice)
        self._at_bottom = True

    def clear_notice(self, slot: str | None = None) -> None:
        for key in [slot] if slot else list(self._notices):
            if (notice := self._notices.pop(key, None)) is not None:
                notice.setParent(None)
                notice.deleteLater()

    def _follow(self, _minimum: int, maximum: int) -> None:
        if self._at_bottom:
            self._scroll.verticalScrollBar().setValue(maximum)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._send.setEnabled(not busy)
        self._input.setReadOnly(busy)
        self._input.setPlaceholderText("Mochi đang nghĩ…" if busy else "Nói với Mochi…")

    def _submit(self) -> None:
        text = self._input.text().strip()
        if text and not self._busy:
            self._input.clear()
            self.send_requested.emit(text)


class MemoriesView(QWidget):
    add_requested = Signal(str, list)
    edit_requested = Signal(int, str)
    tags_requested = Signal(int, list)
    confirm_requested = Signal(int)
    forget_requested = Signal(int)

    def __init__(self):
        super().__init__(objectName="page")
        self._memories: list[Memory] = []
        self._shown: list[Memory] = []
        self._filter = "all"
        self._list = _wrapping_list()
        self._list.setSpacing(0)
        self._text = QPlainTextEdit(placeholderText="What should Mochi remember?")
        self._tags = QLineEdit(placeholderText="Tags, e.g. study food")
        self._note = QLabel(wordWrap=True, objectName="note")
        self._save = _button("Save", "primary")
        self._confirm = _button("Confirm", tip="Keep this as something you told Mochi")
        self._forget = _button("Forget", "danger")
        new = _button("+ New Memory", "primary")
        self._empty = QLabel("Nothing here yet.", objectName="hint", alignment=Qt.AlignmentFlag.AlignCenter)

        self._chips: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        chips = QHBoxLayout()
        for key, caption in (("all", "All"), ("stated", "Stated"), ("observed", "Observed")):
            chip = _button(caption, "chip")
            chip.setCheckable(True)
            chip.setChecked(key == "all")
            group.addButton(chip)
            chip.clicked.connect(lambda _=False, k=key: self._set_filter(k))
            chips.addWidget(chip)
            self._chips[key] = chip
        chips.addStretch()

        self._list.currentRowChanged.connect(self._select)
        self._save.clicked.connect(self._on_save)
        self._confirm.clicked.connect(lambda: self.confirm_requested.emit(self._selected().id))
        self._forget.clicked.connect(self._on_forget)
        new.clicked.connect(self._new)

        header = _header("Memories", "What Mochi remembers about you")
        header.addWidget(new)

        form = QFrame(objectName="card")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(14, 14, 14, 14)
        form_layout.addWidget(self._text)
        form_layout.addWidget(self._tags)
        form_layout.addWidget(self._note)
        buttons = QHBoxLayout()
        buttons.addWidget(self._save)
        buttons.addWidget(self._confirm)
        buttons.addStretch()
        buttons.addWidget(self._forget)
        form_layout.addLayout(buttons)

        left = QVBoxLayout()
        left.addLayout(chips)
        left.addWidget(self._list, 1)
        left.addWidget(self._empty, 1)
        body = QHBoxLayout()
        body.setSpacing(16)
        body.addLayout(left, 5)
        body.addWidget(form, 4, Qt.AlignmentFlag.AlignTop)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addLayout(body, 1)
        self._select(-1)

    def _set_filter(self, key: str) -> None:
        self._filter = key
        self.show_memories(self._memories)

    def _new(self) -> None:
        self._list.setCurrentRow(-1)
        self._select(-1)
        self._text.setFocus()

    def show_memories(self, memories: list[Memory]) -> None:
        keep = self._selected().id if self._selected() else None
        self._memories = memories
        counts = {"all": len(memories)}
        for kind in ("stated", "observed"):
            counts[kind] = sum(m.kind == kind for m in memories)
        for key, chip in self._chips.items():
            chip.setText(f"{key.capitalize()} · {counts[key]}")
        self._shown = [m for m in memories if self._filter in ("all", m.kind)]
        self._list.blockSignals(True)
        self._list.clear()
        for m in self._shown:
            tags = " ".join(f"#{t}" for t in m.tags)
            badge = "Mochi noticed" if m.kind == "observed" else "Stated"
            item = QListWidgetItem(f"{m.text}\n{badge}" + (f"  ·  {tags}" if tags else ""))
            self._list.addItem(item)
        row = next((i for i, m in enumerate(self._shown) if m.id == keep), -1)
        self._list.setCurrentRow(row)
        self._list.blockSignals(False)
        self._empty.setVisible(not self._shown)
        self._list.setVisible(bool(self._shown))
        self._select(row)

    def _selected(self) -> Memory | None:
        row = self._list.currentRow()
        return self._shown[row] if 0 <= row < len(self._shown) else None

    def _select(self, _row: int) -> None:
        m = self._selected()
        self._text.setPlainText(m.text if m else "")
        self._tags.setText(" ".join(f"#{t}" for t in m.tags) if m else "")
        self._confirm.setVisible(bool(m and m.kind == "observed"))
        self._forget.setVisible(m is not None)
        self._save.setText("Save" if m else "Add Memory")
        self._note.setText(
            "Mochi noticed this. Saving an edit also Confirms it." if m and m.kind == "observed" else ""
        )

    def _on_save(self) -> None:
        text, tags = self._text.toPlainText().strip(), _split_tags(self._tags.text())
        if not text:
            return
        m = self._selected()
        if m is None:
            self.add_requested.emit(text, tags)
            return
        if text != m.text or m.kind == "observed":
            self.edit_requested.emit(m.id, text)  # also Confirms an Observed Memory
        self.tags_requested.emit(m.id, tags)

    def _on_forget(self) -> None:
        m = self._selected()
        if m and QMessageBox.question(self, "Forget", f"Forget this Memory?\n\n{m.text}") == QMessageBox.StandardButton.Yes:
            self.forget_requested.emit(m.id)


class TasksView(QWidget):
    """Every Task, with add, edit, done, drop, Focus Sessions and each Task's Focus Session history."""

    add_requested = Signal(str, str, object, bool)  # title, why, due, has_time
    edit_requested = Signal(int, str, str, object, bool)
    done_requested = Signal(int)
    drop_requested = Signal(int)
    delete_requested = Signal(int)
    focus_requested = Signal(int)
    focus_stop_requested = Signal()

    def __init__(self):
        super().__init__(objectName="page")
        self._tasks: list[Task] = []
        self._sessions: list[FocusSession] = []
        self._shown: list[Task] = []
        self._filter = "open"
        self._list = _wrapping_list()
        self._list.setSpacing(0)
        self._empty = QLabel("Nothing here yet.", objectName="hint", alignment=Qt.AlignmentFlag.AlignCenter)
        self._title = QLineEdit(placeholderText="What do you need to do?")
        self._why = QLineEdit(placeholderText="Why? (optional)")
        self._has_due = QCheckBox("Due")
        self._date = QDateEdit(QDate.currentDate(), calendarPopup=True)
        self._has_time = QCheckBox("at")
        self._clock = QTimeEdit(QTime(9, 0))
        self._note = QLabel(wordWrap=True, objectName="note")
        self._history = QLabel(wordWrap=True, objectName="hint")
        self._save = _button("Add Task", "primary")
        self._done = _button("Done")
        self._drop = _button("Drop", tip="You decided not to do it")
        self._focus = _button("Start focus")
        self._delete = _button("Delete", "danger", "Remove it completely")
        new = _button("+ New Task", "primary")

        self._chips: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        chips = QHBoxLayout()
        for key, caption in (("open", "Open"), ("done", "Done"), ("dropped", "Dropped"), ("all", "All")):
            chip = _button(caption, "chip")
            chip.setCheckable(True)
            chip.setChecked(key == self._filter)
            group.addButton(chip)
            chip.clicked.connect(lambda _=False, k=key: self._set_filter(k))
            chips.addWidget(chip)
            self._chips[key] = chip
        chips.addStretch()

        self._list.currentRowChanged.connect(self._select)
        self._has_due.toggled.connect(self._sync_due_fields)
        self._has_time.toggled.connect(self._sync_due_fields)
        self._save.clicked.connect(self._on_save)
        self._done.clicked.connect(lambda: self.done_requested.emit(self._selected().id))
        self._drop.clicked.connect(lambda: self.drop_requested.emit(self._selected().id))
        self._focus.clicked.connect(self._on_focus)
        self._delete.clicked.connect(self._on_delete)
        new.clicked.connect(self._new)

        header = _header("Tasks", "What you mean to do, and focus sessions on it")
        header.addWidget(new)
        form = QFrame(objectName="card")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(14, 14, 14, 14)
        form_layout.addWidget(self._title)
        form_layout.addWidget(self._why)
        due_row = QHBoxLayout()
        for widget in (self._has_due, self._date, self._has_time, self._clock):
            due_row.addWidget(widget)
        due_row.addStretch()
        form_layout.addLayout(due_row)
        form_layout.addWidget(self._note)
        buttons = QHBoxLayout()
        for button in (self._save, self._done, self._drop, self._focus):
            buttons.addWidget(button)
        buttons.addStretch()
        buttons.addWidget(self._delete)
        form_layout.addLayout(buttons)
        form_layout.addWidget(self._history)

        left = QVBoxLayout()
        left.addLayout(chips)
        left.addWidget(self._list, 1)
        left.addWidget(self._empty, 1)
        body = QHBoxLayout()
        body.setSpacing(16)
        body.addLayout(left, 5)
        body.addWidget(form, 4, Qt.AlignmentFlag.AlignTop)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addLayout(body, 1)
        self._select(-1)

    def _set_filter(self, key: str) -> None:
        self._filter = key
        self.show_tasks(self._tasks, self._sessions)

    def _new(self) -> None:
        self._list.setCurrentRow(-1)
        self._select(-1)
        self._title.setFocus()

    def _running(self) -> FocusSession | None:
        return next((s for s in self._sessions if s.ended_at is None), None)

    def show_tasks(self, tasks: list[Task], sessions: list[FocusSession]) -> None:
        keep = self._selected().id if self._selected() else None
        self._tasks, self._sessions = tasks, sessions
        for key, chip in self._chips.items():
            count = len(tasks) if key == "all" else sum(t.status == key for t in tasks)
            chip.setText(f"{key.capitalize()} · {count}")
        self._shown = [t for t in tasks if self._filter in ("all", t.status)]
        self._list.blockSignals(True)
        self._list.clear()
        now = datetime.now()
        for t in self._shown:
            late = t.status == "open" and t.due is not None and (
                t.due if t.due_has_time else datetime.combine(t.due.date(), time(23, 59))
            ) < now
            line = f"{t.title}\n{format_due(t.due, t.due_has_time)}{'  ·  overdue' if late else ''}"
            line += f"  ·  {t.status}" if t.status != "open" else ""
            self._list.addItem(QListWidgetItem(line + (f"\nwhy: {t.why}" if t.why else "")))
        row = next((i for i, t in enumerate(self._shown) if t.id == keep), -1)
        self._list.setCurrentRow(row)
        self._list.blockSignals(False)
        self._empty.setVisible(not self._shown)
        self._list.setVisible(bool(self._shown))
        self._select(row)

    def _selected(self) -> Task | None:
        row = self._list.currentRow()
        return self._shown[row] if 0 <= row < len(self._shown) else None

    def _sync_due_fields(self) -> None:
        self._date.setEnabled(self._has_due.isChecked())
        self._has_time.setEnabled(self._has_due.isChecked())
        self._clock.setEnabled(self._has_due.isChecked() and self._has_time.isChecked())

    def _select(self, _row: int) -> None:
        t = self._selected()
        self._title.setText(t.title if t else "")
        self._why.setText(t.why or "" if t else "")
        self._has_due.setChecked(bool(t and t.due))
        self._has_time.setChecked(bool(t and t.due and t.due_has_time))
        if t and t.due:
            self._date.setDate(QDate(t.due.year, t.due.month, t.due.day))
            self._clock.setTime(QTime(t.due.hour, t.due.minute) if t.due_has_time else QTime(9, 0))
        else:
            self._date.setDate(QDate.currentDate())
            self._clock.setTime(QTime(9, 0))
        self._sync_due_fields()
        self._save.setText("Save" if t else "Add Task")
        for button in (self._drop, self._delete):
            button.setVisible(t is not None)
        self._done.setVisible(bool(t and t.status == "open"))
        self._drop.setVisible(bool(t and t.status == "open"))
        running = self._running()
        self._focus.setVisible(bool(t and (t.status == "open" or (running and running.task_id == t.id))))
        self._focus.setText("Stop focus" if running and t and running.task_id == t.id else "Start focus")
        self._focus.setEnabled(not running or bool(t and running.task_id == t.id))
        self._note.setText(
            f"Added from a chat with Mochi." if t and t.conversation_id is not None else ""
        )
        sessions = [s for s in self._sessions if t and s.task_id == t.id]
        self._history.setText("Focus sessions:\n" + "\n".join(self._session_line(s) for s in sessions) if sessions else "")

    @staticmethod
    def _session_line(s: FocusSession) -> str:
        if s.ended_at is None:
            outcome = "running"
        else:
            outcome = (s.outcome or "") + ("" if s.answered else " (not answered)")
        return f"{s.started_at:%a %d %b, %H:%M}  ·  {s.planned_minutes} min  ·  {outcome}"

    def _due(self) -> tuple[datetime | None, bool]:
        if not self._has_due.isChecked():
            return None, False
        d = self._date.date()
        if self._has_time.isChecked():
            t = self._clock.time()
            return datetime(d.year(), d.month(), d.day(), t.hour(), t.minute()), True
        return datetime(d.year(), d.month(), d.day()), False

    def _on_save(self) -> None:
        title = self._title.text().strip()
        if not title:
            return
        due, has_time = self._due()
        t = self._selected()
        if t is None:
            self.add_requested.emit(title, self._why.text().strip(), due, has_time)
            self._new()
        else:
            self.edit_requested.emit(t.id, title, self._why.text().strip(), due, has_time)

    def _on_focus(self) -> None:
        t = self._selected()
        running = self._running()
        if running and t and running.task_id == t.id:
            self.focus_stop_requested.emit()
        elif t:
            self.focus_requested.emit(t.id)

    def _on_delete(self) -> None:
        t = self._selected()
        if t and QMessageBox.question(self, "Delete", f"Delete this Task for good?\n\n{t.title}") == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(t.id)


class RecapsView(QWidget):
    """Read-only list of Recaps, newest first. They fade on their own, so there is no editing."""

    delete_requested = Signal(int)

    def __init__(self):
        super().__init__(objectName="page")
        self._recaps: list[Recap] = []
        self._list = _wrapping_list()
        self._empty = QLabel(
            "No Recaps yet.\nOne is written when a Conversation ends.",
            objectName="hint", alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._delete = _button("Delete", "danger")
        self._delete.setEnabled(False)
        self._list.currentRowChanged.connect(lambda row: self._delete.setEnabled(0 <= row < len(self._recaps)))
        self._delete.clicked.connect(self._on_delete)
        header = _header("Recaps", "Short notes Mochi keeps about past Conversations. They fade after a few days.")
        header.addWidget(self._delete)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._empty, 1)
        self.show_recaps([])

    def show_recaps(self, recaps: list[Recap]) -> None:
        keep = self._selected().id if self._selected() else None
        self._recaps = recaps
        self._list.blockSignals(True)
        self._list.clear()
        for r in recaps:
            note = "  ·  sensitive" if r.sensitive else ""
            self._list.addItem(QListWidgetItem(f"{r.ended_at:%a %d %b %Y, %H:%M}  ·  {r.interface}{note}\n{r.text}"))
        row = next((i for i, r in enumerate(recaps) if r.id == keep), -1)
        self._list.setCurrentRow(row)
        self._list.blockSignals(False)
        self._delete.setEnabled(row >= 0)
        self._empty.setVisible(not recaps)
        self._list.setVisible(bool(recaps))

    def _selected(self) -> Recap | None:
        row = self._list.currentRow()
        return self._recaps[row] if 0 <= row < len(self._recaps) else None

    def _on_delete(self) -> None:
        r = self._selected()
        if r and QMessageBox.question(self, "Delete", f"Delete this Recap?\n\n{r.text}") == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(r.id)


class MainWindow(QMainWindow):
    """A sidebar of views."""

    presence_changed = Signal()  # shown, hidden, minimised or restored

    def __init__(self, face: Face):
        super().__init__()
        self.setWindowTitle("Mochi")
        self.resize(860, 580)
        self.setMinimumSize(640, 420)
        self.setStyleSheet(theme.STYLE)
        self.conversation = ConversationView(face)
        self.memories = MemoriesView()
        self.recaps = RecapsView()
        self.tasks = TasksView()
        self._tasks: list[Task] = []
        self._sessions: list[FocusSession] = []
        self._strip_timer = QTimer(self, interval=1000, timeout=self._refresh_strip)
        self.conversation.save_log_requested.connect(self._save_log)

        pages = QStackedWidget()
        self._sidebar = QWidget(objectName="sidebar")
        self._sidebar.setFixedWidth(SIDEBAR_WIDTH)
        side = QVBoxLayout(self._sidebar)
        side.setContentsMargins(10, 14, 10, 14)
        self._brand = QLabel("Mochi", objectName="brand")
        self.sidebar_toggle = _button("☰", "icon", "Hide sidebar")
        self.sidebar_toggle.clicked.connect(self._toggle_sidebar)
        top = QHBoxLayout()
        top.addWidget(self._brand)
        top.addStretch()
        top.addWidget(self.sidebar_toggle)
        side.addLayout(top)
        self.nav_buttons: list[QPushButton] = []
        group = QButtonGroup(self)
        group.setExclusive(True)
        entries = [
            ("Chat", self.conversation, None),
            ("Memories", self.memories, None),
            ("Tasks", self.tasks, None),
            ("Recaps", self.recaps, None),
        ]
        for i, (caption, page, soon) in enumerate(entries):
            pages.addWidget(page)
            button = _button(caption + ("  ·  soon" if soon else ""), "nav")
            button.setCheckable(True)
            button.setChecked(i == 0)
            button.clicked.connect(lambda _=False, i=i: pages.setCurrentIndex(i))
            group.addButton(button)
            side.addWidget(button)
            self.nav_buttons.append(button)
        side.addStretch()

        root = QWidget(objectName="root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(pages, 1)
        self.setCentralWidget(root)

    def show_tasks(self, tasks: list[Task], sessions: list[FocusSession]) -> None:
        self._tasks, self._sessions = tasks, sessions
        self.tasks.show_tasks(tasks, sessions)
        self._refresh_strip()

    def _refresh_strip(self) -> None:
        self.conversation.set_strip(strip_text(self._tasks, self._sessions, datetime.now()))

    def _toggle_sidebar(self) -> None:
        collapsing = self._brand.isVisible()
        for widget in (self._brand, *self.nav_buttons):
            widget.setVisible(not collapsing)
        self._sidebar.setFixedWidth(SIDEBAR_COLLAPSED_WIDTH if collapsing else SIDEBAR_WIDTH)
        self.sidebar_toggle.setToolTip("Show sidebar" if collapsing else "Hide sidebar")

    def _save_log(self) -> None:
        messages = self.conversation.messages()
        if not messages:
            self.statusBar().showMessage("Nothing to save yet.", 4000)
            return
        path = chatlog.save(messages)
        self.statusBar().showMessage(f"Saved {path}", 6000)

    @property
    def present(self) -> bool:
        return self.isVisible() and not self.isMinimized()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._strip_timer.start()
        self.presence_changed.emit()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._strip_timer.stop()
        self.presence_changed.emit()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self.presence_changed.emit()

    def open(self) -> None:
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()
