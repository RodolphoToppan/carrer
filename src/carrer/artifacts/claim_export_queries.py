"""Queries for persisted claim-based artifact export receipts."""

from __future__ import annotations

from typing import Any

from carrer.artifacts.claim_export import EXPORT_FORMAT, EXPORT_SCOPES
from carrer.artifacts.claim_export_review import validate_persisted_artifact_export_receipt
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage


def get_artifact_export_receipt(store: GraphStore, receipt_id: str) -> dict[str, Any] | None:
    _require_store(store)
    if not isinstance(receipt_id, str) or not receipt_id:
        raise ValueError("receipt_id is required")
    node = store.nodes.get(receipt_id)
    if node is None or node.get("node_type") != "ArtifactExportReceipt":
        return None
    if _source_type(node) != "career_claim":
        return None
    return validate_persisted_artifact_export_receipt(store, node)


def list_artifact_export_receipts(
    store: GraphStore,
    *,
    source_artifact_id: str | None = None,
    export_scope: str | None = None,
    export_format: str | None = None,
) -> list[dict[str, Any]]:
    _require_store(store)
    _optional_str(source_artifact_id, "source_artifact_id")
    if export_scope is not None and (not isinstance(export_scope, str) or export_scope not in EXPORT_SCOPES):
        raise ValueError("export_scope is invalid")
    if export_format is not None and export_format != EXPORT_FORMAT:
        raise ValueError("export_format is invalid")
    receipts = [
        validate_persisted_artifact_export_receipt(store, node)
        for node in store.nodes_by_type("ArtifactExportReceipt")
        if _source_type(node) == "career_claim"
    ]
    if source_artifact_id is not None:
        receipts = [node for node in receipts if node["properties"]["source_artifact_id"] == source_artifact_id]
    if export_scope is not None:
        receipts = [node for node in receipts if node["properties"]["export_scope"] == export_scope]
    if export_format is not None:
        receipts = [node for node in receipts if node["properties"]["export_format"] == export_format]
    return sorted(receipts, key=lambda node: node["id"])


def _optional_str(value: object, field: str) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise ValueError(f"{field} is required")


def _source_type(node: dict[str, Any]) -> object:
    props = node.get("properties")
    if not isinstance(props, dict):
        return None
    return props.get("source_type")


def _require_store(store: object) -> None:
    missing = [name for name in ("nodes", "nodes_by_type") if not _has_graph_api(store, name)]
    if missing:
        raise ValueError("store is missing required graph API: " + ", ".join(missing))


def _has_graph_api(store: object, name: str) -> bool:
    if not hasattr(store, name):
        return False
    value = getattr(store, name)
    if name == "nodes":
        return isinstance(value, dict)
    return callable(value)
