"""Run a model process with a deadline and stop its tool descendants."""

import os
import signal
import subprocess


def model_process(argv, prompt, trace, err, env, timeout):
    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=trace,
        stderr=err,
        text=True,
        encoding="utf-8",
        env=env,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    try:
        process.communicate(input=prompt, timeout=timeout)
        return process.returncode
    except subprocess.TimeoutExpired as exc:
        raise subprocess.TimeoutExpired(argv, timeout) from exc
    finally:
        # MCP editors must not keep writing after the parent times out or exits.
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=10)
