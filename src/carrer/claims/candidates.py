"""Pure CareerClaimCandidate contract helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from carrer.domain.enums import CONFIDENCE_LEVELS, PRIVACY_LEVELS
from carrer.domain.hashing import stable_hash
from carrer.domain.identity import canonical_refs

CANDIDATE_VERSION = "v1"
CLAIM_TYPES = frozenset({"work_performed", "outcome_achieved", "metric_observed"})
CANDIDATE_STATUSES = frozenset({"proposed", "review_required"})


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def supporting_fact_ref(fact: dict[str, Any]) -> str:
    return "analysis_fact:" + stable_hash(json.loads(_canonical_json(fact)))


def supporting_signal_ref(signal: dict[str, Any]) -> str:
    return "analysis_signal:" + stable_hash(json.loads(_canonical_json(signal)))


def career_claim_candidate_id(
    claim_type: str,
    analysis_ref: str,
    supporting_refs: Iterable[str],
    candidate_version: str = CANDIDATE_VERSION,
) -> str:
    return "career_claim_candidate:" + stable_hash(
        [claim_type, analysis_ref, canonical_refs(supporting_refs), candidate_version]
    )


def career_claim_candidate(
    *,
    claim_type: str,
    statement: str,
    status: str,
    confidence: str,
    privacy_level: str,
    analysis_ref: str,
    contribution_ref: str,
    evidence_refs: list[str],
    supporting_fact_refs: list[str] | None = None,
    supporting_signal_refs: list[str] | None = None,
    reasons: list[str] | None = None,
    warnings: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    facts = canonical_refs(supporting_fact_refs or [])
    signals = canonical_refs(supporting_signal_refs or [])
    candidate = {
        "id": career_claim_candidate_id(claim_type, analysis_ref, [*facts, *signals]),
        "claim_type": claim_type,
        "statement": statement,
        "status": status,
        "confidence": confidence,
        "privacy_level": privacy_level,
        "analysis_ref": analysis_ref,
        "contribution_ref": contribution_ref,
        "evidence_refs": canonical_refs(evidence_refs),
        "supporting_fact_refs": facts,
        "supporting_signal_refs": signals,
        "reasons": canonical_refs(reasons or []),
        "warnings": canonical_refs(warnings or []),
        "metadata": {"candidate_version": CANDIDATE_VERSION} if metadata is None else metadata,
    }
    return validate_career_claim_candidate(candidate)


def validate_career_claim_candidate(candidate: object) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("CareerClaimCandidate must be a dict")
    if not isinstance(candidate.get("id"), str) or not candidate["id"]:
        raise ValueError("id is required")
    if candidate.get("claim_type") not in CLAIM_TYPES:
        raise ValueError(f"Invalid claim_type: {candidate.get('claim_type')}")
    if not isinstance(candidate.get("statement"), str) or not candidate["statement"].strip():
        raise ValueError("statement is required")
    if candidate.get("status") not in CANDIDATE_STATUSES:
        raise ValueError(f"Invalid status: {candidate.get('status')}")
    if candidate.get("confidence") not in CONFIDENCE_LEVELS:
        raise ValueError(f"Invalid confidence: {candidate.get('confidence')}")
    if candidate.get("privacy_level") not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {candidate.get('privacy_level')}")
    for field in ("analysis_ref", "contribution_ref"):
        if not isinstance(candidate.get(field), str) or not candidate[field]:
            raise ValueError(f"{field} is required")
    _ordered_refs(candidate.get("evidence_refs"), "evidence_refs", required=True)
    fact_refs = _ordered_refs(candidate.get("supporting_fact_refs"), "supporting_fact_refs")
    signal_refs = _ordered_refs(candidate.get("supporting_signal_refs"), "supporting_signal_refs")
    if not fact_refs and not signal_refs:
        raise ValueError("candidate requires supporting refs")
    for ref in fact_refs:
        if not ref.startswith("analysis_fact:"):
            raise ValueError("supporting_fact_refs must use analysis_fact refs")
    for ref in signal_refs:
        if not ref.startswith("analysis_signal:"):
            raise ValueError("supporting_signal_refs must use analysis_signal refs")
    _ordered_refs(candidate.get("reasons"), "reasons")
    _ordered_refs(candidate.get("warnings"), "warnings")
    metadata = candidate.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    if metadata.get("candidate_version") != CANDIDATE_VERSION:
        raise ValueError("Invalid candidate_version")
    if candidate["id"] != career_claim_candidate_id(
        candidate["claim_type"], candidate["analysis_ref"], [*fact_refs, *signal_refs], metadata["candidate_version"]
    ):
        raise ValueError("CareerClaimCandidate id does not match stable identity")
    try:
        json.dumps(candidate, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("CareerClaimCandidate must be JSON serializable") from exc
    return candidate


def _ordered_refs(value: object, field: str, *, required: bool = False) -> list[str]:
    if not isinstance(value, list) or (required and not value):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    if value != sorted(set(value)) or any(not isinstance(ref, str) or not ref for ref in value):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    return value
