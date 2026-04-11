"""Local dev server — routes /api/* to the appropriate handler module."""
import sys
import os
import importlib
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROUTES = {
    '/api/analyze':   'analyze',
    '/api/topstocks': 'topstocks',
    '/api/screener':  'screener',
}

class DevRouter(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0]
        module_name = ROUTES.get(path)
        if module_name:
            mod = importlib.import_module(module_name)
            h = object.__new__(mod.handler)
            h.__dict__ = self.__dict__.copy()
            h.do_GET()
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        # Wildcard CORS is intentional here — this file runs only in local
        # development (never deployed). Production handlers in analyze.py and
        # topstocks.py enforce an explicit origin allowlist via security.py.
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def log_message(self, format, *args):
        print(f'[API] {self.path}')

if __name__ == '__main__':
    port = 8000
    print(f'API dev server → http://localhost:{port}')
    print('Routes: /api/analyze  /api/topstocks  /api/screener')
    HTTPServer(('localhost', port), DevRouter).serve_forever()
