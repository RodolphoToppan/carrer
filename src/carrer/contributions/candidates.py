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
    return "contribution_candidate:" + stable_hash(
        [candidate_type, canonical_refs(evidence_refs)]
    )


def parse_iso8601(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO8601 string") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")

    return parsed


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