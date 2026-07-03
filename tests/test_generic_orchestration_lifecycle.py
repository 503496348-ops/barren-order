from scripts.generic_orchestration_lifecycle import WorkItem, allowed, validate_transition_table


def test_transition_table_is_consistent():
    assert validate_transition_table() == []


def test_high_risk_completion_requires_confirmation():
    item = WorkItem("T-1", "ship feature", state="verification")
    item.transition("completed", "reviewer", "all checks passed")
    assert item.state == "pending_confirmation"
    assert item.pending_confirmation["requested_transition"] == ["verification", "completed"]
    item.confirm_pending("lead-reviewer", True)
    assert item.state == "completed"


def test_permission_matrix_is_generic():
    assert allowed("reviewer", "approve") is True
    assert allowed("executor", "approve") is False
