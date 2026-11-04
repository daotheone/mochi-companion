from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from companion.store import Memory, StoredMessage


def _split_tags(raw: str) -> list[str]:
    return [t for t in raw.replace(",", " ").split() if t.strip("#")]


class ConversationView(QWidget):
    send_requested = Signal(str)
    new_requested = Signal()

    def __init__(self):
        super().__init__()
        self._log = QTextBrowser()
        self._input = QLineEdit(placeholderText="Nói với Mochi…")
        self._send = QPushButton("Send")
        new = QPushButton("New Conversation")
        self._input.returnPressed.connect(self._submit)
        self._send.clicked.connect(self._submit)
        new.clicked.connect(self.new_requested.emit)
        row = QHBoxLayout()
        row.addWidget(self._input)
        row.addWidget(self._send)
        row.addWidget(new)
        layout = QVBoxLayout(self)
        layout.addWidget(self._log)
        layout.addLayout(row)

    def show_messages(self, messages: list[StoredMessage]) -> None:
        parts = []
        for m in messages:
            who, colour = ("you", "#555") if m.role == "user" else ("mochi", "#a0522d")
            body = "<br>".join(escape(line) for line in m.content.splitlines() if line.strip())
            parts.append(f'<p><b style="color:{colour}">{who}</b><br>{body}</p>')
        self._log.setHtml("".join(parts) or "<p><i>No Messages yet in this Conversation.</i></p>")
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def set_busy(self, busy: bool) -> None:
        self._send.setEnabled(not busy)
        self._input.setReadOnly(busy)

    def _submit(self) -> None:
        text = self._input.text().strip()
        if text and self._send.isEnabled():
            self._input.clear()
            self.send_requested.emit(text)


class MemoriesView(QWidget):
    add_requested = Signal(str, list)
    edit_requested = Signal(int, str)
    tags_requested = Signal(int, list)
    confirm_requested = Signal(int)
    forget_requested = Signal(int)

    def __init__(self):
        super().__init__()
        self._memories: list[Memory] = []
        self._list = QListWidget()
        self._text = QPlainTextEdit(placeholderText="What should Mochi remember?")
        self._tags = QLineEdit(placeholderText="Tags, e.g. study food")
        self._note = QLabel(wordWrap=True)
        self._save = QPushButton("Save")
        self._confirm = QPushButton("Confirm")
        self._forget = QPushButton("Forget")
        new = QPushButton("New Memory")
        self._list.currentRowChanged.connect(self._select)
        self._save.clicked.connect(self._on_save)
        self._confirm.clicked.connect(lambda: self.confirm_requested.emit(self._selected().id))
        self._forget.clicked.connect(self._on_forget)
        new.clicked.connect(lambda: self._list.setCurrentRow(-1))
        form = QVBoxLayout()
        form.addWidget(self._text)
        form.addWidget(self._tags)
        form.addWidget(self._note)
        buttons = QHBoxLayout()
        for b in (self._save, self._confirm, self._forget):
            buttons.addWidget(b)
        form.addLayout(buttons)
        left = QVBoxLayout()
        left.addWidget(self._list)
        left.addWidget(new)
        layout = QHBoxLayout(self)
        layout.addLayout(left, 1)
        layout.addLayout(form, 1)
        self._select(-1)

    def show_memories(self, memories: list[Memory]) -> None:
        keep = self._selected().id if self._selected() else None
        self._memories = memories
        self._list.blockSignals(True)
        self._list.clear()
        for m in memories:
            tags = "".join(f" #{t}" for t in m.tags)
            item = QListWidgetItem(f"[{m.kind}]{tags}  {m.text}")
            if m.kind == "observed":
                item.setForeground(Qt.GlobalColor.darkYellow)
            self._list.addItem(item)
        row = next((i for i, m in enumerate(memories) if m.id == keep), -1)
        self._list.setCurrentRow(row)
        self._list.blockSignals(False)
        self._select(row)

    def _selected(self) -> Memory | None:
        row = self._list.currentRow()
        return self._memories[row] if 0 <= row < len(self._memories) else None

    def _select(self, _row: int) -> None:
        m = self._selected()
        self._text.setPlainText(m.text if m else "")
        self._tags.setText(" ".join(f"#{t}" for t in m.tags) if m else "")
        self._confirm.setVisible(bool(m and m.kind == "observed"))
        self._forget.setEnabled(m is not None)
        self._save.setText("Save" if m else "Add")
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


class MainWindow(QMainWindow):
    """Conversation and Memories. A Recaps view is added once Recaps exist."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mochi")
        self.resize(720, 520)
        self.conversation = ConversationView()
        self.memories = MemoriesView()
        tabs = QTabWidget()
        tabs.addTab(self.conversation, "Conversation")
        tabs.addTab(self.memories, "Memories")
        self.setCentralWidget(tabs)

    def open(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
