"""Lark coding-agent bridge runtime primitives for BarrenOrder.

This module distills a verified Lark-to-local-agent runtime pattern into
small deterministic contracts: chat/topic/comment scopes, workspace bindings,
agent-aware resume fingerprints, and active-run gating.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from time import time
from typing import Dict, Iterable, Literal, Optional, Tuple

ScopeKind = Literal["dm", "group", "topic", "comment"]
AgentKind = Literal["claude", "codex"]
AccessMode = Literal["read-only", "workspace", "full"]


@dataclass(frozen=True)
class BridgeScope:
    kind: ScopeKind
    chat_id: str
    actor_id: str
    thread_id: str | None = None
    document_token: str | None = None

    @property
    def scope_id(self) -> str:
        if self.kind == "topic" and self.thread_id:
            return f"{self.chat_id}:{self.thread_id}"
        if self.kind == "comment" and self.document_token:
            return f"doc:{self.document_token}"
        return self.chat_id


@dataclass(frozen=True)
class WorkspaceBinding:
    requested: str
    resolved: str
    verified: bool

    @classmethod
    def resolve(cls, requested: str) -> "WorkspaceBinding":
        path = Path(requested or ".").expanduser().resolve()
        return cls(requested=requested, resolved=str(path), verified=path.exists())


@dataclass(frozen=True)
class BridgeRunPolicy:
    agent: AgentKind
    access_mode: AccessMode
    workspace: WorkspaceBinding
    allowed_actor: bool
    attachment_hashes: Tuple[str, ...] = ()

    def fingerprint(self) -> str:
        payload = "\x1f".join([
            self.agent,
            self.access_mode,
            self.workspace.resolved,
            "1" if self.allowed_actor else "0",
            *sorted(self.attachment_hashes),
        ])
        return sha256(payload.encode("utf-8")).hexdigest()[:16]

    def assert_allowed(self) -> None:
        if not self.allowed_actor:
            raise PermissionError("actor is not allowed to start bridge run")
        if not self.workspace.verified:
            raise FileNotFoundError(f"workspace does not exist: {self.workspace.resolved}")


@dataclass
class BridgeSession:
    scope_id: str
    agent: AgentKind
    cwd: str
    policy_fingerprint: str
    session_id: str
    updated_at: float = field(default_factory=time)


class BridgeSessionCatalog:
    def __init__(self) -> None:
        self._sessions: Dict[Tuple[str, AgentKind, str, str], BridgeSession] = {}

    def remember(self, scope: BridgeScope, policy: BridgeRunPolicy, session_id: str) -> BridgeSession:
        entry = BridgeSession(scope.scope_id, policy.agent, policy.workspace.resolved, policy.fingerprint(), session_id)
        self._sessions[(entry.scope_id, entry.agent, entry.cwd, entry.policy_fingerprint)] = entry
        return entry

    def resume_for(self, scope: BridgeScope, policy: BridgeRunPolicy) -> Optional[str]:
        entry = self._sessions.get((scope.scope_id, policy.agent, policy.workspace.resolved, policy.fingerprint()))
        return entry.session_id if entry else None


class ActiveRunRegistry:
    def __init__(self) -> None:
        self._active: Dict[str, str] = {}

    def start(self, scope: BridgeScope, run_id: str) -> None:
        if scope.scope_id in self._active:
            raise RuntimeError(f"run already active for {scope.scope_id}")
        self._active[scope.scope_id] = run_id

    def stop(self, scope: BridgeScope) -> str | None:
        return self._active.pop(scope.scope_id, None)

    def active_scopes(self) -> Iterable[str]:
        return tuple(sorted(self._active))
