import json

import pytest

from companion.companion import EXPRESSIONS
from companion.desktop.sprites import FrameMap, SpriteError


def write(tmp_path, expressions):
    path = tmp_path / "frames.json"
    path.write_text(json.dumps({"sheet": "s.png", "frame_size": [128, 128], "expressions": expressions}))
    return path


def test_loads_every_expression(tmp_path):
    expressions = {e: {"row": i, "frames": 2, "fps": 4} for i, e in enumerate(EXPRESSIONS)}
    fm = FrameMap.load(write(tmp_path, expressions))
    assert fm.sheet == tmp_path / "s.png"
    assert fm.expression("sad").cells == ((0, 2), (1, 2))
    assert fm.frame_size == (128, 128)


def test_a_missing_expression_is_a_readable_error(tmp_path):
    partial = {e: {"row": 0, "frames": 1, "fps": 1} for e in EXPRESSIONS if e != "blush"}
    with pytest.raises(SpriteError, match="blush"):
        FrameMap.load(write(tmp_path, partial))


def test_bundled_map_has_rosa_on_the_sheet_grid():
    fm = FrameMap.load()
    assert fm.sheet.is_file()
    cells = {e: fm.expression(e).cells[0] for e in EXPRESSIONS}
    assert cells == {
        "neutral": (0, 0), "happy": (1, 0), "sad": (0, 1), "smirk": (1, 1),
        "blush": (0, 2), "angry": (1, 2), "surprised": (0, 3), "laugh": (1, 3),
    }


def test_cells_pick_frames_off_a_grid_sheet(tmp_path):
    expressions = {e: {"cells": [[1, 2], [0, 3]], "fps": 2} for e in EXPRESSIONS}
    assert FrameMap.load(write(tmp_path, expressions)).expression("happy").cells == ((1, 2), (0, 3))


def local_map(tmp_path, monkeypatch, text):
    local = tmp_path / "mochi-companion" / "sprites" / "frames.json"
    local.parent.mkdir(parents=True)
    local.write_text(text)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def test_broken_local_map_falls_back_to_the_bundled_one(tmp_path, monkeypatch, capsys):
    from companion.desktop import sprites

    local_map(tmp_path, monkeypatch, "{nope")
    assert sprites.load_frame_map().sheet == FrameMap.load().sheet
    assert "bundled" in capsys.readouterr().err


def test_local_map_without_every_expression_falls_back_to_the_bundled_one(tmp_path, monkeypatch, capsys):
    from companion.desktop import sprites

    old_format = {"sheet": "s.png", "frame_size": [128, 128], "states": {"idle": {"cells": [[0, 0]], "fps": 1}}}
    local_map(tmp_path, monkeypatch, json.dumps(old_format))
    assert sprites.load_frame_map().sheet == FrameMap.load().sheet
    assert "bundled" in capsys.readouterr().err


def alpha(fm, expression, x, y, qapp):
    from PySide6.QtGui import QImage

    col, row = fm.expression(expression).cells[0]
    return QImage(str(fm.sheet)).pixelColor(col * 128 + x, row * 128 + y).alpha()


@pytest.mark.parametrize(
    "expression, x, y",
    [("angry", 65, 73), ("surprised", 51, 57), ("surprised", 83, 58), ("happy", 61, 55), ("blush", 76, 113)],
)
def test_teeth_eyes_and_highlights_are_solid_on_any_background(qapp, expression, x, y):
    assert alpha(FrameMap.load(), expression, x, y, qapp) == 255


@pytest.mark.parametrize("expression, x, y", [("neutral", 78, 75), ("smirk", 78, 78), ("laugh", 85, 78)])
def test_real_gaps_beside_her_neck_stay_see_through(qapp, expression, x, y):
    assert alpha(FrameMap.load(), expression, x, y, qapp) == 0
