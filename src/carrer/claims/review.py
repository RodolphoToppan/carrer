"""Explicit review and persistence for deterministic CareerClaimCandidate."""

from __future__ import annotations

import copy
import json
from typing import Any

from carrer.claims.candidates import validate_career_claim_candidate
from carrer.claims.generation import generate_career_claim_candidates
from carrer.contributions.analysis import parse_iso8601_with_timezone
from carrer.domain.models import career_claim_node
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

CAREER_CLAIM_DERIVED_FROM_ANALYSIS = "CAREER_CLAIM_DERIVED_FROM_ANALYSIS"
CAREER_CLAIM_FROM_CONTRIBUTION = "CAREER_CLAIM_FROM_CONTRIBUTION"
CAREER_CLAIM_SUPPORTED_BY_EVIDENCE = "CAREER_CLAIM_SUPPORTED_BY_EVIDENCE"

_COMPARISON_ERROR = "CareerClaimCandidate does not match current deterministic candidate"


def accept_career_claim_candidate(
    store: GraphStore,
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
) -> dict[str, Any]:
    _require_actor(decision_actor)
    parse_iso8601_with_timezone(decided_at, "decided_at")
    current = _current_matching_candidate(store, candidate)
    node = _claim_node(current, decision_actor=decision_actor, decided_at=decided_at)
    existing = store.nodes.get(node["id"])
    if existing is None:
        persisted, created = store.create_node(node)
        validate_persisted_career_claim(persisted)
    else:
        persisted = validate_persisted_career_claim(existing)
        _ensure_same_claim(persisted, node)
        created = False

    store.create_edge(CAREER_CLAIM_DERIVED_FROM_ANALYSIS, persisted["id"], current["analysis_ref"])
    store.create_edge(CAREER_CLAIM_FROM_CONTRIBUTION, persisted["id"], current["contribution_ref"])
    for ref in current["evidence_refs"]:
        store.create_edge(CAREER_CLAIM_SUPPORTED_BY_EVIDENCE, persisted["id"], ref)
    _audit_acceptance(store, persisted, current, decision_actor=decision_actor, decided_at=decided_at, created=created)
    return {
        "claim": persisted,
        "candidate_id": current["id"],
        "decision": "accepted",
        "created": created,
    }


def reject_career_claim_candidate(
    store: GraphStore,
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    reason: str = "",
) -> dict[str, Any]:
    _require_actor(decision_actor)
    parse_iso8601_with_timezone(decided_at, "decided_at")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")
    current = _current_matching_candidate(store, candidate)
    store.append_audit_record(
        "career_claim_candidate_rejected",
        [current["id"], current["analysis_ref"], current["contribution_ref"]],
        "rejected",
        {
            "candidate_id": current["id"],
            "analysis_id": current["analysis_ref"],
            "contribution_id": current["contribution_ref"],
            "actor": decision_actor,
            "decided_at": decided_at,
            "reason": reason,
            "claim_type": current["claim_type"],
            "confidence": current["confidence"],
            "evidence_refs": len(current["evidence_refs"]),
        },
    )
    return {
        "candidate_id": current["id"],
        "analysis_ref": current["analysis_ref"],
        "contribution_ref": current["contribution_ref"],
        "decision": "rejected",
        "reason": reason,
    }


def validate_persisted_career_claim(node: object) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ValueError("CareerClaim node must be a dict")
    parse_iso8601_with_timezone(node.get("created_at"), "created_at")
    if node.get("node_type") != "CareerClaim":
        raise ValueError("node_type must be CareerClaim")
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    if props.get("status") != "accepted":
        raise ValueError("CareerClaim status must be accepted")
    if not isinstance(props.get("review_actor"), str) or not props["review_actor"].strip():
        raise ValueError("review_actor is required")
    parse_iso8601_with_timezone(props.get("reviewed_at"), "reviewed_at")
    metadata = props.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    candidate_metadata = metadata.get("candidate_metadata")
    if not isinstance(candidate_metadata, dict):
        raise ValueError("candidate_metadata must be an object")
    if metadata.get("candidate_version") != candidate_metadata.get("candidate_version"):
        raise ValueError("candidate_version must match candidate_metadata.candidate_version")
    candidate = {
        "id": metadata.get("candidate_id"),
        "claim_type": props.get("claim_type"),
        "statement": props.get("statement"),
        "status": metadata.get("candidate_status"),
        "confidence": props.get("confidence"),
        "privacy_level": props.get("privacy_level"),
        "analysis_ref": metadata.get("analysis_ref"),
        "contribution_ref": _single_ref(props.get("contribution_refs"), "contribution_refs"),
        "evidence_refs": props.get("evidence_refs"),
        "supporting_fact_refs": metadata.get("supporting_fact_refs"),
        "supporting_signal_refs": metadata.get("supporting_signal_refs"),
        "reasons": metadata.get("reasons"),
        "warnings": metadata.get("warnings"),
        "metadata": candidate_metadata,
    }
    validate_career_claim_candidate(candidate)
    valid = career_claim_node(
        created_at=node["created_at"],
        claim_type=props["claim_type"],
        statement=props["statement"],
        contribution_refs=props["contribution_refs"],
        evidence_refs=props["evidence_refs"],
        status=props["status"],
        confidence=props["confidence"],
        privacy_level=props["privacy_level"],
        audience=props.get("audience", ""),
        metadata=metadata,
    )
    if valid["id"] != node.get("id"):
        raise ValueError("CareerClaim node id does not match stable identity")
    if valid["id"] != node["id"]:
        raise ValueError("CareerClaim envelope id does not match contract id")
    try:
        json.dumps(node, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("CareerClaim node must be JSON serializable") from exc
    return node


def _current_matching_candidate(store: GraphStore, candidate: object) -> dict[str, Any]:
    valid = validate_career_claim_candidate(candidate)
    current = {item["id"]: item for item in generate_career_claim_candidates(store, valid["analysis_ref"])}.get(
        valid["id"]
    )
    if current is None or _canonical_json(valid) != _canonical_json(current):
        raise ValueError(_COMPARISON_ERROR)
    return current


def _claim_node(candidate: dict[str, Any], *, decision_actor: str, decided_at: str) -> dict[str, Any]:
    node = career_claim_node(
        created_at=decided_at,
        claim_type=candidate["claim_type"],
        statement=candidate["statement"],
        contribution_refs=[candidate["contribution_ref"]],
        evidence_refs=copy.deepcopy(candidate["evidence_refs"]),
        status="accepted",
        confidence=candidate["confidence"],
        privacy_level=candidate["privacy_level"],
        metadata={
            "analysis_ref": candidate["analysis_ref"],
            "candidate_id": candidate["id"],
            "candidate_status": candidate["status"],
            "candidate_version": candidate["metadata"]["candidate_version"],
            "supporting_fact_refs": copy.deepcopy(candidate["supporting_fact_refs"]),
            "supporting_signal_refs": copy.deepcopy(candidate["supporting_signal_refs"]),
            "reasons": copy.deepcopy(candidate["reasons"]),
            "warnings": copy.deepcopy(candidate["warnings"]),
            "candidate_metadata": copy.deepcopy(candidate["metadata"]),
        },
    )
    node["properties"]["review_actor"] = decision_actor
    node["properties"]["reviewed_at"] = decided_at
    return node


def _ensure_same_claim(existing: dict[str, Any], expected: dict[str, Any]) -> None:
    if _canonical_json(_without_review(existing)) != _canonical_json(_without_review(expected)):
        raise ValueError("Existing CareerClaim node has incompatible content")


def _without_review(node: dict[str, Any]) -> dict[str, Any]:
    comparable = copy.deepcopy(node)
    comparable.pop("created_at", None)
    comparable["properties"].pop("review_actor", None)
    comparable["properties"].pop("reviewed_at", None)
    return comparable


def _audit_acceptance(
    store: GraphStore,
    node: dict[str, Any],
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    created: bool,
) -> None:
    props = node["properties"]
    store.append_audit_record(
        "career_claim_candidate_accepted",
        [node["id"], candidate["id"], candidate["analysis_ref"], candidate["contribution_ref"]],
        "accepted",
        {
            "claim_id": node["id"],
            "candidate_id": candidate["id"],
            "analysis_id": candidate["analysis_ref"],
            "contribution_id": candidate["contribution_ref"],
            "actor": decision_actor,
            "decided_at": decided_at,
            "created": created,
            "claim_type": props["claim_type"],
            "confidence": props["confidence"],
            "privacy_level": props["privacy_level"],
            "evidence_refs": len(candidate["evidence_refs"]),
            "supporting_fact_refs": len(candidate["supporting_fact_refs"]),
            "supporting_signal_refs": len(candidate["supporting_signal_refs"]),
            "status": props["status"],
        },
    )


def _require_actor(actor: object) -> None:
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("decision_actor is required")


def _single_ref(value: object, field: str) -> str:
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], str) or not value[0]:
        raise ValueError(f"{field} must contain exactly one reference")
    return value[0]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
