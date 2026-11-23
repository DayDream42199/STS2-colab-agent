"""The browser page for playtest.py: click instead of type. Python's standard library only, and only on this computer.

The game runs as it does in the terminal. Where it would wait for typed input it waits for the page instead, and the page sends
the same answers a person would type ("3a", "w", "e"), so saving, --resume and the results don't change. What the terminal would
print goes to the page's list of what happened.
"""
import json
import os
import queue
import re
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest_ui.html")
KEEP_LINES = 400


class Feed:
    """Stands in for sys.stdout: complete lines go to the page."""

    def __init__(self, ui):
        self.ui, self.partial = ui, ""

    def write(self, text):
        self.partial += text
        while "\n" in self.partial:
            line, self.partial = self.partial.split("\n", 1)
            self.ui.add_line(line)
        return len(text)

    def flush(self):
        pass


class PlayUI:
    def __init__(self, resume_line, open_browser=True):
        self.cv = threading.Condition()
        self.answers = queue.Queue()
        self.token = secrets.token_urlsafe(16)
        self.open_browser = open_browser
        self.seq = 0
        self.total = 0                  # lines so far, including any no longer kept
        self.state = dict(tick=0, heading="", table=None, prompt=None, lines=[], total=0, notice="", done=False, resume=resume_line)
        self.real_stdout = None
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.server.daemon_threads = True
        self.server.handle_error = lambda *_: None      # a tab closed or reloaded mid-request is nothing to report
        self.url =f"http://127.0.0.1:{self.server.server_address[1]}/?t={self.token}"

    # ------------------------------------------------------------ the game's side
    def start(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        print(f"The game opens in your browser. If it doesn't, go to:\n  {self.url}\nKeep this window open while you play. Closing it stops the game, and your place stays saved.", flush=True)
        self.real_stdout, sys.stdout = sys.stdout, Feed(self)
        if self.open_browser:
            webbrowser.open(self.url)

    def finish(self):
        """The page gets a moment to read the last state, then everything stops."""
        sys.stdout.flush()
        self._change(done=True, prompt=None)
        time.sleep(1.5)
        sys.stdout = self.real_stdout
        self.server.shutdown()

    def _change(self, **changes):
        with self.cv:
            self.state.update(changes)
            self.state["tick"] += 1
            self.cv.notify_all()

    def add_line(self, line):
        line = line.strip()
        if line:
            with self.cv:
                self.total += 1
                lines = (self.state["lines"] + [line])[-KEEP_LINES:]
            self._change(lines=lines, total=self.total)

    def notice(self, text):
        old = self.state["notice"]
        self._change(notice=f"{old}\n{text}" if old else text)

    def clear_notice(self):
        if self.state["notice"]:
            self._change(notice="")

    def show_table(self, table):
        self._change(table=table)

    def set_heading(self, text):
        self._change(heading=text)

    def read(self, prompt, options, labels=None):
        """Waits for the page's answer. A timed wait, so Ctrl+C in the terminal still gets through."""
        partial, sys.stdout.partial = sys.stdout.partial, ""
        if partial.strip():
            self.add_line(partial)
        clean = prompt.strip()
        skip = "skip" in clean
        clean = re.sub(r"\s*\((?:y/n|1-5|[^)]*skip[^)]*)\)\s*:?\s*$", "", clean)
        with self.cv:
            self.seq += 1
            seq = self.seq
        self._change(prompt=dict(seq=seq, kind="move" if clean.startswith("Your move") else "question", text=clean, options=list(options), labels=labels or {}, skip=skip))
        while True:
            try:
                got_seq, text = self.answers.get(timeout=.25)
            except queue.Empty:
                continue
            if got_seq == seq:
                self.clear_notice()
                return text

    # ------------------------------------------------------------ the page's side
    def _handler(self):
        ui = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def _send(self, code, body=b"", kind="application/json"):
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                url = urlparse(self.path)
                query = parse_qs(url.query)
                if url.path == "/favicon.ico":
                    return self._send(204)
                if query.get("t", [""])[0] != ui.token:
                    return self._send(403, b"This page needs the address shown in the game's window.", "text/plain")
                if url.path == "/":
                    with open(PAGE, "rb") as f:
                        return self._send(200, f.read(), "text/html; charset=utf-8")
                if url.path == "/state":
                    since = int(query.get("since", ["-1"])[0])
                    with ui.cv:
                        ui.cv.wait_for(lambda: ui.state["tick"] != since, timeout=15)
                        body = json.dumps(ui.state).encode()
                    return self._send(200, body)
                return self._send(404)

            def do_POST(self):
                if self.path != "/answer" or self.headers.get("X-Token") != ui.token:
                    return self._send(403)
                row = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 20000)))
                with ui.cv:
                    current = ui.state["prompt"]
                    fresh = current is not None and current["seq"] == row.get("seq")
                if fresh:                       # a double click, or a second tab, doesn't answer twice
                    ui._change(prompt=None)
                    ui.answers.put((row["seq"], str(row.get("text", ""))))
                return self._send(200, b'{"ok": %s}' % (b"true" if fresh else b"false"))

        return Handler
