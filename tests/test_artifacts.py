from __future__ import annotations

from typing import Any

from carrer.artifacts.builders import (
    generate_linkedin_draft,
    generate_resume_draft,
    generate_skill_matrix,
    generate_tailored_resume,
)
from carrer.artifacts.rendering import artifact_markdown, linkedin_markdown, resume_markdown
from carrer.artifacts.service import build_render_validate_trace
from carrer.artifacts.traceability import artifact_traceability, artifact_traceability_markdown
from carrer.artifacts.validation import (
    artifact_validation_markdown,
    validate_artifact,
    warning_severity,
    warning_summary,
)
from carrer.storage.json_graph_storage import JsonGraphStorage


def add_node(store: JsonGraphStorage, node_id: str, node_type: str, **properties: Any) -> dict[str, Any]:
    item, _ = store.create_node(
        {
            "id": node_id,
            "node_type": node_type,
            "created_at": "2026-01-01T00:00:00Z",
            "properties": properties,
        }
    )
    return item


def artifact_store() -> JsonGraphStorage:
    store = JsonGraphStorage()
    add_node(store, "source:test", "SourceNode", name="Synthetic Source")
    add_node(
        store,
        "evidence:api",
        "EvidenceNode",
        evidence_type="COMMIT_EXISTS",
        source_id="test",
        source_entity_type="commit",
        source_entity_id="ABC-123",
        occurred_at="2025-01-10T00:00:00Z",
        privacy_level="artifact_safe",
        metadata={"message": "Implemented Python API integration"},
    )
    add_node(
        store,
        "observation:api",
        "ObservationNode",
        observation_type="TECHNOLOGY_USAGE_PATTERN",
        statement="Repeated Python API integration work.",
        status="accepted",
        confidence="high",
        privacy_level="artifact_safe",
        evidence_refs=["evidence:api"],
        metadata={"technology": "Python"},
    )
    add_node(
        store,
        "knowledge:api",
        "KnowledgeNode",
        knowledge_type="TECHNOLOGY_EXPERIENCE",
        version=1,
        statement="Practical experience with Python.",
        status="accepted",
        confidence="high",
        privacy_level="artifact_safe",
        observation_refs=["observation:api"],
        evidence_refs=["evidence:api"],
    )
    add_node(
        store,
        "knowledge:private",
        "KnowledgeNode",
        knowledge_type="TECHNOLOGY_EXPERIENCE",
        version=1,
        statement="Practical experience with SECRET-INTERNAL.",
        status="accepted",
        confidence="high",
        privacy_level="private",
        observation_refs=["observation:api"],
        evidence_refs=["evidence:api"],
    )
    return store


def test_skill_matrix_builds_stable_publishable_rows() -> None:
    store = artifact_store()

    first = generate_skill_matrix(store)
    second = generate_skill_matrix(store)

    assert first["properties"]["artifact_type"] == "Skill Matrix"
    assert first["id"] == second["id"]
    assert first["properties"]["knowledge_refs"] == ["knowledge:api"]
    assert [row["knowledge_id"] for row in first["properties"]["rows"]] == ["knowledge:api"]
    assert "SECRET-INTERNAL" not in artifact_markdown(first)


def test_builders_handle_empty_and_accepted_knowledge() -> None:
    empty = JsonGraphStorage()
    assert generate_skill_matrix(empty)["properties"]["rows"] == []

    store = artifact_store()
    resume = generate_resume_draft(store)
    linkedin = generate_linkedin_draft(store)

    assert resume["properties"]["artifact_type"] == "Resume"
    assert "summary" in resume["properties"]["sections"]
    assert resume["properties"]["sections"]["highlights"][0]["knowledge_id"] == "knowledge:api"
    assert linkedin["properties"]["artifact_type"] == "LinkedIn"
    assert "headline" in linkedin["properties"]["sections"]


def test_privacy_filtering_respects_artifact_safe_boundary() -> None:
    store = artifact_store()
    artifact = generate_resume_draft(store)
    markdown = resume_markdown(artifact)

    assert "Python" in markdown
    assert "SECRET-INTERNAL" not in markdown
    assert "knowledge:private" not in artifact["properties"]["knowledge_refs"]
    assert validate_artifact(artifact, store) == []


def test_rendering_outputs_markdown_not_python_repr() -> None:
    store = artifact_store()
    resume = generate_resume_draft(store)
    linkedin = generate_linkedin_draft(store)

    resume_text = resume_markdown(resume)
    linkedin_text = linkedin_markdown(linkedin)

    assert resume_text.startswith("# Resume Draft")
    assert "## Evidence-backed Highlights" in resume_text
    assert "- Practical experience with Python" in resume_text
    assert "# LinkedIn Draft" in linkedin_text
    assert "{'knowledge_id'" not in resume_text


def test_traceability_walks_artifact_to_knowledge_observation_evidence() -> None:
    store = artifact_store()
    artifact = generate_skill_matrix(store)

    trace = artifact_traceability(artifact, store)
    markdown = artifact_traceability_markdown(artifact, store)

    assert trace[0]["knowledge"]["id"] == "knowledge:api"
    assert trace[0]["observations"][0]["id"] == "observation:api"
    assert trace[0]["evidence"][0]["id"] == "evidence:api"
    assert "Synthetic Source" in markdown


def test_traceability_keeps_missing_refs_reviewable() -> None:
    artifact = {
        "properties": {
            "artifact_type": "Resume",
            "sections": {
                "highlights": [
                    {
                        "knowledge_id": "knowledge:missing",
                        "statement": "Missing but reviewable.",
                        "confidence": "low",
                        "observation_refs": ["observation:missing"],
                        "evidence_refs": ["evidence:missing"],
                    }
                ]
            },
        }
    }

    trace = artifact_traceability(artifact, JsonGraphStorage())

    assert trace[0]["knowledge"]["status"] == "missing"
    assert trace[0]["knowledge"]["type"] == "UNKNOWN"
    assert trace[0]["evidence"] == []


def test_validation_reports_blockers_reviews_and_summary() -> None:
    store = artifact_store()
    artifact = generate_skill_matrix(store)
    row = artifact["properties"]["rows"][0]
    row["statement"] = "Improved API by 20% at https://internal.example"
    row["evidence_context"]["evidence_count"] = 99
    store.nodes["knowledge:api"]["properties"]["status"] = "proposed"

    warnings = validate_artifact(artifact, store)
    codes = {warning["code"] for warning in warnings}
    markdown = artifact_validation_markdown(artifact, warnings)

    assert {
        "possible_unsupported_metric",
        "possible_private_source_detail",
        "evidence_context_count_mismatch",
        "knowledge_not_accepted",
    } <= codes
    assert warning_severity("possible_unsupported_metric") == "review"
    assert warning_severity("knowledge_not_accepted") == "blocker"
    assert warning_summary(warnings) == "4 (2 blockers, 2 reviews)"
    assert "- status: REVIEW" in markdown


def test_valid_artifact_has_no_warnings() -> None:
    store = artifact_store()
    artifact = generate_skill_matrix(store)

    assert validate_artifact(artifact, store) == []
    assert "- No validation warnings." in artifact_validation_markdown(artifact, [])


def test_tailored_resume_uses_job_description_requirements() -> None:
    store = artifact_store()
    add_node(
        store,
        "evidence:job",
        "EvidenceNode",
        evidence_type="JOB_DESCRIPTION_EXISTS",
        source_id="test",
        source_entity_type="job_description",
        source_entity_id="job-1",
        occurred_at="2025-02-01T00:00:00Z",
        privacy_level="artifact_safe",
        metadata={"title": "Backend Engineer", "technologies": ["Python", "Rust"]},
    )

    artifact = generate_tailored_resume(store, "evidence:job")

    assert artifact["properties"]["artifact_type"] == "Tailored Resume"
    assert artifact["properties"]["matched_requirements"] == 1
    assert artifact["properties"]["sections"]["highlights"][0]["matches_requirements"] == ["Python"]


def test_artifact_service_orchestrates_build_render_validate_trace() -> None:
    store = artifact_store()

    result = build_render_validate_trace(store, generate_skill_matrix)

    assert result["artifact"]["properties"]["artifact_type"] == "Skill Matrix"
    assert result["markdown"].startswith("# Skill Matrix")
    assert result["warnings"] == []
    assert "# Skill Matrix Traceability" in result["traceability_markdown"]
