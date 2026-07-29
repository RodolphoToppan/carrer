from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from career_intelligence_mvp import run_pipeline
from carrer.contributions import (
    analyze_contribution,
    analyze_contribution_data,
    contribution_analysis_id,
    create_contribution,
    validate_contribution_analysis,
)
from carrer.domain.models import evidence_node, knowledge_node
from carrer.storage.json_graph_storage import JsonGraphStorage

NOW = "2026-01-02T03:04:05+00:00"


def _evidence(
    entity_type: str = "commit",
    entity_id: str = "C-1",
    *,
    occurred_at: str | None = NOW,
    privacy_level: str = "artifact_safe",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_type = {
        "work_item": "WORK_ITEM_EXISTS",
        "commit": "COMMIT_EXISTS",
        "pull_request": "MERGE_REQUEST_EXISTS",
        "merge_request": "MERGE_REQUEST_EXISTS",
        "review_comment": "REVIEW_COMMENT_CREATED",
        "documentation": "DOCUMENTATION_EXISTS",
    }[entity_type]
    return evidence_node(
        source_id="test",
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        evidence_type=evidence_type,
        captured_at=NOW,
        occurred_at=occurred_at,
        privacy_level=privacy_level,
        metadata=metadata or {},
    )


def _store_with(nodes: list[dict[str, Any]]) -> JsonGraphStorage:
    store = JsonGraphStorage()
    for node in nodes:
        store.create_node(node)
    return store


def _contribution(store: JsonGraphStorage, evidence_refs: list[str], **kwargs: Any) -> dict[str, Any]:
    data = {
        "contribution_type": "incident_fix",
        "created_at": NOW,
        "title": "Retry fix",
        "evidence_refs": evidence_refs,
        "started_at": "2026-01-01T10:00:00Z",
        "ended_at": "2026-01-01T09:30:00-01:00",
        "actions": ["reviewed retry behavior"],
        "outcomes": [],
        "metadata": {"reviewed": True},
    }
    data.update(kwargs)
    return create_contribution(store, **data)["contribution"]


def _fact_values(analysis: dict[str, Any], field: str, fact_type: str) -> list[Any]:
    return [fact["value"] for fact in analysis[field] if fact["fact_type"] == fact_type]


def test_analyze_contribution_builds_read_only_structural_analysis() -> None:
    work = _evidence("work_item", "WI-1", privacy_level="internal", metadata={"state": "closed", "project": "Carrer"})
    commit = _evidence(
        "commit",
        "C-1",
        metadata={
            "message": "implement retry",
            "repository": "carrer",
            "branch": "feature/retry",
            "latency_after_ms": 300,
            "duration": 2,
        },
    )
    mr = _evidence(
        "merge_request",
        "MR-1",
        metadata={
            "state": "merged",
            "source_branch": "feature/retry",
            "target_branch": "main",
            "metrics": {"error_count": 4},
        },
    )
    store = _store_with([mr, commit, work])
    contribution = _contribution(store, sorted([work["id"], commit["id"], mr["id"]]))
    before = copy.deepcopy({"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records})

    analysis = analyze_contribution(store, contribution["id"])

    assert validate_contribution_analysis(analysis) is analysis
    assert analysis["id"] == contribution_analysis_id(contribution["id"], contribution["properties"]["evidence_refs"])
    assert analysis["privacy_level"] == "internal"
    assert analysis["confidence"] == "high"
    assert analysis["status"] == "proposed"
    assert _fact_values(analysis, "context_facts", "repository") == ["carrer"]
    assert _fact_values(analysis, "context_facts", "project") == ["Carrer"]
    assert "feature/retry" in _fact_values(analysis, "context_facts", "branch")
    assert _fact_values(analysis, "context_facts", "work_item") == ["WI-1"]
    assert "commit_created" in {fact["fact_type"] for fact in analysis["action_facts"]}
    assert "merge_request_opened" in {fact["fact_type"] for fact in analysis["action_facts"]}
    assert "work_item_closed" in {fact["fact_type"] for fact in analysis["outcome_facts"]}
    assert "merge_request_merged" in {fact["fact_type"] for fact in analysis["outcome_facts"]}
    assert {
        (signal["category"], signal["value"], signal["unit"], signal["classification"])
        for signal in analysis["impact_signals"]
    } == {
        ("latency", 300, "ms", "explicit_metric"),
        ("reliability", 4, "count", "explicit_metric"),
    }
    assert "duration" not in {signal["metadata"]["field"] for signal in analysis["impact_signals"]}
    assert store.nodes == before["nodes"]
    assert store.edges == before["edges"]
    assert store.audit_records == before["audit_records"]


def test_analysis_is_deterministic_and_lists_are_ordered() -> None:
    commit = _evidence("commit", "C-1", metadata={"repository": "repo", "branch": "b", "latency_after_ms": 10})
    mr = _evidence("merge_request", "MR-1", metadata={"state": "merged", "source_branch": "b"})
    store = _store_with([mr, commit])
    contribution = _contribution(
        store,
        sorted([mr["id"], commit["id"]]),
        actions=[],
        outcomes=["deployed"],
    )

    first = analyze_contribution(store, contribution["id"])
    second = analyze_contribution(store, contribution["id"])

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["evidence_refs"] == sorted(first["evidence_refs"])
    assert first["reasons"] == sorted(first["reasons"])
    assert first["warnings"] == sorted(first["warnings"])


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing_contribution", "not found"),
        ("wrong_node_type", "Contribution"),
        ("bad_properties", "properties"),
        ("empty_refs", "evidence_refs"),
        ("duplicate_refs", "evidence_refs"),
        ("missing_evidence", "missing node"),
        ("wrong_evidence_type", "EvidenceNode"),
        ("bad_date", "started_at"),
        ("date_without_timezone", "timezone"),
        ("inverted_range", "before or equal"),
        ("bad_privacy", "privacy"),
        ("bad_confidence", "confidence"),
        ("bad_metadata", "JSON"),
    ],
)
def test_revalidation_rejects_invalid_contribution_and_evidence(case: str, message: str) -> None:
    evidence = _evidence()
    store = _store_with([evidence])
    contribution = _contribution(store, [evidence["id"]])
    if case == "missing_contribution":
        store.nodes.pop(contribution["id"])
    elif case == "wrong_node_type":
        contribution.update(node_type="KnowledgeNode")
    elif case == "bad_properties":
        contribution.update(properties=[])
    elif case == "empty_refs":
        contribution["properties"].update(evidence_refs=[])
    elif case == "duplicate_refs":
        contribution["properties"].update(evidence_refs=[evidence["id"], evidence["id"]])
    elif case == "missing_evidence":
        store.nodes.pop(evidence["id"])
    elif case == "wrong_evidence_type":
        store.nodes[evidence["id"]].update(node_type="KnowledgeNode")
    elif case == "bad_date":
        contribution["properties"].update(started_at="not-a-date")
    elif case == "date_without_timezone":
        contribution["properties"].update(started_at="2026-01-01T00:00:00")
    elif case == "inverted_range":
        contribution["properties"].update(started_at="2026-01-02T00:00:00Z", ended_at="2026-01-01T00:00:00Z")
    elif case == "bad_privacy":
        contribution["properties"].update(privacy_level="public")
    elif case == "bad_confidence":
        contribution["properties"].update(confidence="certain")
    elif case == "bad_metadata":
        contribution["properties"].update(metadata={"bad": object()})

    with pytest.raises(ValueError, match=message):
        analyze_contribution(store, contribution["id"])


def test_revalidation_rejects_wrong_node_id_type_and_bad_evidence_payload() -> None:
    evidence = _evidence(metadata={"state": "open"})
    wrong = knowledge_node(
        knowledge_type="TECHNOLOGY_EXPERIENCE",
        statement="Python",
        created_at=NOW,
        evidence_refs=[evidence["id"]],
    )
    store = _store_with([evidence, wrong])
    contribution = _contribution(store, [evidence["id"]])

    with pytest.raises(ValueError, match="Contribution"):
        analyze_contribution(store, wrong["id"])
    store.nodes[evidence["id"]]["properties"]["occurred_at"] = "2026-01-01T00:00:00"
    with pytest.raises(ValueError, match="occurred_at must include a timezone"):
        analyze_contribution(store, contribution["id"])
    store.nodes[evidence["id"]]["properties"]["occurred_at"] = NOW
    store.nodes[evidence["id"]]["properties"]["metadata"] = []
    with pytest.raises(ValueError, match="metadata must be an object"):
        analyze_contribution(store, contribution["id"])


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("wrong_type", "Contribution"),
        ("timezone", "timezone"),
        ("privacy", "privacy"),
        ("metadata", "JSON"),
    ],
)
def test_analyze_contribution_data_applies_public_api_revalidation(case: str, message: str) -> None:
    evidence = _evidence()
    store = _store_with([evidence])
    contribution = _contribution(store, [evidence["id"]])
    if case == "wrong_type":
        contribution.update(node_type="KnowledgeNode")
    elif case == "timezone":
        contribution["properties"].update(started_at="2026-01-01T00:00:00")
    elif case == "privacy":
        contribution["properties"].update(privacy_level="public")
    elif case == "metadata":
        contribution["properties"].update(metadata={"bad": object()})

    with pytest.raises(ValueError, match=message):
        analyze_contribution_data(contribution, [evidence])


def test_outcomes_are_only_explicit_and_absence_warns() -> None:
    commit = _evidence("commit", "C-1", metadata={"message": "created commit"})
    open_mr = _evidence("merge_request", "MR-1", metadata={"state": "opened"})
    published_doc = _evidence("documentation", "D-1", metadata={"status": "published"})
    store = _store_with([commit, open_mr, published_doc])
    contribution = _contribution(
        store,
        sorted([commit["id"], open_mr["id"], published_doc["id"]]),
        actions=[],
        outcomes=[],
        started_at=None,
        ended_at=None,
    )

    analysis = analyze_contribution(store, contribution["id"])

    assert "documentation_published" in {fact["fact_type"] for fact in analysis["outcome_facts"]}
    assert "merge_request_merged" not in {fact["fact_type"] for fact in analysis["outcome_facts"]}
    assert "feature_delivered" not in {fact["fact_type"] for fact in analysis["outcome_facts"]}
    assert "missing_work_dates" in analysis["warnings"]


def test_no_outcome_no_metric_and_single_evidence_are_low_confidence_warnings() -> None:
    commit = _evidence("commit", "C-1", metadata={"message": "improved latency significantly", "latency": 300})
    store = _store_with([commit])
    contribution = _contribution(store, [commit["id"]], actions=[], started_at=None, ended_at=None)

    analysis = analyze_contribution(store, contribution["id"])

    assert analysis["confidence"] == "low"
    assert analysis["status"] == "review_required"
    assert analysis["outcome_facts"] == []
    assert analysis["impact_signals"] == []
    assert analysis["warnings"] == [
        "missing_work_dates",
        "no_explicit_actions",
        "no_explicit_impact_signal",
        "no_explicit_outcome_evidence",
        "single_evidence_only",
    ]


def test_metrics_are_strictly_structural_with_known_fields_and_structured_objects() -> None:
    commit = _evidence(
        "commit",
        "C-1",
        metadata={
            "latency_after_ms": 300,
            "error_count": 4,
            "coverage_percent": 87.5,
            "custom_metric": {"value": 12, "unit": "deployments", "category": "operational_efficiency"},
            "discount_cost": 10,
            "estimated_latency": 250,
            "duration": 2,
            "coverage": 88,
        },
    )
    mr = _evidence("merge_request", "MR-1", metadata={"state": "merged"})
    store = _store_with([commit, mr])
    contribution = _contribution(store, sorted([commit["id"], mr["id"]]))

    analysis = analyze_contribution(store, contribution["id"])

    assert {
        (signal["metadata"]["field"], signal["category"], signal["value"], signal["unit"])
        for signal in analysis["impact_signals"]
    } == {
        ("latency_after_ms", "latency", 300, "ms"),
        ("error_count", "reliability", 4, "count"),
        ("coverage_percent", "quality", 87.5, "percent"),
        ("custom_metric", "operational_efficiency", 12, "deployments"),
    }


def test_medium_confidence_requires_actions_and_outcomes_without_metric() -> None:
    mr = _evidence("merge_request", "MR-1", metadata={"state": "merged"})
    store = _store_with([mr])
    contribution = _contribution(store, [mr["id"]], actions=[])

    analysis = analyze_contribution(store, contribution["id"])

    assert analysis["confidence"] == "medium"
    assert analysis["reasons"] == ["actions_present", "explicit_outcome_present", "no_explicit_metric"]


@pytest.mark.parametrize(
    ("started_at", "ended_at"),
    [
        ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        ("2026-01-01T10:00:00+02:00", "2026-01-01T07:30:00-03:00"),
        ("2026-01-01T01:00:00-03:00", "2026-01-01T05:00:00+00:00"),
        (None, None),
    ],
)
def test_dates_accept_offsets_and_preserve_original_strings(started_at: str | None, ended_at: str | None) -> None:
    evidence = _evidence(occurred_at="2026-01-01T00:00:00Z")
    store = _store_with([evidence])
    contribution = _contribution(store, [evidence["id"]], started_at=started_at, ended_at=ended_at)

    analysis = analyze_contribution(store, contribution["id"])

    if started_at or ended_at:
        assert _fact_values(analysis, "context_facts", "time_range") == [
            {"started_at": started_at, "ended_at": ended_at}
        ]


def test_privacy_private_and_internal_precedence_and_sources_not_mutated() -> None:
    public = _evidence("commit", "C-1", privacy_level="artifact_safe")
    internal = _evidence("work_item", "WI-1", privacy_level="internal")
    private = _evidence("merge_request", "MR-1", privacy_level="private", metadata={"state": "merged"})
    store = _store_with([public, internal, private])
    contribution = _contribution(store, sorted([public["id"], internal["id"], private["id"]]), privacy_level="exported")
    before = copy.deepcopy(store.nodes)

    analysis = analyze_contribution(store, contribution["id"])

    assert analysis["privacy_level"] == "private"
    assert store.nodes == before


def test_compatibility_previous_flows_do_not_run_analysis_or_change_contracts() -> None:
    store, _ = run_pipeline("tests/fixtures/characterization_source_export.json")

    assert store.nodes_by_type("Contribution") == []
    assert store.nodes_by_type("ContributionAnalysis") == []
    assert all("analysis" not in edge["edge_type"].lower() for edge in store.edges)
