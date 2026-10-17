"""Local fixed-principal graph viewer; every API read uses live catalog permissions."""

import argparse
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .config import load_config
from .graph import GraphStore
from .memory import Identity, Memory
from .memory_graph import MemoryGraph
from .memory_tools import MemoryTools
from .services import Services


def authorized_brains(memory):
    with memory.lock:
        return ["private:" + memory.identity.principal] + [
            row[0]
            for row in memory.db.execute(
                "SELECT brain FROM grants WHERE tenant=? AND principal=? "
                "AND role IN ('reader','writer','reviewer') ORDER BY brain LIMIT 100",
                (memory.identity.tenant, memory.identity.principal),
            )
        ]


def handler(memory, tools, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, code, body, content_type="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self):
            host = "127.0.0.1:" + str(self.server.server_port)
            if (
                self.headers.get("Host") != host
                or self.headers.get("Origin", "http://" + host) != "http://" + host
            ):
                return self.reply(403, "{}")
            route = urlsplit(self.path)
            assets = {
                "/": ("memory_viewer.html", "text/html; charset=utf-8"),
                "/viewer.js": ("memory_viewer.js", "text/javascript; charset=utf-8"),
                "/viewer.css": ("memory_viewer.css", "text/css; charset=utf-8"),
            }
            if route.path in assets:
                name, mime = assets[route.path]
                return self.reply(200, (Path(__file__).parent / "web" / name).read_text(), mime)
            if not secrets.compare_digest(
                self.headers.get("Authorization", "").encode("utf-8"),
                ("Bearer " + token).encode("utf-8"),
            ):
                return self.reply(401, "{}")
            params = parse_qs(route.query)
            if route.path == "/api/brains" and not params:
                return self.reply(
                    200,
                    json.dumps(
                        {
                            "principal": memory.identity.principal,
                            "brains": authorized_brains(memory),
                        }
                    ),
                )
            if route.path == "/api/graph" and set(params) <= {"brain", "company"}:
                brains = params.get("brain", [])
                if not brains or len(params.get("company", [])) > 1:
                    return self.reply(400, "{}")
                result = tools.memory_graph(
                    brains, include_company=params.get("company") == ["true"]
                )
                return self.reply(200 if result.get("status") == "ok" else 409, json.dumps(result))
            return self.reply(404, "{}")

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    cfg = load_config(args.config)
    if not cfg.memory_graph_enabled:
        parser.error("Enable memory_graph_enabled and configure the trusted principal/catalog")
    memory = Memory(cfg.memory_db, Identity(cfg.tenant_id, cfg.principal))
    store = GraphStore(cfg)
    tools = MemoryTools(memory, Services(store), MemoryGraph(memory, store))
    token = secrets.token_urlsafe(32)
    server = HTTPServer(("127.0.0.1", args.port), handler(memory, tools, token))
    print(f"Open locally: http://127.0.0.1:{server.server_port}/#" + token, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        memory.close()


if __name__ == "__main__":
    main()
