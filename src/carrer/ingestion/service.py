from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from carrer.domain.hashing import stable_hash
from carrer.domain.timestamps import now
from carrer.storage.json_graph_storage import JsonGraphStorage

from .normalization import normalize_source_export
from .validation import validate_source_export_v1


def load_fixture(path: str | Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(Path(path).read_text(encoding="utf-8")))


def load_source_input(path: str | Path) -> dict[str, Any]:
    data = load_fixture(path)
    if data.get("format") == "source_export_v1":
        validate_source_export_v1(data)
        return normalize_source_export(data)
    return data


def _node(node_id: str, node_type: str, **properties: object) -> dict[str, Any]:
    return {"id": node_id, "node_type": node_type, "created_at": now(), "properties": properties}


def evidence_type_for(record_type: str, payload: dict[str, Any]) -> str:
    if record_type == "work_item":
        return "WORK_ITEM_EXISTS"
    if record_type == "commit":
        return "COMMIT_EXISTS"
    if record_type in ("pull_request", "merge_request"):
        return "MERGE_REQUEST_EXISTS"
    if record_type == "branch":
        return "BRANCH_EXISTS"
    if record_type == "review_comment":
        return "REVIEW_COMMENT_CREATED"
    if record_type == "documentation":
        return "DOCUMENTATION_EXISTS"
    if record_type == "job_description":
        return "JOB_DESCRIPTION_EXISTS"
    return "UNKNOWN_SOURCE_RECORD"


def ingest_fixture(fixture: dict[str, Any], store: JsonGraphStorage) -> dict[str, int]:
    engineer = fixture["engineer"]
    store.create_node(_node(f"engineer:{engineer['id']}", "Engineer", **engineer))

    created = reused = 0
    evidence_by_external_id: dict[str, str] = {}

    for record in fixture["records"]:
        source = record.get("source", fixture["source"])
        store.create_node(_node(f"source:{source['id']}", "Source", **source))
        store.create_node(
            _node(
                f"identity:{engineer['id']}:{source['id']}",
                "SourceIdentity",
                engineer_id=engineer["id"],
                source_id=source["id"],
            )
        )
        store.create_edge(
            "ENGINEER_HAS_IDENTITY", f"engineer:{engineer['id']}", f"identity:{engineer['id']}:{source['id']}"
        )

        payload_hash = stable_hash(record["payload"])
        evidence_type = evidence_type_for(record["type"], record["payload"])
        evidence_id = "evidence:" + stable_hash(
            [source["id"], record["type"], record["external_id"], evidence_type, payload_hash]
        )
        evidence_by_external_id[record["external_id"]] = evidence_id

        evidence = _node(
            evidence_id,
            "EvidenceNode",
            evidence_type=evidence_type,
            source_id=source["id"],
            source_entity_type=record["type"],
            source_entity_id=record["external_id"],
            captured_at=fixture["captured_at"],
            occurred_at=record["occurred_at"],
            content_hash=payload_hash,
            privacy_level=record.get("privacy_level", "artifact_safe"),
            metadata=record["payload"],
        )
        _, was_created = store.create_node(evidence)
        created += int(was_created)
        reused += int(not was_created)
        store.create_edge("EVIDENCE_DESCRIBES_ENTITY", evidence_id, f"engineer:{engineer['id']}")

    for record in fixture["records"]:
        from_id = evidence_by_external_id[record["external_id"]]
        for relation in record["payload"].get("relationships", []):
            to_id = evidence_by_external_id.get(relation.get("external_id"))
            if to_id:
                store.create_edge(
                    "EVIDENCE_RELATED_TO_EVIDENCE", from_id, to_id, source_relation_type=relation.get("type", "")
                )

    source_refs = sorted({f"source:{record.get('source', fixture['source'])['id']}" for record in fixture["records"]})
    store.append_audit_record("ingestion_run", source_refs, "succeeded", {"created": created, "reused": reused})
    return {"records_created": created, "records_reused": reused}
