"""Tests for p1-3: api_keys_required guard (camel-inspired)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from api_keys_guard import (
    api_keys_required,
    check_keys,
    list_guarded_functions,
    MissingAPIKeys,
    KeyStatus,
    KEY_REGISTRY,
)


@pytest.fixture(autouse=True)
def clean_registry():
    saved = dict(KEY_REGISTRY)
    KEY_REGISTRY.clear()
    yield
    KEY_REGISTRY.clear()
    KEY_REGISTRY.update(saved)


class TestCheckKeys:

    def test_all_present(self):
        env = {"KEY_A": "val_a", "KEY_B": "val_b"}
        status = check_keys(["KEY_A", "KEY_B"], env=env)
        assert status.all_present
        assert status.present == ["KEY_A", "KEY_B"]
        assert status.missing == []

    def test_some_missing(self):
        env = {"KEY_A": "val_a"}
        status = check_keys(["KEY_A", "KEY_B"], env=env)
        assert not status.all_present
        assert status.missing == ["KEY_B"]

    def test_empty_value_counts_as_missing(self):
        env = {"KEY_A": "", "KEY_B": "  "}
        status = check_keys(["KEY_A", "KEY_B"], env=env)
        assert not status.all_present
        assert status.missing == ["KEY_A", "KEY_B"]

    def test_empty_list_all_present(self):
        status = check_keys([], env={})
        assert status.all_present


class TestAPIKeysRequired:

    def test_passes_when_keys_present(self):
        @api_keys_required("TEST_API_KEY_1")
        def action() -> dict:
            return {"ok": True}

        os.environ["TEST_API_KEY_1"] = "secret"
        try:
            result = action()
            assert result == {"ok": True}
        finally:
            os.environ.pop("TEST_API_KEY_1", None)

    def test_raises_when_key_missing(self):
        @api_keys_required("TOTALLY_MISSING_KEY_XYZ")
        def action() -> dict:
            return {"ok": True}

        # Ensure the key doesn't exist
        os.environ.pop("TOTALLY_MISSING_KEY_XYZ", None)
        with pytest.raises(MissingAPIKeys) as exc_info:
            action()
        assert "TOTALLY_MISSING_KEY_XYZ" in str(exc_info.value)

    def test_registers_in_registry(self):
        @api_keys_required("KEY_X", "KEY_Y")
        def my_action() -> dict:
            return {}

        assert any("my_action" in k for k in KEY_REGISTRY)
        assert any(v == ["KEY_X", "KEY_Y"] for v in KEY_REGISTRY.values())

    def test_exposes_required_keys_on_wrapper(self):
        @api_keys_required("KEY_A", "KEY_B")
        def my_action() -> dict:
            return {}

        assert my_action._required_keys == ["KEY_A", "KEY_B"]


class TestListGuardedFunctions:

    def test_returns_registered(self):
        @api_keys_required("GUARD_KEY_1")
        def guard_a() -> dict:
            return {}

        @api_keys_required("GUARD_KEY_2", "GUARD_KEY_3")
        def guard_b() -> dict:
            return {}

        guarded = list_guarded_functions()
        assert any("guard_a" in k for k in guarded)
        assert any("guard_b" in k for k in guarded)
        assert any(v == ["GUARD_KEY_2", "GUARD_KEY_3"] for v in guarded.values())
