"""FM1828 lidar GUI: local web server showing the live scan and an occupancy-grid map.

Usage:
  python fm1828_gui.py --port /dev/cu.usbserial-10          # live through the ESP32 bridge
  python fm1828_gui.py --replay ../captures/fm1828-spin-15s.bin
Then open http://127.0.0.1:8765 in a browser.
"""
import argparse
import base64
import json
import os
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fm1828 import FM1828, SerialSource, ReplaySource

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, 'static')


class Hub:
    def __init__(self):
        self.clients = []
        self.lock = threading.Lock()

    def subscribe(self):
        q = queue.Queue(maxsize=20)
        with self.lock:
            self.clients.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)

    def publish(self, msg: str):
        with self.lock:
            for q in list(self.clients):
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    pass  # slow client: drop scan


hub = Hub()
lidar = None
snapshot_dir = None
source_name = ''
started_at = time.time()


def on_scan(scan):
    msg = json.dumps({
        't': round(time.time(), 3), 'speed': scan.speed, 'frames': scan.frames, 'missing': scan.missing_frames,
        'a': [round(a, 2) for a, _ in scan.points], 'd': [d for _, d in scan.points],
    }, separators=(',', ':'))
    hub.publish(msg)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet
        pass

    def handle(self):  # browser reloads reset SSE connections; that is not an error worth a traceback
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError):
            pass

    def _send(self, code, body, ctype='application/json'):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            with open(os.path.join(STATIC, 'index.html'), 'rb') as f:
                return self._send(200, f.read(), 'text/html')
        if self.path == '/api/status':
            st = lidar.status()
            st.update({'source': source_name, 'uptime': round(time.time() - started_at, 1)})
            return self._send(200, json.dumps(st))
        if self.path == '/events':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            q = hub.subscribe()
            try:
                while True:
                    try:
                        msg = q.get(timeout=1.0)
                        self.wfile.write(f'data: {msg}\n\n'.encode())
                    except queue.Empty:
                        self.wfile.write(b': ping\n\n')
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                hub.unsubscribe(q)
            return
        self._send(404, '{"error":"not found"}')

    def do_POST(self):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length else b''
        if self.path != '/api/snapshot':
            print(time.strftime('%H:%M:%S'), 'POST', self.path, body[:80].decode('utf-8', 'replace'), 'from', self.client_address[0], flush=True)
        if self.path == '/api/start':
            threading.Thread(target=lidar.start_motor, daemon=True).start()
            return self._send(200, '{"ok":true,"note":"$ sent, startlds$ follows in 2 s"}')
        if self.path == '/api/stop':
            lidar.stop_motor()
            return self._send(200, '{"ok":true}')
        if self.path == '/api/restart':
            threading.Thread(target=lidar.restart, daemon=True).start()
            return self._send(200, '{"ok":true,"note":"stoplds$ then startldspl$"}')
        if self.path == '/api/snapshot':
            if not snapshot_dir:
                return self._send(400, '{"error":"start the server with --snapshot-dir"}')
            try:
                data = json.loads(body or b'{}')
                os.makedirs(snapshot_dir, exist_ok=True)
                files = []
                stamp = time.strftime('%Y%m%d-%H%M%S')
                for key in ('scan', 'map'):
                    url = data.get(key, '')
                    if not url.startswith('data:image/png;base64,'):
                        continue
                    name = f'{key}-{stamp}.png'
                    with open(os.path.join(snapshot_dir, name), 'wb') as f:
                        f.write(base64.b64decode(url.split(',', 1)[1]))
                    files.append(name)
                return self._send(200, json.dumps({'ok': True, 'files': files}))
            except Exception as e:
                return self._send(400, json.dumps({'error': str(e)}))
        if self.path == '/api/raw':
            try:
                data = json.loads(body or b'{}').get('data', '')
                lidar.send_raw(data.encode('latin-1'))
                return self._send(200, '{"ok":true}')
            except Exception as e:
                return self._send(400, json.dumps({'error': str(e)}))
        self._send(404, '{"error":"not found"}')


def main():
    global lidar, source_name, snapshot_dir
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--port', help='serial port of the ESP32 bridge, e.g. /dev/cu.usbserial-10')
    p.add_argument('--replay', help='raw capture file to replay instead of live hardware')
    p.add_argument('--http-port', type=int, default=8765)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--autostart', action='store_true', help='send the start sequence on launch')
    p.add_argument('--snapshot-dir', help='directory for PNG snapshots saved by the "Сохранить PNG" button')
    a = p.parse_args()
    if not a.port and not a.replay:
        p.error('need --port or --replay')
    snapshot_dir = a.snapshot_dir
    src = ReplaySource(a.replay) if a.replay else SerialSource(a.port)
    source_name = ('replay ' + os.path.basename(a.replay)) if a.replay else a.port
    lidar = FM1828(src, on_scan)
    lidar.open()
    if a.autostart or a.replay:
        threading.Thread(target=lidar.start_motor, daemon=True).start()
    srv = ThreadingHTTPServer((a.host, a.http_port), Handler)
    srv.daemon_threads = True
    print(f'FM1828 GUI: http://{a.host}:{a.http_port}  source={source_name}', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        lidar.close()


if __name__ == '__main__':
    main()
