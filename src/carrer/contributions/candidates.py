"""Pure ContributionCandidate contract helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from carrer.domain.enums import CONFIDENCE_LEVELS, PRIVACY_LEVELS, REVIEW_STATUSES
from carrer.domain.hashing import stable_hash
from carrer.domain.identity import canonical_refs


def contribution_candidate_id(
    candidate_type: str,
    evidence_refs: Iterable[str],
) -> str:
    return "contribution_candidate:" + stable_hash([candidate_type, canonical_refs(evidence_refs)])


def _require_refs(values: object, field: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{field} must contain at least one reference")
    if values != sorted(set(values)) or any(not isinstance(value, str) or not value for value in values):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    return values


def _require_deterministic_list(values: object, field: str) -> None:
    if not isinstance(values, list):
        raise ValueError(f"{field} must be a list")
    if values != sorted(set(values)) or any(not isinstance(value, str) or not value for value in values):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")


def parse_iso8601(value: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO8601 string") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")

    return parsed


def validate_contribution_candidate(candidate: object) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("ContributionCandidate must be a dict")

    candidate_id = candidate.get("id")
    candidate_type = candidate.get("candidate_type")
    title = candidate.get("title")

    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError("ContributionCandidate id is required")
    if not isinstance(candidate_type, str) or not candidate_type.strip():
        raise ValueError("candidate_type is required")
    if not isinstance(title, str):
        raise ValueError("title must be a string")

    evidence_refs = _require_refs(candidate.get("evidence_refs"), "evidence_refs")
    if candidate_id != contribution_candidate_id(candidate_type, evidence_refs):
        raise ValueError("ContributionCandidate id does not match candidate_type and evidence_refs")

    source_refs = candidate.get("source_refs", [])
    if source_refs is not None:
        _require_deterministic_list(source_refs, "source_refs")

    confidence = candidate.get("confidence")
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"Invalid confidence: {confidence}")

    status = candidate.get("status")
    if status not in REVIEW_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    privacy_level = candidate.get("privacy_level")
    if privacy_level not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {privacy_level}")

    started_at = candidate.get("started_at")
    ended_at = candidate.get("ended_at")
    started = parse_iso8601(started_at, "started_at") if started_at is not None else None
    ended = parse_iso8601(ended_at, "ended_at") if ended_at is not None else None
    if started and ended and started > ended:
        raise ValueError("started_at must be before or equal to ended_at")

    _require_deterministic_list(candidate.get("reasons", []), "reasons")
    _require_deterministic_list(candidate.get("signals", []), "signals")
    try:
        json.dumps(candidate.get("metadata", {}), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata must be JSON serializable") from exc

    return candidate


def contribution_candidate(
    *,
    candidate_type: str,
    title: str,
    evidence_refs: list[str],
    source_refs: list[str] | None = None,
    confidence: str = "low",
    status: str = "proposed",
    privacy_level: str = "private",
    started_at: str | None = None,
    ended_at: str | None = None,
    summary: str = "",
    signals: list[str] | None = None,
    reasons: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    refs = canonical_refs(evidence_refs)

    if not refs:
        raise ValueError("ContributionCandidate requires evidence_refs")

    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"Invalid confidence: {confidence}")

    if status not in REVIEW_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    if privacy_level not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {privacy_level}")

    started = parse_iso8601(started_at, "started_at") if started_at else None
    ended = parse_iso8601(ended_at, "ended_at") if ended_at else None

    if started and ended and started > ended:
        raise ValueError("started_at must be before or equal to ended_at")

    candidate = {
        "id": contribution_candidate_id(candidate_type, refs),
        "candidate_type": candidate_type,
        "title": title,
        "summary": summary,
        "confidence": confidence,
        "status": status,
        "privacy_level": privacy_level,
        "evidence_refs": refs,
        "source_refs": canonical_refs(source_refs or []),
        "started_at": started_at,
        "ended_at": ended_at,
        "signals": canonical_refs(signals or []),
        "reasons": canonical_refs(reasons or []),
        "metadata": metadata or {},
    }

    json.dumps(candidate, sort_keys=True)

    return candidate
