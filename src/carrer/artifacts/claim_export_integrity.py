"""Read-only integrity checks for local claim-based artifact exports."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from carrer.artifacts.claim_export_review import (
    ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT,
    ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM,
    ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE,
    validate_artifact_export_receipt_contract,
    validate_original_artifact_export_acceptance_audit,
    validate_persisted_artifact_export_receipt,
)
from carrer.contributions.analysis import parse_iso8601_with_timezone
from carrer.domain.hashing import stable_hash
from carrer.domain.identity import canonical_refs
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

REPORT_TYPE = "artifact_export_integrity"
REPORT_STATUSES = frozenset({"consistent", "repairable", "blocked"})
ISSUE_SEVERITIES = frozenset({"error", "warning"})
REPAIRABLE_ISSUES = frozenset(
    {"artifact_edge_missing", "claim_edge_missing", "evidence_edge_missing", "export_temp_file_present"}
)
BLOCKING_ISSUES = frozenset(
    {
        "receipt_not_found",
        "receipt_wrong_node_type",
        "receipt_wrong_source_type",
        "receipt_contract_invalid",
        "receipt_persisted_validation_invalid",
        "export_file_missing",
        "export_file_content_mismatch",
        "artifact_edge_unexpected",
        "claim_edge_unexpected",
        "evidence_edge_unexpected",
        "original_acceptance_audit_missing",
        "original_acceptance_audit_invalid",
        "original_acceptance_audit_duplicate",
    }
)
ISSUE_CODES = REPAIRABLE_ISSUES | BLOCKING_ISSUES
EXPORT_EDGE_TYPES = {
    ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT,
    ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM,
    ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE,
}


def artifact_export_integrity_report_id(
    receipt_id: str,
    output_directory: str,
    expected_content_hash: str,
    issue_codes: list[str],
) -> str:
    _required_str(receipt_id, "receipt_id")
    _required_str(output_directory, "output_directory")
    _required_str(expected_content_hash, "expected_content_hash")
    codes = _ordered_issue_codes(issue_codes)
    return "artifact_export_integrity_report:" + stable_hash(
        [receipt_id, output_directory, expected_content_hash, codes]
    )


def check_artifact_export_integrity(
    store: GraphStore,
    receipt_id: str,
    *,
    output_directory: str | Path,
    checked_at: str,
) -> dict[str, Any]:
    _require_store(store)
    _required_str(receipt_id, "receipt_id")
    parse_iso8601_with_timezone(checked_at, "checked_at")
    base = _output_directory(output_directory)
    output = str(base)
    issues: list[dict[str, Any]] = []
    checks = {
        "receipt_contract_valid": False,
        "persisted_contract_valid": False,
        "file_exists": False,
        "file_content_matches": None,
        "temporary_file_exists": False,
        "artifact_edge_valid": False,
        "claim_edges_valid": False,
        "evidence_edges_valid": False,
        "original_audit_valid": False,
    }
    receipt = store.nodes.get(receipt_id)
    valid: dict[str, Any] | None = None
    props: dict[str, Any] = {}
    source_artifact_id = "unknown"
    export_candidate_id = "unknown"
    candidate_created_at = "unknown"
    expected_file_name = "unknown.md"
    expected_hash = "unknown"
    claim_refs: list[str] = []
    evidence_refs: list[str] = []
    metadata = {
        "export_scope": "unknown",
        "export_format": "unknown",
        "privacy_level": "unknown",
        "artifact_type": "unknown",
        "audience": "unknown",
        "claim_count": 0,
        "evidence_count": 0,
        "warning_count": 0,
    }

    if receipt is None:
        issues.append(_issue("receipt_not_found", repairable=False))
    elif not isinstance(receipt, dict) or receipt.get("node_type") != "ArtifactExportReceipt":
        issues.append(
            _issue(
                "receipt_wrong_node_type",
                repairable=False,
                actual=receipt.get("node_type") if isinstance(receipt, dict) else None,
            )
        )
    else:
        raw_props = receipt.get("properties")
        if isinstance(raw_props, dict) and raw_props.get("source_type") != "career_claim":
            issues.append(_issue("receipt_wrong_source_type", repairable=False, actual=raw_props.get("source_type")))
        try:
            valid = validate_artifact_export_receipt_contract(receipt)
            checks["receipt_contract_valid"] = True
        except ValueError as exc:
            issues.append(_issue("receipt_contract_invalid", repairable=False, reason=str(exc)))
        if valid is not None:
            props = valid["properties"]
            source_artifact_id = props["source_artifact_id"]
            export_candidate_id = props["export_candidate_id"]
            candidate_created_at = props["candidate_created_at"]
            expected_file_name = props["file_name"]
            expected_hash = props["content_hash"]
            claim_refs = list(props["claim_refs"])
            evidence_refs = list(props["evidence_refs"])
            metadata = {
                "export_scope": props["export_scope"],
                "export_format": props["export_format"],
                "privacy_level": props["privacy_level"],
                "artifact_type": props["metadata"]["artifact_type"],
                "audience": props["metadata"]["audience"],
                "claim_count": props["metadata"]["claim_count"],
                "evidence_count": props["metadata"]["evidence_count"],
                "warning_count": props["metadata"]["warning_count"],
            }
            _audit_issues(store, valid, issues, checks)
            try:
                validate_persisted_artifact_export_receipt(store, valid)
                checks["persisted_contract_valid"] = True
            except ValueError as exc:
                issues.append(_issue("receipt_persisted_validation_invalid", repairable=False, reason=str(exc)))

            target = _safe_child(base, expected_file_name)
            checks["file_exists"] = target.exists()
            if not checks["file_exists"]:
                issues.append(_issue("export_file_missing", repairable=False, file_name=expected_file_name))
            else:
                with target.open("r", encoding="utf-8", newline="") as handle:
                    actual_content = handle.read()
                matches = stable_hash(actual_content) == expected_hash
                checks["file_content_matches"] = matches
                if not matches:
                    issues.append(
                        _issue("export_file_content_mismatch", repairable=False, file_name=expected_file_name)
                    )
            tmp = _safe_child(base, "." + expected_file_name + ".tmp")
            checks["temporary_file_exists"] = tmp.exists()
            if tmp.exists():
                issues.append(_issue("export_temp_file_present", repairable=True, file_name=tmp.name))
            _edge_issues(store, valid, issues, checks)

    issues = _dedupe_issues(issues)
    codes = [item["code"] for item in issues]
    status = (
        "consistent" if not issues else "repairable" if all(code in REPAIRABLE_ISSUES for code in codes) else "blocked"
    )
    report = {
        "id": artifact_export_integrity_report_id(receipt_id, output, expected_hash, codes),
        "report_type": REPORT_TYPE,
        "checked_at": checked_at,
        "receipt_id": receipt_id,
        "source_artifact_id": source_artifact_id,
        "export_candidate_id": export_candidate_id,
        "candidate_created_at": candidate_created_at,
        "output_directory": output,
        "expected_file_name": expected_file_name,
        "expected_content_hash": expected_hash,
        "status": status,
        "issues": issues,
        "checks": checks,
        "traceability": {
            "receipt_ref": receipt_id,
            "professional_artifact_ref": source_artifact_id,
            "claim_refs": claim_refs,
            "evidence_refs": evidence_refs,
        },
        "metadata": metadata,
    }
    return validate_artifact_export_integrity_report(report)


def validate_artifact_export_integrity_report(report: object) -> dict[str, Any]:
    try:
        if not isinstance(report, dict):
            raise ValueError("ArtifactExportIntegrityReport must be a dict")
        _required_str(report.get("id"), "id")
        if report.get("report_type") != REPORT_TYPE:
            raise ValueError("report_type must be artifact_export_integrity")
        parse_iso8601_with_timezone(report.get("checked_at"), "checked_at")
        for field in (
            "receipt_id",
            "source_artifact_id",
            "export_candidate_id",
            "candidate_created_at",
            "output_directory",
            "expected_file_name",
            "expected_content_hash",
        ):
            _required_str(report.get(field), field)
        if report.get("status") not in REPORT_STATUSES:
            raise ValueError("status is invalid")
        issues = _validate_issues(report.get("issues"))
        codes = [item["code"] for item in issues]
        if report["status"] == "consistent" and issues:
            raise ValueError("consistent report cannot contain issues")
        if report["status"] == "repairable" and (not issues or any(code not in REPAIRABLE_ISSUES for code in codes)):
            raise ValueError("repairable report requires only repairable issues")
        if report["status"] == "blocked" and not any(code in BLOCKING_ISSUES for code in codes):
            raise ValueError("blocked report requires a blocking issue")
        _checks(report.get("checks"))
        _semantic_checks(report, codes)
        trace = report.get("traceability")
        if not isinstance(trace, dict):
            raise ValueError("traceability must be an object")
        if trace.get("receipt_ref") != report["receipt_id"]:
            raise ValueError("traceability.receipt_ref must match receipt_id")
        if trace.get("professional_artifact_ref") != report["source_artifact_id"]:
            raise ValueError("traceability.professional_artifact_ref must match source_artifact_id")
        _refs(trace.get("claim_refs"), "traceability.claim_refs", allow_empty=True)
        _refs(trace.get("evidence_refs"), "traceability.evidence_refs", allow_empty=True)
        meta = report.get("metadata")
        if not isinstance(meta, dict):
            raise ValueError("metadata must be an object")
        for field in ("export_scope", "export_format", "privacy_level", "artifact_type", "audience"):
            _required_str(meta.get(field), f"metadata.{field}")
        for field in ("claim_count", "evidence_count", "warning_count"):
            if not isinstance(meta.get(field), int) or meta[field] < 0:
                raise ValueError(f"metadata.{field} must be a non-negative integer")
        if meta["claim_count"] != len(trace["claim_refs"]) or meta["evidence_count"] != len(trace["evidence_refs"]):
            raise ValueError("metadata counts must match refs")
        if report["id"] != artifact_export_integrity_report_id(
            report["receipt_id"], report["output_directory"], report["expected_content_hash"], codes
        ):
            raise ValueError("ArtifactExportIntegrityReport id does not match stable identity")
        _json(report, "ArtifactExportIntegrityReport")
        return report
    except (TypeError, KeyError, AttributeError, IndexError) as exc:
        raise ValueError("ArtifactExportIntegrityReport is invalid") from exc


def _audit_issues(
    store: GraphStore, receipt: dict[str, Any], issues: list[dict[str, Any]], checks: dict[str, Any]
) -> None:
    try:
        validate_original_artifact_export_acceptance_audit(store, receipt)
        checks["original_audit_valid"] = True
    except ValueError as exc:
        message = str(exc)
        if "requires original export acceptance audit" in message:
            issues.append(_issue("original_acceptance_audit_missing", repairable=False))
        elif "exactly one original export acceptance audit" in message:
            issues.append(_issue("original_acceptance_audit_duplicate", repairable=False))
        else:
            issues.append(_issue("original_acceptance_audit_invalid", repairable=False, reason=message))


def _edge_issues(
    store: GraphStore, receipt: dict[str, Any], issues: list[dict[str, Any]], checks: dict[str, Any]
) -> None:
    props = receipt["properties"]
    expected = {
        ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT: [props["source_artifact_id"]],
        ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM: props["claim_refs"],
        ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE: props["evidence_refs"],
    }
    codes = {
        ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT: (
            "artifact_edge_missing",
            "artifact_edge_unexpected",
            "artifact_edge_valid",
        ),
        ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM: ("claim_edge_missing", "claim_edge_unexpected", "claim_edges_valid"),
        ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE: (
            "evidence_edge_missing",
            "evidence_edge_unexpected",
            "evidence_edges_valid",
        ),
    }
    outgoing = [
        edge
        for edge in store.edges
        if isinstance(edge, dict)
        and edge.get("from_node_id") == receipt["id"]
        and edge.get("edge_type") in EXPORT_EDGE_TYPES
    ]
    for edge_type, targets in expected.items():
        actual = [edge.get("to_node_id") for edge in outgoing if edge.get("edge_type") == edge_type]
        malformed = [repr(ref) for ref in actual if not isinstance(ref, str) or not ref]
        unique_actual = canonical_refs(ref for ref in actual if isinstance(ref, str) and ref)
        missing = [ref for ref in targets if ref not in unique_actual]
        unexpected = [ref for ref in unique_actual if ref not in targets]
        duplicates = canonical_refs(ref for ref in unique_actual if actual.count(ref) > 1)
        missing_code, unexpected_code, check_name = codes[edge_type]
        if missing:
            issues.append(_issue(missing_code, repairable=True, refs=missing))
        if unexpected or duplicates or malformed:
            issues.append(
                _issue(unexpected_code, repairable=False, refs=canonical_refs([*unexpected, *duplicates, *malformed]))
            )
        checks[check_name] = not missing and not unexpected and not duplicates and not malformed


def _issue(code: str, *, repairable: bool, **details: Any) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "warning" if repairable else "error",
        "repairable": repairable,
        "details": details,
    }


def _dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [json.loads(key) for key in sorted({json.dumps(issue, sort_keys=True) for issue in issues})]


def _validate_issues(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("issues must be a list")
    issues = _dedupe_issues(value)
    if value != issues:
        raise ValueError("issues must be ordered and deduplicated")
    for issue in issues:
        if not isinstance(issue, dict):
            raise ValueError("issues must contain objects")
        if issue.get("code") not in ISSUE_CODES:
            raise ValueError("issue code is invalid")
        if issue.get("severity") not in ISSUE_SEVERITIES:
            raise ValueError("issue severity is invalid")
        if issue.get("repairable") is not (issue["code"] in REPAIRABLE_ISSUES):
            raise ValueError("issue repairable flag is inconsistent")
        if not isinstance(issue.get("details"), dict):
            raise ValueError("issue details must be an object")
    return issues


def _checks(value: object) -> None:
    expected = {
        "receipt_contract_valid",
        "persisted_contract_valid",
        "file_exists",
        "file_content_matches",
        "temporary_file_exists",
        "artifact_edge_valid",
        "claim_edges_valid",
        "evidence_edges_valid",
        "original_audit_valid",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("checks must contain the expected keys")
    for key in expected - {"file_content_matches"}:
        if not isinstance(value[key], bool):
            raise ValueError(f"checks.{key} has invalid type")
    if not isinstance(value["file_content_matches"], bool) and value["file_content_matches"] is not None:
        raise ValueError("checks.file_content_matches has invalid type")


def _semantic_checks(report: dict[str, Any], codes: list[str]) -> None:
    checks = report["checks"]
    code_set = set(codes)
    consistent_checks = {
        "receipt_contract_valid": True,
        "persisted_contract_valid": True,
        "file_exists": True,
        "file_content_matches": True,
        "temporary_file_exists": False,
        "artifact_edge_valid": True,
        "claim_edges_valid": True,
        "evidence_edges_valid": True,
        "original_audit_valid": True,
    }
    if report["status"] == "consistent" and checks != consistent_checks:
        bad = next(key for key, expected in consistent_checks.items() if checks[key] != expected)
        raise ValueError(f"checks.{bad} is contradictory")
    _require_check(code_set, {"receipt_not_found", "receipt_wrong_node_type"}, checks, "receipt_contract_valid", False)
    _require_check(
        code_set,
        {"receipt_not_found", "receipt_wrong_node_type", "receipt_persisted_validation_invalid"},
        checks,
        "persisted_contract_valid",
        False,
    )
    _require_check(
        code_set, {"receipt_wrong_source_type", "receipt_contract_invalid"}, checks, "receipt_contract_valid", False
    )
    if "export_file_missing" in code_set:
        _expect(checks, "file_exists", False)
        _expect(checks, "file_content_matches", None)
    if "export_file_content_mismatch" in code_set:
        _expect(checks, "file_exists", True)
        _expect(checks, "file_content_matches", False)
    _require_check(code_set, {"export_temp_file_present"}, checks, "temporary_file_exists", True)
    _require_check(
        code_set, {"artifact_edge_missing", "artifact_edge_unexpected"}, checks, "artifact_edge_valid", False
    )
    _require_check(code_set, {"claim_edge_missing", "claim_edge_unexpected"}, checks, "claim_edges_valid", False)
    _require_check(
        code_set, {"evidence_edge_missing", "evidence_edge_unexpected"}, checks, "evidence_edges_valid", False
    )
    _require_check(
        code_set,
        {
            "original_acceptance_audit_missing",
            "original_acceptance_audit_invalid",
            "original_acceptance_audit_duplicate",
        },
        checks,
        "original_audit_valid",
        False,
    )
    if checks["receipt_contract_valid"]:
        if checks["file_exists"] is False:
            _require_issue(code_set, {"export_file_missing"}, "file_exists")
        if checks["file_exists"] is True and checks["file_content_matches"] is False:
            _require_issue(code_set, {"export_file_content_mismatch"}, "file_content_matches")
        if checks["temporary_file_exists"] is True:
            _require_issue(code_set, {"export_temp_file_present"}, "temporary_file_exists")
        if checks["artifact_edge_valid"] is False:
            _require_issue(code_set, {"artifact_edge_missing", "artifact_edge_unexpected"}, "artifact_edge_valid")
        if checks["claim_edges_valid"] is False:
            _require_issue(code_set, {"claim_edge_missing", "claim_edge_unexpected"}, "claim_edges_valid")
        if checks["evidence_edges_valid"] is False:
            _require_issue(code_set, {"evidence_edge_missing", "evidence_edge_unexpected"}, "evidence_edges_valid")
        if checks["original_audit_valid"] is False:
            _require_issue(
                code_set,
                {
                    "original_acceptance_audit_missing",
                    "original_acceptance_audit_invalid",
                    "original_acceptance_audit_duplicate",
                },
                "original_audit_valid",
            )
        if checks["persisted_contract_valid"] is False:
            _require_issue(code_set, {"receipt_persisted_validation_invalid"}, "persisted_contract_valid")
    if report["status"] == "repairable":
        for key in (
            "receipt_contract_valid",
            "persisted_contract_valid",
            "file_exists",
            "file_content_matches",
            "original_audit_valid",
        ):
            _expect(checks, key, True)
        if not code_set & {"artifact_edge_missing", "artifact_edge_unexpected"}:
            _expect(checks, "artifact_edge_valid", True)
        if not code_set & {"claim_edge_missing", "claim_edge_unexpected"}:
            _expect(checks, "claim_edges_valid", True)
        if not code_set & {"evidence_edge_missing", "evidence_edge_unexpected"}:
            _expect(checks, "evidence_edges_valid", True)
        if "export_temp_file_present" not in code_set:
            _expect(checks, "temporary_file_exists", False)


def _require_check(
    codes: set[str], relevant_codes: set[str], checks: dict[str, Any], check_name: str, expected: object
) -> None:
    if codes & relevant_codes:
        _expect(checks, check_name, expected)


def _require_issue(codes: set[str], expected_codes: set[str], check_name: str) -> None:
    if not codes & expected_codes:
        raise ValueError(f"checks.{check_name} requires a matching issue")


def _expect(checks: dict[str, Any], check_name: str, expected: object) -> None:
    if checks[check_name] != expected:
        raise ValueError(f"checks.{check_name} is contradictory")


def _output_directory(output_directory: str | Path) -> Path:
    if not isinstance(output_directory, str | Path):
        raise ValueError("output_directory must be a path")
    base = Path(output_directory).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        raise ValueError("output_directory must be an existing directory")
    return base


def _safe_child(base: Path, file_name: str) -> Path:
    if not file_name or "/" in file_name or "\\" in file_name or ".." in file_name:
        raise ValueError("file_name is unsafe")
    target = (base / file_name).resolve()
    if os.path.commonpath([str(base), str(target)]) != str(base):
        raise ValueError("output path escapes output_directory")
    return target


def _ordered_issue_codes(value: object) -> list[str]:
    if not isinstance(value, list) or value != sorted(set(value)) or any(code not in ISSUE_CODES for code in value):
        raise ValueError("issue_codes must be ordered, deduplicated known issue codes")
    return value


def _refs(value: object, field: str, *, allow_empty: bool) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ValueError(f"{field} must be ordered, deduplicated strings")
    if value != sorted(set(value)) or any(not isinstance(ref, str) or not ref for ref in value):
        raise ValueError(f"{field} must be ordered, deduplicated strings")
    return value


def _require_store(store: object) -> None:
    requirements = ("nodes", "edges", "audit_records")
    missing = [name for name in requirements if not _has_graph_api(store, name)]
    if missing:
        raise ValueError("store is missing required graph API: " + ", ".join(missing))


def _has_graph_api(store: object, name: str) -> bool:
    if not hasattr(store, name):
        return False
    value = getattr(store, name)
    if name == "nodes":
        return isinstance(value, dict)
    if name in {"edges", "audit_records"}:
        return isinstance(value, list)
    return callable(value)


def _required_str(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is required")


def _json(value: object, field: str) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON serializable") from exc


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
