from pathlib import Path
import pytest
from scripts.team_chat_bridge_runtime import ActiveRunRegistry, BridgeRunPolicy, BridgeScope, BridgeSessionCatalog, WorkspaceBinding


def test_topic_scope_and_policy_fingerprint_drive_resume(tmp_path: Path):
    scope = BridgeScope(kind="topic", chat_id="oc_group", thread_id="omt_1", actor_id="ou_user")
    policy = BridgeRunPolicy("claude", "workspace", WorkspaceBinding.resolve(str(tmp_path)), True)
    catalog = BridgeSessionCatalog()
    catalog.remember(scope, policy, "sess-1")
    assert scope.scope_id == "oc_group:omt_1"
    assert catalog.resume_for(scope, policy) == "sess-1"
    changed = BridgeRunPolicy("claude", "read-only", WorkspaceBinding.resolve(str(tmp_path)), True)
    assert catalog.resume_for(scope, changed) is None


def test_active_run_registry_rejects_duplicate_scope():
    scope = BridgeScope(kind="group", chat_id="oc_group", actor_id="ou_user")
    registry = ActiveRunRegistry()
    registry.start(scope, "run-1")
    with pytest.raises(RuntimeError):
        registry.start(scope, "run-2")
    assert registry.stop(scope) == "run-1"
