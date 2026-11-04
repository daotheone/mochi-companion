import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QFrame

from companion.desktop.settings import default_path


def skin_path() -> Path:
    """Local art that is not committed: <config dir>/sprites/balloon.json."""
    return default_path().parent / "sprites" / "balloon.json"


@dataclass(frozen=True)
class BalloonSkin:
    """A nine-slice frame for the Speech Balloon: `slice`-pixel tiles drawn `scale` times larger."""

    frame: QPixmap  # already scaled, with the outside of the border made transparent
    tile: int  # size of one tile after scaling
    text_color: str

    @classmethod
    def load(cls, path: Path | None = None) -> "BalloonSkin | None":
        """The local skin, or None (with a warning if it is broken) to use the plain style."""
        path = path or skin_path()
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text())
            image = QImage(str(path.parent / data["image"]))
            slice_, scale = int(data["slice"]), int(data.get("scale", 2))
            if image.isNull() or image.width() != 3 * slice_ or image.height() != 3 * slice_:
                raise ValueError(f"{data['image']} must be a 3x3 grid of {slice_}px tiles")
            color = str(data.get("text_color", "#000000"))
        except (OSError, ValueError, KeyError, TypeError) as e:
            print(f"[warning] Cannot read balloon skin {path}: {e}; using the plain balloon.", file=sys.stderr)
            return None
        image = _clear_outside(image.convertToFormat(QImage.Format.Format_ARGB32))
        scaled = QPixmap.fromImage(image).scaled(
            image.width() * scale, image.height() * scale, Qt.AspectRatioMode.IgnoreAspectRatio, _NEAREST
        )
        return cls(scaled, slice_ * scale, color)


_NEAREST = Qt.TransformationMode.FastTransformation


def _clear_outside(image: QImage) -> QImage:
    """Make the pixels outside the border transparent: flood from every corner over the corner colour."""
    background = image.pixel(0, 0)
    seen = set()
    todo = [(0, 0), (image.width() - 1, 0), (0, image.height() - 1), (image.width() - 1, image.height() - 1)]
    while todo:
        x, y = todo.pop()
        if (x, y) in seen or not (0 <= x < image.width() and 0 <= y < image.height()):
            continue
        seen.add((x, y))
        if image.pixel(x, y) != background:
            continue
        image.setPixelColor(x, y, QColor(0, 0, 0, 0))
        todo += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return image


class SkinnedCard(QFrame):
    """A QFrame that paints a BalloonSkin around its contents."""

    def __init__(self, skin: BalloonSkin):
        super().__init__()
        self._skin = skin

    def paintEvent(self, _event) -> None:
        t, w, h = self._skin.tile, self.width(), self.height()
        xs, ys = (0, t, w - t), (0, t, h - t)
        widths, heights = (t, w - 2 * t, t), (t, h - 2 * t, t)
        p = QPainter(self)
        for row in range(3):
            for col in range(3):
                target = QRect(xs[col], ys[row], widths[col], heights[row])
                p.drawPixmap(target, self._skin.frame, QRect(col * t, row * t, t, t))
