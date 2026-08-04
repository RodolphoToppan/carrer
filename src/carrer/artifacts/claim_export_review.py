"""Explicit human review for local claim-based artifact export."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from carrer.artifacts.claim_export import (
    build_claim_based_artifact_export_candidate,
    validate_claim_based_artifact_export_candidate,
    validate_export_scope_privacy,
)
from carrer.contributions.analysis import parse_iso8601_with_timezone
from carrer.domain.hashing import stable_hash
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT = "ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT"
ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM = "ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM"
ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE = "ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE"

_CANDIDATE_MISMATCH = "ClaimBasedArtifactExportCandidate does not match current deterministic export candidate"
_RECEIPT_MISMATCH = "ArtifactExportReceipt node does not match deterministic export receipt"


def artifact_export_receipt_id(export_candidate_id: str) -> str:
    if not isinstance(export_candidate_id, str) or not export_candidate_id:
        raise ValueError("export_candidate_id is required")
    return "artifact_export_receipt:" + stable_hash(["claim_based_artifact_export", export_candidate_id])


def accept_claim_based_artifact_export(
    store: GraphStore,
    candidate: dict[str, Any],
    *,
    output_directory: str | Path,
    decision_actor: str,
    decided_at: str,
) -> dict[str, Any]:
    _require_store(store, "nodes", "edges", "audit_records", "create_node", "create_edge")
    _require_actor(decision_actor)
    parse_iso8601_with_timezone(decided_at, "decided_at")
    current = _current_candidate(store, candidate)
    target = _target_path(output_directory, current["file_name"])
    receipt = _receipt_node(current, decision_actor=decision_actor, decided_at=decided_at)
    existing = store.nodes.get(receipt["id"])
    if existing is not None:
        persisted = validate_persisted_artifact_export_receipt(store, existing)
        if persisted["properties"]["candidate_created_at"] != current["created_at"]:
            raise ValueError("export candidate created_at does not match existing ArtifactExportReceipt")
        if not target.exists():
            raise ValueError("ArtifactExportReceipt exists but exported file is missing")
        if target.read_text(encoding="utf-8") != current["content"]:
            raise ValueError("exported file content does not match receipt")
        _audit_accept(
            store,
            persisted,
            current,
            decision_actor=decision_actor,
            decided_at=decided_at,
            created=False,
            written=False,
        )
        return {"receipt": persisted, "decision": "accepted", "created": False, "written": False}
    if target.exists():
        raise ValueError("export target already exists without ArtifactExportReceipt")
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(target, current["content"])
    persisted, created = store.create_node(receipt)
    validate_artifact_export_receipt_contract(persisted)
    _create_edges(store, persisted, current)
    _audit_accept(
        store, persisted, current, decision_actor=decision_actor, decided_at=decided_at, created=created, written=True
    )
    validate_persisted_artifact_export_receipt(store, persisted)
    return {"receipt": persisted, "decision": "accepted", "created": created, "written": True}


def reject_claim_based_artifact_export(
    store: GraphStore,
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    reason: str = "",
) -> dict[str, Any]:
    _require_store(store, "nodes", "edges", "audit_records")
    _require_actor(decision_actor)
    parse_iso8601_with_timezone(decided_at, "decided_at")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")
    current = _current_candidate(store, candidate)
    _audit(
        store,
        "claim_based_artifact_export_rejected",
        [current["id"], current["source_artifact_id"], *current["traceability"]["claim_refs"]],
        "rejected",
        _audit_metadata(current, decision_actor=decision_actor, decided_at=decided_at) | {"reason": reason},
        decided_at=decided_at,
        actor=decision_actor,
    )
    return {
        "candidate_id": current["id"],
        "source_artifact_id": current["source_artifact_id"],
        "decision": "rejected",
        "reason": reason,
    }


def validate_artifact_export_receipt_contract(node: object) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ValueError("ArtifactExportReceipt node must be a dict")
    if not isinstance(node.get("id"), str) or not node["id"]:
        raise ValueError("id is required")
    if node.get("node_type") != "ArtifactExportReceipt":
        raise ValueError("node_type must be ArtifactExportReceipt")
    parse_iso8601_with_timezone(node.get("created_at"), "created_at")
    props = node.get("properties")
    if not isinstance(props, dict):
        raise ValueError("properties must be an object")
    for field in (
        "source_type",
        "source_artifact_id",
        "export_candidate_id",
        "export_scope",
        "export_format",
        "privacy_level",
        "file_name",
        "content_hash",
        "candidate_created_at",
        "output_path",
        "status",
        "review_actor",
        "reviewed_at",
    ):
        if not isinstance(props.get(field), str) or not props[field]:
            raise ValueError(f"{field} is required")
    if props["source_type"] != "career_claim":
        raise ValueError("source_type must be career_claim")
    if props["export_format"] != "markdown":
        raise ValueError("export_format must be markdown")
    validate_export_scope_privacy(props["export_scope"], props["privacy_level"])
    if props["status"] != "exported":
        raise ValueError("status must be exported")
    parse_iso8601_with_timezone(props["candidate_created_at"], "candidate_created_at")
    parse_iso8601_with_timezone(props["reviewed_at"], "reviewed_at")
    if node["created_at"] != props["reviewed_at"]:
        raise ValueError("created_at must match reviewed_at")
    _validate_file_name(props["file_name"])
    if props["output_path"] != props["file_name"]:
        raise ValueError("output_path must match file_name")
    _refs(props.get("claim_refs"), "claim_refs")
    _refs(props.get("evidence_refs"), "evidence_refs")
    metadata = props.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    for field in ("artifact_type", "audience", "artifact_version"):
        if not isinstance(metadata.get(field), str) or not metadata[field]:
            raise ValueError(f"metadata.{field} is required")
    for field in ("claim_count", "evidence_count", "warning_count"):
        if not isinstance(metadata.get(field), int) or metadata[field] < 0:
            raise ValueError(f"metadata.{field} must be a non-negative integer")
    if metadata["claim_count"] != len(props["claim_refs"]) or metadata["evidence_count"] != len(props["evidence_refs"]):
        raise ValueError("metadata counts must match refs")
    if node["id"] != artifact_export_receipt_id(props["export_candidate_id"]):
        raise ValueError("ArtifactExportReceipt id does not match stable identity")
    _json(node, "ArtifactExportReceipt node")
    return node


def validate_persisted_artifact_export_receipt(store: GraphStore, node: object) -> dict[str, Any]:
    _require_store(store, "nodes", "edges", "audit_records")
    valid = validate_artifact_export_receipt_contract(node)
    props = valid["properties"]
    current = build_claim_based_artifact_export_candidate(
        store,
        props["source_artifact_id"],
        export_scope=props["export_scope"],
        export_format=props["export_format"],
        created_at=props["candidate_created_at"],
    )
    expected = _receipt_node(current, decision_actor=props["review_actor"], decided_at=props["reviewed_at"])
    if _canonical_json(valid) != _canonical_json(expected):
        raise ValueError(_RECEIPT_MISMATCH)
    _validate_original_review_audit(store, valid)
    return valid


def _current_candidate(store: GraphStore, candidate: object) -> dict[str, Any]:
    valid = validate_claim_based_artifact_export_candidate(candidate)
    current = build_claim_based_artifact_export_candidate(
        store,
        valid["source_artifact_id"],
        export_scope=valid["export_scope"],
        export_format=valid["export_format"],
        created_at=valid["created_at"],
    )
    if _canonical_json(valid) != _canonical_json(current):
        raise ValueError(_CANDIDATE_MISMATCH)
    return current


def _receipt_node(candidate: dict[str, Any], *, decision_actor: str, decided_at: str) -> dict[str, Any]:
    trace = candidate["traceability"]
    metadata = candidate["metadata"]
    return validate_artifact_export_receipt_contract(
        {
            "id": artifact_export_receipt_id(candidate["id"]),
            "node_type": "ArtifactExportReceipt",
            "created_at": decided_at,
            "properties": {
                "source_type": "career_claim",
                "source_artifact_id": candidate["source_artifact_id"],
                "export_candidate_id": candidate["id"],
                "export_scope": candidate["export_scope"],
                "export_format": candidate["export_format"],
                "privacy_level": candidate["privacy_level"],
                "file_name": candidate["file_name"],
                "content_hash": candidate["content_hash"],
                "candidate_created_at": candidate["created_at"],
                "output_path": candidate["file_name"],
                "status": "exported",
                "review_actor": decision_actor,
                "reviewed_at": decided_at,
                "claim_refs": copy.deepcopy(trace["claim_refs"]),
                "evidence_refs": copy.deepcopy(trace["evidence_refs"]),
                "metadata": {
                    "artifact_type": candidate["artifact_type"],
                    "audience": candidate["audience"],
                    "artifact_version": metadata["artifact_version"],
                    "claim_count": metadata["claim_count"],
                    "evidence_count": metadata["evidence_count"],
                    "warning_count": metadata["warning_count"],
                },
            },
        }
    )


def _target_path(output_directory: str | Path, file_name: str) -> Path:
    if not isinstance(output_directory, str | Path):
        raise ValueError("output_directory must be a path")
    base = Path(output_directory).expanduser().resolve()
    if not file_name or "/" in file_name or "\\" in file_name or ".." in file_name:
        raise ValueError("file_name is unsafe")
    target = (base / file_name).resolve()
    if os.path.commonpath([str(base), str(target)]) != str(base):
        raise ValueError("output path escapes output_directory")
    return target


def _atomic_write(target: Path, content: str) -> None:
    tmp = target.with_name("." + target.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def _create_edges(store: GraphStore, receipt: dict[str, Any], candidate: dict[str, Any]) -> None:
    store.create_edge(ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT, receipt["id"], candidate["source_artifact_id"])
    for ref in candidate["traceability"]["claim_refs"]:
        store.create_edge(ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM, receipt["id"], ref)
    for ref in candidate["traceability"]["evidence_refs"]:
        store.create_edge(ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE, receipt["id"], ref)


def _audit_accept(
    store: GraphStore,
    receipt: dict[str, Any],
    candidate: dict[str, Any],
    *,
    decision_actor: str,
    decided_at: str,
    created: bool,
    written: bool,
) -> None:
    _audit(
        store,
        "claim_based_artifact_export_accepted",
        [receipt["id"], candidate["id"], candidate["source_artifact_id"], *candidate["traceability"]["claim_refs"]],
        "accepted",
        _audit_metadata(candidate, decision_actor=decision_actor, decided_at=decided_at)
        | {"receipt_id": receipt["id"], "created": created, "written": written},
        decided_at=decided_at,
        actor=decision_actor,
    )


def _audit_metadata(candidate: dict[str, Any], *, decision_actor: str, decided_at: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate["id"],
        "source_artifact_id": candidate["source_artifact_id"],
        "artifact_type": candidate["artifact_type"],
        "export_scope": candidate["export_scope"],
        "export_format": candidate["export_format"],
        "privacy_level": candidate["privacy_level"],
        "content_hash": candidate["content_hash"],
        "candidate_created_at": candidate["created_at"],
        "actor": decision_actor,
        "decided_at": decided_at,
        "claim_count": candidate["metadata"]["claim_count"],
        "evidence_count": candidate["metadata"]["evidence_count"],
        "warning_count": candidate["metadata"]["warning_count"],
    }


def _audit(
    store: GraphStore,
    audit_type: str,
    target_refs: list[str],
    result: str,
    metadata: dict[str, Any],
    *,
    decided_at: str,
    actor: str,
) -> None:
    store.audit_records.append(
        {
            "id": "audit:"
            + stable_hash([audit_type, target_refs, result, metadata, decided_at, len(store.audit_records)]),
            "audit_type": audit_type,
            "created_at": decided_at,
            "actor": actor,
            "target_refs": target_refs,
            "result": result,
            "metadata": metadata,
        }
    )


def _validate_original_review_audit(store: GraphStore, receipt: dict[str, Any]) -> None:
    accepted = [
        record
        for record in store.audit_records
        if record.get("audit_type") == "claim_based_artifact_export_accepted"
        and record.get("metadata", {}).get("receipt_id") == receipt["id"]
        and record.get("metadata", {}).get("created") is True
    ]
    if not accepted:
        raise ValueError("ArtifactExportReceipt requires original export acceptance audit")
    if len(accepted) != 1:
        raise ValueError("ArtifactExportReceipt must have exactly one original export acceptance audit")
    first = accepted[0]
    first_index = store.audit_records.index(first)
    props = receipt["properties"]
    metadata = first.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("original export acceptance audit metadata must be an object")
    expected = {
        "result": "accepted",
        "actor": props["review_actor"],
        "created_at": props["reviewed_at"],
        "metadata.actor": props["review_actor"],
        "metadata.decided_at": props["reviewed_at"],
        "metadata.receipt_id": receipt["id"],
        "metadata.candidate_id": props["export_candidate_id"],
        "metadata.candidate_created_at": props["candidate_created_at"],
        "metadata.source_artifact_id": props["source_artifact_id"],
        "metadata.created": True,
        "metadata.written": True,
    }
    actual = {
        "result": first.get("result"),
        "actor": first.get("actor"),
        "created_at": first.get("created_at"),
        "metadata.actor": metadata.get("actor"),
        "metadata.decided_at": metadata.get("decided_at"),
        "metadata.receipt_id": metadata.get("receipt_id"),
        "metadata.candidate_id": metadata.get("candidate_id"),
        "metadata.candidate_created_at": metadata.get("candidate_created_at"),
        "metadata.source_artifact_id": metadata.get("source_artifact_id"),
        "metadata.created": metadata.get("created"),
        "metadata.written": metadata.get("written"),
    }
    if actual != expected:
        raise ValueError("original export acceptance audit does not match ArtifactExportReceipt")
    expected_audit_id = "audit:" + stable_hash(
        [
            first.get("audit_type"),
            first.get("target_refs"),
            first.get("result"),
            metadata,
            first.get("created_at"),
            first_index,
        ]
    )
    if first.get("id") != expected_audit_id:
        raise ValueError("original export acceptance audit id does not match metadata")


def _validate_file_name(file_name: str) -> None:
    if not file_name or not file_name.endswith(".md") or "/" in file_name or "\\" in file_name or ".." in file_name:
        raise ValueError("file_name is unsafe")


def _refs(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    if value != sorted(set(value)) or any(not isinstance(ref, str) or not ref for ref in value):
        raise ValueError(f"{field} must be ordered, deduplicated, non-empty strings")
    return value


def _require_actor(actor: object) -> None:
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("decision_actor is required")


def _require_store(store: object, *requirements: str) -> None:
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


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json(value: object, field: str) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON serializable") from exc
