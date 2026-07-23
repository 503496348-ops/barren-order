"""Flow execution_start/end lifecycle (failure-inclusive)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "modules" / "crew"))

from flow_engine import Flow  # noqa: E402


def test_flow_basic_run():
    """Flow should execute a simple step."""
    flow = Flow("basic")

    @flow.start()
    def boot(state):
        state.set("ok", True)
        return "boot"

    state = flow.run()
    assert state.get("ok") is True


@pytest.mark.xfail(reason="on_execution_lifecycle API not yet implemented in Flow")
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


@pytest.mark.xfail(reason="on_execution_lifecycle API not yet implemented in Flow")
def test_flow_emits_end_on_step_failure():
    events = []

    def obs(name, payload):
        events.append(name)

    flow = Flow("fail", on_execution_lifecycle=obs)

    @flow.start()
    def boot(state):
        raise RuntimeError("boom")

    state = flow.run()
    assert state.has_error()
    assert "execution_end" in events


@pytest.mark.xfail(reason="on_execution_lifecycle API not yet implemented in Flow")
def test_lifecycle_observer_exception_does_not_break_flow():
    def bad_obs(name, payload):
        raise ValueError("observer broken")

    flow = Flow("obs", on_execution_lifecycle=bad_obs)

    @flow.start()
    def boot(state):
        state.set("ok", True)
        return "boot"

    state = flow.run()
    assert state.get("ok") is True
