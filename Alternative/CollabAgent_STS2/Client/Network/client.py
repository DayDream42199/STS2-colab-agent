import threading
import queue

import socketio

from .enums import NetworkEvent

class Client:
    def __init__(self):
        self.sio = socketio.Client()
        self.connected = False

        self.events = queue.Queue()

        self.sio.on("connect", self._on_connect)
        self.sio.on("disconnect", self._on_disconnect)
        self.sio.on("message", self._on_message)

    def connect(self, host, port):
        if self.connected:
            raise RuntimeError("Client is already connected.")

        try:
            self.sio.connect(f"http://{host}:{port}")
        except Exception as error:
            self.events.put((NetworkEvent.CONNECTION_FAILED, error))
            return

    def _on_connect(self):
        self.connected = True
        self.events.put((NetworkEvent.CONNECTED,))

    def _on_disconnect(self):
        self.connected = False
        self.events.put((NetworkEvent.DISCONNECTED,))

    def _on_message(self, data):
        self.events.put((NetworkEvent.MESSAGE_RECEIVED, data))

    def send(self, data):
        if not self.connected:
            raise RuntimeError("Client is not connected.")

        try:
            self.sio.emit("message", data)
        except Exception as error:
            self.events.put((NetworkEvent.SEND_FAILED, error))

    def disconnect(self):
        if not self.connected:
            raise RuntimeError("Client is not connected.")

        self.sio.disconnect()

    def get_event(self):
        try:
            return self.events.get_nowait()
        except queue.Empty:
            return None