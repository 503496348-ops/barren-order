"""Agent repository loader sync/async boundary tests."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_repository_loader import (  # noqa: E402
    AgentLoadError,
    load_agent_from_repository,
    load_agent_from_repository_async,
)


class SyncRepo:
    def get_agent(self, agent_id: str):
        return {"id": agent_id, "kind": "sync"}


class AsyncRepo:
    async def get_agent(self, agent_id: str):
        await asyncio.sleep(0)
        return {"id": agent_id, "kind": "async"}


class MissingRepo:
    pass


def test_sync_get_agent():
    loaded = load_agent_from_repository(SyncRepo(), "alpha")
    assert loaded.agent["id"] == "alpha"
    assert loaded.async_resolved is False
    assert loaded.source == "get_agent"


def test_async_get_agent_from_sync_boundary():
    loaded = load_agent_from_repository(AsyncRepo(), "beta")
    assert loaded.agent["kind"] == "async"
    assert loaded.async_resolved is True


def test_async_api():
    loaded = asyncio.run(load_agent_from_repository_async(AsyncRepo(), "gamma"))
    assert loaded.agent["id"] == "gamma"
    assert loaded.async_resolved is True


def test_missing_getter():
    try:
        load_agent_from_repository(MissingRepo(), "x")
        assert False, "expected error"
    except AgentLoadError as e:
        assert "no callable getter" in str(e)
