from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from career_intelligence_mvp import run_pipeline
from carrer.contributions import (
    accept_contribution_analysis,
    analyze_contribution,
    create_contribution,
    get_contribution_analysis,
    list_contribution_analyses,
    reject_contribution_analysis,
    validate_persisted_contribution_analysis,
)
from carrer.contributions.analysis_review import (
    CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION,
    CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE,
)
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


def _store() -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any], dict[str, Any]]:
    store = JsonGraphStorage()
    commit = _evidence("commit", "C-1", metadata={"repository": "repo", "latency_after_ms": 100})
    mr = _evidence("merge_request", "MR-1", metadata={"state": "merged", "source_branch": "feature/a"})
    private_work = _evidence("work_item", "WI-1", privacy_level="internal", metadata={"state": "closed"})
    for node in (commit, mr, private_work):
        store.create_node(node)
    contribution = create_contribution(
        store,
        contribution_type="incident_fix",
        created_at=NOW,
        title="Retry fix",
        evidence_refs=sorted([commit["id"], mr["id"], private_work["id"]]),
        started_at="2026-01-01T10:00:00Z",
        ended_at="2026-01-01T12:00:00+02:00",
        actions=["reviewed retry behavior"],
        outcomes=["bug resolved"],
    )["contribution"]
    return store, contribution, commit, mr


def _analysis() -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any]]:
    store, contribution, _, _ = _store()
    return store, contribution, analyze_contribution(store, contribution["id"])


def _tampered(analysis: dict[str, Any], field: str) -> dict[str, Any]:
    changed = copy.deepcopy(analysis)
    if field == "id":
        changed["id"] = "contribution_analysis:bad"
    elif field == "contribution_ref":
        changed["contribution_ref"] = "contribution:bad"
    elif field == "evidence_refs":
        changed["evidence_refs"] = changed["evidence_refs"][:-1]
    elif field == "status":
        changed["status"] = "accepted"
    elif field == "privacy_level":
        changed["privacy_level"] = "exported"
    elif field == "confidence":
        changed["confidence"] = "low"
    elif field == "fact":
        changed["context_facts"][0]["value"] = "changed"
    elif field == "signal":
        changed["impact_signals"][0]["value"] = 999
    elif field == "warning":
        changed["warnings"] = ["unexpected_warning"]
    elif field == "metadata":
        changed["metadata"]["analysis_version"] = "v2"
    return changed


def test_acceptance_persists_accepted_analysis_edges_audit_and_minimal_review_metadata() -> None:
    store, contribution, analysis = _analysis()
    before = copy.deepcopy(analysis)

    result = accept_contribution_analysis(
        store,
        analysis,
        decision_actor="human",
        decided_at="2026-01-03T00:00:00Z",
    )

    node = result["analysis"]
    props = node["properties"]
    assert analysis == before
    assert result["decision"] == "accepted"
    assert result["created"] is True
    assert node["id"] == analysis["id"]
    assert node["created_at"] == "2026-01-03T00:00:00Z"
    assert props["status"] == "accepted"
    assert props["privacy_level"] == analysis["privacy_level"] == "internal"
    assert props["confidence"] == analysis["confidence"]
    assert props["context_facts"] == analysis["context_facts"]
    assert props["impact_signals"] == analysis["impact_signals"]
    assert props["analysis_version"] == "v1"
    assert props["review_actor"] == "human"
    assert props["reviewed_at"] == "2026-01-03T00:00:00Z"
    assert validate_persisted_contribution_analysis(node) is node
    edges = {(edge["edge_type"], edge["from_node_id"], edge["to_node_id"]) for edge in store.edges}
    assert (CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION, node["id"], contribution["id"]) in edges
    for ref in analysis["evidence_refs"]:
        assert (CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE, node["id"], ref) in edges
    audit = store.audit_records[-1]
    assert audit["audit_type"] == "contribution_analysis_accepted"
    assert audit["metadata"]["created"] is True
    assert audit["metadata"]["context_facts"] == len(analysis["context_facts"])
    audit_json = json.dumps(audit)
    assert "reviewed retry behavior" not in audit_json
    assert "bug resolved" not in audit_json
    assert "Retry fix" not in audit_json
    assert "100" not in audit_json


def test_acceptance_is_idempotent_and_does_not_replace_original_review() -> None:
    store, _, analysis = _analysis()
    first = accept_contribution_analysis(store, analysis, decision_actor="first", decided_at="2026-01-03T00:00:00Z")
    second = accept_contribution_analysis(store, analysis, decision_actor="second", decided_at="2026-01-04T00:00:00Z")
    audit_records = [
        record for record in store.audit_records if record["audit_type"] == "contribution_analysis_accepted"
    ]

    assert second["created"] is False
    assert second["analysis"] == first["analysis"]
    assert second["analysis"]["created_at"] == "2026-01-03T00:00:00Z"
    assert second["analysis"]["properties"]["review_actor"] == "first"
    assert second["analysis"]["properties"]["reviewed_at"] == "2026-01-03T00:00:00Z"
    assert len(store.nodes_by_type("ContributionAnalysis")) == 1
    assert len(
        [edge for edge in store.edges if edge["edge_type"] == CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE]
    ) == len(analysis["evidence_refs"])
    assert [record["metadata"]["created"] for record in audit_records] == [True, False]
    assert [record["metadata"]["actor"] for record in audit_records] == ["first", "second"]
    assert [record["metadata"]["decided_at"] for record in audit_records] == [
        "2026-01-03T00:00:00Z",
        "2026-01-04T00:00:00Z",
    ]


def test_acceptance_conflicts_when_existing_node_content_is_incompatible() -> None:
    store, _, analysis = _analysis()
    accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)
    store.nodes[analysis["id"]]["properties"]["confidence"] = "low"

    with pytest.raises(ValueError, match="incompatible content"):
        accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)


@pytest.mark.parametrize(
    "decided_at",
    ["2026-01-03T00:00:00Z", "2026-01-03T00:00:00+02:00", "2026-01-03T00:00:00-03:00"],
)
def test_decided_at_accepts_timezone_offsets_and_preserves_string(decided_at: str) -> None:
    store, _, analysis = _analysis()

    result = accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=decided_at)

    assert result["analysis"]["created_at"] == decided_at
    assert result["analysis"]["properties"]["reviewed_at"] == decided_at


@pytest.mark.parametrize("decided_at", ["not-a-date", "2026-01-03T00:00:00"])
def test_decided_at_rejects_invalid_or_timezone_less_timestamp(decided_at: str) -> None:
    store, _, analysis = _analysis()

    with pytest.raises(ValueError, match="decided_at"):
        accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=decided_at)


@pytest.mark.parametrize("actor", ["", "   ", 123])
def test_actor_is_explicit_non_blank_string(actor: object) -> None:
    store, _, analysis = _analysis()

    with pytest.raises(ValueError, match="decision_actor"):
        accept_contribution_analysis(store, analysis, decision_actor=actor, decided_at=NOW)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "contribution_ref",
        "evidence_refs",
        "status",
        "privacy_level",
        "confidence",
        "fact",
        "signal",
        "warning",
        "metadata",
    ],
)
def test_tampered_or_non_reviewable_analysis_cannot_be_accepted_or_rejected(field: str) -> None:
    store, _, analysis = _analysis()
    changed = _tampered(analysis, field)

    with pytest.raises(ValueError):
        accept_contribution_analysis(store, changed, decision_actor="human", decided_at=NOW)
    with pytest.raises(ValueError):
        reject_contribution_analysis(store, changed, decision_actor="human", decided_at=NOW)


def test_stale_analysis_is_rejected_after_contribution_or_evidence_changes() -> None:
    store, contribution, analysis = _analysis()
    store.nodes[contribution["id"]]["properties"]["outcomes"] = []

    with pytest.raises(ValueError, match="does not match current deterministic analysis"):
        accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)

    store, _, analysis = _analysis()
    store.nodes[analysis["evidence_refs"][0]]["properties"]["metadata"]["latency_after_ms"] = 200
    with pytest.raises(ValueError, match="does not match current deterministic analysis"):
        reject_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)


def test_missing_or_wrong_current_refs_fail_revalidation() -> None:
    store, _, analysis = _analysis()
    store.nodes.pop(analysis["contribution_ref"])
    with pytest.raises(ValueError, match="Contribution not found"):
        accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)

    store, _, analysis = _analysis()
    store.nodes[analysis["evidence_refs"][0]]["node_type"] = "KnowledgeNode"
    with pytest.raises(ValueError, match="requires EvidenceNode"):
        accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)


def test_rejection_only_audits_and_preserves_reason_exactly() -> None:
    store, contribution, analysis = _analysis()
    before_nodes = copy.deepcopy(store.nodes)
    before_edges = copy.deepcopy(store.edges)

    result = reject_contribution_analysis(
        store,
        analysis,
        decision_actor="human",
        decided_at=NOW,
        reason="  not mine  ",
    )

    assert result == {
        "analysis_id": analysis["id"],
        "contribution_ref": contribution["id"],
        "decision": "rejected",
        "reason": "  not mine  ",
    }
    assert store.nodes == before_nodes
    assert store.edges == before_edges
    audit = store.audit_records[-1]
    assert audit["audit_type"] == "contribution_analysis_rejected"
    assert audit["metadata"]["reason"] == "  not mine  "
    audit_json = json.dumps(audit)
    assert "reviewed retry behavior" not in audit_json
    assert "bug resolved" not in audit_json


def test_rejection_accepts_empty_reason_and_rejects_non_string_reason() -> None:
    store, _, analysis = _analysis()
    assert (
        reject_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW, reason="")["reason"] == ""
    )

    with pytest.raises(ValueError, match="reason must be a string"):
        reject_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW, reason=3)  # type: ignore[arg-type]


def test_queries_validate_filter_sort_and_do_not_mutate_store() -> None:
    store, contribution, analysis = _analysis()
    accepted = accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)["analysis"]
    other_contribution = create_contribution(
        store,
        contribution_type="other_work",
        created_at=NOW,
        title="Other work",
        evidence_refs=[analysis["evidence_refs"][0]],
    )["contribution"]
    other_analysis = analyze_contribution(store, other_contribution["id"])
    other = accept_contribution_analysis(store, other_analysis, decision_actor="human", decided_at=NOW)["analysis"]
    before = copy.deepcopy({"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records})

    assert get_contribution_analysis(store, analysis["id"]) == accepted
    assert get_contribution_analysis(store, "missing") is None
    assert list_contribution_analyses(store) == sorted([accepted, other], key=lambda node: node["id"])
    assert list_contribution_analyses(store, contribution_ref=contribution["id"]) == [accepted]
    assert list_contribution_analyses(store, status="accepted") == sorted(
        [accepted, other], key=lambda node: node["id"]
    )
    assert before == {"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records}
    with pytest.raises(ValueError, match="Invalid status"):
        list_contribution_analyses(store, status="done")


def test_query_fails_on_invalid_persisted_node() -> None:
    store, _, analysis = _analysis()
    accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)
    store.nodes[analysis["id"]]["properties"]["status"] = "rejected"

    with pytest.raises(ValueError, match="accepted"):
        get_contribution_analysis(store, analysis["id"])


def test_persisted_node_validation_rejects_envelope_id_mismatch() -> None:
    store, _, analysis = _analysis()
    node = accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)["analysis"]
    mismatched = copy.deepcopy(node)
    mismatched["id"] = "contribution_analysis:envelope"

    with pytest.raises(ValueError, match="node id does not match properties id"):
        validate_persisted_contribution_analysis(mismatched)


def test_json_round_trip_preserves_accepted_analysis_edges_and_audit(tmp_path: Path) -> None:
    store, _, analysis = _analysis()
    accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)
    path = tmp_path / "graph.json"

    store.save(path)
    loaded = JsonGraphStorage.load(path)

    assert json.dumps(
        {"nodes": loaded.nodes, "edges": loaded.edges, "audit_records": loaded.audit_records}, sort_keys=True
    )
    assert loaded.nodes == store.nodes
    assert loaded.edges == store.edges
    assert loaded.audit_records == store.audit_records
    assert get_contribution_analysis(loaded, analysis["id"]) == store.nodes[analysis["id"]]


def test_compatibility_existing_flows_do_not_create_or_import_analysis_review() -> None:
    store, _, analysis = _analysis()
    before = copy.deepcopy(store.nodes)
    assert analyze_contribution(store, analysis["contribution_ref"]) == analysis
    assert store.nodes == before

    wrong = knowledge_node(
        knowledge_type="TECHNOLOGY_EXPERIENCE",
        statement="Python.",
        created_at=NOW,
        evidence_refs=[analysis["evidence_refs"][0]],
    )
    store.create_node(wrong)
    assert get_contribution_analysis(store, wrong["id"]) is None

    pipeline_store, _ = run_pipeline("tests/fixtures/characterization_source_export.json")
    assert pipeline_store.nodes_by_type("ContributionAnalysis") == []
