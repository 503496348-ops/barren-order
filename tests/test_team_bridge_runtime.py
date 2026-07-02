from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from team_bridge_runtime import (
    BridgeEvent,
    BridgeRuntime,
    BridgeAction,
    AgentRuntime,
    RuntimeRole,
)


def test_human_message_becomes_manager_inbox_delivery_plan():
    runtime = BridgeRuntime(team_id="alpha")
    runtime.register(AgentRuntime("manager", RuntimeRole.MANAGER, inbox="/team/manager/inbox"))
    runtime.register(AgentRuntime("coder", RuntimeRole.WORKER, inbox="/team/coder/inbox"))

    plan = runtime.plan(BridgeEvent(message_id="m1", sender_id="human", text="请让 Codex 修复测试", team_id="alpha"))

    assert plan.action is BridgeAction.DELIVER
    assert plan.targets == ("manager",)
    assert plan.reason == "manager_ingress"
    assert plan.inbox_writes == {"manager": "/team/manager/inbox"}
    assert plan.pane_injections == ()
    assert plan.audit["source"] == "human"


def test_manager_can_delegate_to_worker_pane_but_duplicate_is_dropped():
    runtime = BridgeRuntime(team_id="alpha")
    runtime.register(AgentRuntime("manager", RuntimeRole.MANAGER, inbox="/team/manager/inbox"))
    runtime.register(AgentRuntime("coder", RuntimeRole.WORKER, pane="tmux:%42", capabilities=("codex", "代码")))

    plan = runtime.plan(BridgeEvent(
        message_id="m2",
        sender_id="manager",
        text="交给 Codex 改代码",
        team_id="alpha",
        is_agent=True,
        keywords=("codex",),
    ))
    assert plan.action is BridgeAction.DELIVER
    assert plan.targets == ("coder",)
    assert plan.reason == "capability_delegate"
    assert plan.pane_injections == ("coder",)

    duplicate = runtime.plan(BridgeEvent(message_id="m2", sender_id="manager", text="重复", team_id="alpha", is_agent=True))
    assert duplicate.action is BridgeAction.DROP
    assert duplicate.reason == "dedup"


def test_slash_login_codex_is_zero_llm_ops_command_and_redacts_secrets():
    runtime = BridgeRuntime(team_id="alpha")
    runtime.register(AgentRuntime("manager", RuntimeRole.MANAGER, inbox="/team/manager/inbox"))
    runtime.register(AgentRuntime("coder", RuntimeRole.WORKER, cred_home="/private/coder", capabilities=("codex",)))

    plan = runtime.plan(BridgeEvent(message_id="m3", sender_id="human", text="/login codex coder", team_id="alpha"))

    assert plan.action is BridgeAction.OPS
    assert plan.reason == "login_device_auth"
    assert plan.ops_command == ("codex", "login", "--device-auth")
    assert plan.ops_env == {"CODEX_HOME": "/private/coder/.codex"}
    assert plan.targets == ("coder",)
    assert "token" not in plan.user_visible.lower()
    assert "secret" not in plan.user_visible.lower()


def test_cross_team_and_unknown_login_target_are_safe_drops():
    runtime = BridgeRuntime(team_id="alpha")
    runtime.register(AgentRuntime("manager", RuntimeRole.MANAGER))

    cross = runtime.plan(BridgeEvent(message_id="m4", sender_id="human", text="hello", team_id="beta"))
    assert cross.action is BridgeAction.DROP
    assert cross.reason == "cross_team"

    unknown = runtime.plan(BridgeEvent(message_id="m5", sender_id="human", text="/login codex ghost", team_id="alpha"))
    assert unknown.action is BridgeAction.DROP
    assert unknown.reason == "unknown_login_target"
