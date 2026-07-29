"""Deterministic, read-only Contribution analysis."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from carrer.contributions.analysis_contracts import contribution_analysis
from carrer.domain.enums import CONFIDENCE_LEVELS, PRIVACY_LEVELS
from carrer.domain.identity import canonical_refs
from carrer.domain.privacy import most_restrictive
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

_STRUCTURAL_ACTIONS = {
    "commit": "commit_created",
    "merge_request": "merge_request_opened",
    "pull_request": "merge_request_opened",
    "review_comment": "review_comment_added",
    "documentation": "documentation_created",
    "work_item": "work_item_updated",
}
_OUTCOME_STATES = {
    "merge_request": {"merged": "merge_request_merged", "completed": "merge_request_merged"},
    "pull_request": {"merged": "merge_request_merged", "completed": "merge_request_merged"},
    "work_item": {"closed": "work_item_closed", "completed": "work_item_closed", "done": "work_item_closed"},
    "documentation": {"published": "documentation_published"},
}
_IMPACT_CATEGORIES = frozenset(
    {
        "performance",
        "reliability",
        "availability",
        "security",
        "cost",
        "throughput",
        "latency",
        "quality",
        "developer_productivity",
        "operational_efficiency",
        "customer_experience",
        "business_metric",
    }
)
_KNOWN_METRICS = {
    "latency_before_ms": ("latency", "ms"),
    "latency_after_ms": ("latency", "ms"),
    "response_time_before_ms": ("latency", "ms"),
    "response_time_after_ms": ("latency", "ms"),
    "processing_time_before_ms": ("latency", "ms"),
    "processing_time_after_ms": ("latency", "ms"),
    "throughput_requests_per_second": ("throughput", "requests_per_second"),
    "requests_per_second": ("throughput", "requests_per_second"),
    "error_count": ("reliability", "count"),
    "failure_count": ("reliability", "count"),
    "retry_count": ("reliability", "count"),
    "availability_percent": ("availability", "percent"),
    "uptime_percent": ("availability", "percent"),
    "tests_passed_count": ("quality", "count"),
    "coverage_percent": ("quality", "percent"),
    "defect_count": ("quality", "count"),
    "bugs_fixed_count": ("quality", "count"),
}


def parse_iso8601_with_timezone(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO8601 string") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def analyze_contribution(store: GraphStore, contribution_id: str) -> dict[str, Any]:
    node = store.nodes.get(contribution_id)
    if node is None:
        raise ValueError(f"Contribution not found: {contribution_id}")
    if node.get("node_type") != "Contribution":
        raise ValueError(f"node must be Contribution, got {node.get('node_type')}")
    props = _contribution_props(node)
    evidence_refs = _ordered_refs(props.get("evidence_refs"), "evidence_refs")
    evidence_nodes = [_evidence_node(store, ref) for ref in evidence_refs]
    _validate_contribution(node, props)
    return analyze_contribution_data(node, evidence_nodes)


def analyze_contribution_data(contribution: dict[str, Any], evidence_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    if contribution.get("node_type") != "Contribution":
        raise ValueError(f"node must be Contribution, got {contribution.get('node_type')}")
    props = _contribution_props(contribution)
    _validate_contribution(contribution, props)
    evidence = sorted(evidence_nodes, key=lambda node: node["id"])
    evidence_refs = _ordered_refs(props.get("evidence_refs"), "evidence_refs")
    if evidence_refs != [node.get("id") for node in evidence]:
        raise ValueError("evidence_nodes must match Contribution.properties.evidence_refs")
    for node in evidence:
        _validate_evidence(node)

    context_facts = _context_facts(contribution, evidence)
    action_facts = _action_facts(contribution, evidence)
    outcome_facts = _outcome_facts(contribution, evidence)
    impact_signals = _impact_signals(evidence)
    warnings = _warnings(props, action_facts, outcome_facts, impact_signals, evidence)
    confidence, reasons = _confidence(action_facts, outcome_facts, impact_signals)
    privacy = most_restrictive(
        [props["privacy_level"], *(node["properties"].get("privacy_level", "private") for node in evidence)]
    )
    return contribution_analysis(
        contribution_ref=contribution["id"],
        privacy_level=privacy,
        context_facts=_dedupe(context_facts),
        action_facts=_dedupe(action_facts),
        outcome_facts=_dedupe(outcome_facts),
        impact_signals=_dedupe(impact_signals),
        evidence_refs=evidence_refs,
        confidence=confidence,
        status="proposed" if outcome_facts else "review_required",
        reasons=reasons,
        warnings=warnings,
    )


def _contribution_props(node: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    return props


def _ordered_refs(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must contain at least one reference")
    if value != sorted(set(value)) or any(not isinstance(ref, str) or not ref for ref in value):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    return value


def _validate_contribution(node: dict[str, Any], props: dict[str, Any]) -> None:
    if not isinstance(node.get("id"), str) or not node["id"]:
        raise ValueError("id is required")
    if props.get("privacy_level") not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {props.get('privacy_level')}")
    if props.get("confidence") not in CONFIDENCE_LEVELS:
        raise ValueError(f"Invalid confidence: {props.get('confidence')}")
    _json(props.get("metadata", {}), "metadata")
    for field in ("created_at", "started_at", "ended_at"):
        if node.get(field) is not None and field == "created_at":
            parse_iso8601_with_timezone(node[field], field)
        if props.get(field) is not None:
            parse_iso8601_with_timezone(props[field], field)
    started = parse_iso8601_with_timezone(props["started_at"], "started_at") if props.get("started_at") else None
    ended = parse_iso8601_with_timezone(props["ended_at"], "ended_at") if props.get("ended_at") else None
    if started and ended and started > ended:
        raise ValueError("started_at must be before or equal to ended_at")


def _evidence_node(store: GraphStore, ref: str) -> dict[str, Any]:
    node = store.nodes.get(ref)
    if node is None:
        raise ValueError(f"evidence_refs references missing node: {ref}")
    if node.get("node_type") != "EvidenceNode":
        raise ValueError(f"evidence_refs requires EvidenceNode, got {node.get('node_type')} for {ref}")
    return node


def _validate_evidence(node: dict[str, Any]) -> None:
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("evidence properties must be an object")
    if props.get("privacy_level") not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {props.get('privacy_level')}")
    for field in ("source_id", "source_entity_type", "source_entity_id", "evidence_type"):
        if not isinstance(props.get(field), str) or not props[field]:
            raise ValueError(f"{field} is required")
    for field in ("created_at", "captured_at", "occurred_at"):
        value = node.get(field) if field == "created_at" else props.get(field)
        if value is not None:
            parse_iso8601_with_timezone(value, field)
    metadata = props.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    _json(metadata, "metadata")


def _context_facts(contribution: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    props = contribution["properties"]
    facts = [_fact("contribution_type", props["contribution_type"], contribution_ref=contribution["id"])]
    if props.get("started_at") or props.get("ended_at"):
        facts.append(
            _fact(
                "time_range",
                {"started_at": props.get("started_at"), "ended_at": props.get("ended_at")},
                contribution_ref=contribution["id"],
            )
        )
    for node in evidence:
        node_props = node["properties"]
        metadata = node_props["metadata"]
        ref = node["id"]
        for field in ("source_id", "source_entity_type", "source_entity_id", "evidence_type", "occurred_at"):
            if node_props.get(field) is not None:
                facts.append(_fact(field, node_props[field], evidence_refs=[ref]))
        if node_props.get("source_entity_type") == "work_item":
            facts.append(_fact("work_item", node_props["source_entity_id"], evidence_refs=[ref]))
        for field in ("repository", "project", "branch", "source_branch", "target_branch"):
            value = metadata.get(field)
            if isinstance(value, str) and value.strip():
                facts.append(_fact("branch" if field.endswith("branch") else field, value.strip(), evidence_refs=[ref]))
    return facts


def _action_facts(contribution: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts = [
        _fact("explicit_action", value, contribution_ref=contribution["id"], reason="Contribution.properties.actions")
        for value in _string_list(contribution["properties"].get("actions"), "actions")
    ]
    for node in evidence:
        source_type = node["properties"]["source_entity_type"]
        if source_type in _STRUCTURAL_ACTIONS:
            facts.append(
                _fact(
                    _STRUCTURAL_ACTIONS[source_type],
                    node["properties"]["source_entity_id"],
                    evidence_refs=[node["id"]],
                    reason=f"source_entity_type={source_type}",
                )
            )
    return facts


def _outcome_facts(contribution: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts = [
        _fact("explicit_outcome", value, contribution_ref=contribution["id"], reason="Contribution.properties.outcomes")
        for value in _string_list(contribution["properties"].get("outcomes"), "outcomes")
    ]
    for node in evidence:
        props = node["properties"]
        metadata = props["metadata"]
        source_type = props["source_entity_type"]
        state = _state(metadata)
        outcome = _OUTCOME_STATES.get(source_type, {}).get(state)
        if outcome:
            facts.append(_fact(outcome, state, evidence_refs=[node["id"]], reason="explicit structured state"))
        if metadata.get("published_at") is not None and source_type == "documentation":
            parse_iso8601_with_timezone(metadata["published_at"], "published_at")
            facts.append(_fact("documentation_published", metadata["published_at"], evidence_refs=[node["id"]]))
        if metadata.get("tests_passed") is True:
            facts.append(_fact("test_passed", True, evidence_refs=[node["id"]]))
        if _state(metadata.get("deployment", {})) in {"completed", "deployed"}:
            facts.append(_fact("deployment_completed", _state(metadata["deployment"]), evidence_refs=[node["id"]]))
    return facts


def _impact_signals(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals = []
    for node in evidence:
        for field, value, category, unit in _metric_items(node["properties"]["metadata"]):
            metric_value = value["value"] if isinstance(value, dict) else value
            if not isinstance(metric_value, int | float) or isinstance(metric_value, bool):
                continue
            signals.append(
                {
                    "category": category,
                    "classification": "explicit_metric",
                    "value": metric_value,
                    "unit": unit,
                    "evidence_refs": [node["id"]],
                    "reason": f"explicit structured metric: {field}",
                    "metadata": {"field": field},
                }
            )
    return signals


def _metric_items(metadata: dict[str, Any]) -> list[tuple[str, Any, str, str]]:
    candidates: list[tuple[str, Any, str, str]] = []
    for key, value in metadata.items():
        known = _known_metric(key, value)
        if known is not None:
            candidates.append(known)
        if isinstance(value, dict) and key == "metrics":
            for nested_key, nested_value in value.items():
                nested_known = _known_metric(nested_key, nested_value)
                if nested_known is not None:
                    candidates.append(nested_known)
    return candidates


def _known_metric(field: str, value: Any) -> tuple[str, Any, str, str] | None:
    if isinstance(value, dict):
        metric_value = value.get("value")
        unit = value.get("unit")
        category = value.get("category")
        if (
            isinstance(metric_value, int | float)
            and not isinstance(metric_value, bool)
            and isinstance(unit, str)
            and unit.strip()
            and isinstance(category, str)
            and category in _IMPACT_CATEGORIES
        ):
            return field, value, category, unit.strip()
    if isinstance(value, int | float) and not isinstance(value, bool) and field in _KNOWN_METRICS:
        category, unit = _KNOWN_METRICS[field]
        return field, value, category, unit
    return None


def _confidence(
    action_facts: list[dict[str, Any]],
    outcome_facts: list[dict[str, Any]],
    impact_signals: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    if outcome_facts and impact_signals:
        return "high", ["all_refs_valid", "explicit_metric_present", "explicit_outcome_present"]
    if action_facts and outcome_facts:
        return "medium", ["actions_present", "explicit_outcome_present", "no_explicit_metric"]
    return "low", ["all_refs_valid", "structural_facts_only"]


def _warnings(
    props: dict[str, Any],
    actions: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[str]:
    warnings = []
    if not props.get("actions"):
        warnings.append("no_explicit_actions")
    if not outcomes:
        warnings.append("no_explicit_outcome_evidence")
    if not signals:
        warnings.append("no_explicit_impact_signal")
    if props.get("started_at") is None or props.get("ended_at") is None:
        warnings.append("missing_work_dates")
    if len(evidence) == 1:
        warnings.append("single_evidence_only")
    return canonical_refs(warnings)


def _state(metadata: Any) -> str:
    if isinstance(metadata, dict):
        value = metadata.get("state", metadata.get("status", ""))
    else:
        value = ""
    return str(value).strip().lower()


def _string_list(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    if value != sorted(set(value)):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    return value


def _fact(
    fact_type: str,
    value: object,
    *,
    evidence_refs: list[str] | None = None,
    contribution_ref: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    fact: dict[str, Any] = {"fact_type": fact_type, "value": value}
    if evidence_refs is not None:
        fact["evidence_refs"] = canonical_refs(evidence_refs)
    if contribution_ref is not None:
        fact["contribution_ref"] = contribution_ref
    if reason is not None:
        fact["reason"] = reason
    return fact


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_json = {json.dumps(item, sort_keys=True): item for item in items}
    return [by_json[key] for key in sorted(by_json)]


def _json(value: object, field: str) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON serializable") from exc
