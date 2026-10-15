"""Independent socket-level screening oracle; imports the checkout via PYTHONPATH.

Run with Python 3.12. No external server or test framework is needed.
Exit 1 means at least one behavioral invariant failed; observations are JSON.
"""
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import urllib3


class FailedTell(io.BytesIO):
    def tell(self):
        raise OSError('non-seekable stream')


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.do_PUT()

    def do_PUT(self):
        body = b''
        if self.headers.get('Transfer-Encoding', '').lower() == 'chunked':
            while True:
                size = int(self.rfile.readline().split(b';')[0], 16)
                if not size:
                    assert self.rfile.readline() == b'\r\n'
                    break
                body += self.rfile.read(size)
                assert self.rfile.read(2) == b'\r\n'
        else:
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        self.server.observed.append({'method': self.command, 'path': self.path,
                                     'body': body.decode('ascii')})
        status = int(self.path.strip('/')) if self.path != '/sink' else 200
        payload = body if status == 200 else b''
        self.send_response(status)
        if status != 200:
            self.send_header('Location', '/sink')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(payload)


def check(client_kind, redirect, failed_tell=False, offset=0):
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.observed = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    body = (FailedTell if failed_tell else io.BytesIO)(b'PREFIX-PAYLOAD')
    body.seek(offset)
    path = f'/{redirect}' if redirect else '/sink'
    client = (urllib3.PoolManager() if client_kind == 'manager'
              else urllib3.HTTPConnectionPool(host, port))
    error = None
    try:
        client.urlopen('PUT', f'http://{host}:{port}{path}' if client_kind == 'manager' else path,
                       body=body, chunked=True, retries=urllib3.Retry(total=2, redirect=2),
                       timeout=urllib3.Timeout(connect=2, read=2))
    except Exception as exc:
        error = type(exc).__name__
    finally:
        client.clear() if client_kind == 'manager' else client.close()
        server.shutdown()
        server.server_close()
        thread.join()
    expected_body = 'PREFIX-PAYLOAD'[offset:]
    if failed_tell and redirect in (307, 308):
        passed = error == 'UnrewindableBodyError' and len(server.observed) == 1
        expectation = 'one initial send, then UnrewindableBodyError before replay'
    elif redirect == 303:
        passed = error is None and server.observed == [
            {'method': 'PUT', 'path': '/303', 'body': expected_body},
            {'method': 'GET', 'path': '/sink', 'body': ''}]
        expectation = '303 discards body and does not rewind it'
    else:
        count = 2 if redirect else 1
        passed = error is None and len(server.observed) == count and all(
            x['body'] == expected_body and x['method'] == 'PUT' for x in server.observed)
        expectation = 'preserve payload and starting offset; initial upload needs no rewind'
    return {'client': client_kind, 'redirect': redirect, 'failed_tell': failed_tell,
            'offset': offset, 'expectation': expectation, 'passed': passed,
            'error': error, 'wire_requests': server.observed}


if __name__ == '__main__':
    cases = [(307, False, 0), (308, False, 7), (None, True, 0),
             (307, True, 0), (303, True, 0), (303, False, 7)]
    results = [check(kind, *case) for kind in ('manager', 'bare_pool') for case in cases]
    print(json.dumps({'import_path': urllib3.__file__, 'results': results,
                      'passed': sum(r['passed'] for r in results), 'total': len(results)}, indent=2))
    raise SystemExit(0 if all(r['passed'] for r in results) else 1)
