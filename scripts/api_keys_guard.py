# -*- coding: utf-8 -*-
"""
API Keys Required Guard — camel-inspired credential declaration for workflow actions.

Decorators for workflow actions to declare required API keys/credentials.
Runtime validates availability before execution, blocking with clear errors
when keys are missing.

Usage:
    from api_keys_guard import api_keys_required, check_keys, KEY_REGISTRY

    @api_keys_required("OPENAI_API_KEY", "SERP_API_KEY")
    def call_llm(prompt: str) -> dict:
        ...

    # Pre-flight check without executing
    status = check_keys(["OPENAI_API_KEY", "SERP_API_KEY"])
    if not status.all_present:
        print(status.missing)
"""
from __future__ import annotations

import functools
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


KEY_REGISTRY: Dict[str, List[str]] = {}  # func_name -> [required keys]


@dataclass
class KeyStatus:
    """Result of a credential availability check."""
    required: List[str]
    present: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

    @property
    def all_present(self) -> bool:
        return len(self.missing) == 0


class MissingAPIKeys(Exception):
    """Raised when required API keys are not available."""
    def __init__(self, missing: List[str], func_name: str = ""):
        self.missing = missing
        self.func_name = func_name
        keys = ", ".join(missing)
        ctx = f" for '{func_name}'" if func_name else ""
        super().__init__(f"Missing required API keys{ctx}: {keys}")


def api_keys_required(*key_names: str) -> Callable:
    """
    Decorator: declare which environment API keys a workflow action requires.

    At call time, checks os.environ for each key. Raises MissingAPIKeys
    if any are absent.

    Args:
        *key_names: environment variable names (e.g. "OPENAI_API_KEY")

    Example:
        @api_keys_required("OPENAI_API_KEY", "DATABASE_URL")
        def deploy_model(version: str) -> dict:
            ...
    """
    keys = list(key_names)

    def decorator(func: Callable) -> Callable:
        KEY_REGISTRY[func.__qualname__] = keys

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            status = check_keys(keys, func.__qualname__)
            if not status.all_present:
                raise MissingAPIKeys(status.missing, func.__qualname__)
            return func(*args, **kwargs)

        wrapper._required_keys = keys  # type: ignore[attr-defined]
        return wrapper

    return decorator


def check_keys(
    key_names: List[str],
    func_name: str = "",
    env: Optional[Dict[str, str]] = None,
) -> KeyStatus:
    """
    Check which of the given API keys are present in the environment.

    Args:
        key_names: list of environment variable names to check
        func_name: optional function name for context
        env: optional override dict (defaults to os.environ)

    Returns:
        KeyStatus with present/missing lists
    """
    environ = env if env is not None else os.environ
    present = []
    missing = []
    for key in key_names:
        if key in environ and environ[key].strip():
            present.append(key)
        else:
            missing.append(key)
    return KeyStatus(required=list(key_names), present=present, missing=missing)


def list_guarded_functions() -> Dict[str, List[str]]:
    """Return all registered function → required keys mappings."""
    return dict(KEY_REGISTRY)
