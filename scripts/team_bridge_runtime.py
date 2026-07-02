"""
Standing team bridge runtime primitives for BarrenOrder.

This module turns group-chat events into auditable delivery plans without
calling an LLM.  It deliberately models the bridge as a state machine:
manager ingress, worker pane delivery, duplicate/drop reasons, and device-auth
login recovery are explicit outputs that can be tested and monitored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Optional


class RuntimeRole(str, Enum):
    MANAGER = "manager"
    WORKER = "worker"


class BridgeAction(str, Enum):
    DELIVER = "deliver"
    DROP = "drop"
    OPS = "ops"


@dataclass(frozen=True)
class AgentRuntime:
    agent_id: str
    role: RuntimeRole
    inbox: str = ""
    pane: str = ""
    cred_home: str = ""
    capabilities: tuple[str, ...] = ()

    def codex_home(self) -> str:
        if not self.cred_home:
            return ""
        return str(PurePosixPath(self.cred_home) / ".codex")

    def can_handle(self, keywords: tuple[str, ...]) -> bool:
        lowered_caps = tuple(c.lower() for c in self.capabilities)
        return any(k.lower() in cap for k in keywords for cap in lowered_caps)


@dataclass(frozen=True)
class BridgeEvent:
    message_id: str
    sender_id: str
    text: str
    team_id: str = "default"
    is_agent: bool = False
    target_agent: Optional[str] = None
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class BridgePlan:
    action: BridgeAction
    reason: str
    targets: tuple[str, ...] = ()
    inbox_writes: dict[str, str] = field(default_factory=dict)
    pane_injections: tuple[str, ...] = ()
    ops_command: tuple[str, ...] = ()
    ops_env: dict[str, str] = field(default_factory=dict)
    user_visible: str = ""
    audit: dict[str, str] = field(default_factory=dict)


class BridgeRuntime:
    """Zero-LLM planning layer for a standing multi-agent team."""

    def __init__(self, team_id: str = "default") -> None:
        self.team_id = team_id
        self._agents: dict[str, AgentRuntime] = {}
        self._seen: set[str] = set()

    def register(self, agent: AgentRuntime) -> None:
        self._agents[agent.agent_id] = agent

    def plan(self, event: BridgeEvent) -> BridgePlan:
        text = (event.text or "").strip()
        if not event.message_id:
            return self._drop("no_msg_id", event)
        if event.message_id in self._seen:
            return self._drop("dedup", event)
        self._seen.add(event.message_id)
        if event.team_id != self.team_id:
            return self._drop("cross_team", event)
        if not text:
            return self._drop("empty", event)

        if text.startswith("/login"):
            return self._login_plan(text, event)

        if event.target_agent:
            target = self._agents.get(event.target_agent)
            if not target:
                return self._drop("unknown_target", event)
            return self._deliver((target.agent_id,), "explicit_target", event)

        sender = self._agents.get(event.sender_id)
        manager = self._manager()
        if sender is None:
            if not manager:
                return self._drop("no_manager", event)
            return self._deliver((manager.agent_id,), "manager_ingress", event)

        if sender.role is RuntimeRole.WORKER:
            if not manager:
                return self._drop("no_manager", event)
            return self._deliver((manager.agent_id,), "worker_return", event)

        target = self._capability_target(event.keywords, exclude=sender.agent_id)
        if target:
            return self._deliver((target.agent_id,), "capability_delegate", event)
        return self._drop("agent_no_target", event)

    def _manager(self) -> Optional[AgentRuntime]:
        for agent in self._agents.values():
            if agent.role is RuntimeRole.MANAGER:
                return agent
        return None

    def _capability_target(self, keywords: tuple[str, ...], exclude: str = "") -> Optional[AgentRuntime]:
        for agent in self._agents.values():
            if agent.agent_id != exclude and agent.role is RuntimeRole.WORKER and agent.can_handle(keywords):
                return agent
        return None

    def _login_plan(self, text: str, event: BridgeEvent) -> BridgePlan:
        parts = text.split()
        if len(parts) < 3 or parts[1].lower() not in {"codex", "codex-cli"}:
            return self._drop("unsupported_login", event)
        target_id = parts[2]
        target = self._agents.get(target_id)
        if not target:
            return self._drop("unknown_login_target", event)
        codex_home = target.codex_home()
        if not codex_home:
            return self._drop("missing_cred_home", event)
        return BridgePlan(
            action=BridgeAction.OPS,
            reason="login_device_auth",
            targets=(target.agent_id,),
            ops_command=("codex", "login", "--device-auth"),
            ops_env={"CODEX_HOME": codex_home},
            user_visible="Open the verification URL and enter the device code shown by the router. Raw credentials are never displayed.",
            audit={"msg_id": event.message_id, "source": event.sender_id, "ops": "device_auth"},
        )

    def _deliver(self, targets: tuple[str, ...], reason: str, event: BridgeEvent) -> BridgePlan:
        inboxes: dict[str, str] = {}
        panes: list[str] = []
        for target_id in targets:
            agent = self._agents[target_id]
            if agent.inbox:
                inboxes[target_id] = agent.inbox
            if agent.pane:
                panes.append(target_id)
        return BridgePlan(
            action=BridgeAction.DELIVER,
            reason=reason,
            targets=targets,
            inbox_writes=inboxes,
            pane_injections=tuple(panes),
            audit={"msg_id": event.message_id, "source": event.sender_id, "team_id": event.team_id},
        )

    def _drop(self, reason: str, event: BridgeEvent) -> BridgePlan:
        return BridgePlan(
            action=BridgeAction.DROP,
            reason=reason,
            audit={"msg_id": event.message_id, "source": event.sender_id, "team_id": event.team_id},
        )
