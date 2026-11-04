import json
from dataclasses import dataclass
from pathlib import Path

STATES = ("idle", "thinking", "replying")
BUNDLED = Path(__file__).parent / "sprites" / "frames.json"


class SpriteError(Exception):
    """The sprite frame-map is missing or malformed."""


@dataclass(frozen=True)
class StateFrames:
    row: int
    frames: int
    fps: int


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
            states = {name: StateFrames(**spec) for name, spec in data["states"].items()}
            sheet = path.parent / data["sheet"]
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise SpriteError(f"Cannot read sprite frame-map {path}: {e}") from e
        for name in STATES:
            if name not in states:
                raise SpriteError(f"Sprite frame-map {path} has no '{name}' state.")
        return cls(sheet, (width, height), states)
