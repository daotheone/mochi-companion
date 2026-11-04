import json
import os
from dataclasses import dataclass
from pathlib import Path

from companion.desktop.placement import SavedPosition

DEFAULT_SIZE = 128
MIN_SIZE, MAX_SIZE = 64, 512


def default_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "mochi-companion" / "desktop.json"


@dataclass(frozen=True)
class DesktopSettings:
    position: SavedPosition | None = None
    size: int = DEFAULT_SIZE

    @classmethod
    def load(cls, path: Path | None = None) -> "DesktopSettings":
        try:
            data = json.loads((path or default_path()).read_text())
            size = data.get("size", DEFAULT_SIZE)
            if not isinstance(size, int) or isinstance(size, bool):
                size = DEFAULT_SIZE
            raw = data.get("position")
            position = None
            if isinstance(raw, dict):
                monitor, dx, dy = raw.get("monitor"), raw.get("dx"), raw.get("dy")
                if isinstance(monitor, str) and isinstance(dx, int) and isinstance(dy, int):
                    position = SavedPosition(monitor, dx, dy)
            return cls(position, max(MIN_SIZE, min(size, MAX_SIZE)))
        except (OSError, ValueError, AttributeError):
            return cls()

    def save(self, path: Path | None = None) -> None:
        path = path or default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        position = None
        if self.position:
            position = {"monitor": self.position.monitor, "dx": self.position.dx, "dy": self.position.dy}
        path.write_text(json.dumps({"size": self.size, "position": position}, indent=2))
