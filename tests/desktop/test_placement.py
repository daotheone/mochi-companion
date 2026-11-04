from companion.desktop.placement import (
    Screen, SavedPosition, balloon_side, place, save_position,
)

LEFT = Screen("DP-1", 0, 0, 1920, 1080)
RIGHT = Screen("HDMI-1", 1920, 0, 1920, 1080)
SIZE = 128


def test_saved_position_is_restored_on_its_monitor():
    assert place(SavedPosition("HDMI-1", 100, 200), [LEFT, RIGHT], LEFT, SIZE) == (2020, 200)


def test_missing_monitor_clamps_to_primary_and_saved_spot_returns_with_it():
    saved = SavedPosition("HDMI-1", 1900, 1000)
    assert place(saved, [LEFT], LEFT, SIZE) == (1920 - SIZE, 1080 - SIZE)
    assert place(saved, [LEFT, RIGHT], LEFT, SIZE) == (1920 + 1792, 952)


def test_no_saved_position_starts_bottom_right_of_primary():
    assert place(None, [LEFT, RIGHT], LEFT, SIZE) == (1920 - SIZE, 1080 - SIZE)


def test_save_position_records_monitor_name_and_offset():
    assert save_position(2020, 200, SIZE, [LEFT, RIGHT]) == SavedPosition("HDMI-1", 100, 200)


def test_balloon_opens_right_unless_it_would_leave_the_screen():
    assert balloon_side(100, SIZE, 260, LEFT) == "right"
    assert balloon_side(1700, SIZE, 260, LEFT) == "left"


def test_character_looks_towards_the_middle_of_the_screen():
    from companion.desktop.placement import facing
    assert facing(100, SIZE, LEFT) == "right"
    assert facing(1700, SIZE, LEFT) == "left"
    assert facing(1920 + 1700, SIZE, RIGHT) == "left"
