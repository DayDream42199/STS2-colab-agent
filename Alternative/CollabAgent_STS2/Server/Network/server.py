import eventlet
eventlet.monkey_patch()

import queue

import greenlet
import socketio

from .enums import NetworkEvent

class Server:
    def __init__(self):
        self.sio = socketio.Server(async_mode="eventlet")
        self.app = socketio.WSGIApp(self.sio)

        self.thread = None
        self._eventlet_socket = None

        self.events = queue.Queue()

        self.sio.on("connect", self._on_connect)
        self.sio.on("disconnect", self._on_disconnect)
        self.sio.on("message", self._on_message)

    def start(self, host, port):
        if self.thread is not None:
            raise RuntimeError("Server is already running.")

        try:
            self._eventlet_socket = eventlet.listen((host, port))
        except OSError as error:
            self.events.put((NetworkEvent.START_FAILED, error))
            return

        self.thread = eventlet.spawn(self._run)

        self.events.put((NetworkEvent.SERVER_STARTED,))

    def _run(self):
        try:
            eventlet.wsgi.server(self._eventlet_socket, self.app, log_output=False)
        except greenlet.GreenletExit:
            raise
        except Exception as error:
            self.events.put((NetworkEvent.START_FAILED, error))
        finally:
            self.thread = None
            self._eventlet_socket = None

    def _on_connect(self, sid, environ):
        self.events.put((NetworkEvent.CLIENT_CONNECTED, sid))

    def _on_disconnect(self, sid):
        self.events.put((NetworkEvent.CLIENT_DISCONNECTED, sid))

    def _on_message(self, sid, data):
        self.events.put((NetworkEvent.MESSAGE_RECEIVED, sid, data))

    def send(self, sid, data):
        if self.thread is None:
            raise RuntimeError("Server is not running.")

        try:
            self.sio.emit("message", data, to=sid)
        except Exception as error:
            self.events.put((NetworkEvent.SEND_FAILED, error))

    def broadcast(self, data):
        if self.thread is None:
            raise RuntimeError("Server is not running.")

        try:
            self.sio.emit("message", data)
        except Exception as error:
            self.events.put((NetworkEvent.SEND_FAILED, error))

    def disconnect(self, sid):
        if self.thread is None:
            raise RuntimeError("Server is not running.")

        try:
            self.sio.disconnect(sid)
        except Exception as error:
            self.events.put((NetworkEvent.CLIENT_DISCONNECT_FAILED, error))

    def get_event(self):
        try:
            return self.events.get_nowait()
        except queue.Empty:
            return None

    def shutdown(self):
        if self.thread is None:
            return

        thread = self.thread
        thread.kill()
        try:
            thread.wait()
        except greenlet.GreenletExit:
            pass

        self.thread = None
        self._eventlet_socket = None