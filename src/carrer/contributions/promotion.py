"""Explicit human review for in-memory ContributionCandidate values."""

from __future__ import annotations

import json
from typing import Any

from carrer.contributions.candidates import parse_iso8601, validate_contribution_candidate
from carrer.contributions.service import create_contribution
from carrer.domain.privacy import derive_privacy
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage


def _require_actor(actor: str) -> None:
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("decision_actor is required")


def _evidence_nodes(store: GraphStore, evidence_refs: list[str]) -> list[dict[str, Any]]:
    nodes = []
    for ref in evidence_refs:
        node = store.nodes.get(ref)
        if node is None:
            raise ValueError(f"evidence_refs references missing node: {ref}")
        if node.get("node_type") != "EvidenceNode":
            raise ValueError(f"evidence_refs requires EvidenceNode, got {node.get('node_type')} for {ref}")
        nodes.append(node)
    return nodes


def _json_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    metadata = dict(value or {})
    json.dumps(metadata, sort_keys=True)
    return metadata


def _date_range(started_at: str | None, ended_at: str | None) -> None:
    started = parse_iso8601(started_at, "started_at") if started_at is not None else None
    ended = parse_iso8601(ended_at, "ended_at") if ended_at is not None else None
    if started and ended and started > ended:
        raise ValueError("started_at must be before or equal to ended_at")


def promote_contribution_candidate(
    store: GraphStore,
    candidate: dict[str, Any],
    *,
    created_at: str,
    decision_actor: str,
    title: str | None = None,
    summary: str = "",
    contribution_type: str | None = None,
    status: str = "draft",
    confidence: str | None = None,
    privacy_level: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    context: str = "",
    actions: list[str] | None = None,
    outcomes: list[str] | None = None,
    technologies: list[str] | None = None,
    domains: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_actor(decision_actor)
    parse_iso8601(created_at, "created_at")
    valid = validate_contribution_candidate(candidate)
    evidence_refs = list(valid["evidence_refs"])
    evidence_nodes = _evidence_nodes(store, evidence_refs)
    final_metadata = _json_metadata(metadata)
    final_metadata.update(
        {
            "candidate_id": valid["id"],
            "candidate_reasons": list(valid.get("reasons", [])),
            "candidate_signals": list(valid.get("signals", [])),
            "promotion_actor": decision_actor,
        }
    )

    requested_privacy = privacy_level if privacy_level is not None else valid["privacy_level"]
    final_started_at = valid["started_at"] if started_at is None else started_at
    final_ended_at = valid["ended_at"] if ended_at is None else ended_at
    _date_range(final_started_at, final_ended_at)
    if contribution_type is not None and (not isinstance(contribution_type, str) or not contribution_type.strip()):
        raise ValueError("contribution_type is required")
    final_privacy = derive_privacy(
        [
            valid["privacy_level"],
            requested_privacy,
            *(node["properties"].get("privacy_level") for node in evidence_nodes),
        ]
    )
    result = create_contribution(
        store,
        contribution_type=valid["candidate_type"] if contribution_type is None else contribution_type,
        created_at=created_at,
        title=valid["title"] if title is None else title,
        summary=summary,
        evidence_refs=evidence_refs,
        source_refs=list(valid.get("source_refs", [])),
        status=status,
        confidence=valid["confidence"] if confidence is None else confidence,
        privacy_level=final_privacy,
        started_at=final_started_at,
        ended_at=final_ended_at,
        context=context,
        actions=actions,
        outcomes=outcomes,
        technologies=technologies,
        domains=domains,
        metadata=final_metadata,
    )
    contribution = result["contribution"]
    store.append_audit_record(
        "contribution_candidate_promoted",
        [valid["id"], contribution["id"]],
        "promoted",
        {
            "candidate_id": valid["id"],
            "contribution_id": contribution["id"],
            "actor": decision_actor,
            "decided_at": created_at,
            "created": result["created"],
            "candidate_type": valid["candidate_type"],
            "evidence_refs": len(evidence_refs),
            "status": contribution["properties"]["status"],
            "confidence": contribution["properties"]["confidence"],
        },
    )
    return {
        "candidate_id": valid["id"],
        "decision": "promoted",
        "contribution": contribution,
        "created": result["created"],
    }


def reject_contribution_candidate(
    store: GraphStore,
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    reason: str = "",
) -> dict[str, Any]:
    _require_actor(decision_actor)
    parse_iso8601(decided_at, "decided_at")
    valid = validate_contribution_candidate(candidate)
    _evidence_nodes(store, list(valid["evidence_refs"]))
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")

    store.append_audit_record(
        "contribution_candidate_rejected",
        [valid["id"]],
        "rejected",
        {
            "candidate_id": valid["id"],
            "actor": decision_actor,
            "decided_at": decided_at,
            "candidate_type": valid["candidate_type"],
            "evidence_refs": len(valid["evidence_refs"]),
            "reason": reason,
        },
    )
    return {"candidate_id": valid["id"], "decision": "rejected", "reason": reason}
