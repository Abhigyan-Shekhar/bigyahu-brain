"""Authenticated SSE snapshots: public job state, never raw model/tool traces."""

import asyncio
import json
import time


async def snapshots(request, snapshot, *, terminal=False, interval=1):
    previous, heartbeat = None, time.monotonic()
    while not await request.is_disconnected():
        value = await asyncio.to_thread(snapshot)
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if encoded != previous:
            yield "event: snapshot\ndata: " + encoded + "\n\n"
            previous, heartbeat = encoded, time.monotonic()
        elif time.monotonic() - heartbeat >= 15:
            yield ": heartbeat\n\n"
            heartbeat = time.monotonic()
        if terminal and value.get("status") not in {"queued", "running"}:
            return
        await asyncio.sleep(interval)
