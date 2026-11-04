import json

from PySide6.QtGui import QColor, QImage

from companion.desktop.skin import BalloonSkin


def make_frame(path):
    """24x24: light outside, a dark ring, light inside."""
    image = QImage(24, 24, QImage.Format.Format_RGB32)
    image.fill(QColor("#e0f8cf"))
    for i in range(2, 22):
        for edge in (2, 21):
            image.setPixelColor(i, edge, QColor("#071821"))
            image.setPixelColor(edge, i, QColor("#071821"))
    image.save(str(path))


def test_loads_scales_and_clears_the_outside_of_the_border(qapp, tmp_path):
    make_frame(tmp_path / "f.png")
    (tmp_path / "b.json").write_text(json.dumps({"image": "f.png", "slice": 8, "scale": 2, "text_color": "#123456"}))
    skin = BalloonSkin.load(tmp_path / "b.json")
    assert skin.tile == 16 and skin.text_color == "#123456"
    image = skin.frame.toImage()
    assert image.width() == 48
    assert image.pixelColor(0, 0).alpha() == 0  # outside the ring
    assert image.pixelColor(24, 24).alpha() == 255  # inside it stays opaque


def test_missing_or_broken_skin_means_plain_balloon(qapp, tmp_path, capsys):
    assert BalloonSkin.load(tmp_path / "none.json") is None
    (tmp_path / "b.json").write_text(json.dumps({"image": "missing.png", "slice": 8}))
    assert BalloonSkin.load(tmp_path / "b.json") is None
    assert "plain balloon" in capsys.readouterr().err
