from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from career_intelligence_mvp import run_pipeline
from carrer.claims import (
    career_claim_candidate,
    career_claim_candidate_id,
    generate_career_claim_candidates,
    generate_career_claim_candidates_from_analysis,
    supporting_fact_ref,
    supporting_signal_ref,
    validate_career_claim_candidate,
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
        "review_comment": "REVIEW_COMMENT_CREATED",
        "documentation": "DOCUMENTATION_EXISTS",
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


def _store() -> tuple[JsonGraphStorage, dict[str, Any]]:
    store = JsonGraphStorage()
    nodes = [
        _evidence("commit", "C-1", metadata={"latency_after_ms": 300}),
        _evidence("merge_request", "MR-1", metadata={"state": "merged"}),
        _evidence("review_comment", "R-1"),
        _evidence("documentation", "D-1", metadata={"published_at": "2026-01-02T00:00:00Z"}),
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
        confidence="medium",
    )["contribution"]
    analysis = analyze_contribution(store, contribution["id"])
    accepted = accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)["analysis"]
    return store, accepted


def _snapshot(store: JsonGraphStorage) -> str:
    return json.dumps(
        {"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records}, sort_keys=True
    )


def test_generation_from_accepted_analysis_is_deterministic_conservative_and_read_only() -> None:
    store, analysis = _store()
    before = _snapshot(store)

    first = generate_career_claim_candidates(store, analysis["id"])
    second = generate_career_claim_candidates(store, analysis["id"])

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert [candidate["id"] for candidate in first] == sorted(candidate["id"] for candidate in first)
    assert _snapshot(store) == before
    assert store.nodes_by_type("CareerClaim") == []
    assert store.nodes_by_type("CareerClaimCandidate") == []
    assert all(validate_career_claim_candidate(candidate) is candidate for candidate in first)
    assert {candidate["claim_type"] for candidate in first} == {
        "work_performed",
        "outcome_achieved",
        "metric_observed",
    }
    statements = {candidate["statement"] for candidate in first}
    assert "Performed work recorded as: reviewed retry behavior." in statements
    assert "Recorded outcome: bug resolved." in statements
    assert "A commit associated with the contribution was created." in statements
    assert "A merge request associated with the contribution was merged." in statements
    assert "Observed latency metric: 300 ms." in statements
    assert not any("successfully" in statement.lower() or "reduced" in statement.lower() for statement in statements)
    assert not any("70%" in statement or "production" in statement.lower() for statement in statements)
    assert {candidate["privacy_level"] for candidate in first} == {"internal"}
    assert all(candidate["confidence"] in {"low", "medium", "high"} for candidate in first)
    metric = next(candidate for candidate in first if candidate["claim_type"] == "metric_observed")
    assert metric["warnings"] == ["analysis_contains_warnings", "metric_is_observation_not_impact"]
    structural = [
        candidate
        for candidate in first
        if candidate["status"] == "review_required" and candidate["claim_type"] != "metric_observed"
    ]
    assert structural
    assert all("structural_" in " ".join(candidate["warnings"]) for candidate in structural)


def test_validation_rejects_invalid_candidate_shapes_and_tampered_identity() -> None:
    store, analysis = _store()
    candidate = next(
        item for item in generate_career_claim_candidates(store, analysis["id"]) if len(item["evidence_refs"]) > 1
    )

    cases = [
        ([], "dict"),
        ({**candidate, "id": "career_claim_candidate:bad"}, "id"),
        ({**candidate, "claim_type": ""}, "claim_type"),
        ({**candidate, "statement": ""}, "statement"),
        ({**candidate, "status": "accepted"}, "status"),
        ({**candidate, "confidence": "certain"}, "confidence"),
        ({**candidate, "privacy_level": "public"}, "privacy"),
        ({**candidate, "analysis_ref": ""}, "analysis_ref"),
        ({**candidate, "contribution_ref": ""}, "contribution_ref"),
        ({**candidate, "evidence_refs": list(reversed(candidate["evidence_refs"]))}, "evidence_refs"),
        ({**candidate, "supporting_fact_refs": [candidate["supporting_fact_refs"][0]] * 2}, "supporting_fact_refs"),
        ({**candidate, "metadata": {}}, "candidate_version"),
        ({**candidate, "metadata": {"candidate_version": "v2"}}, "candidate_version"),
        ({**candidate, "metadata": {"candidate_version": "v1", "bad": object()}}, "JSON"),
    ]
    for bad, message in cases:
        with pytest.raises(ValueError, match=message):
            validate_career_claim_candidate(bad)


def test_generation_revalidates_accepted_node_edges_stale_refs_privacy_and_type() -> None:
    store, analysis = _store()
    assert generate_career_claim_candidates(store, analysis["id"])

    with pytest.raises(ValueError, match="analysis_id"):
        generate_career_claim_candidates(store, "")
    with pytest.raises(ValueError, match="not found"):
        generate_career_claim_candidates(store, "contribution_analysis:missing")

    wrong = knowledge_node(
        knowledge_type="TECHNOLOGY_EXPERIENCE",
        statement="Python",
        created_at=NOW,
        evidence_refs=analysis["properties"]["evidence_refs"][:1],
    )
    store.create_node(wrong)
    with pytest.raises(ValueError, match="ContributionAnalysis"):
        generate_career_claim_candidates(store, wrong["id"])

    stale_store, stale = _store()
    stale_store.nodes[stale["properties"]["contribution_ref"]]["properties"]["outcomes"] = []
    with pytest.raises(ValueError, match="current deterministic analysis"):
        generate_career_claim_candidates(stale_store, stale["id"])

    tampered_store, tampered = _store()
    tampered_store.nodes[tampered["id"]]["properties"]["impact_signals"][0]["value"] = 999
    with pytest.raises(ValueError, match="current deterministic analysis"):
        generate_career_claim_candidates(tampered_store, tampered["id"])

    missing_store, missing = _store()
    missing_store.nodes.pop(missing["properties"]["evidence_refs"][0])
    with pytest.raises(ValueError, match="missing node|missing Evidence"):
        generate_career_claim_candidates(missing_store, missing["id"])

    privacy_store, privacy = _store()
    privacy_store.nodes[privacy["properties"]["contribution_ref"]]["properties"]["privacy_level"] = "private"
    with pytest.raises(ValueError, match="current deterministic analysis"):
        generate_career_claim_candidates(privacy_store, privacy["id"])

    edge_store, edge_analysis = _store()
    edge_store.edges = []
    with pytest.raises(ValueError, match="Missing ContributionAnalysis edge"):
        generate_career_claim_candidates(edge_store, edge_analysis["id"])


def test_supporting_refs_are_stable_and_change_with_source_fact_or_signal() -> None:
    fact = {"fact_type": "explicit_action", "value": "reviewed retry behavior", "contribution_ref": "c"}
    same_fact = {"value": "reviewed retry behavior", "contribution_ref": "c", "fact_type": "explicit_action"}
    changed_fact = {**fact, "value": "reviewed timeout behavior"}
    signal = {"classification": "explicit_metric", "category": "latency", "value": 300, "unit": "ms"}
    changed_signal = {**signal, "value": 301}

    assert supporting_fact_ref(fact) == supporting_fact_ref(same_fact)
    assert supporting_fact_ref(fact) != supporting_fact_ref(changed_fact)
    assert supporting_signal_ref(signal) != supporting_signal_ref(changed_signal)
    assert career_claim_candidate_id("work_performed", "analysis:a", ["b", "a"]) == career_claim_candidate_id(
        "work_performed", "analysis:a", ["a", "b"]
    )


def test_constructor_preserves_explicit_empty_metadata_and_default_only_for_none() -> None:
    valid = {
        "claim_type": "work_performed",
        "statement": "Performed work recorded as: reviewed retry behavior.",
        "status": "proposed",
        "confidence": "high",
        "privacy_level": "internal",
        "analysis_ref": "contribution_analysis:a",
        "contribution_ref": "contribution:a",
        "evidence_refs": ["evidence:a"],
        "supporting_fact_refs": ["analysis_fact:a"],
    }

    assert career_claim_candidate(**valid)["metadata"] == {"candidate_version": "v1"}
    with pytest.raises(ValueError, match="candidate_version"):
        career_claim_candidate(**valid, metadata={})
    with pytest.raises(ValueError, match="candidate_version"):
        career_claim_candidate(**valid, metadata={"candidate_version": "v2"})


def test_pure_generation_validates_node_does_not_mutate_and_handles_no_candidate_or_unsupported_signal() -> None:
    store, analysis = _store()
    node = copy.deepcopy(analysis)
    node["properties"]["action_facts"] = []
    node["properties"]["outcome_facts"] = []
    node["properties"]["impact_signals"] = []
    before = copy.deepcopy(node)

    candidates = generate_career_claim_candidates_from_analysis(node)

    assert node == before
    assert candidates == []
    node["properties"]["impact_signals"] = [
        {
            "category": "latency",
            "classification": "structural_signal",
            "evidence_refs": node["properties"]["evidence_refs"][:1],
        }
    ]
    assert generate_career_claim_candidates_from_analysis(node) == []


@pytest.mark.parametrize("value", ["", "   "])
def test_pure_generation_skips_blank_explicit_action(value: str) -> None:
    store, analysis = _store()
    node = copy.deepcopy(analysis)
    node["properties"]["action_facts"] = [{"fact_type": "explicit_action", "value": value}]
    node["properties"]["outcome_facts"] = []
    node["properties"]["impact_signals"] = []

    assert generate_career_claim_candidates_from_analysis(node) == []


def test_pure_generation_skips_blank_explicit_outcome() -> None:
    store, analysis = _store()
    node = copy.deepcopy(analysis)
    node["properties"]["action_facts"] = []
    node["properties"]["outcome_facts"] = [{"fact_type": "explicit_outcome", "value": ""}]
    node["properties"]["impact_signals"] = []

    assert generate_career_claim_candidates_from_analysis(node) == []


@pytest.mark.parametrize(
    "signal",
    [
        {"classification": "explicit_metric", "category": "latency", "unit": "ms"},
        {"classification": "explicit_metric", "value": 1, "category": "", "unit": "ms"},
        {"classification": "explicit_metric", "value": 1, "category": "   ", "unit": "ms"},
        {"classification": "explicit_metric", "value": 1, "category": "latency", "unit": ""},
        {"classification": "explicit_metric", "value": 1, "category": "latency", "unit": "   "},
        {"classification": "explicit_metric", "value": True, "category": "latency", "unit": "ms"},
    ],
)
def test_pure_generation_skips_invalid_explicit_metric(signal: dict[str, Any]) -> None:
    store, analysis = _store()
    node = copy.deepcopy(analysis)
    node["properties"]["action_facts"] = []
    node["properties"]["outcome_facts"] = []
    node["properties"]["impact_signals"] = [signal]

    assert generate_career_claim_candidates_from_analysis(node) == []


def test_pure_generation_preserves_zero_metric_value() -> None:
    store, analysis = _store()
    node = copy.deepcopy(analysis)
    node["properties"]["action_facts"] = []
    node["properties"]["outcome_facts"] = []
    node["properties"]["impact_signals"] = [
        {"classification": "explicit_metric", "value": 0, "category": "latency", "unit": "ms"}
    ]

    candidates = generate_career_claim_candidates_from_analysis(node)

    assert len(candidates) == 1
    assert candidates[0]["statement"] == "Observed latency metric: 0 ms."
    assert candidates[0]["supporting_signal_refs"] == [supporting_signal_ref(node["properties"]["impact_signals"][0])]


def test_pipeline_and_artifacts_do_not_import_or_generate_claim_candidates() -> None:
    store, _ = run_pipeline("tests/fixtures/characterization_source_export.json")

    assert store.nodes_by_type("CareerClaim") == []
    assert store.nodes_by_type("CareerClaimCandidate") == []
    assert all("claim_candidate" not in edge["edge_type"].lower() for edge in store.edges)
