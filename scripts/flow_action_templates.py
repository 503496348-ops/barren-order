"""Repository-scoped flow definitions and templated action inputs.

The flow engine is deliberately deterministic so it can run in a no-agent cron,
preflight check, or team runtime without asking an LLM to repair malformed tasks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from string import Template
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class FlowActionTemplate:
    name: str
    command_template: str
    required_inputs: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    risk: str = "low"

    def render(self, inputs: Mapping[str, Any]) -> dict[str, Any]:
        missing = [key for key in self.required_inputs if key not in inputs or inputs[key] in (None, "")]
        if missing:
            raise ValueError(f"missing required inputs: {', '.join(missing)}")
        safe_inputs = {key: str(value) for key, value in inputs.items()}
        return {
            "name": self.name,
            "command": Template(self.command_template).safe_substitute(safe_inputs),
            "produces": list(self.produces),
            "risk": self.risk,
        }


@dataclass
class RepositoryFlowDefinition:
    repository: str
    actions: list[FlowActionTemplate]
    entrypoint: str
    reviewers: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors: list[str] = []
        names = [action.name for action in self.actions]
        if self.entrypoint not in names:
            errors.append("entrypoint_not_declared")
        if len(names) != len(set(names)):
            errors.append("duplicate_action_name")
        for action in self.actions:
            if action.risk not in {"low", "medium", "high"}:
                errors.append(f"invalid_risk:{action.name}")
        return errors

    def instantiate(self, action_name: str, inputs: Mapping[str, Any]) -> dict[str, Any]:
        for action in self.actions:
            if action.name == action_name:
                rendered = action.render(inputs)
                rendered["repository"] = self.repository
                rendered["reviewers"] = list(self.reviewers)
                return rendered
        raise KeyError(action_name)


def compile_execution_plan(flow: RepositoryFlowDefinition, sequence: Sequence[str], shared_inputs: Mapping[str, Any]) -> dict[str, Any]:
    errors = flow.validate()
    if errors:
        return {"ready": False, "errors": errors, "steps": []}
    steps = []
    for action_name in sequence:
        try:
            steps.append(flow.instantiate(action_name, shared_inputs))
        except (KeyError, ValueError) as exc:
            return {"ready": False, "errors": [f"{action_name}:{exc}"], "steps": steps}
    return {"ready": True, "errors": [], "steps": steps}


def default_repository_flow(repository: str) -> RepositoryFlowDefinition:
    return RepositoryFlowDefinition(
        repository=repository,
        entrypoint="triage",
        reviewers=["coordinator"],
        actions=[
            FlowActionTemplate("triage", "python3 scripts/doctor.py --repo $repo --mode triage", ("repo",), ("triage_report",)),
            FlowActionTemplate("implement", "python3 scripts/workflow_engine.py --repo $repo --task $task", ("repo", "task"), ("patch",), "medium"),
            FlowActionTemplate("verify", "python3 -m pytest $test_path -q", ("test_path",), ("test_report",)),
        ],
    )
