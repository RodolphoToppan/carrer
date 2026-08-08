"""Contribution analysis CLI commands."""

from __future__ import annotations

import argparse
import copy
from typing import Any, TextIO

from carrer.application import CareerWorkflow
from carrer.storage.json_graph_storage import JsonGraphStorage


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    analyses = subparsers.add_parser("analyses")
    analysis_commands = analyses.add_subparsers(dest="analysis_command", required=True)
    analysis_generate = analysis_commands.add_parser("generate")
    analysis_generate.add_argument("--contribution-id", required=True)
    analysis_generate.set_defaults(handler=_analyses_generate)
    analysis_accept = analysis_commands.add_parser("accept")
    analysis_accept.add_argument("--contribution-id", required=True)
    analysis_accept.add_argument("--actor", required=True)
    analysis_accept.add_argument("--decided-at", required=True)
    analysis_accept.set_defaults(handler=_analyses_accept)
    analysis_reject = analysis_commands.add_parser("reject")
    analysis_reject.add_argument("--contribution-id", required=True)
    analysis_reject.add_argument("--actor", required=True)
    analysis_reject.add_argument("--decided-at", required=True)
    analysis_reject.add_argument("--reason", required=True)
    analysis_reject.set_defaults(handler=_analyses_reject)
    analysis_list = analysis_commands.add_parser("list")
    analysis_list.add_argument("--contribution-ref")
    analysis_list.add_argument("--status")
    analysis_list.set_defaults(handler=_analyses_list)


def print_result(result: Any, stdout: TextIO) -> bool:
    if isinstance(result, dict) and result.get("analysis_type") == "deterministic_contribution_analysis":
        _print_contribution_analysis(result, stdout)
        return True
    if isinstance(result, dict) and result.get("decision") == "accepted" and "analysis" in result:
        _print_accepted_contribution_analysis(result, stdout)
        return True
    if isinstance(result, dict) and result.get("decision") == "rejected" and "analysis_id" in result:
        _print_rejected_contribution_analysis(result, stdout)
        return True
    return False


def _analyses_generate(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    return _current_contribution_analysis(workflow, args.contribution_id)


def _analyses_accept(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    analysis = _current_contribution_analysis(workflow, args.contribution_id)
    before_audit_count = len(workflow.store.audit_records)
    result = workflow.accept_contribution_analysis(
        analysis,
        decision_actor=args.actor,
        decided_at=args.decided_at,
    )
    _verify_contribution_analysis_acceptance(
        workflow.store,
        result,
        analysis,
        args.actor,
        args.decided_at,
        before_audit_count,
    )
    workflow.store.save(args.store)
    return result


def _analyses_reject(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    analysis = _current_contribution_analysis(workflow, args.contribution_id)
    before_nodes = copy.deepcopy(workflow.store.nodes)
    before_edges = copy.deepcopy(workflow.store.edges)
    before_audit_count = len(workflow.store.audit_records)
    result = workflow.reject_contribution_analysis(
        analysis,
        decision_actor=args.actor,
        decided_at=args.decided_at,
        reason=args.reason,
    )
    _verify_contribution_analysis_rejection(
        workflow.store,
        result,
        analysis,
        args.actor,
        args.decided_at,
        before_nodes,
        before_edges,
        before_audit_count,
    )
    workflow.store.save(args.store)
    return result


def _current_contribution_analysis(workflow: CareerWorkflow, contribution_id: str) -> dict[str, Any]:
    if workflow.get_contribution(contribution_id) is None:
        raise ValueError(f"Contribution not found: {contribution_id}")
    return workflow.analyze_contribution(contribution_id)


def _verify_contribution_analysis_acceptance(
    store: JsonGraphStorage,
    result: dict[str, Any],
    current: dict[str, Any],
    actor: str,
    decided_at: str,
    before_audit_count: int,
) -> None:
    if result.get("decision") != "accepted":
        raise ValueError("ContributionAnalysis acceptance result is not accepted")
    analysis = result.get("analysis")
    if not isinstance(analysis, dict):
        raise ValueError("ContributionAnalysis acceptance result is missing analysis")
    analysis_id = current["id"]
    if analysis.get("id") != analysis_id:
        raise ValueError("ContributionAnalysis acceptance result id does not match current analysis")
    persisted = store.nodes.get(analysis_id)
    if persisted != analysis:
        raise ValueError(f"accepted ContributionAnalysis not found before save: {analysis_id}")
    props = analysis.get("properties", {})
    if props.get("contribution_ref") != current["contribution_ref"] or props.get("status") != "accepted":
        raise ValueError(f"accepted ContributionAnalysis state is inconsistent before save: {analysis_id}")
    _require_analysis_audit(
        store,
        "contribution_analysis_accepted",
        analysis_id,
        actor,
        decided_at,
        start=before_audit_count,
    )
    _require_analysis_edges(store, analysis_id, current)


def _verify_contribution_analysis_rejection(
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
        raise ValueError("ContributionAnalysis rejection result is not rejected")
    if result.get("analysis_id") != current["id"] or result.get("contribution_ref") != current["contribution_ref"]:
        raise ValueError("ContributionAnalysis rejection result does not match current analysis")
    if store.nodes != before_nodes or store.edges != before_edges:
        raise ValueError("ContributionAnalysis rejection created unexpected graph state before save")
    _require_analysis_audit(
        store,
        "contribution_analysis_rejected",
        current["id"],
        actor,
        decided_at,
        start=before_audit_count,
    )


def _require_analysis_audit(
    store: JsonGraphStorage,
    audit_type: str,
    analysis_id: str,
    actor: str,
    decided_at: str,
    *,
    start: int = 0,
) -> None:
    if not any(
        record.get("audit_type") == audit_type
        and record.get("metadata", {}).get("analysis_id") == analysis_id
        and record.get("metadata", {}).get("actor") == actor
        and record.get("metadata", {}).get("decided_at") == decided_at
        for record in store.audit_records[start:]
    ):
        raise ValueError(f"ContributionAnalysis audit not found before save: {analysis_id}")


def _require_analysis_edges(store: JsonGraphStorage, analysis_id: str, current: dict[str, Any]) -> None:
    expected = {("CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION", analysis_id, current["contribution_ref"])}
    expected.update(
        ("CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE", analysis_id, ref) for ref in current["evidence_refs"]
    )
    actual = {(edge["edge_type"], edge["from_node_id"], edge["to_node_id"]) for edge in store.edges}
    missing = expected - actual
    if missing:
        raise ValueError(f"ContributionAnalysis provenance not found before save: {analysis_id}")


def _analyses_list(workflow: CareerWorkflow, args: argparse.Namespace) -> list[dict[str, Any]]:
    return workflow.list_contribution_analyses(contribution_ref=args.contribution_ref, status=args.status)


def _print_contribution_analysis(analysis: dict[str, Any], stdout: TextIO) -> None:
    print(f"analysis_id: {analysis['id']}", file=stdout)
    print(f"contribution_ref: {analysis['contribution_ref']}", file=stdout)
    print(f"status: {analysis['status']}", file=stdout)
    print(f"privacy_level: {analysis['privacy_level']}", file=stdout)
    print(f"actions: {len(analysis['action_facts'])}", file=stdout)
    print(f"outcomes: {len(analysis['outcome_facts'])}", file=stdout)
    print(f"impact_signals: {len(analysis['impact_signals'])}", file=stdout)
    if analysis["warnings"]:
        print("warnings: " + ", ".join(analysis["warnings"]), file=stdout)


def _print_accepted_contribution_analysis(result: dict[str, Any], stdout: TextIO) -> None:
    analysis = result["analysis"]
    props = analysis["properties"]
    print(f"decision: {result['decision']}", file=stdout)
    print(f"analysis_id: {analysis['id']}", file=stdout)
    print(f"contribution_ref: {props['contribution_ref']}", file=stdout)
    print(f"created: {result['created']}", file=stdout)


def _print_rejected_contribution_analysis(result: dict[str, Any], stdout: TextIO) -> None:
    print(f"decision: {result['decision']}", file=stdout)
    print(f"analysis_id: {result['analysis_id']}", file=stdout)
    print(f"contribution_ref: {result['contribution_ref']}", file=stdout)
    print(f"reason: {result['reason']}", file=stdout)
