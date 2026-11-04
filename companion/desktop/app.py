import os
import sys
from functools import partial

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from companion.app import build_companion
from companion.desktop import placement
from companion.desktop.balloon import SpeechBalloon
from companion.desktop.chatbox import ChatBox
from companion.desktop.character import CharacterWindow
from companion.desktop.instance import InstanceServer, signal_running_instance
from companion.desktop.mainwindow import MainWindow
from companion.desktop.settings import DesktopSettings
from companion.desktop.sprites import load_frame_map
from companion.desktop.worker import Worker

GAP = 6


def _screens() -> tuple[list[placement.Screen], placement.Screen]:
    def convert(s) -> placement.Screen:
        g = s.geometry()
        return placement.Screen(s.name(), g.x(), g.y(), g.width(), g.height())

    screens = [convert(s) for s in QGuiApplication.screens()]
    primary = convert(QGuiApplication.primaryScreen())
    return screens, primary


class DesktopApp(QObject):
    """Wires the Character, Chat Box, Speech Balloon and Main Window to the worker thread."""

    # UI -> worker. Emitted here so the slots run on the worker's thread.
    send_requested = Signal(str)
    retry_requested = Signal()
    new_conversation_requested = Signal()
    shutdown_requested = Signal()

    def __init__(self, settings: DesktopSettings, worker: Worker):
        super().__init__()
        self.settings = settings
        self.worker = worker
        self.character = CharacterWindow(load_frame_map(), settings.size)
        self.chatbox = ChatBox(settings.size)
        self.balloon = SpeechBalloon()
        self.main_window = MainWindow()
        self._busy = False
        self._wire()

    def _wire(self) -> None:
        w, c, b, m = self.worker, self.character, self.balloon, self.main_window
        # window -> worker
        for source in (self.chatbox.submitted, m.conversation.send_requested):
            source.connect(self.send_requested)
        self.send_requested.connect(w.send)
        self.retry_requested.connect(w.retry)
        self.new_conversation_requested.connect(w.new_conversation)
        self.shutdown_requested.connect(w.shutdown)
        b.retry_requested.connect(self.retry_requested)
        m.conversation.new_requested.connect(self.new_conversation_requested)
        b.confirm_requested.connect(w.confirm_memory)
        b.forget_requested.connect(w.forget_memory)
        m.memories.add_requested.connect(w.add_memory)
        m.memories.edit_requested.connect(w.edit_memory)
        m.memories.tags_requested.connect(w.set_memory_tags)
        m.memories.confirm_requested.connect(w.confirm_memory)
        m.memories.forget_requested.connect(w.forget_memory)
        # worker -> windows
        w.state_changed.connect(self._on_worker_state)
        w.replied.connect(self._on_reply)
        w.failed.connect(self._on_failure)
        w.conversation_changed.connect(m.conversation.show_messages)
        w.memories_changed.connect(m.memories.show_memories)
        # character interaction
        c.clicked.connect(self.toggle_chatbox)
        c.double_clicked.connect(self.open_main_window)
        c.moving.connect(self._face_screen_centre)
        c.moved_by_user.connect(self._on_moved)
        c.hide_requested.connect(self.hide_character)
        c.quit_requested.connect(QApplication.quit)
        self.chatbox.closed.connect(lambda: b.set_pinned(False))
        b.resized.connect(self._place_balloon)

    # --- state ---
    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.chatbox.set_busy(busy)
        self.main_window.conversation.set_busy(busy)

    def _on_worker_state(self, state: str) -> None:
        if state == "thinking":
            self._set_busy(True)
            self.balloon.hide()
            self.character.set_state("thinking")
        else:
            self._set_busy(False)
            self.character.set_state("idle")

    def _on_reply(self, bubbles: list, noticed) -> None:
        self._set_busy(False)
        self.character.set_state("idle")
        self.balloon.show_reply(bubbles, noticed)

    def _on_failure(self, message: str) -> None:
        self.balloon.show_error(message)

    # --- placement ---
    def _current_screen(self) -> placement.Screen:
        screens, primary = _screens()
        centre = self.character.geometry().center()
        return next((s for s in screens if s.contains(centre.x(), centre.y())), primary)

    def place_character(self) -> None:
        screens, primary = _screens()
        x, y = placement.place(self.settings.position, screens, primary, self.settings.size)
        self.character.move(x, y)
        self._face_screen_centre()

    def _face_screen_centre(self) -> None:
        screen, geo = self._current_screen(), self.character.geometry()
        self.character.set_facing(placement.facing(geo.x(), geo.width(), screen))

    def _on_moved(self) -> None:
        screens, _ = _screens()
        pos = self.character.pos()
        saved = placement.save_position(pos.x(), pos.y(), self.settings.size, screens)
        if saved:
            self.settings = DesktopSettings(saved, self.settings.size)
            self.settings.save()
        self._place_balloon()
        if self.chatbox.isVisible():
            self._place_chatbox()

    def _place_balloon(self) -> None:
        if not self.balloon.isVisible():
            return
        screen, geo = self._current_screen(), self.character.geometry()
        side = placement.balloon_side(geo.x(), geo.width(), self.balloon.width(), screen)
        x = geo.right() + GAP if side == "right" else geo.x() - self.balloon.width() - GAP
        bottom = screen.y + screen.height
        y = max(screen.y, min(geo.y(), bottom - self.balloon.height()))
        self.balloon.move(x, y)

    def _place_chatbox(self) -> None:
        screen, geo = self._current_screen(), self.character.geometry()
        below = geo.bottom() + GAP
        y = below if below + self.chatbox.height() <= screen.y + screen.height else geo.y() - self.chatbox.height() - GAP
        x = max(screen.x, min(geo.x(), screen.x + screen.width - self.chatbox.width()))
        self.chatbox.move(x, y)

    # --- actions ---
    def toggle_chatbox(self) -> None:
        if self.chatbox.isVisible():
            self.chatbox.close()
            return
        self.chatbox.show()  # sized before placing
        self._place_chatbox()
        self.chatbox.open_at(self.chatbox.x(), self.chatbox.y())
        self.balloon.set_pinned(True)

    def open_main_window(self) -> None:
        self.chatbox.close()
        self.main_window.open()

    def hide_character(self) -> None:
        self.chatbox.close()
        self.balloon.hide()
        self.character.hide()

    def show_character(self) -> None:
        self.place_character()
        self.character.show()

    def toggle_visibility(self) -> None:
        if self.character.isVisible():
            self.hide_character()
        else:
            self.show_character()


def main() -> None:
    # ADR 0001: native Wayland cannot place or raise windows, so run through XWayland.
    os.environ["QT_QPA_PLATFORM"] = "xcb"
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("mochi-desktop")
    if signal_running_instance():
        return

    # Fail on the main thread, where a bad setup can still exit with its message.
    companion, store = build_companion("character", resume=False)
    store.close()
    thread = QThread()
    worker = Worker(partial(build_companion, "character", False))
    worker.moveToThread(thread)
    thread.started.connect(worker.start)
    ui = DesktopApp(DesktopSettings.load(), worker)
    server = InstanceServer()
    server.toggled.connect(ui.toggle_visibility)

    def stop() -> None:
        ui.shutdown_requested.emit()
        thread.quit()
        thread.wait(5000)

    app.aboutToQuit.connect(stop)
    thread.start()
    ui.show_character()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
