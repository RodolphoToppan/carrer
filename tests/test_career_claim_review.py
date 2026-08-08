from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from career_intelligence_mvp import run_pipeline
from carrer.claims import (
    CAREER_CLAIM_DERIVED_FROM_ANALYSIS,
    CAREER_CLAIM_FROM_CONTRIBUTION,
    CAREER_CLAIM_SUPPORTED_BY_EVIDENCE,
    accept_career_claim_candidate,
    generate_career_claim_candidates,
    get_career_claim,
    list_career_claims,
    reject_career_claim_candidate,
    validate_persisted_career_claim,
)
from carrer.contributions import accept_contribution_analysis, analyze_contribution, create_contribution
from carrer.domain.models import evidence_node, knowledge_node
from carrer.storage.json_graph_storage import JsonGraphStorage

NOW = "2026-01-02T03:04:05+00:00"


def _evidence(
    entity_type: str = "commit",
    entity_id: str = "C-1",
    *,
    privacy_level: str = "artifact_safe",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_type = {
        "commit": "COMMIT_EXISTS",
        "merge_request": "MERGE_REQUEST_EXISTS",
        "work_item": "WORK_ITEM_EXISTS",
    }[entity_type]
    return evidence_node(
        source_id="test",
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        evidence_type=evidence_type,
        captured_at=NOW,
        occurred_at=NOW,
        privacy_level=privacy_level,
        metadata=metadata or {},
    )


def _store() -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any]]:
    store = JsonGraphStorage()
    nodes = [
        _evidence("commit", "C-1", metadata={"latency_after_ms": 300}),
        _evidence("merge_request", "MR-1", metadata={"state": "merged"}),
        _evidence("work_item", "WI-1", privacy_level="internal", metadata={"state": "closed"}),
    ]
    for node in reversed(nodes):
        store.create_node(node)
    contribution = create_contribution(
        store,
        contribution_type="incident_fix",
        created_at=NOW,
        title="Retry fix",
        evidence_refs=[node["id"] for node in nodes],
        actions=["reviewed retry behavior"],
        outcomes=["bug resolved"],
    )["contribution"]
    analysis = analyze_contribution(store, contribution["id"])
    accepted = accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)["analysis"]
    candidate = next(
        item
        for item in generate_career_claim_candidates(store, accepted["id"])
        if item["claim_type"] == "metric_observed"
    )
    return store, accepted, candidate


def _snapshot(store: JsonGraphStorage) -> str:
    return json.dumps(
        {"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records}, sort_keys=True
    )


def test_acceptance_persists_claim_contract_edges_audit_and_preserves_candidate() -> None:
    store, analysis, candidate = _store()
    before = copy.deepcopy(candidate)

    result = accept_career_claim_candidate(
        store,
        candidate,
        decision_actor="human",
        decided_at="2026-01-03T00:00:00Z",
    )

    claim = result["claim"]
    props = claim["properties"]
    assert candidate == before
    assert result == {
        "claim": claim,
        "candidate_id": candidate["id"],
        "decision": "accepted",
        "created": True,
    }
    assert claim["node_type"] == "CareerClaim"
    assert claim["created_at"] == "2026-01-03T00:00:00Z"
    assert props["status"] == "accepted"
    assert props["statement"] == candidate["statement"]
    assert props["claim_type"] == candidate["claim_type"]
    assert props["confidence"] == candidate["confidence"]
    assert props["privacy_level"] == candidate["privacy_level"] == "internal"
    assert props["contribution_refs"] == [candidate["contribution_ref"]]
    assert props["evidence_refs"] == candidate["evidence_refs"]
    assert props["review_actor"] == "human"
    assert props["reviewed_at"] == "2026-01-03T00:00:00Z"
    assert props["metadata"]["analysis_ref"] == analysis["id"]
    assert props["metadata"]["candidate_id"] == candidate["id"]
    assert props["metadata"]["candidate_version"] == "v1"
    assert props["metadata"]["supporting_fact_refs"] == []
    assert props["metadata"]["supporting_signal_refs"] == candidate["supporting_signal_refs"]
    assert validate_persisted_career_claim(claim) is claim

    edges = {(edge["edge_type"], edge["from_node_id"], edge["to_node_id"]) for edge in store.edges}
    assert (CAREER_CLAIM_DERIVED_FROM_ANALYSIS, claim["id"], candidate["analysis_ref"]) in edges
    assert (CAREER_CLAIM_FROM_CONTRIBUTION, claim["id"], candidate["contribution_ref"]) in edges
    assert all((CAREER_CLAIM_SUPPORTED_BY_EVIDENCE, claim["id"], ref) in edges for ref in candidate["evidence_refs"])
    assert not any("Candidate" in edge["edge_type"] for edge in store.edges)

    audit = store.audit_records[-1]
    audit_metadata_json = json.dumps(audit["metadata"])
    assert audit["audit_type"] == "career_claim_candidate_accepted"
    assert audit["metadata"]["created"] is True
    assert audit["metadata"]["actor"] == "human"
    assert audit["metadata"]["decided_at"] == "2026-01-03T00:00:00Z"
    assert audit["metadata"]["evidence_refs"] == len(candidate["evidence_refs"])
    assert "Observed latency metric" not in audit_metadata_json
    assert "reviewed retry behavior" not in audit_metadata_json
    assert "bug resolved" not in audit_metadata_json
    assert "Retry fix" not in audit_metadata_json
    assert "300" not in audit_metadata_json


def test_acceptance_is_idempotent_and_second_audit_uses_current_call() -> None:
    store, _, candidate = _store()
    first = accept_career_claim_candidate(store, candidate, decision_actor="first", decided_at="2026-01-03T00:00:00Z")
    second = accept_career_claim_candidate(
        store,
        candidate,
        decision_actor="second",
        decided_at="2026-01-04T00:00:00-03:00",
    )
    audits = [record for record in store.audit_records if record["audit_type"] == "career_claim_candidate_accepted"]

    assert second["created"] is False
    assert second["claim"] == first["claim"]
    assert second["claim"]["created_at"] == "2026-01-03T00:00:00Z"
    assert second["claim"]["properties"]["review_actor"] == "first"
    assert second["claim"]["properties"]["reviewed_at"] == "2026-01-03T00:00:00Z"
    assert len(store.nodes_by_type("CareerClaim")) == 1
    assert len([edge for edge in store.edges if edge["from_node_id"] == first["claim"]["id"]]) == (
        len(candidate["evidence_refs"]) + 2
    )
    assert [record["metadata"]["created"] for record in audits] == [True, False]
    assert [record["metadata"]["actor"] for record in audits] == ["first", "second"]
    assert [record["metadata"]["decided_at"] for record in audits] == [
        "2026-01-03T00:00:00Z",
        "2026-01-04T00:00:00-03:00",
    ]


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "claim_type",
        "statement",
        "status",
        "confidence",
        "privacy_level",
        "analysis_ref",
        "contribution_ref",
        "evidence_refs",
        "supporting_signal_refs",
        "warnings",
        "reasons",
        "metadata",
    ],
)
def test_tampered_candidate_cannot_be_accepted_or_rejected(field: str) -> None:
    store, _, candidate = _store()
    changed = copy.deepcopy(candidate)
    if field in {"evidence_refs", "supporting_signal_refs", "warnings", "reasons"}:
        changed[field] = []
    elif field == "metadata":
        changed[field] = {"candidate_version": "v2"}
    elif field == "status":
        changed[field] = "accepted"
    else:
        changed[field] = "changed"

    with pytest.raises(ValueError):
        accept_career_claim_candidate(store, changed, decision_actor="human", decided_at=NOW)
    with pytest.raises(ValueError):
        reject_career_claim_candidate(store, changed, decision_actor="human", decided_at=NOW)


def test_stale_or_missing_current_candidate_fails_structural_comparison() -> None:
    store, analysis, candidate = _store()
    store.nodes[analysis["properties"]["contribution_ref"]]["properties"]["outcomes"] = []
    with pytest.raises(ValueError, match="current deterministic candidate|current deterministic analysis"):
        accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)

    store, _, candidate = _store()
    store.nodes.pop(candidate["analysis_ref"])
    with pytest.raises(ValueError, match="not found"):
        reject_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)


@pytest.mark.parametrize(
    "decided_at", ["2026-01-03T00:00:00Z", "2026-01-03T00:00:00+02:00", "2026-01-03T00:00:00-03:00"]
)
def test_decided_at_accepts_timezone_and_preserves_original_string(decided_at: str) -> None:
    store, _, candidate = _store()

    claim = accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=decided_at)["claim"]

    assert claim["created_at"] == decided_at
    assert claim["properties"]["reviewed_at"] == decided_at


@pytest.mark.parametrize("decided_at", ["not-a-date", "2026-01-03T00:00:00"])
def test_decided_at_rejects_invalid_or_timezone_less_timestamp(decided_at: str) -> None:
    store, _, candidate = _store()

    with pytest.raises(ValueError, match="decided_at"):
        accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=decided_at)


@pytest.mark.parametrize("actor", ["", "   ", 123, None])
def test_actor_is_explicit_non_blank_string(actor: object) -> None:
    store, _, candidate = _store()

    with pytest.raises(ValueError, match="decision_actor"):
        accept_career_claim_candidate(store, candidate, decision_actor=actor, decided_at=NOW)  # type: ignore[arg-type]


def test_rejection_only_audits_preserves_reason_and_does_not_write_graph() -> None:
    store, _, candidate = _store()
    before_nodes = copy.deepcopy(store.nodes)
    before_edges = copy.deepcopy(store.edges)

    result = reject_career_claim_candidate(
        store,
        candidate,
        decision_actor="human",
        decided_at=NOW,
        reason="  not useful  ",
    )

    assert result == {
        "candidate_id": candidate["id"],
        "analysis_ref": candidate["analysis_ref"],
        "contribution_ref": candidate["contribution_ref"],
        "decision": "rejected",
        "reason": "  not useful  ",
    }
    assert store.nodes == before_nodes
    assert store.edges == before_edges
    audit = store.audit_records[-1]
    assert audit["audit_type"] == "career_claim_candidate_rejected"
    assert audit["metadata"]["reason"] == "  not useful  "
    assert "Observed latency metric" not in json.dumps(audit)

    with pytest.raises(ValueError, match="reason must be a string"):
        reject_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW, reason=1)  # type: ignore[arg-type]


def test_queries_validate_filter_sort_and_do_not_mutate_store() -> None:
    store, _, candidate = _store()
    first = accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)["claim"]
    other = next(
        item
        for item in generate_career_claim_candidates(store, candidate["analysis_ref"])
        if item["id"] != candidate["id"]
    )
    second = accept_career_claim_candidate(store, other, decision_actor="human", decided_at=NOW)["claim"]
    before = _snapshot(store)

    assert get_career_claim(store, first["id"]) == first
    assert get_career_claim(store, "missing") is None
    assert list_career_claims(store) == sorted([first, second], key=lambda node: node["id"])
    assert list_career_claims(store, analysis_ref=candidate["analysis_ref"])
    assert list_career_claims(store, contribution_ref=candidate["contribution_ref"])
    assert list_career_claims(store, claim_type=candidate["claim_type"]) == [first]
    assert list_career_claims(store, status="accepted") == sorted([first, second], key=lambda node: node["id"])
    assert _snapshot(store) == before
    with pytest.raises(ValueError, match="claim_type must be a string"):
        list_career_claims(store, claim_type=[])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Invalid claim_type"):
        list_career_claims(store, claim_type="unsupported")
    with pytest.raises(ValueError, match="status must be a string"):
        list_career_claims(store, status={})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Invalid status"):
        list_career_claims(store, status="done")


def test_query_and_validation_fail_on_invalid_persisted_node_or_envelope_id() -> None:
    store, _, candidate = _store()
    claim = accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)["claim"]
    store.nodes[claim["id"]]["properties"]["status"] = "rejected"
    with pytest.raises(ValueError, match="accepted"):
        get_career_claim(store, claim["id"])

    mismatched = copy.deepcopy(claim)
    mismatched["id"] = "career_claim:other"
    mismatched["properties"]["status"] = "accepted"
    with pytest.raises(ValueError, match="identity|envelope"):
        validate_persisted_career_claim(mismatched)


def test_persisted_claim_rejects_candidate_version_mismatch() -> None:
    store, _, candidate = _store()
    claim = accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)["claim"]
    changed = copy.deepcopy(claim)
    changed["properties"]["metadata"]["candidate_version"] = "v2"

    with pytest.raises(ValueError, match="candidate_version"):
        validate_persisted_career_claim(changed)


def test_existing_incompatible_claim_id_conflicts() -> None:
    store, _, candidate = _store()
    result = accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)
    store.nodes[result["claim"]["id"]]["properties"]["confidence"] = "low"

    with pytest.raises(ValueError, match="incompatible"):
        accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)


def test_json_round_trip_and_compatibility_with_pipeline_and_artifacts() -> None:
    store, _, candidate = _store()
    accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)
    path = "career_claim_review_round_trip_test.json"
    try:
        store.save(path)
        loaded = JsonGraphStorage.load(path)
    finally:
        import os

        if os.path.exists(path):
            os.remove(path)

    assert loaded.nodes == store.nodes
    assert loaded.edges == store.edges
    assert loaded.audit_records == store.audit_records
    assert get_career_claim(loaded, next(iter(store.nodes_by_type("CareerClaim")))["id"])

    pipeline_store, _ = run_pipeline("tests/fixtures/characterization_source_export.json")
    assert pipeline_store.nodes_by_type("CareerClaim") == []
    assert pipeline_store.nodes_by_type("CareerClaimCandidate") == []


def test_wrong_analysis_contribution_or_evidence_state_fails_revalidation() -> None:
    store, _, candidate = _store()
    wrong = knowledge_node(
        knowledge_type="TECHNOLOGY_EXPERIENCE",
        statement="Python",
        created_at=NOW,
        evidence_refs=candidate["evidence_refs"],
    )
    store.create_node(wrong)
    bad = {**candidate, "analysis_ref": wrong["id"]}
    with pytest.raises(ValueError, match="CareerClaimCandidate"):
        accept_career_claim_candidate(store, bad, decision_actor="human", decided_at=NOW)

    store, analysis, candidate = _store()
    store.nodes.pop(analysis["properties"]["contribution_ref"])
    with pytest.raises(ValueError, match="Contribution not found"):
        accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)

    store, _, candidate = _store()
    store.nodes.pop(candidate["evidence_refs"][0])
    with pytest.raises(ValueError, match="missing node|missing Evidence"):
        accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)
