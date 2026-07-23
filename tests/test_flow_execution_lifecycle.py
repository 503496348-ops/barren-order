"""Flow execution_start/end lifecycle (failure-inclusive)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "modules" / "crew"))

from flow_engine import Flow  # noqa: E402


def test_flow_emits_start_and_end_on_success():
    events = []

    def obs(name, payload):
        events.append((name, payload["status"] if name == "execution_end" else "start"))

    flow = Flow("ok", on_execution_lifecycle=obs)

    @flow.start()
    def boot(state):
        state.set("ok", True)
        return "boot"

    state = flow.run()
    assert state.get("ok") is True
    assert [e[0] for e in events] == ["execution_start", "execution_end"]
    assert events[-1][1] == "success"
    assert flow.execution_summary()["status"] == "success"


def test_flow_emits_end_on_step_failure():
    events = []

    def obs(name, payload):
        events.append((name, payload))

    flow = Flow("bad", on_execution_lifecycle=obs)

    @flow.start()
    def boom(state):
        raise RuntimeError("explode")

    state = flow.run()
    assert [e[0] for e in events] == ["execution_start", "execution_end"]
    end = events[-1][1]
    assert end["status"] == "failed"
    assert end["error"] == "explode"
    assert "boom" in end["failed_steps"]
    assert state.get("_execution_status") == "failed"
    assert flow.last_status == "failed"


def test_lifecycle_observer_exception_does_not_break_flow():
    def bad_obs(name, payload):
        raise RuntimeError("observer broken")

    flow = Flow("obs", on_execution_lifecycle=bad_obs)

    @flow.start()
    def boot(state):
        state.set("v", 1)
        return "boot"

    state = flow.run()
    assert state.get("v") == 1
    assert flow.last_status == "success"
