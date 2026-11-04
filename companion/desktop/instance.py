from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

NAME = "mochi-desktop"


def signal_running_instance(name: str = NAME) -> bool:
    """Ask an already-running Character to toggle its visibility; False if none is running."""
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(500):
        return False
    socket.write(b"toggle")
    socket.waitForBytesWritten(500)
    socket.disconnectFromServer()
    return True


class InstanceServer(QObject):
    toggled = Signal()

    def __init__(self, name: str = NAME):
        super().__init__()
        QLocalServer.removeServer(name)  # a stale socket from a crashed run
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept)
        if not self._server.listen(name):
            raise RuntimeError(f"Cannot listen on {name}: {self._server.errorString()}")

    def _accept(self) -> None:
        while socket := self._server.nextPendingConnection():
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(socket.deleteLater)
            if socket.bytesAvailable():
                self._read(socket)

    def _read(self, socket: QLocalSocket) -> None:
        if bytes(socket.readAll()).strip() == b"toggle":
            self.toggled.emit()
