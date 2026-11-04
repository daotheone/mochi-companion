from companion.desktop.placement import SavedPosition
from companion.desktop.settings import DEFAULT_SIZE, DesktopSettings


def test_round_trip(tmp_path):
    path = tmp_path / "mochi-companion" / "desktop.json"
    DesktopSettings(SavedPosition("DP-1", 5, 6), 160).save(path)
    assert DesktopSettings.load(path) == DesktopSettings(SavedPosition("DP-1", 5, 6), 160)


def test_missing_or_broken_file_gives_defaults(tmp_path):
    path = tmp_path / "desktop.json"
    assert DesktopSettings.load(path) == DesktopSettings(None, DEFAULT_SIZE)
    path.write_text("{not json")
    assert DesktopSettings.load(path) == DesktopSettings(None, DEFAULT_SIZE)
    path.write_text('{"size": "huge", "position": {"monitor": 3}}')
    assert DesktopSettings.load(path) == DesktopSettings(None, DEFAULT_SIZE)
