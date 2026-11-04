from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget


class ChatBox(QWidget):
    """The small input under the Character. Esc closes it."""

    submitted = Signal(str)
    closed = Signal()

    def __init__(self, width: int):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setFixedWidth(width)
        self._input = QLineEdit(self)
        self._input.setPlaceholderText("Nói với Mochi…")
        self._input.setStyleSheet(
            "QLineEdit { background: white; color: #3b2f2f; border: 2px solid #d9c7b8;"
            " border-radius: 12px; padding: 6px 10px; font-size: 14px; }"
        )
        self._input.returnPressed.connect(self._submit)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._input)

    def open_at(self, x: int, y: int) -> None:
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()

    def set_busy(self, busy: bool) -> None:
        """Mochi is thinking: keep the text box but refuse new Messages."""
        self._input.setReadOnly(busy)
        self._input.setPlaceholderText("Mochi đang nghĩ…" if busy else "Nói với Mochi…")

    def _submit(self) -> None:
        text = self._input.text().strip()
        if text and not self._input.isReadOnly():
            self._input.clear()
            self.submitted.emit(text)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        super().closeEvent(event)
        self.closed.emit()
