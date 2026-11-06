import pytest
from PySide6.QtCore import QSize

from companion.desktop.face import Face
from companion.desktop.sprites import FrameMap

SIZE = QSize(128, 128)


@pytest.fixture
def face(qapp):
    return Face(FrameMap.load())


def changed_columns(a, b):
    a, b = a.toImage(), b.toImage()
    return [x for x in range(a.width()) for y in range(a.height()) if a.pixel(x, y) != b.pixel(x, y)]


def test_each_expression_is_a_different_picture(face):
    pictures = []
    for name in ("neutral", "smirk", "angry"):
        face.set_expression(name)
        pictures.append(face.pixmap(SIZE, False).toImage())
    assert pictures[0] != pictures[1] != pictures[2]


def test_thinking_replaces_the_expression_and_stopping_leaves_neutral(face):
    face.set_expression("angry")
    face.set_thinking(True)
    assert face.thinking and face.expression == "neutral"
    face.set_thinking(False)
    assert not face.thinking and face.expression == "neutral"


def test_setting_an_expression_ends_thinking(face):
    face.set_thinking(True)
    face.set_expression("laugh")
    assert not face.thinking and face.expression == "laugh"


def test_changes_are_announced(face):
    seen = []
    face.changed.connect(lambda: seen.append(1))
    face.set_expression("sad")
    face.set_expression("sad")
    assert len(seen) == 1


@pytest.mark.parametrize("mirrored", [False, True])
def test_dots_fill_one_at_a_time_from_the_left_whichever_way_she_faces(face, mirrored):
    plain = face.pixmap(SIZE, mirrored)
    face.set_thinking(True)
    one = changed_columns(plain, face.pixmap(SIZE, mirrored))
    face.tick()
    two = changed_columns(plain, face.pixmap(SIZE, mirrored))
    face.tick()
    three = changed_columns(plain, face.pixmap(SIZE, mirrored))
    assert one and max(one) < max(two) < max(three)
    assert min(one) == min(two) == min(three)
    face.tick()
    assert changed_columns(plain, face.pixmap(SIZE, mirrored)) == one
