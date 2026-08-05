"""Deterministic read-only structural graph integrity reports."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, NamedTuple

from carrer.contributions.analysis import parse_iso8601_with_timezone
from carrer.domain.hashing import stable_hash
from carrer.domain.identity import canonical_refs

REPORT_TYPE = "graph_integrity"
REPORT_VERSION = "v1"
REPORT_STATUSES = frozenset({"valid", "invalid"})
ISSUE_SEVERITIES = frozenset({"error", "warning"})
ISSUE_SUBJECT_TYPES = frozenset({"node", "edge", "audit_record", "store"})
ISSUE_CODES = frozenset(
    {
        "NODE_KEY_ID_MISMATCH",
        "NODE_NOT_OBJECT",
        "NODE_ID_INVALID",
        "NODE_TYPE_INVALID",
        "NODE_CREATED_AT_INVALID",
        "NODE_PROPERTIES_INVALID",
        "EDGE_NOT_OBJECT",
        "EDGE_TYPE_INVALID",
        "EDGE_SOURCE_REF_INVALID",
        "EDGE_TARGET_REF_INVALID",
        "EDGE_SOURCE_NOT_FOUND",
        "EDGE_TARGET_NOT_FOUND",
        "DUPLICATE_EDGE",
        "AUDIT_RECORD_NOT_OBJECT",
        "AUDIT_TYPE_INVALID",
        "AUDIT_CREATED_AT_INVALID",
        "AUDIT_TARGET_REFS_INVALID",
        "AUDIT_RESULT_INVALID",
        "AUDIT_METADATA_INVALID",
        "AUDIT_TARGET_NOT_FOUND",
        "AUDIT_TARGET_REFS_DUPLICATED",
        "AUDIT_TARGET_REFS_NOT_CANONICAL",
    }
)


class _IssueContract(NamedTuple):
    severity: str
    subject_type: str
    collection: str
    field: str | None
    related_refs: str
    metadata: str


ISSUE_CONTRACTS = {
    "NODE_KEY_ID_MISMATCH": _IssueContract("error", "node", "nodes", "id", "nonempty", "empty"),
    "NODE_NOT_OBJECT": _IssueContract("error", "node", "nodes", None, "empty", "empty"),
    "NODE_ID_INVALID": _IssueContract("error", "node", "nodes", "id", "empty", "empty"),
    "NODE_TYPE_INVALID": _IssueContract("error", "node", "nodes", "node_type", "empty", "empty"),
    "NODE_CREATED_AT_INVALID": _IssueContract("error", "node", "nodes", "created_at", "empty", "empty"),
    "NODE_PROPERTIES_INVALID": _IssueContract("error", "node", "nodes", "properties", "empty", "empty"),
    "EDGE_NOT_OBJECT": _IssueContract("error", "edge", "edges", None, "empty", "empty"),
    "EDGE_TYPE_INVALID": _IssueContract("error", "edge", "edges", "edge_type", "empty", "empty"),
    "EDGE_SOURCE_REF_INVALID": _IssueContract("error", "edge", "edges", "from_node_id", "empty", "empty"),
    "EDGE_TARGET_REF_INVALID": _IssueContract("error", "edge", "edges", "to_node_id", "empty", "empty"),
    "EDGE_SOURCE_NOT_FOUND": _IssueContract("error", "edge", "edges", "from_node_id", "nonempty", "empty"),
    "EDGE_TARGET_NOT_FOUND": _IssueContract("error", "edge", "edges", "to_node_id", "nonempty", "empty"),
    "DUPLICATE_EDGE": _IssueContract("warning", "edge", "edges", None, "duplicate_edge", "duplicate_edge"),
    "AUDIT_RECORD_NOT_OBJECT": _IssueContract("error", "audit_record", "audit_records", None, "empty", "empty"),
    "AUDIT_TYPE_INVALID": _IssueContract("error", "audit_record", "audit_records", "audit_type", "empty", "empty"),
    "AUDIT_CREATED_AT_INVALID": _IssueContract(
        "error", "audit_record", "audit_records", "created_at", "empty", "empty"
    ),
    "AUDIT_TARGET_REFS_INVALID": _IssueContract(
        "error", "audit_record", "audit_records", "target_refs", "empty", "empty"
    ),
    "AUDIT_RESULT_INVALID": _IssueContract("error", "audit_record", "audit_records", "result", "empty", "empty"),
    "AUDIT_METADATA_INVALID": _IssueContract("error", "audit_record", "audit_records", "metadata", "empty", "empty"),
    "AUDIT_TARGET_NOT_FOUND": _IssueContract(
        "warning", "audit_record", "audit_records", "target_refs", "nonempty", "empty"
    ),
    "AUDIT_TARGET_REFS_DUPLICATED": _IssueContract(
        "warning", "audit_record", "audit_records", "target_refs", "nonempty", "empty"
    ),
    "AUDIT_TARGET_REFS_NOT_CANONICAL": _IssueContract(
        "warning", "audit_record", "audit_records", "target_refs", "nonempty", "empty"
    ),
}
PERSISTED_REF_PREFIXES = (
    "artifact:",
    "artifact_export_receipt:",
    "artifact_export_repair_receipt:",
    "career_claim:",
    "contribution:",
    "contribution_analysis:",
    "edge:",
    "evidence:",
    "knowledge:",
    "observation:",
)
NODE_SUBJECT_REF_PREFIXES = tuple(prefix for prefix in PERSISTED_REF_PREFIXES if prefix != "edge:")
NON_PERSISTED_REF_PREFIXES = (
    "artifact_export_repair_candidate:",
    "artifact_export_integrity_report:",
    "career_claim_candidate:",
    "claim_based_artifact:",
    "claim_based_artifact_export_candidate:",
    "contribution_analysis_candidate:",
    "contribution_candidate:",
    "graph_integrity_report:",
)
SAFE_STRUCTURAL_REF_PREFIXES = (
    PERSISTED_REF_PREFIXES
    + NON_PERSISTED_REF_PREFIXES
    + (
        "audit:",
        "graph_integrity_issue:",
        "graph_snapshot:",
    )
)
SAFE_ISSUE_FALLBACK_PREFIXES = (
    "audit_target:",
    "edge_endpoint:",
    "invalid_node_ref:",
    "node_key:",
)
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_graph_integrity(
    store: object,
    *,
    node_types: list[str] | None = None,
    severities: list[str] | None = None,
) -> dict[str, Any]:
    """Return an in-memory structural integrity report without mutating the graph store."""
    try:
        nodes, edges, audit_records = _store_parts(store)
        filters = {"node_types": _optional_strings(node_types, "node_types"), "severities": _severities(severities)}
        selected_node_types = filters["node_types"]
        issues = _node_issues(nodes, selected_node_types)
        issues.extend(_edge_issues(nodes, edges, selected_node_types))
        issues.extend(_audit_issues(nodes, audit_records, selected_node_types))
        issues = _ordered_issues(_dedupe_issues(issues))
        if filters["severities"] is not None:
            issues = [issue for issue in issues if issue["severity"] in filters["severities"]]
        snapshot = _graph_snapshot(nodes, edges, audit_records)
        report = {
            "id": "",
            "report_type": REPORT_TYPE,
            "report_version": REPORT_VERSION,
            "status": "invalid" if any(issue["severity"] == "error" for issue in issues) else "valid",
            "summary": _summary(nodes, edges, audit_records, issues),
            "snapshot": snapshot,
            "filters": filters,
            "issues": issues,
        }
        report["id"] = graph_integrity_report_id(report)
        return validate_graph_integrity_report(report)
    except (TypeError, KeyError, AttributeError, IndexError) as exc:
        raise ValueError("GraphIntegrityReport cannot be generated") from exc


def graph_integrity_report_id(report: object) -> str:
    """Return the deterministic report ID for a complete report or canonical report payload."""
    if not isinstance(report, dict):
        raise ValueError("report must be a dict")
    payload = {
        key: report.get(key)
        for key in ("report_type", "report_version", "status", "summary", "snapshot", "filters", "issues")
    }
    _json(payload, "GraphIntegrityReport identity payload")
    return "graph_integrity_report:" + stable_hash(payload)


def validate_graph_integrity_report(report: object) -> dict[str, Any]:
    """Validate, fully recount, and re-identify a GraphIntegrityReport."""
    try:
        if not isinstance(report, dict):
            raise ValueError("GraphIntegrityReport must be a dict")
        expected_keys = {"id", "report_type", "report_version", "status", "summary", "snapshot", "filters", "issues"}
        if set(report) != expected_keys:
            raise ValueError("GraphIntegrityReport fields are invalid")
        if report.get("report_type") != REPORT_TYPE:
            raise ValueError("report_type must be graph_integrity")
        if report.get("report_version") != REPORT_VERSION:
            raise ValueError("report_version must be v1")
        if report.get("status") not in REPORT_STATUSES:
            raise ValueError("status is invalid")
        snapshot = _validate_snapshot(report.get("snapshot"))
        filters = _validate_filters(report.get("filters"))
        if report["filters"] != filters:
            raise ValueError("filters must be canonical")
        issues = _validate_issues(report.get("issues"))
        expected_summary = _summary_from_issues(report.get("summary"), issues)
        if report.get("summary") != expected_summary:
            raise ValueError("summary is inconsistent")
        if (
            expected_summary["node_count"] != snapshot["node_count"]
            or expected_summary["edge_count"] != snapshot["edge_count"]
            or expected_summary["audit_record_count"] != snapshot["audit_record_count"]
        ):
            raise ValueError("summary counts must match snapshot counts")
        expected_status = "invalid" if any(issue["severity"] == "error" for issue in issues) else "valid"
        if report["status"] != expected_status:
            raise ValueError("status is inconsistent")
        if filters["severities"] is not None and any(
            issue["severity"] not in filters["severities"] for issue in issues
        ):
            raise ValueError("issues do not match severity filter")
        if report["id"] != graph_integrity_report_id(report):
            raise ValueError("GraphIntegrityReport id does not match stable identity")
        _json(report, "GraphIntegrityReport")
        return report
    except (TypeError, KeyError, AttributeError, IndexError) as exc:
        raise ValueError("GraphIntegrityReport is invalid") from exc


def _store_parts(store: object) -> tuple[dict[Any, Any], list[Any], list[Any]]:
    if not hasattr(store, "nodes") or not isinstance(store.nodes, dict):
        raise ValueError("store is missing required graph API: nodes")
    if not hasattr(store, "edges") or not isinstance(store.edges, list):
        raise ValueError("store is missing required graph API: edges")
    if not hasattr(store, "audit_records") or not isinstance(store.audit_records, list):
        raise ValueError("store is missing required graph API: audit_records")
    return store.nodes, store.edges, store.audit_records


def _node_issues(nodes: dict[Any, Any], node_types: list[str] | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key in sorted(nodes, key=_safe_sort_key):
        node = nodes[key]
        subject = _node_subject_ref(key)
        if not isinstance(node, dict):
            if node_types is None:
                issues.append(_issue("NODE_NOT_OBJECT", "error", "node", subject, f"nodes.{_path_key(key)}"))
            continue
        node_type = node.get("node_type")
        if node_types is not None and node_type not in node_types:
            continue
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            issues.append(_issue("NODE_ID_INVALID", "error", "node", subject, f"nodes.{_path_key(key)}.id"))
        elif key != node_id:
            issues.append(
                _issue(
                    "NODE_KEY_ID_MISMATCH",
                    "error",
                    "node",
                    subject,
                    f"nodes.{_path_key(key)}.id",
                    related_refs=[_safe_issue_ref(node_id, fallback_prefix="invalid_node_ref:")],
                )
            )
        if not _text(node_type):
            issues.append(_issue("NODE_TYPE_INVALID", "error", "node", subject, f"nodes.{_path_key(key)}.node_type"))
        if not _timestamp(node.get("created_at"), "created_at"):
            issues.append(
                _issue("NODE_CREATED_AT_INVALID", "error", "node", subject, f"nodes.{_path_key(key)}.created_at")
            )
        if not isinstance(node.get("properties"), dict):
            issues.append(
                _issue("NODE_PROPERTIES_INVALID", "error", "node", subject, f"nodes.{_path_key(key)}.properties")
            )
    return issues


def _edge_issues(nodes: dict[Any, Any], edges: list[Any], node_types: list[str] | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    valid_node_ids = {key for key, node in nodes.items() if isinstance(key, str) and isinstance(node, dict)}
    semantic_edges: list[tuple[str, str, str]] = []
    for edge in edges:
        ref = _edge_ref(edge)
        if not isinstance(edge, dict):
            issues.append(_issue("EDGE_NOT_OBJECT", "error", "edge", ref, f"edges.{ref}"))
            continue
        if not _edge_in_scope(nodes, edge, node_types):
            continue
        edge_type = edge.get("edge_type")
        source = edge.get("from_node_id")
        target = edge.get("to_node_id")
        if not _text(edge_type):
            issues.append(_issue("EDGE_TYPE_INVALID", "error", "edge", ref, f"edges.{ref}.edge_type"))
        if not isinstance(source, str) or not source.strip():
            issues.append(_issue("EDGE_SOURCE_REF_INVALID", "error", "edge", ref, f"edges.{ref}.from_node_id"))
        elif source not in valid_node_ids:
            issues.append(
                _issue(
                    "EDGE_SOURCE_NOT_FOUND",
                    "error",
                    "edge",
                    ref,
                    f"edges.{ref}.from_node_id",
                    related_refs=[_safe_issue_ref(source, fallback_prefix="edge_endpoint:")],
                )
            )
        if not isinstance(target, str) or not target.strip():
            issues.append(_issue("EDGE_TARGET_REF_INVALID", "error", "edge", ref, f"edges.{ref}.to_node_id"))
        elif target not in valid_node_ids:
            issues.append(
                _issue(
                    "EDGE_TARGET_NOT_FOUND",
                    "error",
                    "edge",
                    ref,
                    f"edges.{ref}.to_node_id",
                    related_refs=[_safe_issue_ref(target, fallback_prefix="edge_endpoint:")],
                )
            )
        if (
            isinstance(edge_type, str)
            and edge_type.strip()
            and isinstance(source, str)
            and source.strip()
            and isinstance(target, str)
            and target.strip()
        ):
            semantic_edges.append((edge_type, source, target))
    for edge_type, source, target in sorted(key for key, count in Counter(semantic_edges).items() if count > 1):
        ref = _semantic_edge_ref(edge_type, source, target)
        issues.append(
            _issue(
                "DUPLICATE_EDGE",
                "warning",
                "edge",
                ref,
                "edges",
                related_refs=[
                    _safe_issue_ref(source, fallback_prefix="edge_endpoint:"),
                    _safe_issue_ref(target, fallback_prefix="edge_endpoint:"),
                ],
                metadata={"duplicate_count": Counter(semantic_edges)[(edge_type, source, target)]},
            )
        )
    return issues


def _audit_issues(
    nodes: dict[Any, Any], audit_records: list[Any], node_types: list[str] | None
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    valid_node_ids = {key for key, node in nodes.items() if isinstance(key, str) and isinstance(node, dict)}
    for record in audit_records:
        ref = _audit_ref(record)
        if not isinstance(record, dict):
            issues.append(_issue("AUDIT_RECORD_NOT_OBJECT", "error", "audit_record", ref, f"audit_records.{ref}"))
            continue
        if not _text(record.get("audit_type")):
            issues.append(_issue("AUDIT_TYPE_INVALID", "error", "audit_record", ref, f"audit_records.{ref}.audit_type"))
        if not _timestamp(record.get("created_at"), "created_at"):
            issues.append(
                _issue("AUDIT_CREATED_AT_INVALID", "error", "audit_record", ref, f"audit_records.{ref}.created_at")
            )
        target_refs = record.get("target_refs")
        valid_target_refs = isinstance(target_refs, list) and all(_text(value) for value in target_refs)
        if not valid_target_refs:
            issues.append(
                _issue("AUDIT_TARGET_REFS_INVALID", "error", "audit_record", ref, f"audit_records.{ref}.target_refs")
            )
        if not _text(record.get("result")):
            issues.append(_issue("AUDIT_RESULT_INVALID", "error", "audit_record", ref, f"audit_records.{ref}.result"))
        if not isinstance(record.get("metadata"), dict):
            issues.append(
                _issue("AUDIT_METADATA_INVALID", "error", "audit_record", ref, f"audit_records.{ref}.metadata")
            )
        if not isinstance(target_refs, list) or not valid_target_refs:
            continue
        target_refs_list = [target for target in target_refs if isinstance(target, str)]
        persisted_targets = [target for target in target_refs_list if _should_be_persisted_ref(target, valid_node_ids)]
        scoped_targets = [target for target in persisted_targets if _node_ref_in_scope(nodes, target, node_types)]
        for target in canonical_refs(ref for ref in scoped_targets if ref not in valid_node_ids):
            issues.append(
                _issue(
                    "AUDIT_TARGET_NOT_FOUND",
                    "warning",
                    "audit_record",
                    ref,
                    f"audit_records.{ref}.target_refs",
                    related_refs=[_safe_issue_ref(target, fallback_prefix="audit_target:")],
                )
            )
        duplicated = canonical_refs(target for target, count in Counter(target_refs_list).items() if count > 1)
        if duplicated:
            issues.append(
                _issue(
                    "AUDIT_TARGET_REFS_DUPLICATED",
                    "warning",
                    "audit_record",
                    ref,
                    f"audit_records.{ref}.target_refs",
                    related_refs=[_safe_issue_ref(target, fallback_prefix="audit_target:") for target in duplicated],
                )
            )
        if (
            persisted_targets
            and len(persisted_targets) == len(target_refs_list)
            and target_refs_list != canonical_refs(target_refs_list)
        ):
            issues.append(
                _issue(
                    "AUDIT_TARGET_REFS_NOT_CANONICAL",
                    "warning",
                    "audit_record",
                    ref,
                    f"audit_records.{ref}.target_refs",
                    related_refs=[
                        _safe_issue_ref(target, fallback_prefix="audit_target:")
                        for target in canonical_refs(target_refs_list)
                    ],
                )
            )
    return issues


def _issue(
    code: str,
    severity: str,
    subject_type: str,
    subject_ref: str,
    path: str,
    *,
    related_refs: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issue = {
        "id": "",
        "code": code,
        "severity": severity,
        "subject_type": subject_type,
        "subject_ref": subject_ref,
        "path": path,
        "related_refs": canonical_refs(related_refs or []),
        "metadata": metadata if metadata is not None else {},
    }
    issue["id"] = _issue_id(issue)
    return issue


def _issue_id(issue: dict[str, Any]) -> str:
    payload = {
        key: issue.get(key)
        for key in ("code", "severity", "subject_type", "subject_ref", "path", "related_refs", "metadata")
    }
    _json(payload, "GraphIntegrityIssue identity payload")
    return "graph_integrity_issue:" + stable_hash(payload)


def _validate_issues(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("issues must be a list")
    if value != _ordered_issues(value):
        raise ValueError("issues must be ordered deterministically")
    seen: set[str] = set()
    for issue in value:
        if not isinstance(issue, dict):
            raise ValueError("issues must contain objects")
        if set(issue) != {"id", "code", "severity", "subject_type", "subject_ref", "path", "related_refs", "metadata"}:
            raise ValueError("issue fields are invalid")
        if issue["id"] in seen:
            raise ValueError("issues must be deduplicated")
        seen.add(issue["id"])
        if issue.get("code") not in ISSUE_CODES:
            raise ValueError("issue code is invalid")
        if issue.get("severity") not in ISSUE_SEVERITIES:
            raise ValueError("issue severity is invalid")
        if issue.get("subject_type") not in ISSUE_SUBJECT_TYPES:
            raise ValueError("issue subject_type is invalid")
        if not _is_safe_issue_ref(issue.get("subject_ref")):
            raise ValueError("issue subject_ref is invalid")
        if not _is_valid_issue_path(issue.get("path")):
            raise ValueError("issue path is invalid")
        refs = issue.get("related_refs")
        if not isinstance(refs, list) or refs != sorted(set(refs)) or any(not _is_safe_issue_ref(ref) for ref in refs):
            raise ValueError("issue related_refs must be ordered, deduplicated strings")
        _validate_issue_contract(issue)
        if issue["id"] != _issue_id(issue):
            raise ValueError("GraphIntegrityIssue id does not match stable identity")
    return value


def _ordered_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        issues,
        key=lambda issue: (
            issue.get("severity"),
            issue.get("code"),
            issue.get("subject_type"),
            issue.get("subject_ref"),
            issue.get("path"),
            issue.get("related_refs"),
            issue.get("id"),
        ),
    )


def _dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {issue["id"]: issue for issue in issues}
    return [by_id[key] for key in sorted(by_id)]


def _summary(
    nodes: dict[Any, Any], edges: list[Any], audit_records: list[Any], issues: list[dict[str, Any]]
) -> dict[str, int]:
    result = _issue_counts(issues)
    result.update({"node_count": len(nodes), "edge_count": len(edges), "audit_record_count": len(audit_records)})
    return {
        "node_count": result["node_count"],
        "edge_count": result["edge_count"],
        "audit_record_count": result["audit_record_count"],
        "issue_count": result["issue_count"],
        "error_count": result["error_count"],
        "warning_count": result["warning_count"],
    }


def _summary_from_issues(summary: object, issues: list[dict[str, Any]]) -> dict[str, int]:
    if not isinstance(summary, dict):
        raise ValueError("summary must be an object")
    expected_keys = {"node_count", "edge_count", "audit_record_count", "issue_count", "error_count", "warning_count"}
    if set(summary) != expected_keys:
        raise ValueError("summary fields are invalid")
    for key, value in summary.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"summary.{key} must be a non-negative integer")
    counts = _issue_counts(issues)
    return {
        "node_count": summary["node_count"],
        "edge_count": summary["edge_count"],
        "audit_record_count": summary["audit_record_count"],
        "issue_count": counts["issue_count"],
        "error_count": counts["error_count"],
        "warning_count": counts["warning_count"],
    }


def _graph_snapshot(nodes: dict[Any, Any], edges: list[Any], audit_records: list[Any]) -> dict[str, Any]:
    payload = {
        "report_version": REPORT_VERSION,
        "nodes": _canonical_node_items(nodes),
        "edges": _canonical_items(edges),
        "audit_records": _canonical_items([_audit_snapshot_record(record) for record in audit_records]),
    }
    return {
        "id": "graph_snapshot:" + stable_hash(payload),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "audit_record_count": len(audit_records),
    }


def _validate_snapshot(value: object) -> dict[str, int | str]:
    if not isinstance(value, dict):
        raise ValueError("snapshot must be an object")
    expected_keys = {"id", "node_count", "edge_count", "audit_record_count"}
    if set(value) != expected_keys:
        raise ValueError("snapshot fields are invalid")
    snapshot_id = value.get("id")
    if (
        not isinstance(snapshot_id, str)
        or not snapshot_id.startswith("graph_snapshot:")
        or not _is_safe_structural_ref(snapshot_id)
    ):
        raise ValueError("snapshot.id is invalid")
    for field in ("node_count", "edge_count", "audit_record_count"):
        count = value.get(field)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(f"snapshot.{field} must be a non-negative integer")
    _json(value, "GraphIntegrityReport snapshot")
    return {
        "id": snapshot_id,
        "node_count": value["node_count"],
        "edge_count": value["edge_count"],
        "audit_record_count": value["audit_record_count"],
    }


def _issue_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "issue_count": len(issues),
        "error_count": sum(1 for issue in issues if issue["severity"] == "error"),
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
    }


def _validate_filters(value: object) -> dict[str, list[str] | None]:
    if not isinstance(value, dict) or set(value) != {"node_types", "severities"}:
        raise ValueError("filters fields are invalid")
    return {
        "node_types": _optional_strings(value.get("node_types"), "node_types"),
        "severities": _severities(value.get("severities")),
    }


def _optional_strings(value: object, field: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or any(not _text(item) for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return canonical_refs(value)


def _severities(value: object) -> list[str] | None:
    severities = _optional_strings(value, "severities")
    if severities is not None and any(severity not in ISSUE_SEVERITIES for severity in severities):
        raise ValueError("severities contains unsupported values")
    return severities


def _edge_in_scope(nodes: dict[Any, Any], edge: dict[str, Any], node_types: list[str] | None) -> bool:
    if node_types is None:
        return True
    return _node_ref_in_scope(nodes, edge.get("from_node_id"), node_types) or _node_ref_in_scope(
        nodes, edge.get("to_node_id"), node_types
    )


def _node_ref_in_scope(nodes: dict[Any, Any], ref: object, node_types: list[str] | None) -> bool:
    if node_types is None:
        return True
    if not isinstance(ref, str):
        return True
    node = nodes.get(ref)
    return not isinstance(node, dict) or node.get("node_type") in node_types


def _should_be_persisted_ref(ref: str, existing_node_ids: set[str]) -> bool:
    if ref in existing_node_ids:
        return True
    if ref.startswith(NON_PERSISTED_REF_PREFIXES):
        return False
    return ref.startswith(PERSISTED_REF_PREFIXES)


def _edge_ref(edge: object) -> str:
    if isinstance(edge, dict):
        edge_id = edge.get("id")
        if isinstance(edge_id, str) and _is_subject_ref_compatible("edge", edge_id):
            return edge_id
        edge_type = edge.get("edge_type")
        source = edge.get("from_node_id")
        target = edge.get("to_node_id")
        if (
            isinstance(edge_type, str)
            and edge_type.strip()
            and isinstance(source, str)
            and _is_safe_structural_ref(source)
            and isinstance(target, str)
            and _is_safe_structural_ref(target)
        ):
            return _semantic_edge_ref(edge_type, source, target)
    return "edge:" + stable_hash(_safe_shape(edge))


def _semantic_edge_ref(edge_type: str, source: str, target: str) -> str:
    return "edge:" + stable_hash([edge_type, source, target])


def _audit_ref(record: object) -> str:
    if isinstance(record, dict):
        record_id = record.get("id")
        if isinstance(record_id, str) and _is_subject_ref_compatible("audit_record", record_id):
            return record_id
    return "audit:" + stable_hash(_safe_shape(_audit_snapshot_record(record)))


def _safe_shape(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        return [_safe_shape(item) for item in value]
    if isinstance(value, dict):
        return {
            "kind": "dict",
            "items": sorted(
                ({"key": _safe_shape(key), "value": _safe_shape(item)} for key, item in value.items()),
                key=_safe_json,
            ),
        }
    return {"kind": "non_json_value", "type": f"{type(value).__module__}.{type(value).__qualname__}"}


def _canonical_node_items(nodes: dict[Any, Any]) -> list[dict[str, object]]:
    return sorted(
        ({"key": _safe_shape(key), "value": _safe_shape(value)} for key, value in nodes.items()),
        key=_safe_json,
    )


def _canonical_items(values: list[Any]) -> list[object]:
    return sorted((_safe_shape(value) for value in values), key=_safe_json)


def _audit_snapshot_record(record: object) -> object:
    if not isinstance(record, dict):
        return record
    return {key: value for key, value in record.items() if key != "actor"}


def _safe_sort_key(value: object) -> str:
    return _safe_json(_safe_shape(value))


def _safe_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _node_subject_ref(value: object) -> str:
    if isinstance(value, str) and _is_subject_ref_compatible("node", value):
        return value
    return "node_key:" + stable_hash(_safe_shape(value))


def _path_key(value: object) -> str:
    return _node_subject_ref(value)


def _safe_issue_ref(value: object, *, fallback_prefix: str) -> str:
    if fallback_prefix not in SAFE_ISSUE_FALLBACK_PREFIXES:
        raise ValueError("fallback_prefix is invalid")
    if isinstance(value, str) and _is_safe_structural_ref(value):
        return value
    return fallback_prefix + stable_hash(_safe_shape(value))


def _is_safe_issue_ref(value: object) -> bool:
    return _is_safe_structural_ref(value) or _is_safe_fallback_ref(value)


def _is_safe_fallback_ref(value: object) -> bool:
    if not isinstance(value, str) or value.strip() != value:
        return False
    prefix, separator, suffix = value.partition(":")
    return separator == ":" and prefix + ":" in SAFE_ISSUE_FALLBACK_PREFIXES and _HASH_RE.fullmatch(suffix) is not None


def _is_valid_issue_path(value: object) -> bool:
    if value == "edges":
        return True
    if not isinstance(value, str):
        return False
    parts = value.split(".")
    if len(parts) not in {2, 3}:
        return False
    collection, ref = parts[0], parts[1]
    if collection == "nodes":
        return _is_safe_issue_ref(ref) and (
            len(parts) == 2 or parts[2] in {"id", "node_type", "created_at", "properties"}
        )
    if collection == "edges":
        return _is_safe_issue_ref(ref) and (len(parts) == 2 or parts[2] in {"edge_type", "from_node_id", "to_node_id"})
    if collection == "audit_records":
        return _is_safe_issue_ref(ref) and (
            len(parts) == 2 or parts[2] in {"audit_type", "created_at", "target_refs", "result", "metadata"}
        )
    return False


def _validate_issue_contract(issue: dict[str, Any]) -> None:
    contract = ISSUE_CONTRACTS.get(issue["code"])
    if contract is None:
        raise ValueError("issue code is invalid")
    if issue["severity"] != contract.severity:
        raise ValueError("issue severity does not match code")
    if issue["subject_type"] != contract.subject_type:
        raise ValueError("issue subject_type does not match code")
    if not _issue_subject_matches_contract(contract, issue["subject_ref"]):
        raise ValueError("issue subject_ref does not match subject_type")
    path_contract = _issue_path_contract(issue["path"])
    if path_contract is None:
        raise ValueError("issue path is invalid")
    collection, path_ref, field = path_contract
    if (collection, field) != (contract.collection, contract.field):
        raise ValueError("issue path does not match code")
    if path_ref is not None and path_ref != issue["subject_ref"]:
        raise ValueError("issue path ref does not match subject_ref")
    refs = issue["related_refs"]
    if contract.related_refs == "empty" and refs:
        raise ValueError("issue related_refs must be empty for this code")
    if contract.related_refs == "nonempty" and not refs:
        raise ValueError("issue related_refs must be non-empty for this code")
    if contract.related_refs == "duplicate_edge" and not 1 <= len(refs) <= 2:
        raise ValueError("DUPLICATE_EDGE related_refs must contain source and target refs")
    _validate_issue_metadata(contract, issue.get("metadata"))


def _issue_subject_matches_contract(contract: _IssueContract, subject_ref: object) -> bool:
    return _is_subject_ref_compatible(contract.subject_type, subject_ref)


def _is_subject_ref_compatible(subject_type: str, subject_ref: object) -> bool:
    if not isinstance(subject_ref, str):
        return False
    if subject_type == "node":
        return (
            subject_ref.startswith("node_key:")
            and _is_safe_fallback_ref(subject_ref)
            or (subject_ref.startswith(NODE_SUBJECT_REF_PREFIXES) and _is_safe_structural_ref(subject_ref))
        )
    if subject_type == "edge":
        return subject_ref.startswith("edge:") and _is_safe_structural_ref(subject_ref)
    if subject_type == "audit_record":
        return subject_ref.startswith("audit:") and _is_safe_structural_ref(subject_ref)
    return False


def _issue_path_contract(value: object) -> tuple[str, str | None, str | None] | None:
    if value == "edges":
        return ("edges", None, None)
    if not isinstance(value, str):
        return None
    parts = value.split(".")
    if len(parts) == 2:
        return (parts[0], parts[1], None)
    if len(parts) == 3:
        return (parts[0], parts[1], parts[2])
    return None


def _validate_issue_metadata(contract: _IssueContract, metadata: object) -> None:
    if not isinstance(metadata, dict):
        raise ValueError("issue metadata must be an object")
    if contract.metadata == "duplicate_edge":
        if set(metadata) != {"duplicate_count"}:
            raise ValueError("DUPLICATE_EDGE metadata fields are invalid")
        count = metadata.get("duplicate_count")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 1:
            raise ValueError("DUPLICATE_EDGE duplicate_count is invalid")
    elif contract.metadata == "empty" and metadata != {}:
        raise ValueError("issue metadata must be empty for this code")
    _json(metadata, "GraphIntegrityIssue metadata")


def _is_safe_structural_ref(value: object) -> bool:
    if not isinstance(value, str) or not value or value.strip() != value:
        return False
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    prefix, separator, suffix = value.partition(":")
    if separator != ":" or not prefix or not suffix or ":" in suffix:
        return False
    return prefix + ":" in SAFE_STRUCTURAL_REF_PREFIXES and _HASH_RE.fullmatch(suffix) is not None


def _timestamp(value: object, field: str) -> bool:
    try:
        parse_iso8601_with_timezone(value, field)
    except ValueError:
        return False
    return True


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _json(value: object, field: str) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON serializable") from exc
