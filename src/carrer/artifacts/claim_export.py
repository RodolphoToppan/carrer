"""Deterministic in-memory export candidates for accepted claim-based artifacts."""

from __future__ import annotations

import json
import re
from typing import Any

from carrer.artifacts.claim_review import validate_persisted_claim_based_professional_artifact
from carrer.contributions.analysis import parse_iso8601_with_timezone
from carrer.domain.hashing import stable_hash
from carrer.domain.identity import canonical_refs
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

EXPORT_FORMAT = "markdown"
EXPORT_SCOPES = frozenset({"internal", "external"})
EXPORT_PRIVACY_LEVELS = frozenset({"internal", "artifact_safe"})
_ALLOWED_PRIVACY_BY_SCOPE = {
    "internal": frozenset({"internal", "artifact_safe"}),
    "external": frozenset({"artifact_safe"}),
}
_SAFE_NAME = re.compile(r"[^a-z0-9_-]+")


def claim_based_artifact_export_candidate_id(
    source_artifact_id: str,
    export_scope: str,
    export_format: str,
    content_hash: str,
) -> str:
    _required_str(source_artifact_id, "source_artifact_id")
    _validate_scope(export_scope)
    _validate_format(export_format)
    _required_str(content_hash, "content_hash")
    return "claim_based_artifact_export_candidate:" + stable_hash(
        [source_artifact_id, export_scope, export_format, content_hash]
    )


def build_claim_based_artifact_export_candidate(
    store: GraphStore,
    artifact_id: str,
    *,
    export_scope: str,
    export_format: str,
    created_at: str,
) -> dict[str, Any]:
    _require_store(store)
    _required_str(artifact_id, "artifact_id")
    _validate_scope(export_scope)
    _validate_format(export_format)
    parse_iso8601_with_timezone(created_at, "created_at")
    node = store.nodes.get(artifact_id)
    if node is None:
        raise ValueError(f"ProfessionalArtifact not found: {artifact_id}")
    if node.get("node_type") != "ProfessionalArtifact":
        raise ValueError("artifact_id must reference ProfessionalArtifact")
    artifact = validate_persisted_claim_based_professional_artifact(node)
    props = artifact["properties"]
    privacy = props["privacy_level"]
    validate_export_scope_privacy(export_scope, privacy)
    content = props["content"]
    content_hash = stable_hash(content)
    claim_refs = canonical_refs(props["claim_refs"])
    evidence_refs = canonical_refs(props["evidence_refs"])
    candidate = {
        "id": claim_based_artifact_export_candidate_id(artifact["id"], export_scope, export_format, content_hash),
        "candidate_type": "claim_based_artifact_export",
        "created_at": created_at,
        "source_artifact_id": artifact["id"],
        "source_artifact_created_at": artifact["created_at"],
        "artifact_type": props["artifact_type"],
        "audience": props["audience"],
        "privacy_level": privacy,
        "export_scope": export_scope,
        "export_format": EXPORT_FORMAT,
        "file_name": _file_name(props["artifact_type"], content_hash),
        "content": content,
        "content_hash": content_hash,
        "traceability": {
            "professional_artifact_ref": artifact["id"],
            "source_claim_based_artifact_ref": props["source_artifact_id"],
            "claim_refs": claim_refs,
            "evidence_refs": evidence_refs,
        },
        "metadata": {
            "source_type": "career_claim",
            "artifact_version": props["metadata"]["artifact_version"],
            "claim_count": len(claim_refs),
            "evidence_count": len(evidence_refs),
            "warning_count": len(props["warnings"]),
        },
    }
    return validate_claim_based_artifact_export_candidate(candidate)


def validate_claim_based_artifact_export_candidate(candidate: object) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("ClaimBasedArtifactExportCandidate must be a dict")
    _required_str(candidate.get("id"), "id")
    if candidate.get("candidate_type") != "claim_based_artifact_export":
        raise ValueError("candidate_type must be claim_based_artifact_export")
    parse_iso8601_with_timezone(candidate.get("created_at"), "created_at")
    for field in (
        "source_artifact_id",
        "source_artifact_created_at",
        "artifact_type",
        "audience",
        "privacy_level",
        "file_name",
        "content",
        "content_hash",
    ):
        _required_str(candidate.get(field), field)
    parse_iso8601_with_timezone(candidate["source_artifact_created_at"], "source_artifact_created_at")
    _validate_scope(candidate.get("export_scope"))
    _validate_format(candidate.get("export_format"))
    validate_export_scope_privacy(candidate["export_scope"], candidate["privacy_level"])
    if candidate["content_hash"] != stable_hash(candidate["content"]):
        raise ValueError("content_hash must match content")
    if candidate["file_name"] != _file_name(candidate["artifact_type"], candidate["content_hash"]):
        raise ValueError("file_name must be deterministic")
    traceability = candidate.get("traceability")
    if not isinstance(traceability, dict):
        raise ValueError("traceability must be an object")
    if traceability.get("professional_artifact_ref") != candidate["source_artifact_id"]:
        raise ValueError("traceability.professional_artifact_ref must match source_artifact_id")
    _required_str(traceability.get("source_claim_based_artifact_ref"), "traceability.source_claim_based_artifact_ref")
    claim_refs = _refs(traceability.get("claim_refs"), "traceability.claim_refs")
    evidence_refs = _refs(traceability.get("evidence_refs"), "traceability.evidence_refs")
    metadata = candidate.get("metadata")
    if metadata != {
        "source_type": "career_claim",
        "artifact_version": metadata.get("artifact_version") if isinstance(metadata, dict) else None,
        "claim_count": len(claim_refs),
        "evidence_count": len(evidence_refs),
        "warning_count": metadata.get("warning_count") if isinstance(metadata, dict) else None,
    }:
        raise ValueError("metadata must match candidate refs and source")
    _required_str(metadata["artifact_version"], "metadata.artifact_version")
    if not isinstance(metadata["warning_count"], int) or metadata["warning_count"] < 0:
        raise ValueError("metadata.warning_count must be a non-negative integer")
    if candidate["id"] != claim_based_artifact_export_candidate_id(
        candidate["source_artifact_id"],
        candidate["export_scope"],
        candidate["export_format"],
        candidate["content_hash"],
    ):
        raise ValueError("ClaimBasedArtifactExportCandidate id does not match stable identity")
    _json(candidate, "ClaimBasedArtifactExportCandidate")
    return candidate


def _file_name(artifact_type: str, content_hash: str) -> str:
    safe_type = _SAFE_NAME.sub("-", artifact_type.lower()).strip("-_")
    if not safe_type:
        raise ValueError("artifact_type must contain safe filename characters")
    name = f"{safe_type}-{content_hash[:12]}.md"
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError("file_name is unsafe")
    return name


def validate_export_scope_privacy(export_scope: object, privacy_level: object) -> None:
    _validate_scope(export_scope)
    scope = export_scope
    if not isinstance(scope, str):
        raise ValueError("export_scope is invalid")
    if not isinstance(privacy_level, str) or privacy_level not in EXPORT_PRIVACY_LEVELS:
        raise ValueError("privacy_level must be internal or artifact_safe")
    if privacy_level not in _ALLOWED_PRIVACY_BY_SCOPE[scope]:
        raise ValueError("privacy_level is incompatible with export_scope")


def _validate_scope(value: object) -> None:
    if not isinstance(value, str) or value not in EXPORT_SCOPES:
        raise ValueError("export_scope is invalid")


def _validate_format(value: object) -> None:
    if value != EXPORT_FORMAT:
        raise ValueError("export_format must be markdown")


def _refs(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    if value != sorted(set(value)) or any(not isinstance(ref, str) or not ref for ref in value):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    return value


def _required_str(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is required")


def _require_store(store: object) -> None:
    if not hasattr(store, "nodes") or not isinstance(store.nodes, dict):
        raise ValueError("store is missing required graph API: nodes")


def _json(value: object, field: str) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON serializable") from exc
