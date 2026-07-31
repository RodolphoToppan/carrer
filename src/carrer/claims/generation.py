"""Deterministic, read-only CareerClaimCandidate generation."""

from __future__ import annotations

import copy
import json
from typing import Any, cast

from carrer.claims.candidates import (
    CANDIDATE_VERSION,
    career_claim_candidate,
    supporting_fact_ref,
    supporting_signal_ref,
    validate_career_claim_candidate,
)
from carrer.contributions.analysis import analyze_contribution
from carrer.contributions.analysis_review import (
    CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION,
    CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE,
    validate_persisted_contribution_analysis,
)
from carrer.domain.privacy import most_restrictive
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
_ACTION_STATEMENTS = {
    "commit_created": "A commit associated with the contribution was created.",
    "merge_request_opened": "A merge request associated with the contribution was opened.",
    "review_comment_added": "A review comment associated with the contribution was added.",
    "documentation_created": "Documentation associated with the contribution was created.",
    "work_item_updated": "A work item associated with the contribution was updated.",
}
_OUTCOME_STATEMENTS = {
    "merge_request_merged": "A merge request associated with the contribution was merged.",
    "work_item_closed": "A work item associated with the contribution was closed.",
    "documentation_published": "Documentation associated with the contribution was published.",
    "deployment_completed": "A deployment associated with the contribution was completed.",
    "test_passed": "A test associated with the contribution passed.",
}


def generate_career_claim_candidates(store: GraphStore, analysis_id: str) -> list[dict[str, Any]]:
    if not isinstance(analysis_id, str) or not analysis_id:
        raise ValueError("analysis_id is required")
    node = store.nodes.get(analysis_id)
    if node is None:
        raise ValueError(f"ContributionAnalysis not found: {analysis_id}")
    accepted = validate_persisted_contribution_analysis(node)
    _revalidate_current_store_state(store, accepted)
    before = _store_snapshot(store)
    candidates = generate_career_claim_candidates_from_analysis(accepted)
    if _store_snapshot(store) != before:
        raise ValueError("CareerClaimCandidate generation must be read-only")
    return candidates


def generate_career_claim_candidates_from_analysis(analysis_node: object) -> list[dict[str, Any]]:
    node = validate_persisted_contribution_analysis(analysis_node)
    analysis = _analysis_from_node(node)
    candidates = [
        *_action_candidates(analysis),
        *_outcome_candidates(analysis),
        *_metric_candidates(analysis),
    ]
    return sorted(_dedupe_candidates(candidates), key=lambda candidate: candidate["id"])


def _action_candidates(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for fact in analysis["action_facts"]:
        fact_type = fact.get("fact_type")
        if fact_type == "explicit_action" and _usable_text(fact.get("value")):
            result.append(
                _candidate(
                    analysis,
                    claim_type="work_performed",
                    statement=f"Performed work recorded as: {fact['value']}.",
                    fact=fact,
                    status="proposed",
                    rule_confidence="high",
                    reasons=["explicit_action_fact"],
                    warnings=_base_warnings(analysis),
                    metadata={"candidate_version": CANDIDATE_VERSION, "source_fact_type": fact_type},
                )
            )
        elif fact_type in _ACTION_STATEMENTS:
            result.append(
                _candidate(
                    analysis,
                    claim_type="work_performed",
                    statement=_ACTION_STATEMENTS[fact_type],
                    fact=fact,
                    status="review_required",
                    rule_confidence="medium",
                    reasons=["structural_action_fact"],
                    warnings=[*_base_warnings(analysis), "structural_action_only"],
                    metadata={"candidate_version": CANDIDATE_VERSION, "source_fact_type": fact_type},
                )
            )
    return result


def _outcome_candidates(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for fact in analysis["outcome_facts"]:
        fact_type = fact.get("fact_type")
        if fact_type == "explicit_outcome" and _usable_text(fact.get("value")):
            statement = f"Recorded outcome: {fact['value']}."
            status = "proposed"
            confidence = "high"
            reasons = ["explicit_outcome_fact"]
            warnings = _base_warnings(analysis)
        elif fact_type in _OUTCOME_STATEMENTS:
            statement = _OUTCOME_STATEMENTS[fact_type]
            status = "review_required"
            confidence = "medium"
            reasons = ["structural_outcome_fact"]
            warnings = [*_base_warnings(analysis), "structural_outcome_only"]
        else:
            continue
        result.append(
            _candidate(
                analysis,
                claim_type="outcome_achieved",
                statement=statement,
                fact=fact,
                status=status,
                rule_confidence=confidence,
                reasons=reasons,
                warnings=warnings,
                metadata={"candidate_version": CANDIDATE_VERSION, "source_fact_type": fact_type},
            )
        )
    return result


def _metric_candidates(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for signal in analysis["impact_signals"]:
        if not _usable_metric_signal(signal):
            continue
        result.append(
            _candidate(
                analysis,
                claim_type="metric_observed",
                statement=f"Observed {signal['category']} metric: {signal['value']} {signal['unit']}.",
                signal=signal,
                status="proposed",
                rule_confidence="high",
                reasons=["explicit_metric_signal"],
                warnings=[*_base_warnings(analysis), "metric_is_observation_not_impact"],
                metadata={
                    "candidate_version": CANDIDATE_VERSION,
                    "source_signal_classification": signal["classification"],
                },
            )
        )
    return result


def _usable_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _usable_metric_signal(signal: dict[str, Any]) -> bool:
    value = signal.get("value")
    return (
        signal.get("classification") == "explicit_metric"
        and isinstance(value, int | float)
        and not isinstance(value, bool)
        and isinstance(signal.get("category"), str)
        and bool(signal["category"].strip())
        and isinstance(signal.get("unit"), str)
        and bool(signal["unit"].strip())
    )


def _candidate(
    analysis: dict[str, Any],
    *,
    claim_type: str,
    statement: str,
    status: str,
    rule_confidence: str,
    reasons: list[str],
    warnings: list[str],
    metadata: dict[str, Any],
    fact: dict[str, Any] | None = None,
    signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fact_refs = [] if fact is None else [supporting_fact_ref(fact)]
    signal_refs = [] if signal is None else [supporting_signal_ref(signal)]
    return career_claim_candidate(
        claim_type=claim_type,
        statement=statement,
        status=status,
        confidence=_min_confidence(rule_confidence, analysis["confidence"]),
        privacy_level=analysis["privacy_level"],
        analysis_ref=analysis["id"],
        contribution_ref=analysis["contribution_ref"],
        evidence_refs=_support_evidence_refs(analysis, fact, signal),
        supporting_fact_refs=fact_refs,
        supporting_signal_refs=signal_refs,
        reasons=[*reasons, "confidence_capped_by_analysis"],
        warnings=warnings,
        metadata=metadata,
    )


def _support_evidence_refs(
    analysis: dict[str, Any], fact: dict[str, Any] | None, signal: dict[str, Any] | None
) -> list[str]:
    refs = []
    for item in (fact, signal):
        if item is not None and isinstance(item.get("evidence_refs"), list):
            refs.extend(item["evidence_refs"])
    return refs or analysis["evidence_refs"]


def _base_warnings(analysis: dict[str, Any]) -> list[str]:
    warnings = []
    if analysis["warnings"]:
        warnings.append("analysis_contains_warnings")
    if len(analysis["evidence_refs"]) == 1:
        warnings.append("single_evidence_support")
    if any(signal.get("classification") != "explicit_metric" for signal in analysis["impact_signals"]):
        warnings.append("unsupported_impact_signal_classification")
    return warnings


def _min_confidence(left: str, right: str) -> str:
    return left if _CONFIDENCE_ORDER[left] <= _CONFIDENCE_ORDER[right] else right


def _revalidate_current_store_state(store: GraphStore, node: dict[str, Any]) -> None:
    analysis = _analysis_from_node(node)
    contribution = store.nodes.get(analysis["contribution_ref"])
    if contribution is None:
        raise ValueError(f"Contribution not found: {analysis['contribution_ref']}")
    current = analyze_contribution(store, analysis["contribution_ref"])
    if _analysis_for_comparison(analysis) != _analysis_for_comparison(current):
        raise ValueError("ContributionAnalysis does not match current deterministic analysis")
    evidence = [store.nodes.get(ref) for ref in analysis["evidence_refs"]]
    if any(item is None for item in evidence):
        raise ValueError("ContributionAnalysis references missing Evidence")
    if any(item.get("node_type") != "EvidenceNode" for item in evidence if item is not None):
        raise ValueError("ContributionAnalysis evidence_refs require EvidenceNode")
    expected_privacy = most_restrictive(
        [
            contribution["properties"]["privacy_level"],
            *(item["properties"]["privacy_level"] for item in evidence if item is not None),
        ]
    )
    if analysis["privacy_level"] != expected_privacy:
        raise ValueError("ContributionAnalysis privacy does not match current Contribution and Evidence")
    _require_edge(store, CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION, analysis["id"], analysis["contribution_ref"])
    for ref in analysis["evidence_refs"]:
        _require_edge(store, CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE, analysis["id"], ref)


def _require_edge(store: GraphStore, edge_type: str, from_node_id: str, to_node_id: str) -> None:
    if not any(
        edge.get("edge_type") == edge_type
        and edge.get("from_node_id") == from_node_id
        and edge.get("to_node_id") == to_node_id
        for edge in store.edges
    ):
        raise ValueError(f"Missing ContributionAnalysis edge: {edge_type}")


def _analysis_from_node(node: dict[str, Any]) -> dict[str, Any]:
    props = cast(dict[str, Any], copy.deepcopy(node["properties"]))
    props.pop("review_actor", None)
    props.pop("reviewed_at", None)
    props.pop("analysis_version", None)
    return props


def _analysis_for_comparison(analysis: dict[str, Any]) -> str:
    comparable = copy.deepcopy(analysis)
    comparable["status"] = "accepted"
    return json.dumps(comparable, sort_keys=True, separators=(",", ":"))


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {candidate["id"]: validate_career_claim_candidate(candidate) for candidate in candidates}
    return [by_id[key] for key in sorted(by_id)]


def _store_snapshot(store: GraphStore) -> str:
    return json.dumps(
        {"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records}, sort_keys=True
    )
