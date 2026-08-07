"""Explicit human repair decisions for local artifact export integrity."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from carrer.artifacts.claim_export_integrity import (
    REPAIRABLE_ISSUES,
    artifact_export_integrity_report_id,
    check_artifact_export_integrity,
    validate_artifact_export_integrity_report,
)
from carrer.artifacts.claim_export_review import (
    ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT,
    ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM,
    ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE,
)
from carrer.contributions.analysis import parse_iso8601_with_timezone
from carrer.domain.hashing import stable_hash
from carrer.domain.identity import canonical_refs
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

CANDIDATE_TYPE = "artifact_export_repair"
REPAIR_RECEIPT_TYPE = "ArtifactExportRepairReceipt"
REPAIR_ACTIONS = frozenset(
    {
        "create_missing_artifact_edge",
        "create_missing_claim_edges",
        "create_missing_evidence_edges",
        "remove_stale_temp_file",
    }
)
ACTION_BY_ISSUE = {
    "artifact_edge_missing": "create_missing_artifact_edge",
    "claim_edge_missing": "create_missing_claim_edges",
    "evidence_edge_missing": "create_missing_evidence_edges",
    "export_temp_file_present": "remove_stale_temp_file",
}
ACCEPT_ORDER = [
    "create_missing_artifact_edge",
    "create_missing_claim_edges",
    "create_missing_evidence_edges",
    "remove_stale_temp_file",
]


def artifact_export_repair_candidate_id(report_id: str, repair_actions: list[str]) -> str:
    _required_str(report_id, "report_id")
    actions = _ordered_actions(repair_actions)
    return "artifact_export_repair_candidate:" + stable_hash([report_id, actions])


def artifact_export_repair_receipt_id(repair_candidate_id: str) -> str:
    _required_str(repair_candidate_id, "repair_candidate_id")
    return "artifact_export_repair_receipt:" + stable_hash(["artifact_export_repair", repair_candidate_id])


def build_artifact_export_repair_candidate(
    store: GraphStore,
    report: dict[str, Any],
    *,
    created_at: str,
) -> dict[str, Any]:
    _require_store(store)
    valid = validate_artifact_export_integrity_report(report)
    parse_iso8601_with_timezone(created_at, "created_at")
    if valid["status"] != "repairable":
        raise ValueError("ArtifactExportRepairCandidate requires a repairable report")
    current = check_artifact_export_integrity(
        store,
        valid["receipt_id"],
        output_directory=valid["output_directory"],
        checked_at=valid["checked_at"],
    )
    if _canonical_json(current) != _canonical_json(valid):
        raise ValueError("ArtifactExportIntegrityReport is stale or tampered")
    issue_codes = canonical_refs(issue["code"] for issue in current["issues"])
    actions = _ordered_actions(canonical_refs(ACTION_BY_ISSUE[code] for code in issue_codes))
    candidate = {
        "id": artifact_export_repair_candidate_id(current["id"], actions),
        "candidate_type": CANDIDATE_TYPE,
        "created_at": created_at,
        "report_id": current["id"],
        "report_checked_at": current["checked_at"],
        "receipt_id": current["receipt_id"],
        "source_artifact_id": current["source_artifact_id"],
        "repair_actions": actions,
        "issue_codes": issue_codes,
        "output_directory": current["output_directory"],
        "file_name": current["expected_file_name"],
        "content_hash": current["expected_content_hash"],
        "traceability": current["traceability"],
        "metadata": {
            "export_scope": current["metadata"]["export_scope"],
            "export_format": current["metadata"]["export_format"],
            "privacy_level": current["metadata"]["privacy_level"],
        },
    }
    return validate_artifact_export_repair_candidate(candidate)


def validate_artifact_export_repair_candidate(candidate: object) -> dict[str, Any]:
    try:
        if not isinstance(candidate, dict):
            raise ValueError("ArtifactExportRepairCandidate must be a dict")
        _required_str(candidate.get("id"), "id")
        if candidate.get("candidate_type") != CANDIDATE_TYPE:
            raise ValueError("candidate_type must be artifact_export_repair")
        parse_iso8601_with_timezone(candidate.get("created_at"), "created_at")
        parse_iso8601_with_timezone(candidate.get("report_checked_at"), "report_checked_at")
        for field in ("report_id", "receipt_id", "source_artifact_id", "output_directory", "file_name", "content_hash"):
            _required_str(candidate.get(field), field)
        _safe_file_name(candidate["file_name"])
        issue_codes = _ordered_issue_codes(candidate.get("issue_codes"))
        actions = _ordered_actions(candidate.get("repair_actions"))
        expected_actions = _ordered_actions(canonical_refs(ACTION_BY_ISSUE[code] for code in issue_codes))
        if actions != expected_actions:
            raise ValueError("repair_actions must match issue_codes")
        trace = candidate.get("traceability")
        if not isinstance(trace, dict):
            raise ValueError("traceability must be an object")
        if trace.get("receipt_ref") != candidate["receipt_id"]:
            raise ValueError("traceability.receipt_ref must match receipt_id")
        if trace.get("professional_artifact_ref") != candidate["source_artifact_id"]:
            raise ValueError("traceability.professional_artifact_ref must match source_artifact_id")
        _refs(trace.get("claim_refs"), "traceability.claim_refs")
        _refs(trace.get("evidence_refs"), "traceability.evidence_refs")
        meta = candidate.get("metadata")
        if not isinstance(meta, dict):
            raise ValueError("metadata must be an object")
        for field in ("export_scope", "export_format", "privacy_level"):
            _required_str(meta.get(field), f"metadata.{field}")
        if candidate["report_id"] != artifact_export_integrity_report_id(
            candidate["receipt_id"], candidate["output_directory"], candidate["content_hash"], issue_codes
        ):
            raise ValueError("report_id does not match candidate issue context")
        if candidate["id"] != artifact_export_repair_candidate_id(candidate["report_id"], actions):
            raise ValueError("ArtifactExportRepairCandidate id does not match stable identity")
        _json(candidate, "ArtifactExportRepairCandidate")
        return candidate
    except (TypeError, KeyError, AttributeError, IndexError) as exc:
        raise ValueError("ArtifactExportRepairCandidate is invalid") from exc


def validate_artifact_export_repair_acceptance_audit(
    store: GraphStore,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    _require_store(store)
    valid = validate_artifact_export_repair_candidate(candidate)
    matches = []
    for record in store.audit_records:
        if not isinstance(record, dict):
            raise ValueError("audit records must contain objects")
        metadata = record.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("audit metadata must be an object")
        if record.get("audit_type") != "artifact_export_repair_accepted":
            continue
        if not isinstance(metadata, dict):
            raise ValueError("repair acceptance audit metadata must be an object")
        if (
            record.get("result") == "accepted"
            and metadata.get("repair_candidate_id") == valid["id"]
            and metadata.get("receipt_id") == valid["receipt_id"]
            and metadata.get("applied") is True
            and metadata.get("final_status") == "consistent"
        ):
            matches.append(record)
    if not matches:
        raise ValueError("ArtifactExportRepairCandidate has no previous successful repair acceptance")
    if len(matches) != 1:
        raise ValueError("ArtifactExportRepairCandidate must have exactly one original repair acceptance audit")
    first = matches[0]
    metadata = first["metadata"]
    repair_receipt = validate_persisted_artifact_export_repair_receipt(store, valid)
    expected = {
        "target_refs": [valid["receipt_id"], valid["report_id"], valid["id"]],
        "result": "accepted",
        "actor": repair_receipt["properties"]["actor"],
        "created_at": repair_receipt["properties"]["decided_at"],
        "metadata.actor": repair_receipt["properties"]["actor"],
        "metadata.decided_at": repair_receipt["properties"]["decided_at"],
        "metadata.report_id": valid["report_id"],
        "metadata.repair_candidate_id": valid["id"],
        "metadata.repair_candidate_hash": stable_hash(valid),
        "metadata.receipt_id": valid["receipt_id"],
        "metadata.issue_codes": valid["issue_codes"],
        "metadata.repair_actions": valid["repair_actions"],
        "metadata.initial_status": "repairable",
        "metadata.final_status": "consistent",
        "metadata.applied": True,
        "metadata.original_decision_fingerprint": repair_receipt["properties"]["original_decision_fingerprint"],
    }
    actual = {
        "target_refs": first.get("target_refs"),
        "result": first.get("result"),
        "actor": first.get("actor"),
        "created_at": first.get("created_at"),
        "metadata.actor": metadata.get("actor"),
        "metadata.decided_at": metadata.get("decided_at"),
        "metadata.report_id": metadata.get("report_id"),
        "metadata.repair_candidate_id": metadata.get("repair_candidate_id"),
        "metadata.repair_candidate_hash": metadata.get("repair_candidate_hash"),
        "metadata.receipt_id": metadata.get("receipt_id"),
        "metadata.issue_codes": metadata.get("issue_codes"),
        "metadata.repair_actions": metadata.get("repair_actions"),
        "metadata.initial_status": metadata.get("initial_status"),
        "metadata.final_status": metadata.get("final_status"),
        "metadata.applied": metadata.get("applied"),
        "metadata.original_decision_fingerprint": metadata.get("original_decision_fingerprint"),
    }
    if (
        actual != expected
        or first.get("actor") != metadata.get("actor")
        or first.get("created_at") != metadata.get("decided_at")
    ):
        raise ValueError("previous repair acceptance audit does not match candidate")
    if type(metadata.get("repaired_edge_count")) is not int or metadata["repaired_edge_count"] < 0:
        raise ValueError("repair acceptance audit repaired_edge_count must be a non-negative integer")
    if not isinstance(metadata.get("temporary_file_removed"), bool):
        raise ValueError("repair acceptance audit temporary_file_removed must be a bool")
    if metadata["repaired_edge_count"] == 0 and metadata["temporary_file_removed"] is False:
        raise ValueError("repair acceptance audit must record at least one mutation")
    if repair_receipt["properties"]["repaired_edge_count"] != metadata["repaired_edge_count"]:
        raise ValueError("repair receipt repaired_edge_count does not match audit")
    if repair_receipt["properties"]["temporary_file_removed"] != metadata["temporary_file_removed"]:
        raise ValueError("repair receipt temporary_file_removed does not match audit")
    if repair_receipt["properties"]["audit_id"] != first["id"]:
        raise ValueError("repair receipt audit id does not match original audit")
    return first


def validate_persisted_artifact_export_repair_receipt(
    store: GraphStore,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    _require_store(store, "nodes", "audit_records", "nodes_by_type")
    valid = validate_artifact_export_repair_candidate(candidate)
    receipt_id = artifact_export_repair_receipt_id(valid["id"])
    same_candidate = [
        node
        for node in store.nodes_by_type(REPAIR_RECEIPT_TYPE)
        if isinstance(node, dict)
        and isinstance(node.get("properties"), dict)
        and node["properties"].get("repair_candidate_id") == valid["id"]
    ]
    if len(same_candidate) != 1 or same_candidate[0].get("id") != receipt_id:
        raise ValueError("ArtifactExportRepairCandidate must have exactly one repair receipt")
    repair_receipt = validate_artifact_export_repair_receipt_contract(store.nodes.get(receipt_id))
    props = repair_receipt["properties"]
    expected = {
        "repair_candidate_id": valid["id"],
        "report_id": valid["report_id"],
        "receipt_id": valid["receipt_id"],
        "issue_codes": valid["issue_codes"],
        "repair_actions": valid["repair_actions"],
    }
    actual = {
        "repair_candidate_id": props.get("repair_candidate_id"),
        "report_id": props.get("report_id"),
        "receipt_id": props.get("receipt_id"),
        "issue_codes": props.get("issue_codes"),
        "repair_actions": props.get("repair_actions"),
    }
    if actual != expected:
        raise ValueError("ArtifactExportRepairReceipt does not match candidate")
    matches = [
        record
        for record in store.audit_records
        if isinstance(record, dict)
        and record.get("id") == props["audit_id"]
        and record.get("audit_type") == "artifact_export_repair_accepted"
        and record.get("result") == "accepted"
        and isinstance(record.get("metadata"), dict)
        and record["metadata"].get("applied") is True
    ]
    if len(matches) > 1:
        raise ValueError("ArtifactExportRepairReceipt audit_id is duplicated")
    if matches:
        audit = matches[0]
        expected_node = _repair_receipt_node(
            valid,
            audit,
            repaired_edges=audit["metadata"]["repaired_edge_count"],
            removed_tmp=audit["metadata"]["temporary_file_removed"],
        )
        if _canonical_json(repair_receipt) != _canonical_json(expected_node):
            raise ValueError("ArtifactExportRepairReceipt does not match original audit")
    return repair_receipt


def validate_artifact_export_repair_receipt_contract(node: object) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ValueError("ArtifactExportRepairReceipt node must be a dict")
    _required_str(node.get("id"), "id")
    if node.get("node_type") != REPAIR_RECEIPT_TYPE:
        raise ValueError("node_type must be ArtifactExportRepairReceipt")
    parse_iso8601_with_timezone(node.get("created_at"), "created_at")
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    for field in (
        "repair_candidate_id",
        "report_id",
        "receipt_id",
        "actor",
        "decided_at",
        "audit_id",
        "original_decision_fingerprint",
    ):
        _required_str(props.get(field), field)
    parse_iso8601_with_timezone(props["decided_at"], "decided_at")
    if node["created_at"] != props["decided_at"]:
        raise ValueError("created_at must match decided_at")
    issue_codes = _ordered_issue_codes(props.get("issue_codes"))
    repair_actions = _ordered_actions(props.get("repair_actions"))
    if type(props.get("repaired_edge_count")) is not int or props["repaired_edge_count"] < 0:
        raise ValueError("repaired_edge_count must be a non-negative integer")
    if not isinstance(props.get("temporary_file_removed"), bool):
        raise ValueError("temporary_file_removed must be a bool")
    if props["repaired_edge_count"] == 0 and props["temporary_file_removed"] is False:
        raise ValueError("repair receipt must record at least one mutation")
    if node["id"] != artifact_export_repair_receipt_id(props["repair_candidate_id"]):
        raise ValueError("ArtifactExportRepairReceipt id does not match stable identity")
    if props["original_decision_fingerprint"] != _decision_fingerprint(
        {
            "id": props["repair_candidate_id"],
            "report_id": props["report_id"],
            "receipt_id": props["receipt_id"],
            "issue_codes": issue_codes,
            "repair_actions": repair_actions,
        },
        decision_actor=props["actor"],
        decided_at=props["decided_at"],
        repaired_edges=props["repaired_edge_count"],
        removed_tmp=props["temporary_file_removed"],
    ):
        raise ValueError("original_decision_fingerprint does not match repair receipt")
    _json(node, "ArtifactExportRepairReceipt")
    return node


def accept_artifact_export_repair(
    store: GraphStore,
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    verified_at: str,
) -> dict[str, Any]:
    _require_store(store, "nodes", "edges", "audit_records", "create_node", "create_edge")
    _require_actor(decision_actor)
    parse_iso8601_with_timezone(decided_at, "decided_at")
    parse_iso8601_with_timezone(verified_at, "verified_at")
    valid = validate_artifact_export_repair_candidate(candidate)
    current_report = check_artifact_export_integrity(
        store,
        valid["receipt_id"],
        output_directory=valid["output_directory"],
        checked_at=valid["report_checked_at"],
    )
    if current_report["status"] == "consistent":
        _finalize_incomplete_repair_acceptance(store, valid, decision_actor=decision_actor, decided_at=decided_at)
        validate_artifact_export_repair_acceptance_audit(store, valid)
        verified_report = check_artifact_export_integrity(
            store,
            valid["receipt_id"],
            output_directory=valid["output_directory"],
            checked_at=verified_at,
        )
        _audit_repair_accept(
            store,
            valid,
            decision_actor=decision_actor,
            decided_at=decided_at,
            final_status="consistent",
            applied=False,
            repaired_edges=0,
            removed_tmp=False,
        )
        return {
            "report": verified_report,
            "decision": "accepted",
            "applied": False,
            "repaired_edge_count": 0,
            "temporary_file_removed": False,
        }
    if current_report["status"] != "repairable":
        raise ValueError("ArtifactExportRepairCandidate cannot be accepted for blocked export state")
    current = build_artifact_export_repair_candidate(store, current_report, created_at=valid["created_at"])
    if _canonical_json(current) != _canonical_json(valid):
        raise ValueError("ArtifactExportRepairCandidate is stale or tampered")
    receipt = store.nodes[current["receipt_id"]]
    props = receipt["properties"]
    repaired_edges = 0
    removed_tmp = False
    for action in ACCEPT_ORDER:
        if action not in current["repair_actions"]:
            continue
        if action == "create_missing_artifact_edge":
            before = len(store.edges)
            store.create_edge(ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT, current["receipt_id"], props["source_artifact_id"])
            repaired_edges += len(store.edges) - before
        elif action == "create_missing_claim_edges":
            repaired_edges += _create_missing_edges(
                store, ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM, current["receipt_id"], props["claim_refs"]
            )
        elif action == "create_missing_evidence_edges":
            repaired_edges += _create_missing_edges(
                store, ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE, current["receipt_id"], props["evidence_refs"]
            )
        elif action == "remove_stale_temp_file":
            tmp = _tmp_path(Path(current["output_directory"]), current["file_name"])
            if tmp.exists():
                tmp.unlink()
                removed_tmp = True
    final = check_artifact_export_integrity(
        store,
        current["receipt_id"],
        output_directory=current["output_directory"],
        checked_at=verified_at,
    )
    if final["status"] != "consistent":
        raise ValueError("artifact export repair did not produce a consistent report")
    audit = _repair_accept_audit(
        current,
        decided_at=decided_at,
        decision_actor=decision_actor,
        final_status=final["status"],
        applied=True,
        repaired_edges=repaired_edges,
        removed_tmp=removed_tmp,
        audit_index=len(store.audit_records),
    )
    repair_receipt = _repair_receipt_node(current, audit, repaired_edges=repaired_edges, removed_tmp=removed_tmp)
    store.create_node(repair_receipt)
    _append_audit(store, audit)
    validate_artifact_export_repair_acceptance_audit(store, current)
    return {
        "report": final,
        "decision": "accepted",
        "applied": True,
        "repaired_edge_count": repaired_edges,
        "temporary_file_removed": removed_tmp,
    }


def reject_artifact_export_repair(
    store: GraphStore,
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    reason: str = "",
) -> dict[str, Any]:
    _require_store(store)
    _require_actor(decision_actor)
    parse_iso8601_with_timezone(decided_at, "decided_at")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")
    current = _current_candidate(store, candidate)
    _audit(
        store,
        "artifact_export_repair_rejected",
        [current["receipt_id"], current["report_id"], current["id"]],
        "rejected",
        {
            "report_id": current["report_id"],
            "repair_candidate_id": current["id"],
            "receipt_id": current["receipt_id"],
            "issue_codes": current["issue_codes"],
            "repair_actions": current["repair_actions"],
            "actor": decision_actor,
            "decided_at": decided_at,
            "initial_status": "repairable",
            "reason": reason,
        },
        decided_at=decided_at,
        actor=decision_actor,
    )
    return {
        "candidate_id": current["id"],
        "receipt_id": current["receipt_id"],
        "decision": "rejected",
        "reason": reason,
    }


def _current_candidate(store: GraphStore, candidate: object) -> dict[str, Any]:
    valid = validate_artifact_export_repair_candidate(candidate)
    current_report = check_artifact_export_integrity(
        store,
        valid["receipt_id"],
        output_directory=valid["output_directory"],
        checked_at=valid["report_checked_at"],
    )
    current = build_artifact_export_repair_candidate(store, current_report, created_at=valid["created_at"])
    if _canonical_json(current) != _canonical_json(valid):
        raise ValueError("ArtifactExportRepairCandidate is stale or tampered")
    return current


def _finalize_incomplete_repair_acceptance(
    store: GraphStore,
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
) -> None:
    receipt_id = artifact_export_repair_receipt_id(candidate["id"])
    if receipt_id not in store.nodes:
        return
    if any(
        isinstance(record, dict)
        and record.get("audit_type") == "artifact_export_repair_accepted"
        and isinstance(record.get("metadata"), dict)
        and record["metadata"].get("repair_candidate_id") == candidate["id"]
        and record["metadata"].get("applied") is True
        for record in store.audit_records
    ):
        return
    repair_receipt = validate_persisted_artifact_export_repair_receipt(store, candidate)
    props = repair_receipt["properties"]
    if props["actor"] != decision_actor or props["decided_at"] != decided_at:
        raise ValueError("incomplete repair acceptance requires original actor and decided_at")
    audit = _repair_accept_audit(
        candidate,
        decision_actor=props["actor"],
        decided_at=props["decided_at"],
        final_status="consistent",
        applied=True,
        repaired_edges=props["repaired_edge_count"],
        removed_tmp=props["temporary_file_removed"],
        audit_index=len(store.audit_records),
    )
    if audit["id"] != props["audit_id"]:
        raise ValueError("incomplete repair acceptance audit id cannot be recovered deterministically")
    _append_audit(store, audit)


def _audit_repair_accept(
    store: GraphStore,
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    final_status: str,
    applied: bool,
    repaired_edges: int,
    removed_tmp: bool,
) -> dict[str, Any]:
    audit = _repair_accept_audit(
        candidate,
        decision_actor=decision_actor,
        decided_at=decided_at,
        final_status=final_status,
        applied=applied,
        repaired_edges=repaired_edges,
        removed_tmp=removed_tmp,
        audit_index=len(store.audit_records),
    )
    _append_audit(store, audit)
    return audit


def _repair_accept_audit(
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    final_status: str,
    applied: bool,
    repaired_edges: int,
    removed_tmp: bool,
    audit_index: int,
) -> dict[str, Any]:
    fingerprint = _decision_fingerprint(
        candidate,
        decision_actor=decision_actor,
        decided_at=decided_at,
        repaired_edges=repaired_edges,
        removed_tmp=removed_tmp,
    )
    metadata = {
        "report_id": candidate["report_id"],
        "repair_candidate_id": candidate["id"],
        "repair_candidate_hash": stable_hash(candidate),
        "receipt_id": candidate["receipt_id"],
        "issue_codes": candidate["issue_codes"],
        "repair_actions": candidate["repair_actions"],
        "actor": decision_actor,
        "decided_at": decided_at,
        "initial_status": "repairable",
        "final_status": final_status,
        "applied": applied,
        "repaired_edge_count": repaired_edges,
        "temporary_file_removed": removed_tmp,
    }
    if applied:
        metadata["original_decision_fingerprint"] = fingerprint
    target_refs = [candidate["receipt_id"], candidate["report_id"], candidate["id"]]
    return {
        "id": "audit:"
        + stable_hash(["artifact_export_repair_accepted", target_refs, "accepted", metadata, decided_at, audit_index]),
        "audit_type": "artifact_export_repair_accepted",
        "created_at": decided_at,
        "actor": decision_actor,
        "target_refs": target_refs,
        "result": "accepted",
        "metadata": metadata,
    }


def _repair_receipt_node(
    candidate: dict[str, Any],
    audit: dict[str, Any],
    *,
    repaired_edges: int,
    removed_tmp: bool,
) -> dict[str, Any]:
    metadata = audit["metadata"]
    return validate_artifact_export_repair_receipt_contract(
        {
            "id": artifact_export_repair_receipt_id(candidate["id"]),
            "node_type": REPAIR_RECEIPT_TYPE,
            "created_at": metadata["decided_at"],
            "properties": {
                "repair_candidate_id": candidate["id"],
                "report_id": candidate["report_id"],
                "receipt_id": candidate["receipt_id"],
                "actor": metadata["actor"],
                "decided_at": metadata["decided_at"],
                "issue_codes": candidate["issue_codes"],
                "repair_actions": candidate["repair_actions"],
                "repaired_edge_count": repaired_edges,
                "temporary_file_removed": removed_tmp,
                "audit_id": audit["id"],
                "original_decision_fingerprint": metadata["original_decision_fingerprint"],
            },
        }
    )


def _decision_fingerprint(
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    repaired_edges: int,
    removed_tmp: bool,
) -> str:
    return stable_hash(
        [
            candidate["id"],
            candidate["report_id"],
            candidate["receipt_id"],
            decision_actor,
            decided_at,
            candidate["issue_codes"],
            candidate["repair_actions"],
            repaired_edges,
            removed_tmp,
        ]
    )


def _create_missing_edges(store: GraphStore, edge_type: str, from_node_id: str, targets: list[str]) -> int:
    before = len(store.edges)
    for target in targets:
        store.create_edge(edge_type, from_node_id, target)
    return len(store.edges) - before


def _tmp_path(base: Path, file_name: str) -> Path:
    tmp = (base / ("." + file_name + ".tmp")).resolve()
    if os.path.commonpath([str(base.resolve()), str(tmp)]) != str(base.resolve()):
        raise ValueError("temporary path escapes output_directory")
    return tmp


def _audit(
    store: GraphStore,
    audit_type: str,
    target_refs: list[str],
    result: str,
    metadata: dict[str, Any],
    *,
    decided_at: str,
    actor: str,
) -> dict[str, Any]:
    record = {
        "id": "audit:" + stable_hash([audit_type, target_refs, result, metadata, decided_at, len(store.audit_records)]),
        "audit_type": audit_type,
        "created_at": decided_at,
        "actor": actor,
        "target_refs": target_refs,
        "result": result,
        "metadata": metadata,
    }
    return _append_audit(store, record)


def _append_audit(store: GraphStore, record: dict[str, Any]) -> dict[str, Any]:
    store.audit_records.append(record)
    return record


def _ordered_issue_codes(value: object) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or value != sorted(set(value))
        or any(code not in REPAIRABLE_ISSUES for code in value)
    ):
        raise ValueError("issue_codes must be ordered, deduplicated repairable issue codes")
    return value


def _ordered_actions(value: object) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or value != sorted(set(value))
        or any(action not in REPAIR_ACTIONS for action in value)
    ):
        raise ValueError("repair_actions must be ordered, deduplicated known actions")
    return value


def _refs(value: object, field: str) -> list[str]:
    if (
        not isinstance(value, list)
        or value != sorted(set(value))
        or any(not isinstance(ref, str) or not ref for ref in value)
    ):
        raise ValueError(f"{field} must be ordered, deduplicated strings")
    return value


def _safe_file_name(file_name: str) -> None:
    if not file_name or not file_name.endswith(".md") or "/" in file_name or "\\" in file_name or ".." in file_name:
        raise ValueError("file_name is unsafe")


def _require_store(
    store: object,
    *requirements: str,
) -> None:
    if not requirements:
        requirements = ("nodes", "edges", "audit_records", "nodes_by_type")
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


def _require_actor(actor: object) -> None:
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("decision_actor is required")


def _required_str(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is required")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json(value: object, field: str) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON serializable") from exc
