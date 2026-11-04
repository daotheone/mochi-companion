from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import QMenu, QWidget

from companion.desktop.sprites import FrameMap

DRAG_THRESHOLD = 4  # pixels; less than this is a click, not a drag


class CharacterWindow(QWidget):
    """Mochi on screen: frameless, transparent, always on top, never takes focus."""

    clicked = Signal()
    double_clicked = Signal()
    moving = Signal()
    moved_by_user = Signal()
    hide_requested = Signal()
    quit_requested = Signal()

    def __init__(self, frame_map: FrameMap, size: int):
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
        self._map = frame_map
        self._sheet = QPixmap(str(frame_map.sheet))
        self._state = "idle"
        self._frame = 0
        self._facing = "right"
        self._cache: dict[tuple[str, int, bool], QPixmap] = {}
        self._press: QPoint | None = None
        self._grab_offset = QPoint()
        self._dragging = False
        self._timer = QTimer(self, timeout=self._advance)
        self._apply_state()

    @property
    def state(self) -> str:
        return self._state

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state, self._frame = state, 0
            self._apply_state()

    def set_facing(self, side: str) -> None:
        """Which way Mochi looks; the art is mirrored when it natively faces the other way."""
        if side != self._facing:
            self._facing = side
            self._update_frame()

    def _apply_state(self) -> None:
        self._timer.start(1000 // max(1, self._map.state(self._state).fps))
        self._update_frame()

    def _advance(self) -> None:
        self._frame = (self._frame + 1) % len(self._map.state(self._state).cells)
        self._update_frame()

    def _current(self) -> QPixmap:
        mirrored = self._facing != self._map.faces
        key = (self._state, self._frame, mirrored)
        if key not in self._cache:
            w, h = self._map.frame_size
            spec = self._map.state(self._state)
            col, row = spec.cells[self._frame]
            frame = self._sheet.copy(col * w, row * h, w, h)
            if mirrored:
                frame = frame.transformed(QTransform().scale(-1, 1))
            self._cache[key] = frame.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        return self._cache[key]

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
