import json
import sys
from dataclasses import dataclass
from pathlib import Path

STATES = ("idle", "thinking", "replying")
BUNDLED = Path(__file__).parent / "sprites" / "frames.json"


class SpriteError(Exception):
    """The sprite frame-map is missing or malformed."""


@dataclass(frozen=True)
class StateFrames:
    cells: tuple[tuple[int, int], ...]  # (column, row) of each frame on the sheet
    fps: int

    @classmethod
    def parse(cls, spec: dict) -> "StateFrames":
        """Either {"row", "frames", "fps"} for an animation strip, or {"cells": [[col, row], ...], "fps"}."""
        if "cells" in spec:
            cells = tuple((int(c), int(r)) for c, r in spec["cells"])
        else:
            cells = tuple((i, int(spec["row"])) for i in range(int(spec["frames"])))
        if not cells:
            raise ValueError("a state needs at least one frame")
        return cls(cells, int(spec["fps"]))


@dataclass(frozen=True)
class FrameMap:
    sheet: Path
    frame_size: tuple[int, int]
    states: dict[str, StateFrames]

    def state(self, name: str) -> StateFrames:
        return self.states[name]

    @classmethod
    def load(cls, path: Path = BUNDLED) -> "FrameMap":
        """Read a frame-map; the sheet path is relative to the map file."""
        try:
            data = json.loads(path.read_text())
            width, height = data["frame_size"]
            states = {name: StateFrames.parse(spec) for name, spec in data["states"].items()}
            sheet = path.parent / data["sheet"]
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            raise SpriteError(f"Cannot read sprite frame-map {path}: {e}") from e
        for name in STATES:
            if name not in states:
                raise SpriteError(f"Sprite frame-map {path} has no '{name}' state.")
        return cls(sheet, (width, height), states)


def user_map_path() -> Path:
    """Local art that is not committed: <config dir>/sprites/frames.json."""
    from companion.desktop.settings import default_path

    return default_path().parent / "sprites" / "frames.json"


def load_frame_map() -> FrameMap:
    """The local art if present and valid, else the bundled placeholder."""
    local = user_map_path()
    if local.is_file():
        try:
            fm = FrameMap.load(local)
            if fm.sheet.is_file():
                return fm
            print(f"[warning] sprite sheet {fm.sheet} not found; using the placeholder.", file=sys.stderr)
        except SpriteError as e:
            print(f"[warning] {e}; using the placeholder.", file=sys.stderr)
    return FrameMap.load()
