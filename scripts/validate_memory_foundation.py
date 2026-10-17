"""Disposable validation engines; never connect to saved demo databases."""

import argparse
import contextlib
import json
import os
import selectors
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def engine(folder):
    folder.mkdir(parents=True)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    owner = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts/run_lite.py"),
            "--db",
            str(folder / "brain.rdb"),
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(owner.stdout, selectors.EVENT_READ)
            if not selector.select(40):
                raise RuntimeError("Validation engine startup timed out")
        ready = owner.stdout.readline()
        if not ready or json.loads(ready)["status"] != "ready":
            raise RuntimeError("Validation engine startup failed")
        yield port
    finally:
        owner.terminate()
        out, err = owner.communicate(timeout=30)
        (folder / "engine-stderr.txt").write_text(err)
        if owner.returncode or "Lite stopped with SAVE" not in out:
            raise RuntimeError("Validation engine did not stop cleanly")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument(
        "--benchmark-output", type=Path, default=ROOT / "data/validation/memory-benchmark.json"
    )
    args = parser.parse_args()
    runtime = ROOT / "data/validation"
    runtime.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="memory-foundation-", dir=runtime))
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    env.pop("BRAIN_OPERATOR_SESSION", None)
    with engine(run / "suite") as port:
        config = run / "suite/config.local.yaml"
        config.write_text(
            yaml.safe_dump(
                {
                    "repo_root": str(ROOT),
                    "repo_id": "fixture:validation",
                    "repo_url": "https://github.com/example/fixture",
                    "principal": "fixture",
                    "port": port,
                }
            )
        )
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=ROOT,
            env={
                **env,
                "BRAIN_INTEGRATION": "1",
                "BRAIN_LITE_TESTS": "1",
                "BRAIN_TEST_CONFIG": str(config),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        (run / "pytest.txt").write_text(result.stdout + result.stderr)
        print(result.stdout[-7000:] + result.stderr[-1000:], flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    if args.model_dir:
        with engine(run / "retrieval") as port:
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/benchmark_memory.py"),
                    "--port",
                    str(port),
                    "--model-dir",
                    str(args.model_dir.resolve()),
                    "--output",
                    str(args.benchmark_output.resolve()),
                ],
                env=env,
                cwd=ROOT,
                check=True,
            )
    print("Disposable validation complete; owners stopped with SAVE.")


if __name__ == "__main__":
    main()
