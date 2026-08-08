"""Career claim CLI commands."""

from __future__ import annotations

import argparse
import copy
from typing import Any, TextIO

from carrer.application import CareerWorkflow
from carrer.claims import (
    CAREER_CLAIM_DERIVED_FROM_ANALYSIS,
    CAREER_CLAIM_FROM_CONTRIBUTION,
    CAREER_CLAIM_SUPPORTED_BY_EVIDENCE,
    validate_persisted_career_claim,
)
from carrer.storage.json_graph_storage import JsonGraphStorage


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    claims = subparsers.add_parser("claims")
    claim_commands = claims.add_subparsers(dest="claim_command", required=True)
    claim_generate = claim_commands.add_parser("generate")
    claim_generate.add_argument("--analysis-id", required=True)
    claim_generate.set_defaults(handler=_claims_generate)
    claim_accept = claim_commands.add_parser("accept")
    claim_accept.add_argument("--analysis-id", required=True)
    claim_accept.add_argument("--candidate-id", required=True)
    claim_accept.add_argument("--actor", required=True)
    claim_accept.add_argument("--decided-at", required=True)
    claim_accept.set_defaults(handler=_claims_accept)
    claim_reject = claim_commands.add_parser("reject")
    claim_reject.add_argument("--analysis-id", required=True)
    claim_reject.add_argument("--candidate-id", required=True)
    claim_reject.add_argument("--actor", required=True)
    claim_reject.add_argument("--decided-at", required=True)
    claim_reject.add_argument("--reason", required=True)
    claim_reject.set_defaults(handler=_claims_reject)
    claim_list = claim_commands.add_parser("list")
    claim_list.add_argument("--analysis-ref")
    claim_list.add_argument("--contribution-ref")
    claim_list.add_argument("--claim-type")
    claim_list.add_argument("--status")
    claim_list.set_defaults(handler=_claims_list)


def print_result(result: Any, stdout: TextIO) -> bool:
    if isinstance(result, list) and all(
        isinstance(item, dict) and "claim_type" in item and "analysis_ref" in item for item in result
    ):
        _print_career_claim_candidates(result, stdout)
        return True
    if isinstance(result, dict) and result.get("decision") == "accepted" and "claim" in result:
        _print_accepted_career_claim_candidate(result, stdout)
        return True
    if isinstance(result, dict) and result.get("decision") == "rejected" and "analysis_ref" in result:
        _print_rejected_career_claim_candidate(result, stdout)
        return True
    return False


def _claims_list(workflow: CareerWorkflow, args: argparse.Namespace) -> list[dict[str, Any]]:
    return workflow.list_career_claims(
        analysis_ref=args.analysis_ref,
        contribution_ref=args.contribution_ref,
        claim_type=args.claim_type,
        status=args.status,
    )


def _claims_generate(workflow: CareerWorkflow, args: argparse.Namespace) -> list[dict[str, Any]]:
    _accepted_contribution_analysis(workflow, args.analysis_id)
    return workflow.generate_career_claim_candidates(args.analysis_id)


def _claims_accept(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    candidate = _current_career_claim_candidate(workflow, args.analysis_id, args.candidate_id)
    before_audit_count = len(workflow.store.audit_records)
    result = workflow.accept_career_claim_candidate(
        candidate,
        decision_actor=args.actor,
        decided_at=args.decided_at,
    )
    _verify_career_claim_acceptance(
        workflow.store,
        result,
        candidate,
        args.actor,
        args.decided_at,
        before_audit_count,
    )
    workflow.store.save(args.store)
    return result


def _claims_reject(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    candidate = _current_career_claim_candidate(workflow, args.analysis_id, args.candidate_id)
    before_nodes = copy.deepcopy(workflow.store.nodes)
    before_edges = copy.deepcopy(workflow.store.edges)
    before_audit_count = len(workflow.store.audit_records)
    result = workflow.reject_career_claim_candidate(
        candidate,
        decision_actor=args.actor,
        decided_at=args.decided_at,
        reason=args.reason,
    )
    _verify_career_claim_rejection(
        workflow.store,
        result,
        candidate,
        args.actor,
        args.decided_at,
        before_nodes,
        before_edges,
        before_audit_count,
    )
    workflow.store.save(args.store)
    return result


def _accepted_contribution_analysis(workflow: CareerWorkflow, analysis_id: str) -> dict[str, Any]:
    analysis = workflow.get_contribution_analysis(analysis_id)
    if analysis is None:
        raise ValueError(f"ContributionAnalysis not found: {analysis_id}")
    if analysis["properties"].get("status") != "accepted":
        raise ValueError(f"ContributionAnalysis is not accepted: {analysis_id}")
    return analysis


def _current_career_claim_candidate(
    workflow: CareerWorkflow,
    analysis_id: str,
    candidate_id: str,
) -> dict[str, Any]:
    _accepted_contribution_analysis(workflow, analysis_id)
    candidates = workflow.generate_career_claim_candidates(analysis_id)
    matches = [candidate for candidate in candidates if candidate.get("id") == candidate_id]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one current CareerClaimCandidate for analysis {analysis_id} "
            f"and id {candidate_id}, found {len(matches)}"
        )
    return matches[0]


def _verify_career_claim_acceptance(
    store: JsonGraphStorage,
    result: dict[str, Any],
    current: dict[str, Any],
    actor: str,
    decided_at: str,
    before_audit_count: int,
) -> None:
    if result.get("decision") != "accepted":
        raise ValueError("CareerClaimCandidate acceptance result is not accepted")
    if result.get("candidate_id") != current["id"]:
        raise ValueError("CareerClaimCandidate acceptance result does not match current candidate")
    claim = result.get("claim")
    if not isinstance(claim, dict):
        raise ValueError("CareerClaimCandidate acceptance result is missing claim")
    validate_persisted_career_claim(claim)
    persisted = store.nodes.get(claim["id"])
    if persisted != claim:
        raise ValueError(f"accepted CareerClaim not found before save: {claim['id']}")
    props = claim["properties"]
    metadata = props["metadata"]
    if (
        props.get("status") != "accepted"
        or props.get("claim_type") != current["claim_type"]
        or props.get("statement") != current["statement"]
        or props.get("confidence") != current["confidence"]
        or props.get("privacy_level") != current["privacy_level"]
        or props.get("contribution_refs") != [current["contribution_ref"]]
        or props.get("evidence_refs") != current["evidence_refs"]
        or metadata.get("candidate_id") != current["id"]
        or metadata.get("analysis_ref") != current["analysis_ref"]
    ):
        raise ValueError(f"accepted CareerClaim state is inconsistent before save: {claim['id']}")
    _require_claim_audit(
        store,
        "career_claim_candidate_accepted",
        current,
        actor,
        decided_at,
        start=before_audit_count,
        claim_id=claim["id"],
    )
    _require_claim_edges(store, claim["id"], current)


def _verify_career_claim_rejection(
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
        raise ValueError("CareerClaimCandidate rejection result is not rejected")
    if (
        result.get("candidate_id") != current["id"]
        or result.get("analysis_ref") != current["analysis_ref"]
        or result.get("contribution_ref") != current["contribution_ref"]
    ):
        raise ValueError("CareerClaimCandidate rejection result does not match current candidate")
    if store.nodes != before_nodes or store.edges != before_edges:
        raise ValueError("CareerClaimCandidate rejection created unexpected graph state before save")
    _require_claim_audit(
        store,
        "career_claim_candidate_rejected",
        current,
        actor,
        decided_at,
        start=before_audit_count,
    )


def _require_claim_audit(
    store: JsonGraphStorage,
    audit_type: str,
    current: dict[str, Any],
    actor: str,
    decided_at: str,
    *,
    start: int = 0,
    claim_id: str | None = None,
) -> None:
    if not any(
        record.get("audit_type") == audit_type
        and record.get("metadata", {}).get("candidate_id") == current["id"]
        and record.get("metadata", {}).get("analysis_id") == current["analysis_ref"]
        and record.get("metadata", {}).get("contribution_id") == current["contribution_ref"]
        and record.get("metadata", {}).get("actor") == actor
        and record.get("metadata", {}).get("decided_at") == decided_at
        and (claim_id is None or record.get("metadata", {}).get("claim_id") == claim_id)
        for record in store.audit_records[start:]
    ):
        raise ValueError(f"CareerClaimCandidate audit not found before save: {current['id']}")


def _require_claim_edges(store: JsonGraphStorage, claim_id: str, current: dict[str, Any]) -> None:
    expected = {
        (CAREER_CLAIM_DERIVED_FROM_ANALYSIS, claim_id, current["analysis_ref"]),
        (CAREER_CLAIM_FROM_CONTRIBUTION, claim_id, current["contribution_ref"]),
    }
    expected.update((CAREER_CLAIM_SUPPORTED_BY_EVIDENCE, claim_id, ref) for ref in current["evidence_refs"])
    actual = {(edge["edge_type"], edge["from_node_id"], edge["to_node_id"]) for edge in store.edges}
    missing = expected - actual
    if missing:
        raise ValueError(f"CareerClaim provenance not found before save: {claim_id}")


def _print_career_claim_candidates(candidates: list[dict[str, Any]], stdout: TextIO) -> None:
    print(f"items: {len(candidates)}", file=stdout)
    for candidate in candidates:
        fields = [
            candidate["id"],
            f"claim_type={candidate['claim_type']}",
            f"status={candidate['status']}",
            f"confidence={candidate['confidence']}",
            f"privacy_level={candidate['privacy_level']}",
            f"contribution_ref={candidate['contribution_ref']}",
            f"evidence_count={len(candidate['evidence_refs'])}",
        ]
        print("- " + " ".join(fields), file=stdout)
        print(f"  statement: {candidate['statement']}", file=stdout)
        if candidate["warnings"]:
            print("  warnings: " + ", ".join(candidate["warnings"]), file=stdout)


def _print_accepted_career_claim_candidate(result: dict[str, Any], stdout: TextIO) -> None:
    claim = result["claim"]
    props = claim["properties"]
    print(f"decision: {result['decision']}", file=stdout)
    print(f"candidate_id: {result['candidate_id']}", file=stdout)
    print(f"claim_id: {claim['id']}", file=stdout)
    print(f"claim_type: {props['claim_type']}", file=stdout)
    print(f"created: {result['created']}", file=stdout)


def _print_rejected_career_claim_candidate(result: dict[str, Any], stdout: TextIO) -> None:
    print(f"decision: {result['decision']}", file=stdout)
    print(f"candidate_id: {result['candidate_id']}", file=stdout)
    print(f"analysis_ref: {result['analysis_ref']}", file=stdout)
    print(f"contribution_ref: {result['contribution_ref']}", file=stdout)
    print(f"reason: {result['reason']}", file=stdout)
