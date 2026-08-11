"""Claim-based artifact export CLI commands."""

from __future__ import annotations

import argparse
import copy
from typing import Any, TextIO

from carrer.application import CareerWorkflow
from carrer.artifacts import (
    ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT,
    ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM,
    ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE,
    validate_artifact_export_receipt_contract,
    validate_persisted_artifact_export_receipt,
)
from carrer.storage.json_graph_storage import JsonGraphStorage


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    exports = subparsers.add_parser("exports")
    export_commands = exports.add_subparsers(dest="export_command", required=True)

    export_build = export_commands.add_parser("build")
    _add_export_candidate_args(export_build)
    export_build.set_defaults(handler=_exports_build)

    export_accept = export_commands.add_parser("accept")
    _add_export_candidate_args(export_accept)
    export_accept.add_argument("--output-directory", required=True)
    export_accept.add_argument("--actor", required=True)
    export_accept.add_argument("--decided-at", required=True)
    export_accept.set_defaults(handler=_exports_accept)

    export_reject = export_commands.add_parser("reject")
    _add_export_candidate_args(export_reject)
    export_reject.add_argument("--actor", required=True)
    export_reject.add_argument("--decided-at", required=True)
    export_reject.add_argument("--reason", required=True)
    export_reject.set_defaults(handler=_exports_reject)

    export_list = export_commands.add_parser("list")
    export_list.add_argument("--source-artifact-id")
    export_list.add_argument("--export-scope")
    export_list.add_argument("--export-format")
    export_list.set_defaults(handler=_exports_list)


def print_result(result: Any, stdout: TextIO) -> bool:
    if isinstance(result, dict) and result.get("candidate_type") == "claim_based_artifact_export":
        _print_export_candidate(result, stdout)
        return True
    if isinstance(result, dict) and result.get("decision") == "accepted" and "receipt" in result:
        _print_accepted_export(result, stdout)
        return True
    if isinstance(result, dict) and result.get("decision") == "rejected" and "candidate_id" in result:
        _print_rejected_export(result, stdout)
        return True
    return False


def _add_export_candidate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--export-scope", required=True)
    parser.add_argument("--export-format", required=True)
    parser.add_argument("--created-at", required=True)


def _exports_build(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    return _current_export_candidate(workflow, args)


def _exports_accept(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    candidate = _current_export_candidate(workflow, args)
    before_audit_count = len(workflow.store.audit_records)
    result = workflow.accept_export(
        candidate,
        output_directory=args.output_directory,
        decision_actor=args.actor,
        decided_at=args.decided_at,
    )
    _verify_export_acceptance(workflow.store, result, candidate, args.actor, args.decided_at, before_audit_count)
    workflow.store.save(args.store)
    return result


def _exports_reject(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    candidate = _current_export_candidate(workflow, args)
    before_nodes = copy.deepcopy(workflow.store.nodes)
    before_edges = copy.deepcopy(workflow.store.edges)
    before_audit_count = len(workflow.store.audit_records)
    result = workflow.reject_export(
        candidate,
        decision_actor=args.actor,
        decided_at=args.decided_at,
        reason=args.reason,
    )
    _verify_export_rejection(
        workflow.store,
        result,
        candidate,
        args.actor,
        args.decided_at,
        args.reason,
        before_nodes,
        before_edges,
        before_audit_count,
    )
    workflow.store.save(args.store)
    return result


def _exports_list(workflow: CareerWorkflow, args: argparse.Namespace) -> list[dict[str, Any]]:
    return workflow.list_export_receipts(
        source_artifact_id=args.source_artifact_id,
        export_scope=args.export_scope,
        export_format=args.export_format,
    )


def _current_export_candidate(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    return workflow.build_export_candidate(
        args.artifact_id,
        export_scope=args.export_scope,
        export_format=args.export_format,
        created_at=args.created_at,
    )


def _verify_export_acceptance(
    store: JsonGraphStorage,
    result: dict[str, Any],
    candidate: dict[str, Any],
    actor: str,
    decided_at: str,
    before_audit_count: int,
) -> None:
    if result.get("decision") != "accepted":
        raise ValueError("ClaimBasedArtifactExport acceptance result is not accepted")
    if not isinstance(result.get("created"), bool):
        raise ValueError("ClaimBasedArtifactExport acceptance result created must be bool")
    if not isinstance(result.get("written"), bool):
        raise ValueError("ClaimBasedArtifactExport acceptance result written must be bool")
    receipt = result.get("receipt")
    if not isinstance(receipt, dict):
        raise ValueError("ClaimBasedArtifactExport acceptance result is missing receipt")
    validate_artifact_export_receipt_contract(receipt)
    persisted = store.nodes.get(receipt["id"])
    if persisted != receipt:
        raise ValueError(f"ArtifactExportReceipt not found before save: {receipt['id']}")
    validate_persisted_artifact_export_receipt(store, persisted)
    props = receipt["properties"]
    if (
        props.get("source_artifact_id") != candidate["source_artifact_id"]
        or props.get("export_candidate_id") != candidate["id"]
        or props.get("export_scope") != candidate["export_scope"]
        or props.get("export_format") != candidate["export_format"]
        or props.get("privacy_level") != candidate["privacy_level"]
        or props.get("file_name") != candidate["file_name"]
        or props.get("content_hash") != candidate["content_hash"]
        or props.get("candidate_created_at") != candidate["created_at"]
        or (result.get("created") is True and props.get("review_actor") != actor)
    ):
        raise ValueError(f"ArtifactExportReceipt state is inconsistent before save: {receipt['id']}")
    _require_export_accept_audit(
        store,
        receipt,
        candidate,
        actor,
        decided_at,
        before_audit_count,
        created=result["created"],
        written=result["written"],
    )
    _require_export_edges(store, receipt["id"], candidate)


def _verify_export_rejection(
    store: JsonGraphStorage,
    result: dict[str, Any],
    candidate: dict[str, Any],
    actor: str,
    decided_at: str,
    reason: str,
    before_nodes: dict[str, dict],
    before_edges: list[dict],
    before_audit_count: int,
) -> None:
    if result.get("decision") != "rejected":
        raise ValueError("ClaimBasedArtifactExport rejection result is not rejected")
    if (
        result.get("candidate_id") != candidate["id"]
        or result.get("source_artifact_id") != candidate["source_artifact_id"]
    ):
        raise ValueError("ClaimBasedArtifactExport rejection result does not match current candidate")
    if result.get("reason") != reason:
        raise ValueError("ClaimBasedArtifactExport rejection result reason does not match current decision")
    if store.nodes != before_nodes or store.edges != before_edges:
        raise ValueError("ClaimBasedArtifactExport rejection created unexpected graph state before save")
    _require_export_reject_audit(store, candidate, actor, decided_at, before_audit_count)


def _require_export_accept_audit(
    store: JsonGraphStorage,
    receipt: dict[str, Any],
    candidate: dict[str, Any],
    actor: str,
    decided_at: str,
    start: int,
    *,
    created: bool,
    written: bool,
) -> None:
    if not any(
        record.get("audit_type") == "claim_based_artifact_export_accepted"
        and record.get("metadata", {}).get("receipt_id") == receipt["id"]
        and record.get("metadata", {}).get("candidate_id") == candidate["id"]
        and record.get("metadata", {}).get("source_artifact_id") == candidate["source_artifact_id"]
        and record.get("metadata", {}).get("export_scope") == candidate["export_scope"]
        and record.get("metadata", {}).get("export_format") == candidate["export_format"]
        and record.get("metadata", {}).get("content_hash") == candidate["content_hash"]
        and record.get("metadata", {}).get("candidate_created_at") == candidate["created_at"]
        and record.get("metadata", {}).get("actor") == actor
        and record.get("metadata", {}).get("decided_at") == decided_at
        and record.get("metadata", {}).get("created") == created
        and record.get("metadata", {}).get("written") == written
        for record in store.audit_records[start:]
    ):
        raise ValueError(f"ClaimBasedArtifactExport acceptance audit not found before save: {candidate['id']}")


def _require_export_reject_audit(
    store: JsonGraphStorage,
    candidate: dict[str, Any],
    actor: str,
    decided_at: str,
    start: int,
) -> None:
    if not any(
        record.get("audit_type") == "claim_based_artifact_export_rejected"
        and record.get("metadata", {}).get("candidate_id") == candidate["id"]
        and record.get("metadata", {}).get("source_artifact_id") == candidate["source_artifact_id"]
        and record.get("metadata", {}).get("export_scope") == candidate["export_scope"]
        and record.get("metadata", {}).get("export_format") == candidate["export_format"]
        and record.get("metadata", {}).get("actor") == actor
        and record.get("metadata", {}).get("decided_at") == decided_at
        for record in store.audit_records[start:]
    ):
        raise ValueError(f"ClaimBasedArtifactExport rejection audit not found before save: {candidate['id']}")


def _require_export_edges(store: JsonGraphStorage, receipt_id: str, candidate: dict[str, Any]) -> None:
    expected = {(ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT, receipt_id, candidate["source_artifact_id"])}
    expected.update(
        (ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM, receipt_id, ref) for ref in candidate["traceability"]["claim_refs"]
    )
    expected.update(
        (ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE, receipt_id, ref)
        for ref in candidate["traceability"]["evidence_refs"]
    )
    actual = {(edge["edge_type"], edge["from_node_id"], edge["to_node_id"]) for edge in store.edges}
    if expected - actual:
        raise ValueError(f"ArtifactExportReceipt provenance not found before save: {receipt_id}")


def _print_export_candidate(candidate: dict[str, Any], stdout: TextIO) -> None:
    metadata = candidate["metadata"]
    print(f"candidate_id: {candidate['id']}", file=stdout)
    print(f"source_artifact_id: {candidate['source_artifact_id']}", file=stdout)
    print(f"export_scope: {candidate['export_scope']}", file=stdout)
    print(f"export_format: {candidate['export_format']}", file=stdout)
    print(f"file_name: {candidate['file_name']}", file=stdout)
    print(f"content_hash: {candidate['content_hash']}", file=stdout)
    print(f"privacy_level: {candidate['privacy_level']}", file=stdout)
    print(f"claim_count: {metadata['claim_count']}", file=stdout)
    print(f"evidence_count: {metadata['evidence_count']}", file=stdout)


def _print_accepted_export(result: dict[str, Any], stdout: TextIO) -> None:
    receipt = result["receipt"]
    props = receipt["properties"]
    print(f"decision: {result['decision']}", file=stdout)
    print(f"receipt_id: {receipt['id']}", file=stdout)
    print(f"source_artifact_id: {props['source_artifact_id']}", file=stdout)
    print(f"file_name: {props['file_name']}", file=stdout)
    print(f"created: {result['created']}", file=stdout)
    print(f"written: {result['written']}", file=stdout)


def _print_rejected_export(result: dict[str, Any], stdout: TextIO) -> None:
    print(f"decision: {result['decision']}", file=stdout)
    print(f"candidate_id: {result['candidate_id']}", file=stdout)
    print(f"source_artifact_id: {result['source_artifact_id']}", file=stdout)
    print(f"reason: {result['reason']}", file=stdout)
