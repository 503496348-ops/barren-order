"""Workflow lifecycle tests — validates core workflow engine data structures."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from workflow_engine import (  # noqa: E402
    ExecutionMode,
    TaskLifecycleEvent,
    TaskDefinition,
    WorkflowBuilder,
    WorkflowDefinition,
    WorkflowStatus,
)


def test_task_lifecycle_events_enum():
    """TaskLifecycleEvent should have expected values."""
    assert TaskLifecycleEvent.STARTED == 'started'
    assert TaskLifecycleEvent.SUCCEEDED == 'succeeded'
    assert TaskLifecycleEvent.FAILED == 'failed'
    assert TaskLifecycleEvent.RETRYING == 'retrying'


def test_task_definition_creation():
    """TaskDefinition should be creatable with required fields."""
    td = TaskDefinition(
        task_id='t1',
        name='Test Task',
        keywords=['test'],
        depends_on=[],
        on_success=[],
        on_failure=[],
        metadata={},
    )
    assert td.task_id == 't1'
    assert td.name == 'Test Task'
    assert td.timeout == 120.0


def test_workflow_builder_creates_definition():
    """WorkflowBuilder should produce a valid WorkflowDefinition."""
    builder = WorkflowBuilder('wf1', name='test_workflow')
    builder.add_task("Task 1", TaskDefinition(
        task_id='t1', name='Task 1', keywords=[], depends_on=[],
        on_success=[], on_failure=[], metadata={},
    ))
    wf = builder.build()
    assert isinstance(wf, WorkflowDefinition)
    assert wf.name == 'test_workflow'
    assert len(wf.tasks) == 1
