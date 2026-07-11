"""Regression tests for manager-led hierarchical workflow execution."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from workflow_engine import ExecutionMode, TaskDefinition, WorkflowDefinition, WorkflowExecutor


def test_hierarchical_mode_dispatches_manager_before_delegated_workers():
    calls = []

    def dispatch(agent_id, prompt, keywords, context):
        calls.append((agent_id, prompt, dict(context)))
        return f"output:{agent_id}", None

    workflow = WorkflowDefinition(
        workflow_id="hierarchical-demo",
        name="hierarchical demo",
        execution_mode=ExecutionMode.HIERARCHICAL,
        manager_agent_id="manager",
        tasks=[TaskDefinition("research", "Research", agent_id="researcher", prompt="Research {{user_query}}")],
    )

    run = WorkflowExecutor(workflow, dispatch).run({"user_query": "MCP risks"})

    assert run.status.value == "success"
    assert [call[0] for call in calls] == ["manager", "researcher"]
    assert run.context["manager_plan"] == "output:manager"
    assert run.context["delegated_by"]["research"] == "manager"


def test_hierarchical_mode_requires_manager_agent_id():
    workflow = WorkflowDefinition(
        workflow_id="invalid-hierarchical",
        name="invalid hierarchical",
        execution_mode=ExecutionMode.HIERARCHICAL,
        tasks=[TaskDefinition("research", "Research", agent_id="researcher")],
    )
    with pytest.raises(ValueError, match="manager_agent_id"):
        WorkflowExecutor(workflow)


def test_hierarchical_configuration_round_trips_through_json_dict():
    workflow = WorkflowDefinition.from_dict({
        "workflow_id": "roundtrip",
        "name": "roundtrip",
        "execution_mode": "hierarchical",
        "manager_agent_id": "manager",
        "tasks": [{"task_id": "work", "name": "Work", "agent_id": "worker"}],
    })
    assert workflow.execution_mode is ExecutionMode.HIERARCHICAL
    assert workflow.manager_agent_id == "manager"
    assert workflow.to_dict()["execution_mode"] == "hierarchical"
