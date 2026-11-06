from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from companion.desktop import chatlog, theme
from companion.desktop.face import Face
from companion.store import Memory, Recap, StoredMessage


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


class ComingSoon(QWidget):
    """Stand-in for a feature that does not exist yet."""

    def __init__(self, title: str, text: str, issue: str):
        super().__init__(objectName="page")
        card = QFrame(objectName="soon")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(32, 32, 32, 32)
        inner.setSpacing(6)
        for widget in (
            QLabel(title, objectName="title"),
            QLabel(text, objectName="hint", wordWrap=True),
            QLabel(f"Coming soon · {issue}", objectName="hint"),
        ):
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner.addWidget(widget)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.addStretch()
        layout.addWidget(card)
        layout.addStretch()


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

    def __init__(self, face: Face):
        super().__init__(objectName="page")
        self._messages: list[StoredMessage] = []
        self._busy = False
        self._notice: QWidget | None = None
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

    def show_error(self, message: str) -> None:
        self._show_notice(message, [("Retry", self.retry_requested.emit)])

    def show_noticed(self, memory: Memory) -> None:
        self._show_notice(f"mochi noticed: {memory.text}", [
            ("Confirm", lambda: self.confirm_requested.emit(memory.id)),
            ("Forget", lambda: self.forget_requested.emit(memory.id)),
        ])

    def _show_notice(self, text: str, actions: list) -> None:
        """A note at the bottom of the history, with buttons; using one dismisses it."""
        self.clear_notice()
        self._notice = QWidget()
        column = QVBoxLayout(self._notice)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(QLabel(text, objectName="hint", wordWrap=True))
        row = QHBoxLayout()
        for caption, action in actions:
            button = _button(caption)
            button.clicked.connect(lambda _=False, action=action: (self.clear_notice(), action()))
            row.addWidget(button)
        row.addStretch()
        column.addLayout(row)
        self._holder_layout.insertWidget(1, self._notice)
        self._at_bottom = True

    def clear_notice(self) -> None:
        if self._notice is not None:
            self._notice.setParent(None)
            self._notice.deleteLater()
            self._notice = None

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
    """A sidebar of views. Tasks is a stand-in until that feature exists."""

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
            ("Tasks", ComingSoon(
                "Tasks & focus", "Plan small steps, run a focus timer, and get a gentle check-in.", "#4"
            ), "Coming soon"),
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
        self.presence_changed.emit()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
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
