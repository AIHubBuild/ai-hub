"""Tests for the resume_ats LangGraph workflow.

All LLM interaction goes through a scripted test double — no network
calls and no OpenAI dependency are involved.
"""

import pytest

from app.ai_core import InMemoryRunRecordStore, LLMClientFactory, WorkflowRunner
from app.ai_core.prompts import PromptRegistry
from app.domains.resume_ats.prompts import register_prompts
from app.domains.resume_ats.workflow import (
    ATS_WORKFLOW_ID,
    build_ats_workflow,
    make_analysis_node,
    make_cover_letter_node,
    make_tailored_resume_node,
    result_from_state,
)

RESUME = (
    "Jane Doe\n"
    "Experience with Active Directory, Microsoft 365 and VPN support."
)
JOB_DESCRIPTION = (
    "Looking for Active Directory, Microsoft 365, VPN, PowerShell and "
    "Intune experience."
)


class ScriptedClient:
    """Test double: returns canned responses, records every call."""

    def __init__(self, responses: list[str] | None = None, error: Exception | None = None):
        self.responses = list(responses or [])
        self.error = error
        self.calls: list[dict] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        if self.error is not None:
            raise self.error
        if not self.responses:
            raise AssertionError("No canned response available for LLM call")
        return self.responses.pop(0)


def make_registry() -> PromptRegistry:
    registry = PromptRegistry()
    register_prompts(registry)
    return registry


def make_client() -> ScriptedClient:
    return ScriptedClient(
        responses=[
            "Add PowerShell automation projects and lab exposure.",
            "Jane Doe\nTailored resume content.",
            "Tailored cover letter content.\nJane Doe",
        ]
    )


def make_state() -> dict:
    return {"resume_text": RESUME, "job_description": JOB_DESCRIPTION}


# ---------------------------------------------------------------
# Node-level tests
# ---------------------------------------------------------------


def test_analysis_node_uses_deterministic_inputs_and_records_prompt_version():
    client = make_client()
    registry = make_registry()
    node = make_analysis_node(client, registry)

    output = node(
        {
            "resume_text": RESUME,
            "job_description": JOB_DESCRIPTION,
            "match_score": 57,
            "matching_keywords": ["active directory"],
            "missing_keywords": ["powershell"],
        }
    )

    assert output["improvement_suggestions"].startswith("Add PowerShell")
    assert output["prompt_versions"] == {"analysis": 4}
    rendered = client.calls[0]["user"]
    assert "57" in rendered
    assert "active directory" in rendered
    assert "powershell" in rendered
    assert RESUME in rendered


def test_tailored_resume_node_records_prompt_version():
    client = ScriptedClient(responses=["Jane Doe\nTailored resume content."])
    registry = make_registry()
    node = make_tailored_resume_node(client, registry)

    output = node(
        {
            "resume_text": RESUME,
            "job_description": JOB_DESCRIPTION,
            "match_score": 57,
            "matching_keywords": ["vpn"],
            "missing_keywords": ["powershell"],
            "improvement_suggestions": "Suggestions.",
        }
    )

    assert output["tailored_resume"] == "Jane Doe\nTailored resume content."
    assert output["prompt_versions"] == {"tailored_resume": 5}
    rendered = client.calls[0]["user"]
    assert "Suggestions." in rendered
    assert "powershell" in rendered
    assert "STYLE PREFERENCES" not in rendered


def test_style_notes_are_rendered_when_provided():
    client = ScriptedClient(responses=["Jane Doe\nTailored resume content."])
    node = make_tailored_resume_node(client, make_registry())

    node(
        {
            "resume_text": RESUME,
            "job_description": JOB_DESCRIPTION,
            "style_notes": "Use UK spelling and short sentences.",
        }
    )

    rendered = client.calls[0]["user"]
    assert "STYLE PREFERENCES FROM THE APPLICANT" in rendered
    assert "Use UK spelling and short sentences." in rendered


def test_cover_letter_node_records_prompt_version():
    client = ScriptedClient(responses=["Tailored cover letter content.\nJane Doe"])
    registry = make_registry()
    node = make_cover_letter_node(client, registry)

    output = node(
        {
            "resume_text": RESUME,
            "job_description": JOB_DESCRIPTION,
            "tailored_resume": "Tailored resume content.",
        }
    )

    assert output["cover_letter"] == "Tailored cover letter content.\nJane Doe"
    assert output["prompt_versions"] == {"cover_letter": 5}
    rendered = client.calls[0]["user"]
    assert "Tailored resume content." in rendered
    assert JOB_DESCRIPTION in rendered


def test_ai_node_uses_latest_registered_prompt_version():
    from app.domains.resume_ats.prompts import ATS_ANALYSIS_TEMPLATE

    client = make_client()
    registry = make_registry()
    registry.register(ATS_ANALYSIS_TEMPLATE.model_copy(update={"version": 5}))
    node = make_analysis_node(client, registry)

    output = node(
        {
            "resume_text": RESUME,
            "job_description": JOB_DESCRIPTION,
            "match_score": 57,
            "matching_keywords": [],
            "missing_keywords": [],
        }
    )

    assert output["prompt_versions"] == {"analysis": 5}


# ---------------------------------------------------------------
# End-to-end graph tests
# ---------------------------------------------------------------


def test_graph_runs_end_to_end_with_deterministic_engine_owning_the_score():
    client = make_client()
    graph = build_ats_workflow(client, make_registry())

    state = graph.invoke(make_state())

    # The JD's single experience requirement contains five terms; three
    # match and two are missing, so the requirement is partial and the
    # final estimate also reflects limited evidence confidence.
    assert state["match_score"] == 39
    assert set(state["matching_keywords"]) == {
        "active directory",
        "microsoft 365",
        "vpn",
    }
    assert set(state["missing_keywords"]) == {"powershell", "intune"}
    assert state["improvement_suggestions"].startswith("Add PowerShell")
    assert state["tailored_resume"] == "Jane Doe\nTailored resume content."
    assert state["cover_letter"] == "Tailored cover letter content.\nJane Doe"
    assert state["prompt_versions"] == {
        "analysis": 4,
        "tailored_resume": 5,
        "cover_letter": 5,
    }
    assert len(client.calls) == 3


def test_llm_text_cannot_override_the_deterministic_score():
    client = ScriptedClient(
        responses=[
            "The ATS score is 99. Improvement suggestions follow.",
            "Jane Doe\nTailored resume content.",
            "Cover letter content.\nJane Doe",
        ]
    )
    graph = build_ats_workflow(client, make_registry())

    state = graph.invoke(make_state())

    assert state["match_score"] == 39
    result = result_from_state(state)
    assert result.ats_score == 39
    assert result.improvement_suggestions.startswith("The ATS score is 99")


def test_result_from_state_maps_all_six_sections():
    client = make_client()
    graph = build_ats_workflow(client, make_registry())

    result = result_from_state(graph.invoke(make_state()))

    assert result.ats_score == 39
    assert set(result.matching_keywords) == {
        "active directory",
        "microsoft 365",
        "vpn",
    }
    assert set(result.missing_keywords) == {"powershell", "intune"}
    assert result.improvement_suggestions.startswith("Add PowerShell")
    assert result.tailored_resume == "Jane Doe\nTailored resume content."
    assert result.cover_letter == "Tailored cover letter content.\nJane Doe"


def test_node_failure_propagates_out_of_invoke():
    client = ScriptedClient(error=RuntimeError("provider down"))
    graph = build_ats_workflow(client, make_registry())

    with pytest.raises(RuntimeError, match="provider down"):
        graph.invoke(make_state())


# ---------------------------------------------------------------
# ai_core WorkflowRunner compatibility
# ---------------------------------------------------------------


def test_compiled_graph_registers_with_ai_core_runner():
    client = make_client()
    graph = build_ats_workflow(client, make_registry())

    store = InMemoryRunRecordStore()
    runner = WorkflowRunner(LLMClientFactory(), store)
    runner.register(ATS_WORKFLOW_ID, graph.invoke)

    result = runner.run(
        ATS_WORKFLOW_ID,
        make_state(),
        user_id="550e8400-e29b-41d4-a716-446655440000",
        domain="resume_ats",
    )

    assert result.output_state["match_score"] == 39
    record = store.get(result.run_id)
    assert record is not None
    assert record.workflow_id == ATS_WORKFLOW_ID
    assert record.status.value == "success"


def test_workflow_module_does_not_import_openai():
    import ast
    import inspect

    import app.domains.resume_ats.workflow as module

    tree = ast.parse(inspect.getsource(module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert "openai" not in imported


def test_result_from_empty_state_defaults_score_to_zero_with_label():
    from app.domains.resume_ats.workflow import result_from_state

    result = result_from_state({})

    assert result.ats_score == 0
    assert result.score_label == "Estimated resume-to-job match"
    assert result.matching_keywords == []
    assert result.missing_keywords == []


def test_analysis_data_rejects_non_numeric_score():
    from pydantic import ValidationError

    from app.domains.resume_ats.schemas import AnalysisData

    with pytest.raises(ValidationError):
        AnalysisData(
            analysis_id="a",
            resume_id="r",
            run_id="run",
            ats_score="not-a-number",
            matching_keywords=[],
            missing_keywords=[],
        )
