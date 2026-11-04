"""Draw the placeholder spritesheet: a round mochi, 4 frames per state (idle, thinking, replying)."""
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen

FRAME = 128
OUT = Path(__file__).resolve().parent.parent / "companion/desktop/sprites/placeholder.png"


def draw(p: QPainter, x: int, y: int, state: int, frame: int) -> None:
    squash = [0, 4, 0, -4][frame] if state == 0 else [0, 3, 6, 3][frame] if state == 2 else 0
    p.setPen(QPen(QColor("#d9c7b8"), 3))
    p.setBrush(QColor("#fff7ef"))
    p.drawEllipse(QRectF(x + 18 - squash, y + 40 + squash, 92 + 2 * squash, 70 - squash))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#3b2f2f"))
    eye_y = y + 68 + squash
    if state == 1 and frame % 2:  # thinking: eyes look up
        eye_y -= 6
    p.drawEllipse(QRectF(x + 44, eye_y, 9, 12))
    p.drawEllipse(QRectF(x + 75, eye_y, 9, 12))
    if state == 2:  # replying: open mouth
        p.setBrush(QColor("#e58b8b"))
        p.drawEllipse(QRectF(x + 58, y + 88 + squash, 12, 8 + frame % 2 * 3))
    elif state == 1:
        p.setBrush(QColor("#c9bdb2"))
        for i in range(frame):
            p.drawEllipse(QRectF(x + 92 + i * 9, y + 24 - i * 3, 6, 6))


def main() -> None:
    app = QGuiApplication(sys.argv)  # noqa: F841 - needed for painting
    image = QImage(FRAME * 4, FRAME * 3, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for state in range(3):
        for frame in range(4):
            draw(p, frame * FRAME, state * FRAME, state, frame)
    p.end()
    image.save(str(OUT))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
