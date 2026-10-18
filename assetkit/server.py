"""Локальная студия: та же страница, что на GitHub Pages, но считает «родной» Python — быстрее и без ограничений браузера.
Слушает только этот компьютер (127.0.0.1)."""
import base64, json, os, threading, webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from . import api

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = threading.Lock()

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith('/api/ping'): return self._json(200, {'ok': True, 'engine': 'native'})
        return super().do_GET()
    def do_POST(self):
        if not self.path.startswith('/api/call'): return self._json(404, {'error': 'нет такого адреса'})
        try:
            d = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            blobs = [base64.b64decode(x) for x in d.get('blobs', [])]
            with LOCK: res, out = api.call(d['cmd'], d.get('args') or {}, blobs)
            self._json(200, {'result': res, 'blobs': [base64.b64encode(x).decode() for x in out]})
        except Exception as e:
            import traceback; self._json(200, {'result': {'error': str(e) or e.__class__.__name__, 'trace': traceback.format_exc()[-1500:]}, 'blobs': []})

def serve(port=8777, open_browser=True):
    srv = ThreadingHTTPServer(('127.0.0.1', port), H); url = f'http://127.0.0.1:{port}/'
    print('Студия:', url, '— Ctrl+C, чтобы остановить')
    if open_browser: threading.Timer(.6, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
