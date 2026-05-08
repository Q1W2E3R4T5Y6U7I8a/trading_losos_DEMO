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
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
MA_DATA_FILE = os.path.join(DATA_DIR, "live_data.json")
RSI_DATA_FILE = os.path.join(DATA_DIR, "rsi_live_data.json")
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
    template_path = TMPL_FILE
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer_template.html")
    
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            _template = f.read()
    else:
        _template = """<!DOCTYPE html><html><head><title>Viewer</title></head><body><h1>Trading Viewer</h1><div id="data"></div><script>fetch('/data').then(r=>r.json()).then(d=>{document.getElementById('data').innerHTML=JSON.stringify(d);});</script></body></html>"""


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
    print(f"\n  🔄 Switched to {strategy.upper()} strategy")
    print(f"  📁 Reading from: {_current_data_file}")
    
    if os.path.exists(_current_data_file):
        try:
            with open(_current_data_file, "r") as f:
                raw_data = json.load(f)
            _latest = filter_data(raw_data)
            broadcast(_latest)
        except Exception as e:
            print(f"  Error loading {strategy} data: {e}")


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
            self.send_header("X-Accel-Buffering", "no")
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
        try:
            if os.path.exists(_current_data_file):
                mtime = os.path.getmtime(_current_data_file)
                if mtime > last_mtime:
                    # Read with retry for Windows locks
                    raw_data = None
                    for attempt in range(3):
                        try:
                            with open(_current_data_file, "r") as f:
                                raw_data = json.load(f)
                            break
                        except (PermissionError, json.JSONDecodeError):
                            time.sleep(0.05)
                    
                    if raw_data:
                        last_mtime = mtime
                        filtered = filter_data(raw_data)
                        _latest = filtered
                        broadcast(filtered)
                        
                        total = sum(filtered.get("profits", {}).values())
                        ts = datetime.now().strftime("%H:%M:%S")
                        print(f"\r  [VIEWER] {_current_strategy.upper()} TOTAL: ${total:+.2f}                    ", end="", flush=True)
        except:
            pass
        time.sleep(0.5)

def main():
    load_template()
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Start with MA strategy if available
    if os.path.exists(MA_DATA_FILE):
        switch_strategy("ma")
    elif os.path.exists(RSI_DATA_FILE):
        switch_strategy("rsi")
    
    threading.Thread(target=watch_file, daemon=True).start()
    
    # Try to bind to port, if fails try next port
    port = PORT
    server = None
    for attempt in range(5):
        try:
            server = socketserver.ThreadingTCPServer(("", port), Handler)
            break
        except OSError:
            print(f"  Port {port} in use, trying {port + 1}...")
            port += 1
    
    if server is None:
        print("  ❌ Could not find available port")
        return
    
    url = f"http://localhost:{port}"
    
    print(f"\n  🚀 3D VIEWER → {url}")
    print(f"  📁 MA data: {MA_DATA_FILE}")
    print(f"  📁 RSI data: {RSI_DATA_FILE}")
    print(f"  💡 Switch strategies using buttons in viewer\n")
    
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Viewer stopped")
        server.shutdown()


if __name__ == "__main__":
    main()