"""Workflow run-level lifecycle hooks including hierarchical failure path."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from workflow_engine import (  # noqa: E402
    ExecutionMode,
    RunLifecycleEvent,
    TaskDefinition,
    WorkflowBuilder,
    WorkflowDefinition,
    WorkflowExecutor,
    WorkflowStatus,
)


def test_run_lifecycle_success_path():
    events = []

    def on_run(event, run):
        events.append((event, run.status))

    wf = (
        WorkflowBuilder("rlc_ok", "run lifecycle ok")
        .add_task(task_id="t1", name="T1", agent_id="a", prompt="p")
        .build()
    )

    def dispatch(agent_id, prompt, keywords, context):
        return {"ok": True}, None

    run = WorkflowExecutor(wf, dispatch_fn=dispatch, on_run_lifecycle=on_run).run()
    assert run.status == WorkflowStatus.SUCCESS
    assert [e[0] for e in events] == [RunLifecycleEvent.STARTED, RunLifecycleEvent.ENDED]
    assert events[-1][1] == WorkflowStatus.SUCCESS


def test_run_lifecycle_fires_on_hierarchical_prep_failure():
    events = []

    def on_run(event, run):
        events.append((event, run.status, run.context.get("manager_error")))

    workflow = WorkflowDefinition(
        workflow_id="rlc_bad",
        name="run lifecycle hierarchical fail",
        execution_mode=ExecutionMode.HIERARCHICAL,
        manager_agent_id="manager",
        tasks=[TaskDefinition("t1", "T1", agent_id="worker", prompt="do work")],
    )

    def dispatch(agent_id, prompt, keywords, context):
        if agent_id == "manager":
            raise RuntimeError("manager offline")
        return {"ok": True}, None

    run = WorkflowExecutor(workflow, dispatch_fn=dispatch, on_run_lifecycle=on_run).run()
    assert run.status == WorkflowStatus.FAILED
    assert [e[0] for e in events] == [RunLifecycleEvent.STARTED, RunLifecycleEvent.ENDED]
    assert events[-1][1] == WorkflowStatus.FAILED
    assert events[-1][2] and "manager offline" in events[-1][2]


def test_run_lifecycle_fires_on_task_failure():
    events = []

    def on_run(event, run):
        events.append((event, run.status))

    wf = (
        WorkflowBuilder("rlc_task_fail", "task fail end")
        .add_task(task_id="t1", name="T1", agent_id="a", prompt="p", max_retries=0)
        .build()
    )

    def dispatch(agent_id, prompt, keywords, context):
        return None, "permanent failure"

    run = WorkflowExecutor(wf, dispatch_fn=dispatch, on_run_lifecycle=on_run).run()
    assert run.status == WorkflowStatus.FAILED
    assert [e[0] for e in events] == [RunLifecycleEvent.STARTED, RunLifecycleEvent.ENDED]
    assert events[-1][1] == WorkflowStatus.FAILED
