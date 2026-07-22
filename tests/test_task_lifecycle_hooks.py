"""Tests for task lifecycle hooks (crewAI-inspired execution events)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from workflow_engine import (
    ExecutionMode,
    TaskDefinition,
    TaskLifecycleEvent,
    TaskResult,
    TaskStatus,
    WorkflowDefinition,
    WorkflowExecutor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_workflow(task_id="t1", max_retries=2, retry_delay=0.0, condition=None):
    """Build a minimal single-task workflow."""
    return WorkflowDefinition(
        workflow_id="wf-test",
        name="test",
        tasks=[TaskDefinition(
            task_id=task_id,
            name=f"Task {task_id}",
            agent_id="agent",
            prompt="do something",
            max_retries=max_retries,
            retry_delay=retry_delay,
            condition=condition,
        )],
    )


def _collect_events():
    """Return (events_list, callback_fn)."""
    events: list[tuple] = []

    def cb(event: TaskLifecycleEvent, task_id: str, task_name: str, result: TaskResult | None):
        events.append((event, task_id, task_name, result))

    return events, cb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTaskLifecycleHooks:
    """Verify that WorkflowExecutor fires lifecycle callbacks correctly."""

    def test_started_event_fires_before_dispatch(self):
        """STARTED should be the first event emitted for a task."""
        events, cb = _collect_events()
        call_order = []

        def dispatch(agent_id, prompt, keywords, context):
            call_order.append("dispatch")
            return "ok", None

        executor = WorkflowExecutor(
            _make_workflow(),
            dispatch_fn=dispatch,
            on_task_lifecycle=cb,
        )
        executor.run()

        # STARTED must fire before the dispatch call
        assert len(events) >= 2  # STARTED + SUCCEEDED
        assert events[0][0] == TaskLifecycleEvent.STARTED
        assert call_order[0] == "dispatch"

    def test_succeeded_event_fires_on_success(self):
        """SUCCEEDED event should carry the result with status=SUCCESS."""
        events, cb = _collect_events()

        def dispatch(agent_id, prompt, keywords, context):
            return "output", None

        executor = WorkflowExecutor(
            _make_workflow(),
            dispatch_fn=dispatch,
            on_task_lifecycle=cb,
        )
        executor.run()

        succeeded = [e for e in events if e[0] == TaskLifecycleEvent.SUCCEEDED]
        assert len(succeeded) == 1
        _, tid, tname, result = succeeded[0]
        assert tid == "t1"
        assert tname == "Task t1"
        assert result is not None
        assert result.status == TaskStatus.SUCCESS
        assert result.output == "output"

    def test_failed_event_fires_after_all_retries_exhausted(self):
        """FAILED should fire only when all retries are consumed."""
        events, cb = _collect_events()

        def dispatch(agent_id, prompt, keywords, context):
            return None, "boom"

        executor = WorkflowExecutor(
            _make_workflow(max_retries=2, retry_delay=0.0),
            dispatch_fn=dispatch,
            on_task_lifecycle=cb,
        )
        executor.run()

        failed = [e for e in events if e[0] == TaskLifecycleEvent.FAILED]
        assert len(failed) == 1
        _, tid, tname, result = failed[0]
        assert tid == "t1"
        assert result is not None
        assert result.status == TaskStatus.FAILED
        assert "2 attempts failed" in result.error

    def test_retrying_event_fires_on_each_retry(self):
        """RETRYING should fire once per failed attempt (except the last)."""
        events, cb = _collect_events()

        def dispatch(agent_id, prompt, keywords, context):
            return None, "transient error"

        executor = WorkflowExecutor(
            _make_workflow(max_retries=3, retry_delay=0.0),
            dispatch_fn=dispatch,
            on_task_lifecycle=cb,
        )
        executor.run()

        retrying = [e for e in events if e[0] == TaskLifecycleEvent.RETRYING]
        # With 3 retries and all failing: RETRYING fires on attempt 1, 2, 3
        assert len(retrying) == 3

    def test_no_failed_event_on_success(self):
        """FAILED should NOT fire when the task succeeds."""
        events, cb = _collect_events()

        def dispatch(agent_id, prompt, keywords, context):
            return "ok", None

        WorkflowExecutor(
            _make_workflow(),
            dispatch_fn=dispatch,
            on_task_lifecycle=cb,
        ).run()

        failed = [e for e in events if e[0] == TaskLifecycleEvent.FAILED]
        assert len(failed) == 0

    def test_no_events_for_skipped_task(self):
        """No lifecycle events should fire when a task is skipped by condition."""
        from workflow_engine import BranchCondition
        events, cb = _collect_events()

        # Workflow with two tasks: t1 (no deps), t2 depends on t1 with FAILED condition
        # Since t1 succeeds, t2 should be skipped
        wf = WorkflowDefinition(
            workflow_id="wf-skip",
            name="skip test",
            tasks=[
                TaskDefinition(task_id="t1", name="T1", agent_id="a", prompt="p"),
                TaskDefinition(
                    task_id="t2", name="T2", agent_id="a", prompt="p",
                    depends_on=["t1"],
                    condition=BranchCondition.FAILED,
                ),
            ],
        )

        def dispatch(agent_id, prompt, keywords, context):
            return "ok", None

        WorkflowExecutor(wf, dispatch_fn=dispatch, on_task_lifecycle=cb).run()

        t2_events = [e for e in events if e[1] == "t2"]
        assert len(t2_events) == 0

    def test_callback_exception_does_not_break_execution(self):
        """A throwing callback must not crash the workflow."""
        def bad_callback(event, tid, tname, result):
            raise RuntimeError("callback exploded")

        def dispatch(agent_id, prompt, keywords, context):
            return "ok", None

        run = WorkflowExecutor(
            _make_workflow(),
            dispatch_fn=dispatch,
            on_task_lifecycle=bad_callback,
        ).run()

        assert run.status.value == "success"
        assert run.task_results["t1"].status == TaskStatus.SUCCESS

    def test_no_callback_registered_still_works(self):
        """WorkflowExecutor should work fine with no lifecycle callback."""
        def dispatch(agent_id, prompt, keywords, context):
            return "ok", None

        run = WorkflowExecutor(
            _make_workflow(),
            dispatch_fn=dispatch,
            # on_task_lifecycle omitted
        ).run()

        assert run.status.value == "success"

    def test_retry_then_success_fires_correct_sequence(self):
        """First attempt fails (retry), second succeeds → correct event sequence."""
        events, cb = _collect_events()
        attempt_counter = {"n": 0}

        def dispatch(agent_id, prompt, keywords, context):
            attempt_counter["n"] += 1
            if attempt_counter["n"] == 1:
                return None, "first attempt error"
            return "recovered", None

        executor = WorkflowExecutor(
            _make_workflow(max_retries=2, retry_delay=0.0),
            dispatch_fn=dispatch,
            on_task_lifecycle=cb,
        )
        executor.run()

        event_types = [e[0] for e in events]
        assert event_types == [
            TaskLifecycleEvent.STARTED,
            TaskLifecycleEvent.RETRYING,
            TaskLifecycleEvent.SUCCEEDED,
        ]

    def test_event_result_carries_task_metadata(self):
        """SUCCEEDED result should carry agent_id and output."""
        events, cb = _collect_events()

        def dispatch(agent_id, prompt, keywords, context):
            return {"data": 42}, None

        WorkflowExecutor(
            _make_workflow(),
            dispatch_fn=dispatch,
            on_task_lifecycle=cb,
        ).run()

        succeeded = [e for e in events if e[0] == TaskLifecycleEvent.SUCCEEDED][0]
        result = succeeded[3]
        assert result.agent_id == "agent"
        assert result.output == {"data": 42}
        assert result.attempt == 1

    def test_failed_event_result_carries_error_info(self):
        """FAILED result should carry the error message and attempt count."""
        events, cb = _collect_events()

        def dispatch(agent_id, prompt, keywords, context):
            return None, "permanent failure"

        WorkflowExecutor(
            _make_workflow(max_retries=1, retry_delay=0.0),
            dispatch_fn=dispatch,
            on_task_lifecycle=cb,
        ).run()

        failed = [e for e in events if e[0] == TaskLifecycleEvent.FAILED][0]
        result = failed[3]
        assert "permanent failure" in result.error
        assert result.attempt == 1


class TestTaskLifecycleEventEnum:
    """Verify enum values are stable and well-formed."""

    def test_enum_values(self):
        assert TaskLifecycleEvent.STARTED.value == "started"
        assert TaskLifecycleEvent.SUCCEEDED.value == "succeeded"
        assert TaskLifecycleEvent.FAILED.value == "failed"
        assert TaskLifecycleEvent.RETRYING.value == "retrying"

    def test_enum_members(self):
        assert set(TaskLifecycleEvent) == {
            TaskLifecycleEvent.STARTED,
            TaskLifecycleEvent.SUCCEEDED,
            TaskLifecycleEvent.FAILED,
            TaskLifecycleEvent.RETRYING,
        }
