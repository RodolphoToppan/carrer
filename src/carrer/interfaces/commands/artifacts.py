"""Claim-based artifact CLI commands."""

from __future__ import annotations

import argparse
import copy
from typing import Any, TextIO

from carrer.application import CareerWorkflow
from carrer.artifacts import (
    PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM,
    PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE,
    validate_persisted_claim_based_professional_artifact,
)
from carrer.storage.json_graph_storage import JsonGraphStorage


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    artifacts = subparsers.add_parser("artifacts")
    artifact_commands = artifacts.add_subparsers(dest="artifact_command", required=True)

    artifact_build = artifact_commands.add_parser("build")
    _add_artifact_selection_args(artifact_build)
    artifact_build.set_defaults(handler=_artifacts_build)

    artifact_accept = artifact_commands.add_parser("accept")
    _add_artifact_selection_args(artifact_accept)
    artifact_accept.add_argument("--actor", required=True)
    artifact_accept.add_argument("--decided-at", required=True)
    artifact_accept.set_defaults(handler=_artifacts_accept)

    artifact_reject = artifact_commands.add_parser("reject")
    _add_artifact_selection_args(artifact_reject)
    artifact_reject.add_argument("--actor", required=True)
    artifact_reject.add_argument("--decided-at", required=True)
    artifact_reject.add_argument("--reason", required=True)
    artifact_reject.set_defaults(handler=_artifacts_reject)

    artifact_list = artifact_commands.add_parser("list")
    artifact_list.add_argument("--claim-ref")
    artifact_list.add_argument("--artifact-type")
    artifact_list.add_argument("--audience")
    artifact_list.add_argument("--status")
    artifact_list.set_defaults(handler=_artifacts_list)


def print_result(result: Any, stdout: TextIO) -> bool:
    if isinstance(result, dict) and result.get("status") == "draft" and "items" in result:
        _print_claim_based_artifact(result, stdout)
        return True
    if isinstance(result, dict) and result.get("decision") == "accepted" and "artifact" in result:
        _print_accepted_claim_based_artifact(result, stdout)
        return True
    if isinstance(result, dict) and result.get("decision") == "rejected" and "source_artifact_id" in result:
        _print_rejected_claim_based_artifact(result, stdout)
        return True
    return False


def _add_artifact_selection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--claim-id", action="append", dest="claim_ids", required=True)
    parser.add_argument("--artifact-type", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--created-at", required=True)


def _artifacts_build(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    return _current_claim_based_artifact(workflow, args)


def _artifacts_accept(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    artifact = _current_claim_based_artifact(workflow, args)
    before_audit_count = len(workflow.store.audit_records)
    result = workflow.accept_claim_based_artifact(
        artifact,
        decision_actor=args.actor,
        decided_at=args.decided_at,
    )
    _verify_claim_based_artifact_acceptance(
        workflow.store,
        result,
        artifact,
        args.actor,
        args.decided_at,
        before_audit_count,
    )
    workflow.store.save(args.store)
    return result


def _artifacts_reject(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    artifact = _current_claim_based_artifact(workflow, args)
    before_nodes = copy.deepcopy(workflow.store.nodes)
    before_edges = copy.deepcopy(workflow.store.edges)
    before_audit_count = len(workflow.store.audit_records)
    result = workflow.reject_claim_based_artifact(
        artifact,
        decision_actor=args.actor,
        decided_at=args.decided_at,
        reason=args.reason,
    )
    _verify_claim_based_artifact_rejection(
        workflow.store,
        result,
        artifact,
        args.actor,
        args.decided_at,
        before_nodes,
        before_edges,
        before_audit_count,
    )
    workflow.store.save(args.store)
    return result


def _artifacts_list(workflow: CareerWorkflow, args: argparse.Namespace) -> list[dict[str, Any]]:
    return workflow.list_claim_based_artifacts(
        claim_ref=args.claim_ref,
        artifact_type=args.artifact_type,
        audience=args.audience,
        status=args.status,
    )


def _current_claim_based_artifact(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    return workflow.build_claim_based_artifact(
        claim_ids=args.claim_ids,
        artifact_type=args.artifact_type,
        audience=args.audience,
        created_at=args.created_at,
    )


def _verify_claim_based_artifact_acceptance(
    store: JsonGraphStorage,
    result: dict[str, Any],
    current: dict[str, Any],
    actor: str,
    decided_at: str,
    before_audit_count: int,
) -> None:
    if result.get("decision") != "accepted":
        raise ValueError("ClaimBasedArtifact acceptance result is not accepted")
    if result.get("source_artifact_id") != current["id"]:
        raise ValueError("ClaimBasedArtifact acceptance result does not match current draft")
    artifact = result.get("artifact")
    if not isinstance(artifact, dict):
        raise ValueError("ClaimBasedArtifact acceptance result is missing artifact")
    validate_persisted_claim_based_professional_artifact(artifact)
    persisted = store.nodes.get(artifact["id"])
    if persisted != artifact:
        raise ValueError(f"accepted ProfessionalArtifact not found before save: {artifact['id']}")
    props = artifact["properties"]
    if (
        props.get("source_type") != "career_claim"
        or props.get("status") != "accepted"
        or props.get("source_artifact_id") != current["id"]
        or props.get("artifact_type") != current["artifact_type"]
        or props.get("audience") != current["audience"]
        or props.get("privacy_level") != current["privacy_level"]
        or props.get("claim_refs") != current["traceability"]["claim_refs"]
        or props.get("items") != current["items"]
        or props.get("warnings") != current["warnings"]
    ):
        raise ValueError(f"accepted ProfessionalArtifact state is inconsistent before save: {artifact['id']}")
    _require_artifact_audit(
        store,
        "claim_based_artifact_accepted",
        current,
        actor,
        decided_at,
        start=before_audit_count,
        persisted_artifact_id=artifact["id"],
    )
    _require_artifact_edges(store, artifact["id"], props["claim_refs"], props["evidence_refs"])


def _verify_claim_based_artifact_rejection(
    store: JsonGraphStorage,
    result: dict[str, Any],
    current: dict[str, Any],
    actor: str,
    decided_at: str,
    before_nodes: dict[str, dict],
    before_edges: list[dict],
    before_audit_count: int,
) -> None:
    if result.get("decision") != "rejected":
        raise ValueError("ClaimBasedArtifact rejection result is not rejected")
    if (
        result.get("source_artifact_id") != current["id"]
        or result.get("artifact_type") != current["artifact_type"]
        or result.get("audience") != current["audience"]
    ):
        raise ValueError("ClaimBasedArtifact rejection result does not match current draft")
    if store.nodes != before_nodes or store.edges != before_edges:
        raise ValueError("ClaimBasedArtifact rejection created unexpected graph state before save")
    _require_artifact_audit(
        store,
        "claim_based_artifact_rejected",
        current,
        actor,
        decided_at,
        start=before_audit_count,
    )


def _require_artifact_audit(
    store: JsonGraphStorage,
    audit_type: str,
    current: dict[str, Any],
    actor: str,
    decided_at: str,
    *,
    start: int = 0,
    persisted_artifact_id: str | None = None,
) -> None:
    if not any(
        record.get("audit_type") == audit_type
        and record.get("metadata", {}).get("source_artifact_id") == current["id"]
        and record.get("metadata", {}).get("artifact_type") == current["artifact_type"]
        and record.get("metadata", {}).get("audience") == current["audience"]
        and record.get("metadata", {}).get("actor") == actor
        and record.get("metadata", {}).get("decided_at") == decided_at
        and (
            persisted_artifact_id is None
            or record.get("metadata", {}).get("persisted_artifact_id") == persisted_artifact_id
        )
        for record in store.audit_records[start:]
    ):
        raise ValueError(f"ClaimBasedArtifact audit not found before save: {current['id']}")


def _require_artifact_edges(
    store: JsonGraphStorage,
    artifact_id: str,
    claim_refs: list[str],
    evidence_refs: list[str],
) -> None:
    expected = {(PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM, artifact_id, ref) for ref in claim_refs}
    expected.update((PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE, artifact_id, ref) for ref in evidence_refs)
    actual = {(edge["edge_type"], edge["from_node_id"], edge["to_node_id"]) for edge in store.edges}
    if expected - actual:
        raise ValueError(f"ProfessionalArtifact provenance not found before save: {artifact_id}")


def _print_claim_based_artifact(artifact: dict[str, Any], stdout: TextIO) -> None:
    print(f"artifact_id: {artifact['id']}", file=stdout)
    print(f"artifact_type: {artifact['artifact_type']}", file=stdout)
    print(f"audience: {artifact['audience']}", file=stdout)
    print(f"status: {artifact['status']}", file=stdout)
    print(f"privacy_level: {artifact['privacy_level']}", file=stdout)
    print(f"claim_count: {artifact['metadata']['claim_count']}", file=stdout)
    print("claim_ids: " + ", ".join(artifact["traceability"]["claim_refs"]), file=stdout)
    if artifact["warnings"]:
        print("warnings: " + ", ".join(artifact["warnings"]), file=stdout)
    print("content:", file=stdout)
    for item in artifact["items"]:
        print(item["text"], file=stdout)


def _print_accepted_claim_based_artifact(result: dict[str, Any], stdout: TextIO) -> None:
    artifact = result["artifact"]
    props = artifact["properties"]
    print(f"decision: {result['decision']}", file=stdout)
    print(f"source_artifact_id: {result['source_artifact_id']}", file=stdout)
    print(f"artifact_id: {artifact['id']}", file=stdout)
    print(f"artifact_type: {props['artifact_type']}", file=stdout)
    print(f"created: {result['created']}", file=stdout)


def _print_rejected_claim_based_artifact(result: dict[str, Any], stdout: TextIO) -> None:
    print(f"decision: {result['decision']}", file=stdout)
    print(f"source_artifact_id: {result['source_artifact_id']}", file=stdout)
    print(f"artifact_type: {result['artifact_type']}", file=stdout)
    print(f"audience: {result['audience']}", file=stdout)
    print(f"reason: {result['reason']}", file=stdout)
