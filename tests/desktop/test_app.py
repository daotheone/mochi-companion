import os

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

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
    windows = (app.character, app.chatbox, app.balloon, app.main_window)
    for window in windows:
        window.close()
    worker.shutdown()
    # Destroy the Qt side now: left to the garbage collector, a window can die mid-paint and crash the run.
    for qt_object in (*windows, app.face, app):
        qt_object.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


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


def test_reply_stacks_bubbles_in_the_balloon(ui):
    ui.chatbox.submitted.emit("hi")
    QTest.qWait(50)
    assert ui.balloon.isVisible()
    assert ui.balloon._stack.count() == 2
    assert ui.face.expression == "neutral" and not ui.face.thinking


def test_provider_failure_shows_retry_and_a_neutral_face(ui):
    ui.provider.fail_with = "network down"
    ui.chatbox.submitted.emit("hi")
    assert ui.balloon.isVisible()
    assert ui.face.expression == "neutral" and not ui.face.thinking
    ui.provider.fail_with = None
    ui.balloon.retry_requested.emit()
    QTest.qWait(50)
    assert ui.balloon._stack.count() == 2


def reply_with(ui, text):
    ui.provider.replies = [text]
    ui.chatbox.submitted.emit("hi")
    QTest.qWait(20)
    ui.balloon.leaveEvent(None)  # offscreen, the balloon opens under the cursor and counts as hovered


def test_character_shows_the_expression_of_a_reply(ui):
    reply_with(ui, "[feel: smirk]\nlười vcl")
    assert ui.face.expression == "smirk"


def test_a_new_expression_replaces_the_last(ui):
    reply_with(ui, "[feel: smirk]\nlười vcl")
    reply_with(ui, "[feel: laugh]\nhaha")
    assert ui.face.expression == "laugh"


def test_expression_returns_to_neutral_when_the_balloon_starts_fading(ui):
    reply_with(ui, "[feel: angry]\ncút")
    ui.balloon._fade()
    assert ui.face.expression == "neutral"


def test_expression_waits_for_the_fade_and_the_chat_box_holds_it_off(ui):
    reply_with(ui, "[feel: angry]\ncút")
    assert ui.balloon._fade_timer.isActive()
    click(ui.character)
    reply_with(ui, "[feel: angry]\ncút")
    assert ui.face.expression == "angry"
    assert not ui.balloon._fade_timer.isActive()


def test_hover_rescue_does_not_bring_the_expression_back(ui):
    reply_with(ui, "[feel: angry]\ncút")
    ui.balloon._fade()
    ui.balloon.enterEvent(None)
    assert ui.face.expression == "neutral"


def test_thinking_replaces_the_current_expression(ui):
    reply_with(ui, "[feel: angry]\ncút")
    thinking = []
    ui.worker.state_changed.connect(lambda _: thinking.append(ui.face.thinking))
    reply_with(ui, "[feel: happy]\nok")
    assert thinking == [True]


def test_a_fade_left_over_from_the_last_reply_does_not_stop_the_thinking_dots(ui):
    reply_with(ui, "[feel: angry]\ncút")
    ui.balloon._fade_timer.setInterval(1)
    ui._on_worker_state("thinking")
    QTest.qWait(20)
    assert ui.face.thinking


def test_error_after_an_expression_shows_neutral(ui):
    reply_with(ui, "[feel: angry]\ncút")
    ui.provider.fail_with = "network down"
    ui.chatbox.submitted.emit("hi")
    assert ui.face.expression == "neutral"


def test_hiding_the_character_clears_the_expression(ui):
    reply_with(ui, "[feel: angry]\ncút")
    ui.hide_character()
    assert ui.face.expression == "neutral"


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


def test_recaps_view_lists_a_recap_after_a_conversation_ends_and_deletes_it(ui):
    ui.send_requested.emit("hi")
    ui.new_conversation_requested.emit()
    view = ui.main_window.recaps
    assert view._list.count() == 1
    assert not view._empty.isVisibleTo(view)

    view.delete_requested.emit(view._recaps[0].id)
    assert view._list.count() == 0
    assert view._empty.isVisibleTo(view)


def open_main(ui):
    ui.open_main_window()
    QTest.qWait(10)


def send_from_main(ui, text):
    ui.provider.replies = [text]
    ui.main_window.conversation.send_requested.emit("hi")
    QTest.qWait(20)


def notice_buttons(ui):
    return {b.text(): b for b in ui.main_window.conversation.findChildren(QPushButton) if b.text() in ("Retry", "Confirm", "Forget")}


def test_opening_the_main_window_replaces_the_character(ui):
    reply_with(ui, "hello")
    open_main(ui)
    assert not ui.character.isVisible() and not ui.balloon.isVisible()
    ui.main_window.close()
    QTest.qWait(10)
    assert ui.character.isVisible()


def test_minimising_the_main_window_brings_the_character_back(ui):
    open_main(ui)
    ui.main_window.showMinimized()
    QTest.qWait(10)
    assert ui.character.isVisible()
    ui.open_main_window()
    QTest.qWait(10)
    assert not ui.main_window.isMinimized() and not ui.character.isVisible()


def test_a_character_the_user_hid_stays_hidden_after_the_main_window_closes(ui):
    ui.hide_character()
    open_main(ui)
    ui.main_window.close()
    QTest.qWait(10)
    assert not ui.character.isVisible()


def test_toggling_while_the_main_window_is_open_never_shows_mochi_twice(ui):
    open_main(ui)
    ui.toggle_visibility()
    ui.toggle_visibility()
    assert not ui.character.isVisible()
    ui.main_window.close()
    QTest.qWait(10)
    assert ui.character.isVisible()


def test_reply_in_the_main_window_shows_no_balloon_and_lands_in_the_history(ui):
    open_main(ui)
    send_from_main(ui, "[feel: laugh]\nhaha")
    assert not ui.balloon.isVisible() and not ui.character.isVisible()
    assert ui.face.expression == "laugh"
    assert ui.main_window.conversation.messages()[-1].content == "haha"


def test_a_reply_after_the_main_window_closes_uses_the_balloon(ui):
    open_main(ui)
    ui.main_window.close()
    QTest.qWait(10)
    send_from_main(ui, "hello")
    assert ui.balloon.isVisible()


def test_portrait_is_native_size_and_redraws_with_the_face(ui):
    open_main(ui)
    portrait = ui.main_window.conversation.portrait
    assert (portrait.width(), portrait.height()) == (128, 128)
    before = portrait.grab().toImage()
    ui.face.set_expression("angry")
    assert portrait.grab().toImage() != before
    ui.face.set_thinking(True)
    assert portrait.grab().toImage() != before


def test_portrait_keeps_its_native_direction_when_the_character_is_mirrored(ui):
    open_main(ui)
    native = ui.main_window.conversation.portrait.grab().toImage()
    ui.character.set_facing("left")
    assert ui.main_window.conversation.portrait.grab().toImage() == native


def test_portrait_returns_to_neutral_after_the_hold(ui):
    open_main(ui)
    send_from_main(ui, "[feel: angry]\ncút")
    assert ui.face.expression == "angry"
    assert ui._expression_hold.interval() == 30_000
    ui._expression_hold.setInterval(1)
    ui._expression_hold.start()
    QTest.qWait(20)
    assert ui.face.expression == "neutral"


def test_an_expression_carried_into_the_main_window_still_returns_to_neutral(ui):
    click(ui.character)
    reply_with(ui, "[feel: angry]\ncút")
    ui._expression_hold.setInterval(1)
    open_main(ui)
    QTest.qWait(20)
    assert ui.face.expression == "neutral"


def test_the_hold_does_not_stop_the_thinking_dots(ui):
    open_main(ui)
    send_from_main(ui, "[feel: angry]\ncút")
    ui._expression_hold.setInterval(1)
    ui._expression_hold.start()
    ui._on_worker_state("thinking")
    QTest.qWait(20)
    assert ui.face.thinking


def test_failed_reply_offers_retry_in_the_conversation(ui):
    open_main(ui)
    ui.provider.fail_with = "network down"
    send_from_main(ui, "x")
    assert not ui.balloon.isVisible()
    ui.provider.fail_with = None
    ui.provider.replies = ["back"]
    notice_buttons(ui)["Retry"].click()
    QTest.qWait(20)
    assert ui.main_window.conversation.messages()[-1].content == "back"
    assert not notice_buttons(ui)


def test_retry_survives_opening_the_main_window_after_a_failure(ui):
    ui.provider.fail_with = "network down"
    ui.chatbox.submitted.emit("hi")
    open_main(ui)
    assert "Retry" in notice_buttons(ui)


NOTICING = "ô tốt\n[observe: tags=study | likes small steps]"


def test_noticed_memory_can_be_confirmed_from_the_conversation(ui):
    open_main(ui)
    send_from_main(ui, NOTICING)
    notice_buttons(ui)["Confirm"].click()
    QTest.qWait(20)
    assert [m.kind for m in ui.worker.companion.memories()] == ["stated"]
    assert not notice_buttons(ui)


def test_noticed_memory_can_be_forgotten_from_the_conversation(ui):
    open_main(ui)
    send_from_main(ui, NOTICING)
    notice_buttons(ui)["Forget"].click()
    QTest.qWait(20)
    assert ui.worker.companion.memories() == []


def test_unanswered_notice_leaves_on_the_next_message_and_stays_unconfirmed(ui):
    open_main(ui)
    send_from_main(ui, NOTICING)
    send_from_main(ui, "next")
    assert not notice_buttons(ui)
    assert [m.kind for m in ui.worker.companion.memories()] == ["observed"]


def test_layout_holds_at_the_minimum_window_size(ui):
    open_main(ui)
    window = ui.main_window
    window.resize(window.minimumSize())
    QTest.qWait(20)
    assert (window.width(), window.height()) == (640, 420)
    view = window.conversation
    bottom_right = view.portrait.mapTo(view, view.portrait.rect().bottomRight())
    assert view.rect().contains(bottom_right)
    assert view._input.x() > view.portrait.x()
    assert view._input.height() > 0 and view._scroll.height() > 60


def test_a_reply_still_revealing_does_not_bring_the_balloon_back_over_the_main_window(ui):
    ui.balloon._reveal.setInterval(10)
    ui.provider.replies = ["one\ntwo\nthree"]
    ui.chatbox.submitted.emit("hi")
    open_main(ui)
    QTest.qWait(60)
    assert not ui.balloon.isVisible()


def test_a_one_bubble_reply_notices_only_once(ui):
    from PySide6.QtWidgets import QLabel

    reply_with(ui, NOTICING)
    QTest.qWait(20)
    assert len([l for l in ui.balloon.findChildren(QLabel) if l.objectName() == "noticed"]) == 1


def test_a_hold_left_from_the_main_window_does_not_end_a_chat_box_expression(ui):
    open_main(ui)
    send_from_main(ui, "[feel: smirk]\nhi")
    ui.main_window.close()
    QTest.qWait(10)
    ui._expression_hold.setInterval(30)
    ui._expression_hold.start()
    click(ui.character)
    reply_with(ui, "[feel: angry]\ncút")
    QTest.qWait(60)
    assert ui.face.expression == "angry"


def test_toggling_with_the_main_window_open_leaves_the_portrait_expression(ui):
    open_main(ui)
    send_from_main(ui, "[feel: smirk]\nhi")
    ui.toggle_visibility()
    assert ui.face.expression == "smirk"


def test_opening_the_main_window_on_a_neutral_face_starts_no_hold(ui):
    open_main(ui)
    assert not ui._expression_hold.isActive()


def test_history_follows_new_messages(ui):
    ui.main_window.resize(ui.main_window.minimumSize())
    open_main(ui)
    bar = ui.main_window.conversation._scroll.verticalScrollBar()
    for i in range(8):
        send_from_main(ui, f"reply {i}\nsecond line\nthird line")
    QTest.qWait(30)
    assert bar.maximum() > 0
    assert bar.value() == bar.maximum()


def test_a_notice_is_scrolled_into_view(ui):
    ui.main_window.resize(ui.main_window.minimumSize())
    open_main(ui)
    for i in range(6):
        send_from_main(ui, f"reply {i}\nsecond line\nthird line")
    send_from_main(ui, NOTICING)
    QTest.qWait(30)
    bar = ui.main_window.conversation._scroll.verticalScrollBar()
    assert bar.value() == bar.maximum()


def test_reading_back_is_not_interrupted_by_resizing(ui):
    ui.main_window.resize(ui.main_window.minimumSize())
    open_main(ui)
    for i in range(8):
        send_from_main(ui, f"reply {i}\nsecond line\nthird line")
    QTest.qWait(30)
    bar = ui.main_window.conversation._scroll.verticalScrollBar()
    bar.setValue(0)
    ui.main_window.resize(700, 460)
    QTest.qWait(30)
    assert bar.value() == 0


def test_sidebar_collapses_and_comes_back(ui):
    open_main(ui)
    window = ui.main_window
    wide = window.conversation.width()
    window.sidebar_toggle.click()
    QTest.qWait(20)
    assert not any(b.isVisible() for b in window.nav_buttons)
    assert window.sidebar_toggle.isVisible()
    assert window.conversation.width() > wide
    window.sidebar_toggle.click()
    QTest.qWait(20)
    assert all(b.isVisible() for b in window.nav_buttons)
    assert window.conversation.width() == wide


def test_collapsing_the_sidebar_keeps_the_current_page(ui):
    open_main(ui)
    window = ui.main_window
    window.nav_buttons[1].click()
    window.sidebar_toggle.click()
    QTest.qWait(20)
    assert window.memories.isVisible()


LONG_TEXT = "Người dùng thức khuya trò chuyện với Mochi và đùa về việc sẽ bị bỏ rơi. " * 12


def show_long_page(ui, nav_index):
    from datetime import datetime

    from companion.store import Memory, Recap

    window = ui.main_window
    open_main(ui)
    window.resize(860, 580)
    window.recaps.show_recaps([Recap(i, i, "character", LONG_TEXT, False, datetime.now(), datetime.now()) for i in range(6)])
    window.memories.show_memories([Memory(i, LONG_TEXT, (), "stated") for i in range(6)])
    window.nav_buttons[nav_index].click()
    QTest.qWait(30)
    return window.recaps._list if nav_index == 3 else window.memories._list


def assert_wraps_inside(view):
    assert not view.horizontalScrollBar().isVisible()
    assert view.horizontalScrollBar().maximum() == 0


@pytest.mark.parametrize("nav_index", [1, 3], ids=["memories", "recaps"])
def test_long_text_wraps_to_the_list_at_any_width(ui, nav_index):
    view = show_long_page(ui, nav_index)
    assert_wraps_inside(view)
    tall = view.visualItemRect(view.item(0)).height()
    ui.main_window.resize(640, 420)
    QTest.qWait(30)
    assert_wraps_inside(view)
    assert view.visualItemRect(view.item(0)).height() > tall
