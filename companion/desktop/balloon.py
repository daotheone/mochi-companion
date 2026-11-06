from PySide6.QtCore import QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from companion.desktop import theme
from companion.desktop.skin import BalloonSkin, SkinnedCard
from companion.store import Memory
from companion.tasks import TaskProposal, format_due

WIDTH = 260
BORDER = 2  # the plain card's stylesheet border; it shrinks the area the layout sees
BUBBLE_DELAY_MS = 700
FADE_AFTER_MS = 30_000
FADE_MS = 1_000

STYLE = """
QFrame#card { background: %(panel)s; border: 2px solid %(border)s; border-radius: 16px; }
QLabel { color: %(text)s; font-size: 14px; }
QLabel#noticed, QLabel#proposal { color: %(dim)s; font-size: 12px; }
QPushButton {
    font-size: 12px; padding: 3px 12px; color: %(text)s; background: %(panel)s;
    border: 1.5px solid %(border)s; border-radius: 10px;
}
QPushButton:hover { border-color: %(accent)s; color: %(accent)s; }
"""
PLAIN = {
    "text": theme.INK, "dim": theme.DIM, "panel": theme.PANEL, "border": theme.BORDER, "accent": theme.ACCENT,
}


class SpeechBalloon(QWidget):
    """Mochi's latest reply: Bubbles appear one at a time and stack."""

    finished = Signal()  # the last Bubble is on screen
    resized = Signal()
    fading = Signal()
    retry_requested = Signal()
    confirm_requested = Signal(int)
    forget_requested = Signal(int)
    task_add_requested = Signal(object)
    notice_answered = Signal(object, str)
    dismissed = Signal()  # hidden by any route; a waiting Reminder can take the spot

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
        skin = BalloonSkin.load()
        if skin:
            card = SkinnedCard(skin)
            self._inset = 0  # the skin is painted, not a stylesheet border
            self.setStyleSheet(STYLE % {**PLAIN, "text": skin.text_color, "dim": skin.text_color})
        else:
            card = QFrame(objectName="card")
            self._inset = BORDER
            self.setStyleSheet(STYLE % PLAIN)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        self._stack = QVBoxLayout(card)
        if skin:
            self._stack.setContentsMargins(skin.tile, skin.tile, skin.tile, skin.tile)
        self._pending: list[str] = []
        self._noticed: Memory | None = None
        self._proposal: TaskProposal | None = None
        self._noticed_row = None
        self._sticky = False  # a Reminder or Check-in never fades
        self._pinned = False
        self._hovered = False
        self._reveal = QTimer(self, interval=BUBBLE_DELAY_MS, timeout=self._reveal_next)
        self._fade_timer = QTimer(self, singleShot=True, interval=FADE_AFTER_MS, timeout=self._fade)
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self, duration=FADE_MS)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self.hide)

    def show_reply(self, bubbles: list[str], noticed: Memory | None, proposal: TaskProposal | None = None) -> None:
        self._begin()
        self._pending = list(bubbles)
        self._noticed = noticed
        self._proposal = proposal
        self._reveal_next()
        if self._pending:
            self._reveal.start()

    def show_error(self, message: str) -> None:
        self._begin()
        self._add_label(message)
        row = QHBoxLayout()
        retry = QPushButton("Retry")
        retry.show()
        retry.clicked.connect(self.retry_requested.emit)
        retry.clicked.connect(self.hide)
        row.addWidget(retry)
        row.addStretch()
        self._stack.addLayout(row)
        self._shown()

    def show_notice(self, notice) -> None:
        """A Reminder or Check-in: stays until answered."""
        self._begin()
        self._sticky = True
        self._add_label(notice.text)
        row = QHBoxLayout()
        for action, caption in notice.actions:
            button = QPushButton(caption)
            button.show()
            button.clicked.connect(lambda _=False, a=action: self.notice_answered.emit(notice, a))
            button.clicked.connect(lambda _=False: self.hide())
            row.addWidget(button)
        row.addStretch()
        self._stack.addLayout(row)
        self._shown()

    @property
    def sticky_notice(self) -> bool:
        return self._sticky and self.isVisible()

    def set_pinned(self, pinned: bool) -> None:
        """While pinned (Chat Box open) the Speech Balloon never fades."""
        self._pinned = pinned
        self._restart_fade()

    def _begin(self) -> None:
        self._reveal.stop()
        self._clear(self._stack)
        self._fade_anim.stop()
        self.setWindowOpacity(1.0)
        self._sticky = False
        self._proposal = None

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
        label.ensurePolished()
        label.show()  # a layout ignores hidden widgets, and a new child stays hidden until the next event-loop turn

    def _reveal_next(self) -> None:
        if self._pending:
            self._add_label(self._pending.pop(0))
        if not self._pending:
            self._reveal.stop()
            if self._noticed:
                self._add_noticed(self._noticed)
            if self._proposal:
                self._add_proposal(self._proposal)
            self._shown()
            self.finished.emit()
        else:
            self._shown()

    def _add_noticed(self, memory: Memory) -> None:
        self._add_label(f"mochi noticed: {memory.text}", "noticed")
        row = QHBoxLayout()
        for caption, signal in (("Confirm", self.confirm_requested), ("Forget", self.forget_requested)):
            button = QPushButton(caption)
            button.show()
            button.clicked.connect(lambda _=False, s=signal: s.emit(memory.id))
            button.clicked.connect(lambda _=False: self._drop_noticed())
            row.addWidget(button)
        row.addStretch()
        self._stack.addLayout(row)
        self._noticed_row = row

    def _add_proposal(self, proposal: TaskProposal) -> None:
        when = format_due(proposal.due, proposal.has_time)
        self._add_label(f"task: {proposal.title} ({when})", "proposal")
        row = QHBoxLayout()
        for caption, signal in (("Add", self.task_add_requested), ("Dismiss", None)):
            button = QPushButton(caption)
            button.show()
            if signal:
                button.clicked.connect(lambda _=False, p=proposal: self.task_add_requested.emit(p))
            button.clicked.connect(lambda _=False, r=row: self._drop_proposal(r))
            row.addWidget(button)
        row.addStretch()
        self._stack.addLayout(row)

    def _drop_proposal(self, row) -> None:
        self._proposal = None
        self._drop_row("proposal", row)

    def _drop_noticed(self) -> None:
        self._noticed = None
        self._drop_row("noticed", self._noticed_row)

    def _drop_row(self, label: str, row) -> None:
        for i in reversed(range(self._stack.count())):
            item = self._stack.itemAt(i)
            if item.layout() is row:
                self._clear(row)
                self._stack.removeItem(item)
            elif item.widget() and item.widget().objectName() == label:
                item.widget().deleteLater()
                self._stack.removeItem(item)
        self._shown()

    def _fit(self) -> None:
        self._stack.invalidate()
        # sizeHint() ignores word-wrap; height-for-width at the real inner width does not.
        self.setFixedHeight(self._stack.heightForWidth(WIDTH - 2 * self._inset) + 2 * self._inset)
        self.resized.emit()

    def _shown(self) -> None:
        self._fit()
        if not self.isVisible():
            self.show()
        # Fonts from the stylesheet only apply once the window is polished and shown, which can
        # change the wrapped height; fit again then.
        QTimer.singleShot(0, self._fit)
        self._restart_fade()

    def _restart_fade(self) -> None:
        self._fade_timer.stop()
        if self.isVisible() and not self._pinned and not self._sticky and not self._hovered and not self._reveal.isActive():
            self._fade_timer.start()

    def _fade(self) -> None:
        self.fading.emit()
        self._fade_anim.start()

    def hideEvent(self, event) -> None:
        # Hidden means done: a late Bubble would show it again, and fading would end the Expression.
        self._reveal.stop()
        self._pending = []
        self._fade_timer.stop()
        super().hideEvent(event)
        self.dismissed.emit()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._fade_anim.stop()
        self.setWindowOpacity(1.0)
        self._fade_timer.stop()

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._restart_fade()
