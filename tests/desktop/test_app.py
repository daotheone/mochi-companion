import os

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from companion.companion import Companion
from companion.desktop import balloon as balloon_module
from companion.desktop.app import DesktopApp
from companion.desktop.settings import DesktopSettings
from companion.desktop.worker import Worker
from companion.fake_provider import FakeProvider
from companion.store import Store


@pytest.fixture
def ui(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(balloon_module, "BUBBLE_DELAY_MS", 1)
    provider = FakeProvider(["one\ntwo"])

    def factory():
        store = Store(tmp_path / "m.db")
        return Companion(store, provider, "P", interface="character", resume=False), store

    worker = Worker(factory)
    worker.start()
    app = DesktopApp(DesktopSettings(), worker)
    app.provider = provider
    app.show_character()
    yield app
    for window in (app.character, app.chatbox, app.balloon, app.main_window):
        window.close()
    worker.shutdown()


def click(window, pos=QPoint(64, 100)):
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=pos)


def test_click_toggles_the_chat_box_and_pins_the_balloon(ui):
    click(ui.character)
    assert ui.chatbox.isVisible()
    click(ui.character)
    assert not ui.chatbox.isVisible()


def test_drag_is_not_a_click_and_saves_the_position(ui, tmp_path):
    start = ui.character.pos()
    QTest.mousePress(ui.character, Qt.MouseButton.LeftButton, pos=QPoint(64, 100))
    QTest.mouseMove(ui.character, QPoint(30, 100))
    QTest.mouseRelease(ui.character, Qt.MouseButton.LeftButton, pos=QPoint(30, 100))
    assert not ui.chatbox.isVisible()
    assert ui.character.pos() != start
    assert (tmp_path / "config" / "mochi-companion" / "desktop.json").is_file()


def test_double_click_closes_chat_box_and_opens_main_window(ui):
    click(ui.character)
    QTest.mouseDClick(ui.character, Qt.MouseButton.LeftButton, pos=QPoint(64, 100))
    assert not ui.chatbox.isVisible()
    assert ui.main_window.isVisible()


def test_reply_stacks_bubbles_in_the_balloon_and_returns_to_idle(ui):
    ui.chatbox.submitted.emit("hi")
    QTest.qWait(50)
    assert ui.balloon.isVisible()
    assert ui.balloon._stack.count() == 2
    assert ui.character.state == "idle"


def test_provider_failure_shows_retry_and_returns_to_idle(ui):
    ui.provider.fail_with = "network down"
    ui.chatbox.submitted.emit("hi")
    assert ui.balloon.isVisible()
    assert ui.character.state == "idle"
    ui.provider.fail_with = None
    ui.balloon.retry_requested.emit()
    QTest.qWait(50)
    assert ui.balloon._stack.count() == 2


def test_hide_and_toggle_visibility(ui):
    ui.toggle_visibility()
    assert not ui.character.isVisible()
    ui.toggle_visibility()
    assert ui.character.isVisible()


def test_wrapped_bubbles_do_not_overlap(ui):
    from PySide6.QtWidgets import QLabel
    ui.balloon.show_reply(["dài " * 40, "dài " * 40], None)
    QTest.qWait(50)
    labels = sorted(ui.balloon.findChildren(QLabel), key=lambda l: l.y())
    assert len(labels) == 2
    assert labels[0].y() + labels[0].height() <= labels[1].y()
    assert labels[1].y() + labels[1].height() <= ui.balloon.height()


def test_chat_box_is_as_wide_as_the_sprite(ui):
    assert ui.chatbox.width() == ui.character.width()


def test_character_mirrors_on_the_far_side_of_the_screen(ui):
    ui.character.move(0, 100)
    ui._face_screen_centre()
    assert ui.character._facing == "right"
    ui.character.move(ui.character.screen().geometry().width() - 130, 100)
    ui._face_screen_centre()
    assert ui.character._facing == "left"


def test_vietnamese_bubbles_fit_inside_the_balloon(ui):
    from PySide6.QtWidgets import QLabel
    text = "vừa hong quần vừa hong mắt, nói chung là đi đi nhanh lên không là mưa đó nha"
    ui.balloon.show_reply([text, text], None)
    QTest.qWait(50)
    for label in ui.balloon.findChildren(QLabel):
        assert label.height() >= label.heightForWidth(label.width())
        assert label.y() + label.height() <= ui.balloon.height()
