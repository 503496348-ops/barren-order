"""Agent repository loader with sync/async boundary.

Supports repository backends that return either plain agent objects or
awaitables (async getters). Keeps workflow code free of async plumbing.
"""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Union


AgentLike = Any
GetAgentFn = Callable[[str], Union[AgentLike, Awaitable[AgentLike]]]


@dataclass
class LoadedAgent:
    agent_id: str
    agent: AgentLike
    source: str = "repository"
    async_resolved: bool = False


class AgentLoadError(RuntimeError):
    """Raised when an agent cannot be loaded from the repository."""


def _run_awaitable(value: Awaitable[Any]) -> Any:
    """Resolve awaitable from sync context without assuming a free event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)

    # Already inside a loop: schedule and wait via a fresh loop in a thread.
    import concurrent.futures

    def _runner() -> Any:
        return asyncio.run(value)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result()


def resolve_agent_value(value: Union[AgentLike, Awaitable[AgentLike]]) -> tuple[AgentLike, bool]:
    """Return (agent, async_resolved)."""
    if inspect.isawaitable(value):
        return _run_awaitable(value), True  # type: ignore[arg-type]
    return value, False


def load_agent_from_repository(
    repository: Any,
    agent_id: str,
    *,
    getter_names: tuple[str, ...] = ("get_agent", "load_agent", "fetch_agent"),
) -> LoadedAgent:
    """Load one agent from a repository object.

    Repository may expose sync or async getters named in ``getter_names``.
    """
    if not agent_id:
        raise AgentLoadError("agent_id is required")

    getter = None
    used_name = ""
    for name in getter_names:
        cand = getattr(repository, name, None)
        if callable(cand):
            getter = cand
            used_name = name
            break

    if getter is None and callable(repository):
        getter = repository
        used_name = "callable"

    if getter is None:
        raise AgentLoadError(
            f"repository has no callable getter among {getter_names}"
        )

    try:
        raw = getter(agent_id)
        agent, async_resolved = resolve_agent_value(raw)
    except AgentLoadError:
        raise
    except Exception as exc:  # noqa: BLE001 - boundary surface
        raise AgentLoadError(f"failed to load agent '{agent_id}': {exc}") from exc

    if agent is None:
        raise AgentLoadError(f"agent '{agent_id}' not found via {used_name}")

    return LoadedAgent(
        agent_id=agent_id,
        agent=agent,
        source=used_name,
        async_resolved=async_resolved,
    )


async def load_agent_from_repository_async(
    repository: Any,
    agent_id: str,
    *,
    getter_names: tuple[str, ...] = ("get_agent", "load_agent", "fetch_agent"),
) -> LoadedAgent:
    """Async variant: awaits awaitable getters in-place."""
    if not agent_id:
        raise AgentLoadError("agent_id is required")

    getter = None
    used_name = ""
    for name in getter_names:
        cand = getattr(repository, name, None)
        if callable(cand):
            getter = cand
            used_name = name
            break
    if getter is None and callable(repository):
        getter = repository
        used_name = "callable"
    if getter is None:
        raise AgentLoadError(
            f"repository has no callable getter among {getter_names}"
        )

    try:
        raw = getter(agent_id)
        if inspect.isawaitable(raw):
            agent = await raw
            async_resolved = True
        else:
            agent = raw
            async_resolved = False
    except AgentLoadError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AgentLoadError(f"failed to load agent '{agent_id}': {exc}") from exc

    if agent is None:
        raise AgentLoadError(f"agent '{agent_id}' not found via {used_name}")

    return LoadedAgent(
        agent_id=agent_id,
        agent=agent,
        source=used_name,
        async_resolved=async_resolved,
    )
