"""Explicit read-only artifacts from accepted CareerClaim nodes."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sized
from typing import Any

from carrer.claims.candidates import CLAIM_TYPES
from carrer.claims.review import (
    CAREER_CLAIM_DERIVED_FROM_ANALYSIS,
    CAREER_CLAIM_FROM_CONTRIBUTION,
    CAREER_CLAIM_SUPPORTED_BY_EVIDENCE,
    validate_persisted_career_claim,
)
from carrer.contributions.analysis import parse_iso8601_with_timezone
from carrer.domain.enums import CONFIDENCE_LEVELS, PRIVACY_LEVELS
from carrer.domain.hashing import stable_hash
from carrer.domain.identity import canonical_refs
from carrer.domain.privacy import most_restrictive
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

ARTIFACT_VERSION = "v1"
CLAIM_BASED_ARTIFACT_TYPES = frozenset({"resume_claims", "linkedin_claims"})
CLAIM_BASED_AUDIENCES = frozenset({"internal", "public"})
_ALLOWED_PRIVACY_BY_AUDIENCE = {
    "internal": frozenset({"internal", "artifact_safe", "exported"}),
    "public": frozenset({"artifact_safe", "exported"}),
}
_HEADINGS = {"resume_claims": "Career Claims", "linkedin_claims": "Selected Career Claims"}


def claim_based_artifact_id(
    artifact_type: str,
    audience: str,
    claim_refs: Iterable[str],
    artifact_version: str = ARTIFACT_VERSION,
) -> str:
    _validate_artifact_type_and_audience(artifact_type=artifact_type, audience=audience)
    if not isinstance(artifact_version, str) or not artifact_version:
        raise ValueError("artifact_version must be a string")
    refs = _materialized_claim_refs(claim_refs)
    return "claim_based_artifact:" + stable_hash([artifact_type, audience, canonical_refs(refs), artifact_version])


def build_artifact_from_career_claims(
    store: GraphStore,
    *,
    claim_ids: list[str],
    artifact_type: str,
    audience: str,
    created_at: str,
) -> dict[str, Any]:
    _validate_store(store)
    refs = _selected_claim_refs(claim_ids)
    claims = []
    for ref in refs:
        node = store.nodes.get(ref)
        if node is None:
            raise ValueError(f"CareerClaim not found: {ref}")
        if node.get("node_type") != "CareerClaim":
            raise ValueError("claim_ids must reference CareerClaim nodes")
        claim = validate_persisted_career_claim(node)
        _validate_claim_edges(store, claim)
        claims.append(claim)
    return build_artifact_from_claim_nodes(
        claims,
        artifact_type=artifact_type,
        audience=audience,
        created_at=created_at,
    )


def build_artifact_from_claim_nodes(
    claims: list[dict[str, Any]],
    *,
    artifact_type: str,
    audience: str,
    created_at: str,
) -> dict[str, Any]:
    _validate_artifact_inputs(artifact_type=artifact_type, audience=audience, created_at=created_at)
    if not isinstance(claims, list) or not claims:
        raise ValueError("claims must be a non-empty list")
    valid_claims = [validate_persisted_career_claim(claim) for claim in claims]
    claim_refs = _selected_claim_refs([claim["id"] for claim in valid_claims])
    by_id = {claim["id"]: claim for claim in valid_claims}
    ordered = sorted(
        (by_id[ref] for ref in claim_refs), key=lambda claim: (claim["properties"]["claim_type"], claim["id"])
    )
    items = [_artifact_item(claim, audience) for claim in ordered]
    artifact = claim_based_artifact(
        artifact_type=artifact_type,
        audience=audience,
        created_at=created_at,
        items=items,
    )
    return validate_claim_based_artifact(artifact)


def claim_based_artifact(
    *,
    artifact_type: str,
    audience: str,
    created_at: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    _validate_artifact_inputs(artifact_type=artifact_type, audience=audience, created_at=created_at)
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty list")
    checked_items = [_validate_item(item) for item in items]
    for item in checked_items:
        _validate_item_privacy_for_audience(item["privacy_level"], audience)
    claim_refs = [item["claim_ref"] for item in checked_items]
    if len(claim_refs) != len(set(claim_refs)):
        raise ValueError("items must be ordered by claim_type and claim_ref with unique claim refs")
    claim_types = canonical_refs(item["claim_type"] for item in checked_items)
    warnings = _artifact_warnings(checked_items)
    artifact = {
        "id": claim_based_artifact_id(artifact_type, audience, claim_refs),
        "artifact_type": artifact_type,
        "audience": audience,
        "created_at": created_at,
        "status": "draft",
        "privacy_level": most_restrictive([item["privacy_level"] for item in checked_items]),
        "items": checked_items,
        "warnings": warnings,
        "traceability": {"claim_refs": canonical_refs(claim_refs)},
        "metadata": {
            "artifact_version": ARTIFACT_VERSION,
            "source_type": "career_claim",
            "claim_count": len(checked_items),
            "claim_types": claim_types,
        },
    }
    return validate_claim_based_artifact(artifact)


def validate_claim_based_artifact(artifact: object) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        raise ValueError("ClaimBasedArtifact must be a dict")
    _validate_artifact_inputs(
        artifact_type=artifact.get("artifact_type"),
        audience=artifact.get("audience"),
        created_at=artifact.get("created_at"),
    )
    if artifact.get("status") != "draft":
        raise ValueError("status must be draft")
    if not isinstance(artifact.get("privacy_level"), str):
        raise ValueError("privacy_level must be a string")
    if artifact["privacy_level"] not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {artifact.get('privacy_level')}")
    items = artifact.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty list")
    checked_items = [_validate_item(item) for item in items]
    for item in checked_items:
        _validate_item_privacy_for_audience(item["privacy_level"], artifact["audience"])
    if items != sorted(items, key=lambda item: (item["claim_type"], item["claim_ref"])):
        raise ValueError("items must be ordered by claim_type and claim_ref")
    claim_refs = [item["claim_ref"] for item in checked_items]
    if len(claim_refs) != len(set(claim_refs)):
        raise ValueError("claim refs must be deduplicated")
    if artifact.get("id") != claim_based_artifact_id(artifact["artifact_type"], artifact["audience"], claim_refs):
        raise ValueError("ClaimBasedArtifact id does not match stable identity")
    if artifact["privacy_level"] != most_restrictive([item["privacy_level"] for item in checked_items]):
        raise ValueError("privacy_level must be derived from items")
    expected_warnings = _artifact_warnings(checked_items)
    if artifact.get("warnings") != expected_warnings:
        raise ValueError("warnings must match deterministic item warnings")
    traceability = artifact.get("traceability")
    if not isinstance(traceability, dict) or traceability.get("claim_refs") != canonical_refs(claim_refs):
        raise ValueError("traceability.claim_refs must match items")
    metadata = artifact.get("metadata")
    claim_types = canonical_refs(item["claim_type"] for item in checked_items)
    if metadata != {
        "artifact_version": ARTIFACT_VERSION,
        "source_type": "career_claim",
        "claim_count": len(checked_items),
        "claim_types": claim_types,
    }:
        raise ValueError("metadata must be minimal and deterministic")
    try:
        json.dumps(artifact, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("ClaimBasedArtifact must be JSON serializable") from exc
    return artifact


def render_claim_based_artifact_markdown(artifact: dict[str, Any]) -> str:
    valid = validate_claim_based_artifact(artifact)
    lines = [f"# {_HEADINGS[valid['artifact_type']]}", ""]
    lines.extend(f"- {item['text']}" for item in valid["items"])
    return "\n".join(lines) + "\n"


def _artifact_item(claim: dict[str, Any], audience: str) -> dict[str, Any]:
    props = claim["properties"]
    privacy = props["privacy_level"]
    _validate_item_privacy_for_audience(privacy, audience)
    metadata = props["metadata"]
    contribution_ref = _single_ref(props["contribution_refs"], "contribution_refs")
    traceability = {
        "claim_ref": claim["id"],
        "candidate_ref": metadata["candidate_id"],
        "analysis_ref": metadata["analysis_ref"],
        "contribution_ref": contribution_ref,
        "evidence_refs": canonical_refs(props["evidence_refs"]),
        "supporting_fact_refs": canonical_refs(metadata["supporting_fact_refs"]),
        "supporting_signal_refs": canonical_refs(metadata["supporting_signal_refs"]),
    }
    return {
        "text": props["statement"],
        "claim_ref": claim["id"],
        "claim_type": props["claim_type"],
        "confidence": props["confidence"],
        "privacy_level": privacy,
        "traceability": traceability,
        "candidate_warning_count": len(metadata["warnings"]),
    }


def _validate_item(item: object) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("item must be a dict")
    if not isinstance(item.get("text"), str) or not item["text"].strip():
        raise ValueError("item text is required")
    for field in ("claim_ref", "claim_type", "confidence", "privacy_level"):
        if not isinstance(item.get(field), str) or not item[field]:
            raise ValueError(f"{field} is required")
    if item["claim_type"] not in CLAIM_TYPES:
        raise ValueError(f"Invalid claim_type: {item['claim_type']}")
    if item["confidence"] not in CONFIDENCE_LEVELS:
        raise ValueError(f"Invalid confidence: {item['confidence']}")
    if item["privacy_level"] not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {item['privacy_level']}")
    traceability = item.get("traceability")
    if not isinstance(traceability, dict):
        raise ValueError("traceability must be an object")
    if traceability.get("claim_ref") != item["claim_ref"]:
        raise ValueError("traceability.claim_ref must match item claim_ref")
    for field in ("candidate_ref", "analysis_ref", "contribution_ref"):
        if not isinstance(traceability.get(field), str) or not traceability[field]:
            raise ValueError(f"traceability.{field} is required")
    _ordered_refs(traceability.get("evidence_refs"), "traceability.evidence_refs", required=True)
    _ordered_refs(traceability.get("supporting_fact_refs"), "traceability.supporting_fact_refs")
    _ordered_refs(traceability.get("supporting_signal_refs"), "traceability.supporting_signal_refs")
    if not isinstance(item.get("candidate_warning_count"), int) or item["candidate_warning_count"] < 0:
        raise ValueError("candidate_warning_count must be a non-negative integer")
    return item


def _validate_artifact_inputs(*, artifact_type: object, audience: object, created_at: object) -> None:
    _validate_artifact_type_and_audience(artifact_type=artifact_type, audience=audience)
    parse_iso8601_with_timezone(created_at, "created_at")


def _validate_artifact_type_and_audience(*, artifact_type: object, audience: object) -> None:
    if not isinstance(artifact_type, str):
        raise ValueError("artifact_type must be a string")
    if artifact_type not in CLAIM_BASED_ARTIFACT_TYPES:
        raise ValueError(f"Invalid artifact_type: {artifact_type}")
    if not isinstance(audience, str):
        raise ValueError("audience must be a string")
    if audience not in CLAIM_BASED_AUDIENCES:
        raise ValueError(f"Invalid audience: {audience}")


def _validate_item_privacy_for_audience(privacy_level: str, audience: str) -> None:
    if privacy_level not in _ALLOWED_PRIVACY_BY_AUDIENCE[audience]:
        raise ValueError("CareerClaim privacy is incompatible with artifact audience")


def _selected_claim_refs(claim_ids: object) -> list[str]:
    if not isinstance(claim_ids, list) or not claim_ids:
        raise ValueError("claim_ids must be a non-empty list")
    if any(not isinstance(ref, str) or not ref for ref in claim_ids):
        raise ValueError("claim_ids must contain non-empty strings")
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("claim_ids must be deduplicated")
    return canonical_refs(claim_ids)


def _materialized_claim_refs(claim_refs: object) -> list[str]:
    if isinstance(claim_refs, str) or claim_refs is None or not isinstance(claim_refs, Iterable):
        raise ValueError("claim_refs must be a non-empty iterable of strings")
    if isinstance(claim_refs, Sized) and len(claim_refs) == 0:
        raise ValueError("claim_refs must be a non-empty iterable of strings")
    try:
        refs = list(claim_refs)
    except TypeError as exc:
        raise ValueError("claim_refs must be a non-empty iterable of strings") from exc
    if not refs:
        raise ValueError("claim_refs must be a non-empty iterable of strings")
    if any(not isinstance(ref, str) or not ref for ref in refs):
        raise ValueError("claim_refs must contain non-empty strings")
    if len(refs) != len(set(refs)):
        raise ValueError("claim_refs must be deduplicated")
    return refs


def _validate_claim_edges(store: GraphStore, claim: dict[str, Any]) -> None:
    props = claim["properties"]
    metadata = props["metadata"]
    analysis_ref = metadata["analysis_ref"]
    contribution_ref = _single_ref(props["contribution_refs"], "contribution_refs")
    evidence_refs = canonical_refs(props["evidence_refs"])
    _require_target(store, analysis_ref, "ContributionAnalysis")
    _require_target(store, contribution_ref, "Contribution")
    for ref in evidence_refs:
        _require_target(store, ref, "EvidenceNode")
    _require_exact_edges(store, CAREER_CLAIM_DERIVED_FROM_ANALYSIS, claim["id"], [analysis_ref])
    _require_exact_edges(store, CAREER_CLAIM_FROM_CONTRIBUTION, claim["id"], [contribution_ref])
    _require_exact_edges(store, CAREER_CLAIM_SUPPORTED_BY_EVIDENCE, claim["id"], evidence_refs)


def _require_target(store: GraphStore, node_id: str, node_type: str) -> None:
    node = store.nodes.get(node_id)
    if node is None:
        raise ValueError(f"CareerClaim provenance target not found: {node_id}")
    if node.get("node_type") != node_type:
        raise ValueError(f"CareerClaim provenance target must be {node_type}")


def _require_exact_edges(store: GraphStore, edge_type: str, from_node_id: str, expected_targets: list[str]) -> None:
    targets = sorted(
        edge["to_node_id"]
        for edge in store.edges
        if edge.get("edge_type") == edge_type and edge.get("from_node_id") == from_node_id
    )
    if targets != sorted(expected_targets):
        raise ValueError("CareerClaim provenance edges do not match persisted refs")


def _single_ref(value: object, field: str) -> str:
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], str) or not value[0]:
        raise ValueError(f"{field} must contain exactly one reference")
    return value[0]


def _ordered_refs(value: object, field: str, *, required: bool = False) -> list[str]:
    if not isinstance(value, list) or (required and not value):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    if value != sorted(set(value)) or any(not isinstance(ref, str) or not ref for ref in value):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    return value


def _artifact_warnings(items: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if any(item["privacy_level"] == "internal" for item in items):
        warnings.append("contains_internal_claim")
    if any(item["claim_type"] == "metric_observed" for item in items):
        warnings.append("contains_metric_observation")
    if len({item["claim_type"] for item in items}) > 1:
        warnings.append("mixed_claim_types")
    if len(items) == 1:
        warnings.append("single_claim_artifact")
    if any(item["candidate_warning_count"] > 0 for item in items):
        warnings.append("claim_has_candidate_warnings")
    return canonical_refs(warnings)


def _validate_store(store: object) -> None:
    if not hasattr(store, "nodes") or not hasattr(store, "edges"):
        raise ValueError("store must expose nodes and edges")
