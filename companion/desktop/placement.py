from dataclasses import dataclass


@dataclass(frozen=True)
class Screen:
    name: str
    x: int
    y: int
    width: int
    height: int

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.width and self.y <= py < self.y + self.height


@dataclass(frozen=True)
class SavedPosition:
    monitor: str
    dx: int
    dy: int


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def _inside(screen: Screen, dx: int, dy: int, size: int) -> tuple[int, int]:
    return (
        screen.x + _clamp(dx, 0, screen.width - size),
        screen.y + _clamp(dy, 0, screen.height - size),
    )


def place(saved: SavedPosition | None, screens: list[Screen], primary: Screen, size: int) -> tuple[int, int]:
    """Where to put the Character. A missing monitor falls back to the primary one, unsaved."""
    if saved is None:
        return _inside(primary, primary.width, primary.height, size)
    screen = next((s for s in screens if s.name == saved.monitor), primary)
    return _inside(screen, saved.dx, saved.dy, size)


def save_position(x: int, y: int, size: int, screens: list[Screen]) -> SavedPosition | None:
    """Monitor name plus offset for the monitor holding the Character's centre."""
    centre = (x + size // 2, y + size // 2)
    screen = next((s for s in screens if s.contains(*centre)), None)
    return None if screen is None else SavedPosition(screen.name, x - screen.x, y - screen.y)


def facing(x: int, size: int, screen: Screen) -> str:
    """Look towards the middle of the screen: left from the right half, right from the left half."""
    return "left" if x + size // 2 > screen.x + screen.width // 2 else "right"


def balloon_side(x: int, size: int, balloon_width: int, screen: Screen) -> str:
    """Open beside the Character on whichever side has room, preferring the right."""
    return "right" if x + size + balloon_width <= screen.x + screen.width else "left"
