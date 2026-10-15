"""One owner for a persisted Lite engine; all other processes use the normal driver."""

import argparse
import fcntl
import json
import signal
import socket
import threading
from pathlib import Path

from redislite.falkordb_client import FalkorDB


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--port", type=int, default=6379)
    args = parser.parse_args()
    path = args.db.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("This database already has a Lite owner") from None
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", args.port))
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        db = FalkorDB(
            str(path),
            serverconfig={
                "bind": "127.0.0.1",
                "port": str(args.port),
                "save": "60 1",
                "appendonly": "yes",
                "appendfsync": "everysec",
            },
        )
        try:
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "port": args.port,
                        "db": str(path),
                        "redis": db.client.info("server")["redis_version"],
                        "modules": db.client.execute_command("MODULE", "LIST"),
                    }
                ),
                flush=True,
            )
            stop.wait()
        finally:
            # Explicit owner shutdown saves even while other clients remain connected.
            db.client.shutdown(save=True)
            print("Lite stopped with SAVE", flush=True)


if __name__ == "__main__":
    main()
