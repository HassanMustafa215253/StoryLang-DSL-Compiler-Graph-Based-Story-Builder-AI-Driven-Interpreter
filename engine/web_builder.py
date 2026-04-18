"""
Web-based StoryLang builder.
Serves a local graph-based builder UI and returns the resulting StoryLang source
back to the REPL.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from .display import Display


HTML_FILE = Path(__file__).with_suffix(".html")


class WebStoryBuilder:
    def __init__(self, display: Display):
        self.display = display

    def build_web(self, initial_source: str = "") -> Optional[str]:
        html = self._load_template().replace("__INITIAL_SOURCE_JSON__", json.dumps(initial_source))
        done = threading.Event()
        result = {"source": None, "cancelled": False}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def _send(self, code: int, body: str, content_type: str = "text/plain; charset=utf-8"):
                data = body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    self._send(200, html, "text/html; charset=utf-8")
                    return
                self._send(404, "Not found")

            def do_POST(self):
                if self.path not in ("/api/finish", "/api/cancel"):
                    self._send(404, "Not found")
                    return

                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    self._send(400, "Invalid JSON")
                    return

                if self.path == "/api/finish":
                    source = data.get("source", "")
                    if not isinstance(source, str):
                        self._send(400, "Invalid source")
                        return
                    result["source"] = source
                    result["cancelled"] = False
                    done.set()
                    self._send(200, "ok")
                    return

                result["source"] = None
                result["cancelled"] = True
                done.set()
                self._send(200, "ok")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        host = server.server_address[0]
        port = server.server_address[1]
        url = f"http://{host}:{port}/"

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        self.display.print_info("Opening web builder in your browser...")
        self.display.print_info("Use the Source tab to edit source directly, or the graph to edit scenes.")

        opened = webbrowser.open(url)
        if not opened:
            self.display.print_warning(f"Browser did not open automatically. Open this URL manually: {url}")

        try:
            done.wait()
        except KeyboardInterrupt:
            result["cancelled"] = True
            result["source"] = None
        finally:
            server.shutdown()
            server.server_close()

        if result["cancelled"]:
            self.display.print_info("Web builder cancelled.")
            return None

        source = result.get("source")
        return source.strip() if isinstance(source, str) else None

    def _load_template(self) -> str:
        if not HTML_FILE.exists():
            raise FileNotFoundError(f"Missing web builder UI file: {HTML_FILE}")
        return HTML_FILE.read_text(encoding="utf-8")
