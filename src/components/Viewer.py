"""
3D Viewer for Simulation Data
"""

import json
import os
import queue
import socketserver
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8765
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT_DIR, "data")
MA_DATA_FILE = os.path.join(DATA_DIR, "ma_sim_data.json")
RSI_DATA_FILE = os.path.join(DATA_DIR, "rsi_sim_data.json")
TMPL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer_template.html")

_clients = []
_lock = threading.Lock()
_latest = {}
_template = ""
_current_strategy = "ma"
_current_data_file = MA_DATA_FILE

SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
    "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
    "CADJPY", "CADCHF", "CHFJPY", "NZDJPY", "NZDCAD",
]


def load_template():
    global _template
    with open(TMPL_FILE, "r", encoding="utf-8") as f:
        _template = f.read()


def broadcast(data: dict):
    global _latest
    _latest = data
    msg = ("data: " + json.dumps(data) + "\n\n").encode()
    with _lock:
        for q in list(_clients):
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass


def filter_data(data: dict) -> dict:
    if not data or "symbols" not in data:
        return data
    filtered = data.copy()
    filtered["symbols"] = SYMBOLS
    return filtered


def switch_strategy(strategy: str):
    global _current_strategy, _current_data_file, _latest
    _current_strategy = strategy
    _current_data_file = MA_DATA_FILE if strategy == "ma" else RSI_DATA_FILE
    
    if os.path.exists(_current_data_file):
        with open(_current_data_file, "r") as f:
            raw_data = json.load(f)
        _latest = filter_data(raw_data)
        broadcast(_latest)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = _template.replace("{{DATA_JSON}}", json.dumps(_latest))
            self._ok("text/html; charset=utf-8", html.encode())
        elif self.path == "/data":
            self._ok("application/json", json.dumps(_latest).encode())
        elif self.path == "/strategy":
            self._ok("application/json", json.dumps({
                "current": _current_strategy,
                "ma_available": os.path.exists(MA_DATA_FILE),
                "rsi_available": os.path.exists(RSI_DATA_FILE),
            }).encode())
        elif self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = queue.Queue(maxsize=20)
            with _lock:
                _clients.append(q)
            if _latest:
                self.wfile.write(("data: " + json.dumps(_latest) + "\n\n").encode())
            try:
                while True:
                    try:
                        msg = q.get(timeout=15)
                        self.wfile.write(msg)
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except:
                pass
            finally:
                with _lock:
                    if q in _clients:
                        _clients.remove(q)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/switch":
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length))
            strategy = data.get('strategy', 'ma')
            if strategy in ['ma', 'rsi']:
                switch_strategy(strategy)
                self._ok("application/json", json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def _ok(self, content_type: str, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def watch_file():
    last_mtime = 0
    while True:
        if os.path.exists(_current_data_file):
            mtime = os.path.getmtime(_current_data_file)
            if mtime > last_mtime:
                last_mtime = mtime
                with open(_current_data_file, "r") as f:
                    raw_data = json.load(f)
                _latest = filter_data(raw_data)
                broadcast(_latest)
        time.sleep(0.5)


def main():
    load_template()
    os.makedirs(DATA_DIR, exist_ok=True)
    
    threading.Thread(target=watch_file, daemon=True).start()
    
    server = socketserver.ThreadingTCPServer(("", PORT), Handler)
    url = f"http://localhost:{PORT}"
    
    print(f"\n  🚀 3D VIEWER → {url}")
    print(f"  📁 Data: {DATA_DIR}\n")
    
    threading.Timer(1.0, webbrowser.open, args=[url]).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Viewer stopped")


if __name__ == "__main__":
    main()