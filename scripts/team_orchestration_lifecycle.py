"""Team orchestration lifecycle primitives for BarrenOrder.

Team task state machine and review-gate helpers for multi-agent work.
The vocabulary is intentionally generic: no themed roles, no proprietary
project names, and no UI copy that leaks an external source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

TERMINAL_STATES = {"completed", "cancelled"}

TRANSITIONS: dict[str, set[str]] = {
    "intake": {"planning", "cancelled"},
    "planning": {"review", "blocked", "cancelled"},
    "review": {"queued", "planning", "blocked", "cancelled"},
    "queued": {"running", "blocked", "cancelled"},
    "running": {"verification", "blocked", "cancelled"},
    "verification": {"completed", "running", "review", "pending_confirmation", "cancelled"},
    "pending_confirmation": {"completed", "verification", "cancelled"},
    "blocked": {"planning", "review", "queued", "running", "verification", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

HIGH_RISK_TRANSITIONS = {
    ("verification", "completed"),
    ("running", "cancelled"),
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "coordinator": {"create", "plan", "assign", "advance", "block"},
    "reviewer": {"review", "reject", "approve", "confirm", "block"},
    "executor": {"start", "progress", "submit", "block"},
    "operator": {"pause", "resume", "retry", "rollback", "escalate"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FlowEntry:
    source: str
    target: str
    actor: str
    reason: str = ""
    timestamp: str = field(default_factory=utc_now)


@dataclass
class WorkItem:
    item_id: str
    title: str
    state: str = "intake"
    owner: str = "coordinator"
    flow_log: list[FlowEntry] = field(default_factory=list)
    pending_confirmation: dict | None = None

    def transition(self, target: str, actor: str, reason: str = "", *, confirm: bool = False) -> "WorkItem":
        if target not in TRANSITIONS.get(self.state, set()):
            raise ValueError(f"invalid transition: {self.state} -> {target}")
        if (self.state, target) in HIGH_RISK_TRANSITIONS and not confirm:
            original_state = self.state
            self.state = "pending_confirmation"
            self.pending_confirmation = {
                "requested_transition": [original_state, target],
                "requested_by": actor,
                "reason": reason,
                "requested_at": utc_now(),
            }
            self.flow_log.append(FlowEntry(original_state, "pending_confirmation", actor, reason))
            return self
        old = self.state
        self.state = target
        self.pending_confirmation = None
        self.flow_log.append(FlowEntry(old, target, actor, reason))
        return self

    def confirm_pending(self, actor: str, approve: bool, reason: str = "") -> "WorkItem":
        if not self.pending_confirmation:
            raise ValueError("no pending confirmation")
        source, target = self.pending_confirmation["requested_transition"]
        if approve:
            self.state = target
            self.flow_log.append(FlowEntry("pending_confirmation", target, actor, reason or "confirmed"))
        else:
            self.state = source
            self.flow_log.append(FlowEntry("pending_confirmation", source, actor, reason or "rejected"))
        self.pending_confirmation = None
        return self


def validate_transition_table(transitions: dict[str, Iterable[str]] = TRANSITIONS) -> list[str]:
    """Return deterministic issues for a lifecycle transition table."""
    issues: list[str] = []
    states = set(transitions)
    for state, targets in sorted(transitions.items()):
        for target in sorted(set(targets)):
            if target not in states:
                issues.append(f"unknown target state: {state}->{target}")
        if state in TERMINAL_STATES and set(targets):
            issues.append(f"terminal state has outgoing transitions: {state}")
    for required in ("intake", "planning", "review", "running", "verification", "completed"):
        if required not in states:
            issues.append(f"missing required state: {required}")
    return issues


def allowed(role: str, action: str) -> bool:
    return action in ROLE_PERMISSIONS.get(role, set())
