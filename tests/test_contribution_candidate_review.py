from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from career_intelligence_mvp import run_pipeline
from carrer.contributions import (
    create_contribution,
    find_contribution_candidates,
    promote_contribution_candidate,
    promotion,
    reject_contribution_candidate,
    validate_contribution_candidate,
)
from carrer.contributions.candidates import contribution_candidate, contribution_candidate_id
from carrer.contributions.service import CONTRIBUTION_SUPPORTED_BY_EVIDENCE
from carrer.domain.models import evidence_node, knowledge_node
from carrer.storage.json_graph_storage import JsonGraphStorage

NOW = "2026-01-02T03:04:05+00:00"


def _source(source_id: str = "source:test", visibility: str = "artifact_safe") -> dict[str, Any]:
    return {
        "id": source_id,
        "node_type": "Source",
        "created_at": NOW,
        "properties": {"id": source_id.removeprefix("source:"), "name": "Test", "visibility": visibility},
    }


def _evidence(entity_id: str = "C-1", privacy_level: str = "artifact_safe") -> dict[str, Any]:
    return evidence_node(
        source_id="test",
        source_entity_type="commit",
        source_entity_id=entity_id,
        evidence_type="COMMIT_EXISTS",
        captured_at=NOW,
        occurred_at=NOW,
        payload={"message": entity_id},
        privacy_level=privacy_level,
    )


def _store() -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any]]:
    store = JsonGraphStorage()
    source = _source()
    evidence = _evidence()
    store.create_node(source)
    store.create_node(evidence)
    return store, source, evidence


def _candidate(evidence_refs: list[str], **overrides: Any) -> dict[str, Any]:
    data = {
        "candidate_type": "change_delivery",
        "title": "Fix retry flow",
        "evidence_refs": evidence_refs,
        "source_refs": ["source:test"],
        "confidence": "medium",
        "status": "proposed",
        "privacy_level": "artifact_safe",
        "started_at": NOW,
        "ended_at": NOW,
        "signals": ["commit"],
        "reasons": ["explicit_evidence_relationship"],
        "metadata": {"evidence_count": len(evidence_refs)},
    }
    data.update(overrides)
    return contribution_candidate(**data)


def test_validate_contribution_candidate_accepts_valid_candidate_and_does_not_mutate() -> None:
    _, _, evidence = _store()
    candidate = _candidate([evidence["id"]])
    before = copy.deepcopy(candidate)

    assert validate_contribution_candidate(candidate) is candidate
    assert candidate == before


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda item: item.update(id="contribution_candidate:bad"), "id does not match"),
        (lambda item: item.update(evidence_refs=[]), "evidence_refs"),
        (lambda item: item.update(evidence_refs=["evidence:b", "evidence:a"]), "evidence_refs"),
        (lambda item: item.update(evidence_refs=["evidence:a", "evidence:a"]), "evidence_refs"),
        (lambda item: item.update(confidence="certain"), "confidence"),
        (lambda item: item.update(privacy_level="public"), "privacy"),
        (lambda item: item.update(status="done"), "status"),
        (lambda item: item.update(started_at="2026-01-01T00:00:00"), "timezone"),
        (
            lambda item: item.update(started_at="2026-01-03T00:00:00+00:00", ended_at=NOW),
            "started_at must be before",
        ),
        (lambda item: item.update(metadata={"bad": object()}), "JSON serializable"),
    ],
)
def test_validate_contribution_candidate_rejects_invalid_contracts(mutate: Any, message: str) -> None:
    candidate = _candidate(["evidence:a"])
    mutate(candidate)
    if message == "id does not match":
        candidate["evidence_refs"] = ["evidence:a"]
    with pytest.raises(ValueError, match=message):
        validate_contribution_candidate(candidate)


def test_validate_contribution_candidate_rejects_non_dict_and_missing_fields() -> None:
    with pytest.raises(ValueError, match="dict"):
        validate_contribution_candidate("candidate")
    with pytest.raises(ValueError, match="id"):
        validate_contribution_candidate({"candidate_type": "change_delivery", "title": "A", "evidence_refs": ["e:a"]})


def test_promotion_revalidates_evidence_exists_and_type() -> None:
    store, _, evidence = _store()
    candidate = _candidate([evidence["id"]])
    missing = _candidate(["evidence:missing"])

    assert (
        promote_contribution_candidate(store, candidate, created_at=NOW, decision_actor="human")["decision"]
        == "promoted"
    )
    with pytest.raises(ValueError, match="missing node"):
        promote_contribution_candidate(store, missing, created_at=NOW, decision_actor="human")


@pytest.mark.parametrize("node_type", ["KnowledgeNode", "Contribution"])
def test_promotion_rejects_candidate_refs_that_are_not_evidence(node_type: str) -> None:
    store, _, evidence = _store()
    if node_type == "KnowledgeNode":
        wrong = knowledge_node(
            knowledge_type="TECHNOLOGY_EXPERIENCE",
            statement="Python.",
            created_at=NOW,
            evidence_refs=[evidence["id"]],
        )
        store.create_node(wrong)
    else:
        wrong = create_contribution(
            store,
            contribution_type="manual",
            created_at=NOW,
            title="Manual",
            evidence_refs=[evidence["id"]],
        )["contribution"]

    candidate = _candidate([wrong["id"]], source_refs=[])
    with pytest.raises(ValueError, match=f"requires EvidenceNode, got {node_type}"):
        promote_contribution_candidate(store, candidate, created_at=NOW, decision_actor="human")


def test_minimal_promotion_uses_create_contribution_and_preserves_candidate_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, evidence = _store()
    candidate = _candidate([evidence["id"]])
    called = False
    real_create = promotion.create_contribution

    def spy_create(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return real_create(*args, **kwargs)

    monkeypatch.setattr(promotion, "create_contribution", spy_create)

    result = promote_contribution_candidate(store, candidate, created_at=NOW, decision_actor="human")
    node = result["contribution"]

    assert called is True
    assert result["candidate_id"] == candidate["id"]
    assert result["created"] is True
    assert node["properties"]["evidence_refs"] == candidate["evidence_refs"]
    assert node["properties"]["title"] == candidate["title"]
    assert node["properties"]["contribution_type"] == candidate["candidate_type"]
    assert node["properties"]["started_at"] == candidate["started_at"]
    assert node["properties"]["ended_at"] == candidate["ended_at"]
    assert node["properties"]["confidence"] == candidate["confidence"]
    assert node["properties"]["privacy_level"] == candidate["privacy_level"]
    assert node["properties"]["metadata"]["candidate_id"] == candidate["id"]


def test_promotion_allows_explicit_overrides_without_changing_candidate_refs() -> None:
    store, _, evidence = _store()
    candidate = _candidate([evidence["id"]])

    result = promote_contribution_candidate(
        store,
        candidate,
        created_at=NOW,
        decision_actor="human",
        title="Adjusted title",
        summary="Adjusted summary",
        contribution_type="incident_fix",
        context="Explicit context",
        actions=["added retry"],
        outcomes=["bug resolved"],
        technologies=["Python"],
        domains=["marketplace"],
        metadata={"review_note": "ok", "evidence_refs": ["ignored"]},
    )
    props = result["contribution"]["properties"]

    assert props["title"] == "Adjusted title"
    assert props["summary"] == "Adjusted summary"
    assert props["contribution_type"] == "incident_fix"
    assert props["context"] == "Explicit context"
    assert props["actions"] == ["added retry"]
    assert props["outcomes"] == ["bug resolved"]
    assert props["technologies"] == ["Python"]
    assert props["domains"] == ["marketplace"]
    assert props["metadata"]["review_note"] == "ok"
    assert props["evidence_refs"] == candidate["evidence_refs"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"started_at": "2026-01-01T00:00:00"}, "timezone"),
        ({"ended_at": "not-a-date"}, "ended_at must be an ISO8601 string"),
        (
            {"started_at": "2026-01-03T00:00:00+00:00", "ended_at": "2026-01-01T00:00:00+00:00"},
            "started_at must be before",
        ),
        ({"contribution_type": ""}, "contribution_type"),
        ({"confidence": ""}, "confidence"),
    ],
)
def test_promotion_rejects_invalid_explicit_overrides(kwargs: dict[str, Any], message: str) -> None:
    store, _, evidence = _store()
    candidate = _candidate([evidence["id"]])

    with pytest.raises(ValueError, match=message):
        promote_contribution_candidate(store, candidate, created_at=NOW, decision_actor="human", **kwargs)


def test_promotion_never_downgrades_privacy_or_persists_candidate_or_candidate_edge() -> None:
    store, _, evidence = _store()
    private = _evidence("C-private", privacy_level="private")
    store.create_node(private)
    candidate = _candidate(sorted([evidence["id"], private["id"]]), privacy_level="internal")

    result = promote_contribution_candidate(
        store,
        candidate,
        created_at=NOW,
        decision_actor="human",
        privacy_level="exported",
    )

    assert result["contribution"]["properties"]["privacy_level"] == "private"
    assert "ContributionCandidate" not in {node["node_type"] for node in store.nodes.values()}
    assert all(candidate["id"] not in (edge["from_node_id"], edge["to_node_id"]) for edge in store.edges)


def test_promotion_is_idempotent_edges_are_deduplicated_and_audit_records_reuse() -> None:
    store, _, evidence = _store()
    candidate = _candidate([evidence["id"]])

    first = promote_contribution_candidate(store, candidate, created_at=NOW, decision_actor="human")
    second = promote_contribution_candidate(store, candidate, created_at=NOW, decision_actor="human")

    assert first["created"] is True
    assert second["created"] is False
    assert first["contribution"]["id"] == second["contribution"]["id"]
    assert len(store.nodes_by_type("Contribution")) == 1
    assert len([edge for edge in store.edges if edge["edge_type"] == CONTRIBUTION_SUPPORTED_BY_EVIDENCE]) == 1
    records = [record for record in store.audit_records if record["audit_type"] == "contribution_candidate_promoted"]
    assert [record["metadata"]["created"] for record in records] == [True, False]


def test_rejection_validates_audits_and_does_not_persist_nodes_or_edges() -> None:
    store, _, evidence = _store()
    candidate = _candidate([evidence["id"]], title="customer-secret-title")
    before_nodes = copy.deepcopy(store.nodes)

    result = reject_contribution_candidate(
        store,
        candidate,
        decision_actor="human",
        decided_at=NOW,
        reason="not my work",
    )

    assert result == {"candidate_id": candidate["id"], "decision": "rejected", "reason": "not my work"}
    assert store.nodes == before_nodes
    assert store.edges == []
    records = [record for record in store.audit_records if record["audit_type"] == "contribution_candidate_rejected"]
    assert len(records) == 1
    assert records[0]["metadata"]["reason"] == "not my work"
    assert "customer-secret-title" not in json.dumps(records)


def test_rejection_rejects_empty_actor_and_invalid_timestamp() -> None:
    store, _, evidence = _store()
    candidate = _candidate([evidence["id"]])

    with pytest.raises(ValueError, match="decision_actor"):
        reject_contribution_candidate(store, candidate, decision_actor="", decided_at=NOW)
    with pytest.raises(ValueError, match="decided_at"):
        reject_contribution_candidate(store, candidate, decision_actor="human", decided_at="2026-01-01T00:00:00")


def test_compatibility_clustering_manual_contribution_pipeline_and_json_serialization(tmp_path: Any) -> None:
    store, _, evidence = _store()
    before = copy.deepcopy(store.nodes)
    candidates = find_contribution_candidates(store)
    manual = create_contribution(
        store,
        contribution_type="manual",
        created_at=NOW,
        title="Manual",
        evidence_refs=[evidence["id"]],
    )
    path = tmp_path / "graph.json"
    store.save(path)
    loaded = JsonGraphStorage.load(path)
    pipeline_store, _ = run_pipeline("tests/fixtures/characterization_source_export.json")

    assert store.nodes[evidence["id"]] == before[evidence["id"]]
    assert candidates == []
    assert manual["created"] is True
    json.dumps({"nodes": loaded.nodes, "edges": loaded.edges, "audit_records": loaded.audit_records})
    assert pipeline_store.nodes_by_type("Contribution") == []
    assert all(node["node_type"] != "ContributionCandidate" for node in pipeline_store.nodes.values())


def test_candidate_identity_formula_is_enforced_after_manual_dict_change() -> None:
    candidate = _candidate(["evidence:a"])
    candidate["candidate_type"] = "documentation"
    assert candidate["id"] != contribution_candidate_id(candidate["candidate_type"], candidate["evidence_refs"])
    with pytest.raises(ValueError, match="id does not match"):
        validate_contribution_candidate(candidate)
