from PySide6.QtCore import QObject, QRect, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QTransform

from companion.companion import NEUTRAL
from companion.desktop.sprites import FrameMap

DOT_MS = 350
DOT_SIZE, DOT_GAP, DOT_OUTLINE = 6, 5, 1  # in pixels of the 128px art
DOT_TOP = 7
HEAD_CENTRE = 58  # across the art as it natively faces
DOT_FILL, DOT_EDGE = QColor("#fff6e8"), QColor("#3a2020")


class Face(QObject):
    """Mochi's current look, shared by everything that draws it: an Expression, or thinking dots on neutral."""

    changed = Signal()

    def __init__(self, frame_map: FrameMap):
        super().__init__()
        self._map = frame_map
        self._sheet = QPixmap(str(frame_map.sheet))
        self._expression = NEUTRAL
        self._thinking = False
        self._frame = 0
        self._dots = 1
        self._cache: dict[tuple, QPixmap] = {}
        self._timer = QTimer(self, timeout=self.tick)
        self._restart_timer()

    @property
    def faces(self) -> str:
        return self._map.faces

    @property
    def expression(self) -> str:
        return self._expression

    @property
    def thinking(self) -> bool:
        return self._thinking

    def set_expression(self, expression: str) -> None:
        if expression != self._expression or self._thinking:
            self._show(expression, False)

    def set_thinking(self, thinking: bool) -> None:
        if thinking != self._thinking:
            self._show(NEUTRAL, thinking)

    def _show(self, expression: str, thinking: bool) -> None:
        self._expression, self._thinking = expression, thinking
        self._frame, self._dots = 0, 1
        self._restart_timer()
        self.changed.emit()

    def _restart_timer(self) -> None:
        fps = self._map.expression(self._expression).fps
        self._timer.start(DOT_MS if self._thinking else 1000 // max(1, fps))

    def tick(self) -> None:
        """Advance the animation: a thinking dot, or the Expression's next frame."""
        before = (self._frame, self._dots)
        if self._thinking:
            self._dots = self._dots % 3 + 1
        else:
            self._frame = (self._frame + 1) % len(self._map.expression(self._expression).cells)
        if (self._frame, self._dots) != before:
            self.changed.emit()

    def pixmap(self, size: QSize, mirrored: bool) -> QPixmap:
        dots = self._dots if self._thinking else 0
        key = (self._expression, self._frame, mirrored, size.width(), size.height(), dots)
        if key not in self._cache:
            self._cache[key] = self._draw(size, mirrored, dots)
        return self._cache[key]

    def _draw(self, size: QSize, mirrored: bool, dots: int) -> QPixmap:
        w, h = self._map.frame_size
        col, row = self._map.expression(self._expression).cells[self._frame]
        frame = self._sheet.copy(col * w, row * h, w, h)
        if mirrored:
            frame = frame.transformed(QTransform().scale(-1, 1))
        frame = frame.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        if dots:
            self._draw_dots(frame, w, mirrored, dots)
        return frame

    @staticmethod
    def _draw_dots(frame: QPixmap, art_width: int, mirrored: bool, dots: int) -> None:
        """After mirroring, so they always fill left to right."""
        scale = frame.width() / art_width
        centre = art_width - 1 - HEAD_CENTRE if mirrored else HEAD_CENTRE
        left = centre - (3 * DOT_SIZE + 2 * DOT_GAP) / 2
        painter = QPainter(frame)
        for i in range(dots):
            x = left + i * (DOT_SIZE + DOT_GAP)
            inner = QRect(round(x * scale), round(DOT_TOP * scale), round(DOT_SIZE * scale), round(DOT_SIZE * scale))
            edge = max(1, round(DOT_OUTLINE * scale))
            painter.fillRect(inner.adjusted(-edge, -edge, edge, edge), DOT_EDGE)
            painter.fillRect(inner, DOT_FILL)
        painter.end()
