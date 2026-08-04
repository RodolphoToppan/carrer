"""Explicit review and persistence for claim-based artifacts."""

from __future__ import annotations

import copy
import json
from typing import Any

from carrer.artifacts.claim_based import (
    ARTIFACT_VERSION,
    build_artifact_from_career_claims,
    render_claim_based_artifact_markdown,
    validate_claim_based_artifact,
)
from carrer.contributions.analysis import parse_iso8601_with_timezone
from carrer.domain.hashing import stable_hash
from carrer.domain.identity import canonical_refs
from carrer.domain.models import professional_artifact_contract
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM = "PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM"
PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE = "PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE"

_COMPARISON_ERROR = "ClaimBasedArtifact does not match current deterministic artifact"
_NODE_COMPARISON_ERROR = "ProfessionalArtifact node does not match deterministic claim-based artifact"


def claim_based_professional_artifact_id(source_artifact_id: str) -> str:
    if not isinstance(source_artifact_id, str) or not source_artifact_id:
        raise ValueError("source_artifact_id is required")
    return "artifact:" + stable_hash(["claim_based_artifact", source_artifact_id])


def accept_claim_based_artifact(
    store: GraphStore,
    artifact: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
) -> dict[str, Any]:
    _require_store(store)
    _require_actor(decision_actor)
    parse_iso8601_with_timezone(decided_at, "decided_at")
    current = _current_artifact(store, artifact)
    node = _professional_artifact_node(current, decision_actor=decision_actor, decided_at=decided_at)
    existing = store.nodes.get(node["id"])
    if existing is None:
        persisted, created = store.create_node(node)
        validate_persisted_claim_based_professional_artifact(persisted)
    else:
        persisted = validate_persisted_claim_based_professional_artifact(existing)
        _ensure_same_artifact(persisted, node)
        created = False

    for ref in current["traceability"]["claim_refs"]:
        store.create_edge(PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM, persisted["id"], ref)
    for ref in _evidence_refs(current):
        store.create_edge(PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE, persisted["id"], ref)
    _audit(
        store,
        "claim_based_artifact_accepted",
        [persisted["id"], current["id"], *current["traceability"]["claim_refs"]],
        "accepted",
        _audit_metadata(current, decision_actor=decision_actor, decided_at=decided_at)
        | {"persisted_artifact_id": persisted["id"], "status": "accepted", "created": created},
        decided_at=decided_at,
        actor=decision_actor,
    )
    return {
        "artifact": persisted,
        "source_artifact_id": current["id"],
        "decision": "accepted",
        "created": created,
    }


def reject_claim_based_artifact(
    store: GraphStore,
    artifact: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    reason: str = "",
) -> dict[str, Any]:
    _require_store(store)
    _require_actor(decision_actor)
    parse_iso8601_with_timezone(decided_at, "decided_at")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")
    current = _current_artifact(store, artifact)
    _audit(
        store,
        "claim_based_artifact_rejected",
        [current["id"], *current["traceability"]["claim_refs"]],
        "rejected",
        _audit_metadata(current, decision_actor=decision_actor, decided_at=decided_at) | {"reason": reason},
        decided_at=decided_at,
        actor=decision_actor,
    )
    return {
        "source_artifact_id": current["id"],
        "artifact_type": current["artifact_type"],
        "audience": current["audience"],
        "decision": "rejected",
        "reason": reason,
    }


def validate_persisted_claim_based_professional_artifact(node: object) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ValueError("ProfessionalArtifact node must be a dict")
    parse_iso8601_with_timezone(node.get("created_at"), "created_at")
    if node.get("node_type") != "ProfessionalArtifact":
        raise ValueError("node_type must be ProfessionalArtifact")
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    if props.get("source_type") != "career_claim":
        raise ValueError("source_type must be career_claim")
    if props.get("status") != "accepted":
        raise ValueError("status must be accepted")
    if not isinstance(props.get("review_actor"), str) or not props["review_actor"].strip():
        raise ValueError("review_actor is required")
    parse_iso8601_with_timezone(props.get("reviewed_at"), "reviewed_at")
    artifact = _artifact_from_node(node)
    validate_claim_based_artifact(artifact)
    if props.get("content") != render_claim_based_artifact_markdown(artifact):
        raise ValueError("content must match deterministic Markdown")
    if props.get("evidence_refs") != _evidence_refs(artifact):
        raise ValueError("evidence_refs must match artifact items")
    expected = _professional_artifact_node(
        artifact,
        decision_actor=props["review_actor"],
        decided_at=props["reviewed_at"],
    )
    professional_artifact_contract(node)
    if _canonical_json(node) != _canonical_json(expected):
        raise ValueError(_NODE_COMPARISON_ERROR)
    _json(node, "ProfessionalArtifact node")
    return node


def _current_artifact(store: GraphStore, artifact: object) -> dict[str, Any]:
    valid = validate_claim_based_artifact(artifact)
    claim_refs = _claim_refs(valid)
    try:
        current = build_artifact_from_career_claims(
            store,
            claim_ids=claim_refs,
            artifact_type=valid["artifact_type"],
            audience=valid["audience"],
            created_at=valid["created_at"],
        )
    except ValueError as exc:
        raise ValueError(_COMPARISON_ERROR) from exc
    if _canonical_json(valid) != _canonical_json(current):
        raise ValueError(_COMPARISON_ERROR)
    return current


def _professional_artifact_node(
    artifact: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
) -> dict[str, Any]:
    claim_refs = copy.deepcopy(artifact["traceability"]["claim_refs"])
    evidence_refs = _evidence_refs(artifact)
    node = {
        "id": claim_based_professional_artifact_id(artifact["id"]),
        "node_type": "ProfessionalArtifact",
        "created_at": artifact["created_at"],
        "properties": {
            "artifact_type": artifact["artifact_type"],
            "audience": artifact["audience"],
            "source_type": "career_claim",
            "source_artifact_id": artifact["id"],
            "artifact_version": ARTIFACT_VERSION,
            "status": "accepted",
            "privacy_level": artifact["privacy_level"],
            "content": render_claim_based_artifact_markdown(artifact),
            "claim_refs": claim_refs,
            "knowledge_refs": [],
            "evidence_refs": evidence_refs,
            "items": copy.deepcopy(artifact["items"]),
            "warnings": copy.deepcopy(artifact["warnings"]),
            "traceability": copy.deepcopy(artifact["traceability"]),
            "review_actor": decision_actor,
            "reviewed_at": decided_at,
            "metadata": {
                "artifact_version": ARTIFACT_VERSION,
                "source_type": "career_claim",
                "source_artifact_id": artifact["id"],
                "claim_count": len(claim_refs),
                "evidence_count": len(evidence_refs),
                "warning_count": len(artifact["warnings"]),
            },
        },
    }
    return professional_artifact_contract(node)


def _artifact_from_node(node: dict[str, Any]) -> dict[str, Any]:
    props = node["properties"]
    return {
        "id": props.get("source_artifact_id"),
        "artifact_type": props.get("artifact_type"),
        "audience": props.get("audience"),
        "created_at": node.get("created_at"),
        "status": "draft",
        "privacy_level": props.get("privacy_level"),
        "items": props.get("items"),
        "warnings": props.get("warnings"),
        "traceability": props.get("traceability"),
        "metadata": {
            "artifact_version": props.get("artifact_version"),
            "source_type": props.get("source_type"),
            "claim_count": len(props.get("claim_refs", [])) if isinstance(props.get("claim_refs"), list) else None,
            "claim_types": canonical_refs(
                item.get("claim_type", "") for item in props.get("items", []) if isinstance(item, dict)
            )
            if isinstance(props.get("items"), list)
            else None,
        },
    }


def _claim_refs(artifact: dict[str, Any]) -> list[str]:
    traceability = artifact.get("traceability")
    if not isinstance(traceability, dict):
        raise ValueError("traceability must be an object")
    refs = traceability.get("claim_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError("traceability.claim_refs must be a non-empty list")
    if refs != sorted(set(refs)) or any(not isinstance(ref, str) or not ref for ref in refs):
        raise ValueError("traceability.claim_refs must be ordered, deduplicated, non-empty strings")
    return refs


def _evidence_refs(artifact: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in artifact["items"]:
        refs.extend(item["traceability"]["evidence_refs"])
    return canonical_refs(refs)


def _ensure_same_artifact(existing: dict[str, Any], expected: dict[str, Any]) -> None:
    if _canonical_json(_without_review(existing)) != _canonical_json(_without_review(expected)):
        raise ValueError("Existing ProfessionalArtifact node has incompatible content")


def _without_review(node: dict[str, Any]) -> dict[str, Any]:
    comparable = copy.deepcopy(node)
    comparable["properties"].pop("review_actor", None)
    comparable["properties"].pop("reviewed_at", None)
    return comparable


def _audit_metadata(
    artifact: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
) -> dict[str, Any]:
    claim_refs = artifact["traceability"]["claim_refs"]
    evidence_refs = _evidence_refs(artifact)
    return {
        "source_artifact_id": artifact["id"],
        "artifact_type": artifact["artifact_type"],
        "audience": artifact["audience"],
        "privacy_level": artifact["privacy_level"],
        "actor": decision_actor,
        "decided_at": decided_at,
        "claim_count": len(claim_refs),
        "evidence_count": len(evidence_refs),
        "warning_count": len(artifact["warnings"]),
        "artifact_version": artifact["metadata"]["artifact_version"],
        "source_type": "career_claim",
    }


def _audit(
    store: GraphStore,
    audit_type: str,
    target_refs: list[str],
    result: str,
    metadata: dict[str, Any],
    *,
    decided_at: str,
    actor: str,
) -> None:
    store.audit_records.append(
        {
            "id": "audit:"
            + stable_hash([audit_type, target_refs, result, metadata, decided_at, len(store.audit_records)]),
            "audit_type": audit_type,
            "created_at": decided_at,
            "actor": actor,
            "target_refs": target_refs,
            "result": result,
            "metadata": metadata,
        }
    )


def _require_actor(actor: object) -> None:
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("decision_actor is required")


def _require_store(store: object) -> None:
    if not hasattr(store, "nodes") or not hasattr(store, "edges") or not hasattr(store, "audit_records"):
        raise ValueError("store must expose nodes, edges, and audit_records")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json(value: object, field: str) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON serializable") from exc
