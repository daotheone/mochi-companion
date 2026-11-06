from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from companion.desktop.theme import CHATBOX_STYLE


class ChatBox(QWidget):
    """The small input under the Character. Esc closes it."""

    submitted = Signal(str)
    closed = Signal()

    def __init__(self, width: int):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # no square corners behind the rounded input
        self.setFixedWidth(width)
        self._input = QLineEdit(self)
        self._input.setPlaceholderText("Nói với Mochi…")
        self._input.setStyleSheet(CHATBOX_STYLE)
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
