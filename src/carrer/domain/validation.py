"""Small pure validators for canonical domain dictionaries."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from carrer.domain.enums import (
    ARTIFACT_PRIVACY_LEVELS,
    ARTIFACT_STATUSES,
    CONFIDENCE_LEVELS,
    PRIVACY_LEVELS,
    REVIEW_STATUSES,
    SOURCE_ENTITY_TYPES,
)


def _require_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")


def _require_refs(values: object, field: str) -> None:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{field} must contain at least one reference")
    if values != sorted(set(values)) or any(not isinstance(value, str) or not value for value in values):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")


def _validate_json(value: object, field: str) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON serializable") from exc


def _parse_optional_date(value: object, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO8601 string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_evidence(node: dict[str, Any]) -> dict[str, Any]:
    _require_text(node.get("id"), "id")
    if node.get("node_type") != "EvidenceNode":
        raise ValueError("node_type must be EvidenceNode")
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    for field in (
        "source_id",
        "source_entity_type",
        "source_entity_id",
        "evidence_type",
        "captured_at",
        "content_hash",
    ):
        _require_text(props.get(field), field)
    if props["source_entity_type"] not in SOURCE_ENTITY_TYPES:
        raise ValueError(f"Invalid source_entity_type: {props['source_entity_type']}")
    if props.get("privacy_level") not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {props.get('privacy_level')}")
    _validate_json(props.get("metadata", {}), "metadata")
    return node


def validate_observation(node: dict[str, Any]) -> dict[str, Any]:
    _require_text(node.get("id"), "id")
    if node.get("node_type") != "ObservationNode":
        raise ValueError("node_type must be ObservationNode")
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    _require_text(props.get("observation_type"), "observation_type")
    _require_text(props.get("statement"), "statement")
    _require_refs(props.get("evidence_refs"), "evidence_refs")
    if props.get("confidence") not in CONFIDENCE_LEVELS:
        raise ValueError(f"Invalid confidence: {props.get('confidence')}")
    if props.get("privacy_level") not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {props.get('privacy_level')}")
    _validate_json(props.get("metadata", {}), "metadata")
    return node


def validate_knowledge(node: dict[str, Any]) -> dict[str, Any]:
    _require_text(node.get("id"), "id")
    if node.get("node_type") != "KnowledgeNode":
        raise ValueError("node_type must be KnowledgeNode")
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    _require_text(props.get("knowledge_type"), "knowledge_type")
    _require_text(props.get("statement"), "statement")
    evidence_refs = props.get("evidence_refs", [])
    observation_refs = props.get("observation_refs", [])
    if not evidence_refs and not observation_refs:
        raise ValueError("knowledge requires evidence_refs or observation_refs")
    if evidence_refs:
        _require_refs(evidence_refs, "evidence_refs")
    if observation_refs:
        _require_refs(observation_refs, "observation_refs")
    if props.get("status") not in REVIEW_STATUSES:
        raise ValueError(f"Invalid status: {props.get('status')}")
    if props.get("confidence") not in CONFIDENCE_LEVELS:
        raise ValueError(f"Invalid confidence: {props.get('confidence')}")
    if props.get("privacy_level") not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {props.get('privacy_level')}")
    _validate_json(props.get("metadata", {}), "metadata")
    return node


def validate_contribution(node: dict[str, Any]) -> dict[str, Any]:
    _require_text(node.get("id"), "id")
    if node.get("node_type") != "Contribution":
        raise ValueError("node_type must be Contribution")
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    if not str(props.get("title", "")).strip() and not str(props.get("summary", "")).strip():
        raise ValueError("title or summary is required")
    if props.get("status") not in REVIEW_STATUSES:
        raise ValueError(f"Invalid status: {props.get('status')}")
    if props.get("confidence") not in CONFIDENCE_LEVELS:
        raise ValueError(f"Invalid confidence: {props.get('confidence')}")
    if props.get("privacy_level") not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {props.get('privacy_level')}")
    ref_fields = ("evidence_refs", "observation_refs", "knowledge_refs", "source_refs")
    if not any(props.get(field) for field in ref_fields):
        raise ValueError("contribution requires provenance")
    for field in ref_fields:
        if props.get(field):
            _require_refs(props[field], field)
    started_at = _parse_optional_date(props.get("started_at"), "started_at")
    ended_at = _parse_optional_date(props.get("ended_at"), "ended_at")
    if started_at and ended_at and started_at > ended_at:
        raise ValueError("started_at must be before or equal to ended_at")
    _validate_json(props.get("metadata", {}), "metadata")
    return node


def validate_career_claim(node: dict[str, Any]) -> dict[str, Any]:
    _require_text(node.get("id"), "id")
    if node.get("node_type") != "CareerClaim":
        raise ValueError("node_type must be CareerClaim")
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    _require_text(props.get("claim_type"), "claim_type")
    _require_text(props.get("statement"), "statement")
    ref_fields = ("contribution_refs", "knowledge_refs", "evidence_refs")
    if not any(props.get(field) for field in ref_fields):
        raise ValueError("career claim requires support")
    for field in ref_fields:
        if props.get(field):
            _require_refs(props[field], field)
    if props.get("status") not in REVIEW_STATUSES:
        raise ValueError(f"Invalid status: {props.get('status')}")
    if props.get("confidence") not in CONFIDENCE_LEVELS:
        raise ValueError(f"Invalid confidence: {props.get('confidence')}")
    if props.get("privacy_level") not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {props.get('privacy_level')}")
    _validate_json(props.get("metadata", {}), "metadata")
    return node


def validate_professional_artifact(node: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ValueError("ProfessionalArtifact node must be a dict")
    _require_text(node.get("id"), "id")
    if node.get("node_type") != "ProfessionalArtifact":
        raise ValueError("node_type must be ProfessionalArtifact")
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    _require_text(props.get("artifact_type"), "artifact_type")
    if not isinstance(props.get("knowledge_refs", []), list):
        raise ValueError("knowledge_refs must be a list")
    source_type = props.get("source_type")
    if source_type is not None and not isinstance(source_type, str):
        raise ValueError("source_type must be a string")
    status = props.get("status")
    if not isinstance(status, str):
        raise ValueError("status must be a string")
    privacy_level = props.get("privacy_level")
    if not isinstance(privacy_level, str):
        raise ValueError("privacy_level must be a string")
    if source_type == "career_claim":
        if status != "accepted":
            raise ValueError("career_claim ProfessionalArtifact status must be accepted")
        if privacy_level not in {"internal", "artifact_safe"}:
            raise ValueError(f"Invalid career_claim artifact privacy level: {privacy_level}")
        _validate_json(props, "properties")
        return node
    if status not in ARTIFACT_STATUSES:
        raise ValueError(f"Invalid artifact status: {status}")
    if privacy_level not in ARTIFACT_PRIVACY_LEVELS:
        raise ValueError(f"Invalid artifact privacy level: {privacy_level}")
    _validate_json(props, "properties")
    return node
