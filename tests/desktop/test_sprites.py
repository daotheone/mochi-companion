import json

import pytest

from companion.desktop.sprites import FrameMap, SpriteError, STATES


def write(tmp_path, states):
    path = tmp_path / "frames.json"
    path.write_text(json.dumps({"sheet": "s.png", "frame_size": [128, 128], "states": states}))
    return path


def test_loads_every_state(tmp_path):
    states = {s: {"row": i, "frames": 2, "fps": 4} for i, s in enumerate(STATES)}
    fm = FrameMap.load(write(tmp_path, states))
    assert fm.sheet == tmp_path / "s.png"
    assert fm.state("thinking").row == STATES.index("thinking")
    assert fm.frame_size == (128, 128)


def test_missing_state_is_a_readable_error(tmp_path):
    with pytest.raises(SpriteError, match="replying"):
        FrameMap.load(write(tmp_path, {"idle": {"row": 0, "frames": 1, "fps": 1}, "thinking": {"row": 1, "frames": 1, "fps": 1}}))


def test_bundled_placeholder_map_is_valid():
    fm = FrameMap.load()
    assert fm.sheet.is_file()
