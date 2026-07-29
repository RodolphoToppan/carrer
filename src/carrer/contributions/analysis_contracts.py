"""Pure ContributionAnalysis contract helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from carrer.domain.enums import CONFIDENCE_LEVELS, PRIVACY_LEVELS, REVIEW_STATUSES
from carrer.domain.hashing import stable_hash
from carrer.domain.identity import canonical_refs

ANALYSIS_VERSION = "v1"


def contribution_analysis_id(
    contribution_ref: str,
    evidence_refs: Iterable[str],
    analysis_version: str = ANALYSIS_VERSION,
) -> str:
    return "contribution_analysis:" + stable_hash([contribution_ref, canonical_refs(evidence_refs), analysis_version])


def _require_list_of_dicts(value: object, field: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{field} must be a list of objects")


def _require_ordered_unique_strings(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    if value != sorted(set(value)):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    return value


def validate_contribution_analysis(analysis: object) -> dict[str, Any]:
    if not isinstance(analysis, dict):
        raise ValueError("ContributionAnalysis must be a dict")
    if not isinstance(analysis.get("id"), str) or not analysis["id"]:
        raise ValueError("id is required")
    if not isinstance(analysis.get("contribution_ref"), str) or not analysis["contribution_ref"]:
        raise ValueError("contribution_ref is required")
    if analysis.get("analysis_type") != "deterministic_contribution_analysis":
        raise ValueError("analysis_type must be deterministic_contribution_analysis")
    if analysis.get("status") not in REVIEW_STATUSES:
        raise ValueError(f"Invalid status: {analysis.get('status')}")
    if analysis.get("confidence") not in CONFIDENCE_LEVELS:
        raise ValueError(f"Invalid confidence: {analysis.get('confidence')}")
    if analysis.get("privacy_level") not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {analysis.get('privacy_level')}")
    evidence_refs = _require_ordered_unique_strings(analysis.get("evidence_refs"), "evidence_refs")
    if analysis["id"] != contribution_analysis_id(analysis["contribution_ref"], evidence_refs):
        raise ValueError("ContributionAnalysis id does not match contribution_ref and evidence_refs")
    for field in ("context_facts", "action_facts", "outcome_facts", "impact_signals"):
        _require_list_of_dicts(analysis.get(field), field)
    for field in ("reasons", "warnings"):
        _require_ordered_unique_strings(analysis.get(field), field)
    try:
        json.dumps(analysis.get("metadata", {}), sort_keys=True)
        json.dumps(analysis, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("ContributionAnalysis must be JSON serializable") from exc
    return analysis


def contribution_analysis(
    *,
    contribution_ref: str,
    privacy_level: str,
    context_facts: list[dict[str, Any]],
    action_facts: list[dict[str, Any]],
    outcome_facts: list[dict[str, Any]],
    impact_signals: list[dict[str, Any]],
    evidence_refs: list[str],
    confidence: str,
    status: str = "proposed",
    reasons: list[str] | None = None,
    warnings: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    refs = canonical_refs(evidence_refs)
    analysis = {
        "id": contribution_analysis_id(contribution_ref, refs),
        "contribution_ref": contribution_ref,
        "analysis_type": "deterministic_contribution_analysis",
        "status": status,
        "confidence": confidence,
        "privacy_level": privacy_level,
        "context_facts": sorted(context_facts, key=lambda item: json.dumps(item, sort_keys=True)),
        "action_facts": sorted(action_facts, key=lambda item: json.dumps(item, sort_keys=True)),
        "outcome_facts": sorted(outcome_facts, key=lambda item: json.dumps(item, sort_keys=True)),
        "impact_signals": sorted(impact_signals, key=lambda item: json.dumps(item, sort_keys=True)),
        "evidence_refs": refs,
        "reasons": canonical_refs(reasons or []),
        "warnings": canonical_refs(warnings or []),
        "metadata": metadata or {"analysis_version": ANALYSIS_VERSION},
    }
    return validate_contribution_analysis(analysis)
