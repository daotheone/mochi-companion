from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

from companion.desktop.face import Face

DRAG_THRESHOLD = 4  # pixels; less than this is a click, not a drag


class CharacterWindow(QWidget):
    """Mochi on screen: frameless, transparent, always on top, never takes focus."""

    clicked = Signal()
    double_clicked = Signal()
    moving = Signal()
    moved_by_user = Signal()
    hide_requested = Signal()
    quit_requested = Signal()

    def __init__(self, face: Face, size: int):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Mochi")
        self.setFixedSize(size, size)
        self._face = face
        self._facing = "right"
        self._press: QPoint | None = None
        self._grab_offset = QPoint()
        self._dragging = False
        face.changed.connect(self._update_frame)
        self._update_frame()

    def set_facing(self, side: str) -> None:
        """Which way Mochi looks; the art is mirrored when it natively faces the other way."""
        if side != self._facing:
            self._facing = side
            self._update_frame()

    def _current(self) -> QPixmap:
        return self._face.pixmap(self.size(), self._facing != self._face.faces)

    def _update_frame(self) -> None:
        # The mask is the input shape too: clicks on transparent pixels reach the window below.
        self.setMask(self._current().mask())
        self.update()

    def paintEvent(self, _event) -> None:
        QPainter(self).drawPixmap(0, 0, self._current())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._grab_offset = self._press - self.pos()
            self._dragging = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press is None:
            return
        here = event.globalPosition().toPoint()
        if not self._dragging and (here - self._press).manhattanLength() >= DRAG_THRESHOLD:
            self._dragging = True
        if self._dragging:
            self.move(here - self._grab_offset)
            self.moving.emit()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        dragged, self._press = self._dragging, None
        self._dragging = False
        if dragged:
            self.moved_by_user.emit()
        else:
            self.clicked.emit()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.addAction("Hide", self.hide_requested.emit)
        menu.addAction("Quit", self.quit_requested.emit)
        menu.exec(event.globalPos())
