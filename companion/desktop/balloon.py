from PySide6.QtCore import QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from companion.store import Memory

WIDTH = 260
BUBBLE_DELAY_MS = 700
FADE_AFTER_MS = 30_000
FADE_MS = 1_000

STYLE = """
QFrame#card { background: white; border: 2px solid #d9c7b8; border-radius: 14px; }
QLabel { color: #3b2f2f; font-size: 14px; }
QLabel#noticed { color: #7a6a60; font-size: 12px; }
QPushButton { font-size: 12px; padding: 2px 8px; }
"""


class SpeechBalloon(QWidget):
    """Mochi's latest reply: Bubbles appear one at a time and stack."""

    finished = Signal()  # the last Bubble is on screen
    resized = Signal()
    retry_requested = Signal()
    confirm_requested = Signal(int)
    forget_requested = Signal(int)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(WIDTH)
        self.setStyleSheet(STYLE)
        card = QFrame(self, objectName="card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        self._stack = QVBoxLayout(card)
        self._pending: list[str] = []
        self._noticed: Memory | None = None
        self._pinned = False
        self._hovered = False
        self._reveal = QTimer(self, interval=BUBBLE_DELAY_MS, timeout=self._reveal_next)
        self._fade_timer = QTimer(self, singleShot=True, interval=FADE_AFTER_MS, timeout=self._fade)
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self, duration=FADE_MS)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self.hide)

    def show_reply(self, bubbles: list[str], noticed: Memory | None) -> None:
        self._begin()
        self._pending = list(bubbles)
        self._noticed = noticed
        self._reveal_next()
        self._reveal.start()

    def show_error(self, message: str) -> None:
        self._begin()
        self._add_label(message)
        row = QHBoxLayout()
        retry = QPushButton("Retry")
        retry.clicked.connect(self.retry_requested.emit)
        retry.clicked.connect(self.hide)
        row.addWidget(retry)
        row.addStretch()
        self._stack.addLayout(row)
        self._shown()

    def set_pinned(self, pinned: bool) -> None:
        """While pinned (Chat Box open) the Speech Balloon never fades."""
        self._pinned = pinned
        self._restart_fade()

    def _begin(self) -> None:
        self._reveal.stop()
        self._clear(self._stack)
        self._fade_anim.stop()
        self.setWindowOpacity(1.0)

    def _clear(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear(item.layout())

    def _add_label(self, text: str, name: str = "") -> None:
        label = QLabel(text, wordWrap=True, objectName=name)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._stack.addWidget(label)

    def _reveal_next(self) -> None:
        if self._pending:
            self._add_label(self._pending.pop(0))
        if not self._pending:
            self._reveal.stop()
            if self._noticed:
                self._add_noticed(self._noticed)
            self._shown()
            self.finished.emit()
        else:
            self._shown()

    def _add_noticed(self, memory: Memory) -> None:
        self._add_label(f"mochi noticed: {memory.text}", "noticed")
        row = QHBoxLayout()
        for caption, signal in (("Confirm", self.confirm_requested), ("Forget", self.forget_requested)):
            button = QPushButton(caption)
            button.clicked.connect(lambda _=False, s=signal: s.emit(memory.id))
            button.clicked.connect(lambda _=False: self._drop_noticed())
            row.addWidget(button)
        row.addStretch()
        self._stack.addLayout(row)

    def _drop_noticed(self) -> None:
        self._noticed = None
        for i in reversed(range(self._stack.count())):
            item = self._stack.itemAt(i)
            if item.layout():
                self._clear(item.layout())
                self._stack.removeItem(item)
            elif item.widget() and item.widget().objectName() == "noticed":
                item.widget().deleteLater()
                self._stack.removeItem(item)
        self._shown()

    def _shown(self) -> None:
        self.adjustSize()
        if not self.isVisible():
            self.show()
        self.resized.emit()
        self._restart_fade()

    def _restart_fade(self) -> None:
        self._fade_timer.stop()
        if self.isVisible() and not self._pinned and not self._hovered and not self._reveal.isActive():
            self._fade_timer.start()

    def _fade(self) -> None:
        self._fade_anim.start()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._fade_anim.stop()
        self.setWindowOpacity(1.0)
        self._fade_timer.stop()

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._restart_fade()
