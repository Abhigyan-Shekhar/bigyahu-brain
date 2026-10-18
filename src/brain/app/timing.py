"""Persist actual stage boundaries so latency is observable without estimates."""

from datetime import UTC, datetime

from .activity import elapsed_seconds


def set_stage(state, uid, name, label):
    value = state.get(uid)
    stages = value.get("stage_timings", [])[-39:]
    now = datetime.now(UTC).isoformat()
    if stages and not stages[-1].get("finished_at"):
        stages[-1] = {**stages[-1], "finished_at": now}
    stages.append({"name": name, "started_at": now, "finished_at": None})
    state.update(uid, stage=label, activity_phase=name, stage_timings=stages)


def finish_stage(state, uid):
    value = state.get(uid)
    stages = value.get("stage_timings", [])
    if stages and not stages[-1].get("finished_at"):
        stages[-1] = {**stages[-1], "finished_at": datetime.now(UTC).isoformat()}
    state.update(uid, activity_phase=None, stage_timings=stages)


def stage_progress(value):
    running = value.get("status") in {"queued", "running"}
    return [
        {
            "name": stage["name"],
            "active": running and not stage.get("finished_at"),
            "seconds": elapsed_seconds(stage["started_at"], stage.get("finished_at"), running),
        }
        for stage in value.get("stage_timings", [])
    ]
