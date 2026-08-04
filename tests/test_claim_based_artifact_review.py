from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from carrer.artifacts import (
    PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM,
    PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE,
    accept_claim_based_artifact,
    build_artifact_from_career_claims,
    claim_based_professional_artifact_id,
    get_claim_based_professional_artifact,
    list_claim_based_professional_artifacts,
    reject_claim_based_artifact,
    render_claim_based_artifact_markdown,
    validate_persisted_claim_based_professional_artifact,
)
from carrer.claims import accept_career_claim_candidate, generate_career_claim_candidates
from carrer.contributions import accept_contribution_analysis, analyze_contribution, create_contribution
from carrer.domain.models import evidence_node
from carrer.storage.json_graph_storage import JsonGraphStorage

NOW = "2026-01-02T03:04:05+00:00"
DRAFT_AT = "2026-01-03T00:00:00Z"
DECIDED_AT = "2026-01-04T05:06:07-03:00"


def _evidence(entity_type: str, entity_id: str, *, privacy_level: str = "artifact_safe") -> dict[str, Any]:
    return evidence_node(
        source_id="test",
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        evidence_type={
            "commit": "COMMIT_EXISTS",
            "merge_request": "MERGE_REQUEST_EXISTS",
            "work_item": "WORK_ITEM_EXISTS",
        }[entity_type],
        captured_at=NOW,
        occurred_at=NOW,
        privacy_level=privacy_level,
        metadata={"state": "merged", "latency_after_ms": 300},
    )


def _store(*, privacy_level: str = "artifact_safe") -> tuple[JsonGraphStorage, dict[str, Any]]:
    store = JsonGraphStorage()
    evidence = [
        _evidence("commit", "C-1", privacy_level=privacy_level),
        _evidence("merge_request", "MR-1", privacy_level=privacy_level),
        _evidence("work_item", "WI-1", privacy_level=privacy_level),
    ]
    for node in evidence:
        store.create_node(node)
    contribution = create_contribution(
        store,
        contribution_type="incident_fix",
        created_at=NOW,
        title="Retry fix",
        evidence_refs=[node["id"] for node in evidence],
        actions=["reviewed retry behavior"],
        outcomes=["bug resolved"],
        privacy_level=privacy_level,
    )["contribution"]
    analysis = accept_contribution_analysis(
        store,
        analyze_contribution(store, contribution["id"]),
        decision_actor="human",
        decided_at=NOW,
    )["analysis"]
    claims = [
        accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)["claim"]
        for candidate in generate_career_claim_candidates(store, analysis["id"])
    ]
    artifact = build_artifact_from_career_claims(
        store,
        claim_ids=[claim["id"] for claim in claims[:2]],
        artifact_type="resume_claims",
        audience="internal" if privacy_level == "internal" else "public",
        created_at=DRAFT_AT,
    )
    return store, artifact


def _snapshot(store: JsonGraphStorage) -> str:
    return json.dumps({"nodes": store.nodes, "edges": store.edges}, sort_keys=True)


def _set_path(value: dict[str, Any], path: list[str], replacement: object) -> None:
    current = value
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = replacement


def test_accept_persists_professional_artifact_edges_audit_and_preserves_content() -> None:
    store, artifact = _store()

    result = accept_claim_based_artifact(store, artifact, decision_actor="reviewer", decided_at=DECIDED_AT)

    persisted = result["artifact"]
    props = persisted["properties"]
    assert result == {
        "artifact": persisted,
        "source_artifact_id": artifact["id"],
        "decision": "accepted",
        "created": True,
    }
    assert validate_persisted_claim_based_professional_artifact(persisted) is persisted
    assert persisted["node_type"] == "ProfessionalArtifact"
    assert persisted["created_at"] == DRAFT_AT
    assert props["source_type"] == "career_claim"
    assert props["status"] == "accepted"
    assert props["artifact_type"] == artifact["artifact_type"]
    assert props["audience"] == artifact["audience"]
    assert props["privacy_level"] == artifact["privacy_level"]
    assert props["content"] == render_claim_based_artifact_markdown(artifact)
    assert props["items"] == artifact["items"]
    assert props["claim_refs"] == artifact["traceability"]["claim_refs"]
    assert props["review_actor"] == "reviewer"
    assert props["reviewed_at"] == DECIDED_AT
    assert {
        edge["to_node_id"]
        for edge in store.edges
        if edge["edge_type"] == PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM and edge["from_node_id"] == persisted["id"]
    } == set(artifact["traceability"]["claim_refs"])
    assert {
        edge["to_node_id"]
        for edge in store.edges
        if edge["edge_type"] == PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE and edge["from_node_id"] == persisted["id"]
    } == set(props["evidence_refs"])
    audit = store.audit_records[-1]
    assert audit["audit_type"] == "claim_based_artifact_accepted"
    assert audit["created_at"] == DECIDED_AT
    assert audit["metadata"]["created"] is True
    assert "content" not in json.dumps(audit)
    assert artifact["items"][0]["text"] not in json.dumps(audit)


def test_claim_based_professional_artifact_id_is_stable_and_review_independent() -> None:
    store, artifact = _store()
    first = accept_claim_based_artifact(store, artifact, decision_actor="first", decided_at=DECIDED_AT)["artifact"]
    second = accept_claim_based_artifact(
        store,
        artifact,
        decision_actor="second",
        decided_at="2026-01-05T05:06:07+02:00",
    )["artifact"]

    assert claim_based_professional_artifact_id(artifact["id"]) == first["id"] == second["id"]
    assert claim_based_professional_artifact_id(artifact["id"]) == claim_based_professional_artifact_id(artifact["id"])
    with pytest.raises(ValueError, match="source_artifact_id"):
        claim_based_professional_artifact_id("")
    with pytest.raises(ValueError, match="source_artifact_id"):
        claim_based_professional_artifact_id(None)  # type: ignore[arg-type]


def test_accept_is_idempotent_without_overwriting_first_review() -> None:
    store, artifact = _store()
    first = accept_claim_based_artifact(store, artifact, decision_actor="first", decided_at=DECIDED_AT)
    edge_count = len(store.edges)
    second_at = "2026-01-05T05:06:07+02:00"

    second = accept_claim_based_artifact(store, artifact, decision_actor="second", decided_at=second_at)

    assert second["created"] is False
    assert second["artifact"] == first["artifact"]
    assert second["artifact"]["properties"]["review_actor"] == "first"
    assert second["artifact"]["properties"]["reviewed_at"] == DECIDED_AT
    assert len(store.edges) == edge_count
    assert store.audit_records[-1]["metadata"]["actor"] == "second"
    assert store.audit_records[-1]["metadata"]["decided_at"] == second_at
    assert store.audit_records[-1]["metadata"]["created"] is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["properties", "claim_refs"], ["career_claim:a", "career_claim:z"]),
        (["properties", "knowledge_refs"], ["knowledge:unexpected"]),
        (["properties", "artifact_version"], "v2"),
        (["properties", "metadata", "artifact_version"], "v2"),
        (["properties", "metadata", "source_artifact_id"], "claim_based_artifact:other"),
        (["properties", "metadata", "claim_count"], 99),
        (["properties", "metadata", "evidence_count"], 99),
        (["properties", "metadata", "warning_count"], 99),
        (["properties", "traceability", "claim_refs"], ["career_claim:a", "career_claim:z"]),
    ],
)
def test_persisted_professional_artifact_validation_compares_full_node(path: list[str], value: object) -> None:
    store, artifact = _store()
    persisted = accept_claim_based_artifact(store, artifact, decision_actor="reviewer", decided_at=DECIDED_AT)[
        "artifact"
    ]
    changed = copy.deepcopy(persisted)
    _set_path(changed, path, value)

    with pytest.raises(ValueError):
        validate_persisted_claim_based_professional_artifact(changed)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "claim_based_artifact:other"),
        ("artifact_type", "linkedin_claims"),
        ("audience", "internal"),
        ("status", "accepted"),
        ("privacy_level", "exported"),
        ("warnings", []),
        ("metadata", {"artifact_version": "v2"}),
    ],
)
def test_accept_reject_tampered_artifact(field: str, value: object) -> None:
    store, artifact = _store()
    changed = copy.deepcopy(artifact)
    changed[field] = value

    with pytest.raises(ValueError):
        accept_claim_based_artifact(store, changed, decision_actor="reviewer", decided_at=DECIDED_AT)
    with pytest.raises(ValueError):
        reject_claim_based_artifact(store, changed, decision_actor="reviewer", decided_at=DECIDED_AT)


def test_accept_reject_stale_artifact_after_claim_change() -> None:
    store, artifact = _store()
    claim_ref = artifact["traceability"]["claim_refs"][0]
    store.nodes[claim_ref]["properties"]["statement"] = "Changed statement."

    with pytest.raises(ValueError, match="current deterministic artifact"):
        accept_claim_based_artifact(store, artifact, decision_actor="reviewer", decided_at=DECIDED_AT)
    with pytest.raises(ValueError, match="current deterministic artifact"):
        reject_claim_based_artifact(store, artifact, decision_actor="reviewer", decided_at=DECIDED_AT)


def test_reject_records_only_safe_audit() -> None:
    store, artifact = _store()
    before = _snapshot(store)

    result = reject_claim_based_artifact(
        store,
        artifact,
        decision_actor="reviewer",
        decided_at="2026-01-04T05:06:07Z",
        reason="  keep spaces  ",
    )

    assert result["decision"] == "rejected"
    assert result["reason"] == "  keep spaces  "
    assert _snapshot(store) == before
    audit = store.audit_records[-1]
    assert audit["audit_type"] == "claim_based_artifact_rejected"
    assert audit["metadata"]["reason"] == "  keep spaces  "
    assert "content" not in json.dumps(audit)
    assert artifact["items"][0]["text"] not in json.dumps(audit)


@pytest.mark.parametrize("actor", ["", "   ", None, 123, []])
def test_actor_is_required(actor: object) -> None:
    store, artifact = _store()
    with pytest.raises(ValueError, match="decision_actor"):
        accept_claim_based_artifact(store, artifact, decision_actor=actor, decided_at=DECIDED_AT)  # type: ignore[arg-type]


@pytest.mark.parametrize("decided_at", ["bad", "2026-01-04T05:06:07"])
def test_decided_at_must_be_iso8601_with_timezone(decided_at: str) -> None:
    store, artifact = _store()
    with pytest.raises(ValueError, match="decided_at"):
        accept_claim_based_artifact(store, artifact, decision_actor="reviewer", decided_at=decided_at)


def test_reason_must_be_string() -> None:
    store, artifact = _store()
    with pytest.raises(ValueError, match="reason"):
        reject_claim_based_artifact(store, artifact, decision_actor="reviewer", decided_at=DECIDED_AT, reason=[])  # type: ignore[arg-type]


def test_queries_return_only_valid_claim_based_professional_artifacts() -> None:
    store, artifact = _store()
    accepted = accept_claim_based_artifact(store, artifact, decision_actor="reviewer", decided_at=DECIDED_AT)[
        "artifact"
    ]
    store.create_node(
        {
            "id": "artifact:legacy",
            "node_type": "ProfessionalArtifact",
            "created_at": DRAFT_AT,
            "properties": {
                "artifact_type": "Resume",
                "knowledge_refs": [],
                "status": "draft",
                "privacy_level": "draft_private",
            },
        }
    )

    assert get_claim_based_professional_artifact(store, accepted["id"]) == accepted
    assert get_claim_based_professional_artifact(store, "artifact:missing") is None
    assert get_claim_based_professional_artifact(store, "artifact:legacy") is None
    assert list_claim_based_professional_artifacts(store) == [accepted]
    assert list_claim_based_professional_artifacts(store, claim_ref=artifact["traceability"]["claim_refs"][0]) == [
        accepted
    ]
    assert list_claim_based_professional_artifacts(store, artifact_type="resume_claims") == [accepted]
    assert list_claim_based_professional_artifacts(store, audience=artifact["audience"]) == [accepted]
    assert list_claim_based_professional_artifacts(store, status="accepted") == [accepted]
    with pytest.raises(ValueError):
        list_claim_based_professional_artifacts(store, artifact_type="resume")


def test_query_fails_invalid_persisted_node() -> None:
    store, artifact = _store()
    accepted = accept_claim_based_artifact(store, artifact, decision_actor="reviewer", decided_at=DECIDED_AT)[
        "artifact"
    ]
    store.nodes[accepted["id"]]["properties"]["source_artifact_id"] = "claim_based_artifact:other"

    with pytest.raises(ValueError):
        get_claim_based_professional_artifact(store, accepted["id"])
    with pytest.raises(ValueError):
        list_claim_based_professional_artifacts(store)
