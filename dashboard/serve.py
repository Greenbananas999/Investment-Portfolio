"""Serve the built site with Python's built-in http.server (no installs)."""

import functools
import http.server
import socketserver
import threading
import webbrowser
from pathlib import Path


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):   # keep the console readable
        pass


def serve(site, port=8000, open_browser=False):
    site = Path(site)
    handler = functools.partial(QuietHandler, directory=str(site))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://localhost:{port}/"
        print(f"Serving {site} at {url}  (Ctrl+C to stop)")
        if open_browser:
            threading.Timer(0.5, webbrowser.open, args=(url,)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
