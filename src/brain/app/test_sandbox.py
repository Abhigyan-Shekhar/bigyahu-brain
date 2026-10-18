"""Bounded approved test execution through Codex's OS sandbox; never fall back to a shell."""

import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


def sandbox_command(work, scratch, argv):
    codex = shutil.which("codex")
    if not codex or sys.platform not in {"darwin", "linux"}:
        raise ValueError("A supported Codex OS sandbox is required for test execution")
    launcher = [codex]
    with Path(codex).open("rb") as executable:
        node_wrapper = executable.read(64).splitlines()[0] == b"#!/usr/bin/env node"
    if node_wrapper:
        node = shutil.which("node")
        if not node:
            raise ValueError("The npm Codex launcher requires Node.js on the server PATH")
        # The child environment deliberately omits user PATH entries. Resolve Node
        # before applying that environment; sandbox permissions remain unchanged.
        launcher = [str(Path(node).resolve()), str(Path(codex).resolve())]
    # Resolve the interpreter: execution through a venv symlink is denied by narrow OS profiles.
    filesystem = {
        ":minimal": "read",
        str(work.resolve()): "write",
        str(scratch.resolve()): "write",
        str(Path(sys.prefix).resolve()): "read",
        str(Path(sys.base_prefix).resolve()): "read",
    }
    filesystem[str(work.resolve() / ".git")] = "read"
    table = "{" + ",".join(json.dumps(k) + "=" + json.dumps(v) for k, v in filesystem.items()) + "}"
    name = "brain-tests-" + work.parent.name.replace("_", "-")
    return [
        *launcher,
        "sandbox",
        "-P",
        name,
        "-C",
        str(work),
        "-c",
        f"permissions.{name}.filesystem=" + table,
        "-c",
        f"permissions.{name}.network.enabled=false",
        "--",
        str(Path(sys.executable).resolve()),
        *argv[1:],
    ]


def test_environment(work, scratch):
    import site

    return {
        "PATH": os.pathsep.join(["/usr/bin", "/bin"]),
        "LANG": "en_US.UTF-8",
        "TMPDIR": str(scratch),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONPATH": os.pathsep.join([str(work / "src"), str(work), *site.getsitepackages()]),
    }


def bounded_run(command, work, env, log, timeout=120):
    """Cap combined output and kill the process group on timeout or output overflow."""
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=work,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    outcome, size = "exited", 0
    try:
        with log.open("wb") as stream, selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                if time.monotonic() - started > timeout:
                    outcome = "timeout"
                    break
                events = selector.select(0.2)
                if events:
                    data = os.read(process.stdout.fileno(), 16384)
                    if not data:
                        break
                    size += len(data)
                    stream.write(data[: max(0, 512000 - (size - len(data)))])
                    if size > 512000:
                        outcome = "output_limit"
                        break
                elif process.poll() is not None:
                    break
        if outcome == "exited":
            try:
                process.wait(timeout=max(0.1, timeout - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                outcome = "timeout"
    finally:
        # Descendants must not outlive a test command, including successful parents.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)
        process.stdout.close()
    return {
        "argv": command[command.index("--") + 1 :] if "--" in command else command,
        "exit_code": process.returncode,
        "outcome": outcome,
        "passed": outcome == "exited" and process.returncode == 0,
        "output": log.read_bytes()[-20000:].decode("utf-8", errors="replace"),
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }


def run_tests(work, run, commands):
    scratch = run / "scratch"
    scratch.mkdir(exist_ok=True)
    env = test_environment(work, scratch)
    results = []
    for i, argv in enumerate(commands):
        result = bounded_run(sandbox_command(work, scratch, argv), work, env, run / f"test-{i}.log")
        # Return the approved portable argv, not host interpreter paths.
        result["argv"] = argv
        pattern = r"(\d+) passed" if argv[2] == "pytest" else r"Ran (\d+) tests?"
        counts = re.findall(pattern, result["output"])
        result["tests_reported"] = int(counts[-1]) if counts else 0
        result["passed"] = result["passed"] and result["tests_reported"] > 0
        results.append(result)
    return results
