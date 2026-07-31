"""Explicit review and persistence for deterministic ContributionAnalysis."""

from __future__ import annotations

import copy
import json
from typing import Any, cast

from carrer.contributions.analysis import analyze_contribution, parse_iso8601_with_timezone
from carrer.contributions.analysis_contracts import ANALYSIS_VERSION, validate_contribution_analysis
from carrer.domain.enums import REVIEW_STATUSES
from carrer.domain.privacy import most_restrictive
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION = "CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION"
CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE = "CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE"

_REVIEWABLE_STATUSES = frozenset({"proposed", "review_required"})
_COMPARISON_ERROR = "ContributionAnalysis does not match current deterministic analysis"


def accept_contribution_analysis(
    store: GraphStore,
    analysis: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
) -> dict[str, Any]:
    _require_actor(decision_actor)
    parse_iso8601_with_timezone(decided_at, "decided_at")
    current = _current_matching_analysis(store, analysis)
    node = _accepted_node(current, decision_actor=decision_actor, decided_at=decided_at)
    existing = store.nodes.get(node["id"])
    if existing is not None:
        persisted = validate_persisted_contribution_analysis(existing)
        _ensure_same_accepted_analysis(persisted, node)
        created = False
    else:
        persisted, created = store.create_node(node)
        validate_persisted_contribution_analysis(persisted)

    store.create_edge(CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION, persisted["id"], current["contribution_ref"])
    for ref in current["evidence_refs"]:
        store.create_edge(CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE, persisted["id"], ref)
    _audit_acceptance(store, persisted, decision_actor=decision_actor, decided_at=decided_at, created=created)
    return {"analysis": persisted, "decision": "accepted", "created": created}


def reject_contribution_analysis(
    store: GraphStore,
    analysis: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    reason: str = "",
) -> dict[str, Any]:
    _require_actor(decision_actor)
    parse_iso8601_with_timezone(decided_at, "decided_at")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")
    current = _current_matching_analysis(store, analysis)
    store.append_audit_record(
        "contribution_analysis_rejected",
        [current["id"], current["contribution_ref"]],
        "rejected",
        {
            "analysis_id": current["id"],
            "contribution_id": current["contribution_ref"],
            "actor": decision_actor,
            "decided_at": decided_at,
            "reason": reason,
            "confidence": current["confidence"],
            "evidence_refs": len(current["evidence_refs"]),
        },
    )
    return {
        "analysis_id": current["id"],
        "contribution_ref": current["contribution_ref"],
        "decision": "rejected",
        "reason": reason,
    }


def get_contribution_analysis(store: GraphStore, analysis_id: str) -> dict[str, Any] | None:
    if not isinstance(analysis_id, str) or not analysis_id:
        raise ValueError("analysis_id is required")
    node = store.nodes.get(analysis_id)
    if node is None or node.get("node_type") != "ContributionAnalysis":
        return None
    return validate_persisted_contribution_analysis(node)


def list_contribution_analyses(
    store: GraphStore,
    *,
    contribution_ref: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    if contribution_ref is not None and (not isinstance(contribution_ref, str) or not contribution_ref):
        raise ValueError("contribution_ref is required")
    if status is not None and (not isinstance(status, str) or status not in REVIEW_STATUSES):
        raise ValueError(f"Invalid status: {status}")
    nodes = [validate_persisted_contribution_analysis(node) for node in store.nodes_by_type("ContributionAnalysis")]
    if contribution_ref is not None:
        nodes = [node for node in nodes if node["properties"]["contribution_ref"] == contribution_ref]
    if status is not None:
        nodes = [node for node in nodes if node["properties"]["status"] == status]
    return sorted(nodes, key=lambda node: node["id"])


def validate_persisted_contribution_analysis(node: object) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ValueError("ContributionAnalysis node must be a dict")
    if not isinstance(node.get("id"), str) or not node["id"]:
        raise ValueError("id is required")
    if node.get("node_type") != "ContributionAnalysis":
        raise ValueError("node_type must be ContributionAnalysis")
    parse_iso8601_with_timezone(node.get("created_at"), "created_at")
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    if props.get("status") != "accepted":
        raise ValueError("ContributionAnalysis node status must be accepted")
    if not isinstance(props.get("review_actor"), str) or not props["review_actor"].strip():
        raise ValueError("review_actor is required")
    parse_iso8601_with_timezone(props.get("reviewed_at"), "reviewed_at")
    if props.get("analysis_version") != ANALYSIS_VERSION:
        raise ValueError("Invalid analysis_version")
    valid = validate_contribution_analysis(_analysis_from_node(node))
    if node["id"] != valid["id"]:
        raise ValueError("ContributionAnalysis node id does not match properties id")
    if valid["status"] != "accepted":
        raise ValueError("ContributionAnalysis node status must be accepted")
    try:
        json.dumps(node, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("ContributionAnalysis node must be JSON serializable") from exc
    return node


def _current_matching_analysis(store: GraphStore, analysis: object) -> dict[str, Any]:
    if not isinstance(analysis, dict):
        raise ValueError("ContributionAnalysis must be a dict")
    valid = validate_contribution_analysis(analysis)
    if valid["status"] not in _REVIEWABLE_STATUSES:
        raise ValueError(f"ContributionAnalysis status is not reviewable: {valid['status']}")
    current = analyze_contribution(store, valid["contribution_ref"])
    if _canonical_json(valid) != _canonical_json(current):
        raise ValueError(_COMPARISON_ERROR)
    _confirm_current_privacy(store, current)
    return current


def _accepted_node(analysis: dict[str, Any], *, decision_actor: str, decided_at: str) -> dict[str, Any]:
    props = copy.deepcopy(analysis)
    props["status"] = "accepted"
    props["analysis_version"] = props["metadata"]["analysis_version"]
    props["review_actor"] = decision_actor
    props["reviewed_at"] = decided_at
    return {
        "id": analysis["id"],
        "node_type": "ContributionAnalysis",
        "created_at": decided_at,
        "properties": props,
    }


def _analysis_from_node(node: dict[str, Any]) -> dict[str, Any]:
    props = cast(dict[str, Any], copy.deepcopy(node["properties"]))
    props.pop("review_actor", None)
    props.pop("reviewed_at", None)
    props.pop("analysis_version", None)
    return props


def _ensure_same_accepted_analysis(existing: dict[str, Any], expected: dict[str, Any]) -> None:
    existing_analysis = _analysis_from_node(existing)
    expected_analysis = _analysis_from_node(expected)
    if _canonical_json(existing_analysis) != _canonical_json(expected_analysis):
        raise ValueError("Existing ContributionAnalysis node has incompatible content")


def _confirm_current_privacy(store: GraphStore, analysis: dict[str, Any]) -> None:
    contribution = store.nodes[analysis["contribution_ref"]]
    evidence = [store.nodes[ref] for ref in analysis["evidence_refs"]]
    expected = most_restrictive(
        [
            contribution["properties"]["privacy_level"],
            *(node["properties"]["privacy_level"] for node in evidence),
        ]
    )
    if analysis["privacy_level"] != expected:
        raise ValueError("ContributionAnalysis privacy does not match current Contribution and Evidence")


def _audit_acceptance(
    store: GraphStore,
    node: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    created: bool,
) -> None:
    props = node["properties"]
    store.append_audit_record(
        "contribution_analysis_accepted",
        [node["id"], props["contribution_ref"]],
        "accepted",
        {
            "analysis_id": node["id"],
            "contribution_id": props["contribution_ref"],
            "actor": decision_actor,
            "decided_at": decided_at,
            "created": created,
            "confidence": props["confidence"],
            "privacy_level": props["privacy_level"],
            "evidence_refs": len(props["evidence_refs"]),
            "context_facts": len(props["context_facts"]),
            "action_facts": len(props["action_facts"]),
            "outcome_facts": len(props["outcome_facts"]),
            "impact_signals": len(props["impact_signals"]),
            "status": props["status"],
        },
    )


def _require_actor(actor: object) -> None:
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("decision_actor is required")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
