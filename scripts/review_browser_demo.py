"""Human-run interactive review entry point for Windows, macOS, and Linux."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from brain.config import load_config

ROOT = Path(__file__).resolve().parents[1]
REPO = "demo:urllib3:browser:eligible"


def review(config):
    cfg = load_config(config)
    if cfg.repo_id != REPO or cfg.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Expected the isolated loopback demo configuration")
    env = {**os.environ, "BRAIN_CONFIG": str(config), "BRAIN_OPERATOR_SESSION": "1"}
    for uid in ("D-1", "D-2"):
        print(f"LOCAL DEMO ONLY: independently review {uid} and every linked source.", flush=True)
        for command in ("inspect", "approve"):
            subprocess.run([sys.executable, "-m", "brain", command, uid], env=env, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=ROOT / "config/brain.browser-demo.local.yaml")
    review(parser.parse_args().config.resolve())
