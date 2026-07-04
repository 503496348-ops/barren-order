from scripts.flow_action_templates import FlowActionTemplate, RepositoryFlowDefinition, compile_execution_plan, default_repository_flow


def test_action_template_renders_required_inputs():
    action = FlowActionTemplate("verify", "pytest $path -q", ("path",), ("report",))
    rendered = action.render({"path": "tests/test_flow.py"})
    assert rendered["command"] == "pytest tests/test_flow.py -q"
    assert rendered["produces"] == ["report"]


def test_action_template_rejects_missing_inputs():
    action = FlowActionTemplate("run", "tool $target", ("target",))
    try:
        action.render({})
    except ValueError as exc:
        assert "target" in str(exc)
    else:
        raise AssertionError("missing input should fail")


def test_repository_flow_validation_catches_bad_entrypoint():
    flow = RepositoryFlowDefinition("demo", [FlowActionTemplate("build", "make")], entrypoint="triage")
    assert "entrypoint_not_declared" in flow.validate()


def test_compile_execution_plan_builds_ordered_steps():
    flow = default_repository_flow("demo-repo")
    plan = compile_execution_plan(flow, ["triage", "verify"], {"repo": "demo-repo", "test_path": "tests/"})
    assert plan["ready"] is True
    assert [step["name"] for step in plan["steps"]] == ["triage", "verify"]
    assert plan["steps"][0]["repository"] == "demo-repo"
