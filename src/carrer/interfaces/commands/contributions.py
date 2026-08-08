"""Contribution CLI commands."""

from __future__ import annotations

import argparse
from typing import Any, TextIO

from carrer.application import CareerWorkflow
from carrer.storage.json_graph_storage import JsonGraphStorage


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    contributions = subparsers.add_parser("contributions")
    contribution_commands = contributions.add_subparsers(dest="contribution_command", required=True)
    contribution_commands.add_parser("list").set_defaults(handler=_contributions_list)
    contribution_commands.add_parser("discover").set_defaults(handler=_contributions_discover)
    contribution_promote = contribution_commands.add_parser("promote")
    contribution_promote.add_argument("--candidate-id", required=True)
    contribution_promote.add_argument("--actor", required=True)
    contribution_promote.add_argument("--decided-at", required=True)
    contribution_promote.set_defaults(handler=_contributions_promote)
    contribution_reject = contribution_commands.add_parser("reject")
    contribution_reject.add_argument("--candidate-id", required=True)
    contribution_reject.add_argument("--actor", required=True)
    contribution_reject.add_argument("--decided-at", required=True)
    contribution_reject.add_argument("--reason", required=True)
    contribution_reject.set_defaults(handler=_contributions_reject)


def print_result(result: Any, stdout: TextIO) -> bool:
    if isinstance(result, dict) and result.get("decision") == "promoted":
        _print_promoted_contribution_candidate(result, stdout)
        return True
    if isinstance(result, dict) and result.get("decision") == "rejected" and "candidate_id" in result:
        _print_rejected_contribution_candidate(result, stdout)
        return True
    return False


def _contributions_list(workflow: CareerWorkflow, args: argparse.Namespace) -> list[dict[str, Any]]:
    return workflow.list_contributions()


def _contributions_discover(workflow: CareerWorkflow, args: argparse.Namespace) -> list[dict[str, Any]]:
    return workflow.discover_contribution_candidates()


def _contributions_promote(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    candidate = _current_contribution_candidate(workflow, args.candidate_id)
    result = workflow.promote_contribution_candidate(
        candidate,
        created_at=args.decided_at,
        decision_actor=args.actor,
    )
    _verify_contribution_decision(workflow.store, result)
    workflow.store.save(args.store)
    return result


def _contributions_reject(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    candidate = _current_contribution_candidate(workflow, args.candidate_id)
    result = workflow.reject_contribution_candidate(
        candidate,
        decision_actor=args.actor,
        decided_at=args.decided_at,
        reason=args.reason,
    )
    _verify_contribution_decision(workflow.store, result)
    workflow.store.save(args.store)
    return result


def _current_contribution_candidate(workflow: CareerWorkflow, candidate_id: str) -> dict[str, Any]:
    matches = [
        candidate for candidate in workflow.discover_contribution_candidates() if candidate.get("id") == candidate_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one current ContributionCandidate for id {candidate_id}, found {len(matches)}"
        )
    return matches[0]


def _verify_contribution_decision(store: JsonGraphStorage, result: dict[str, Any]) -> None:
    candidate_id = result.get("candidate_id")
    if not candidate_id:
        raise ValueError("ContributionCandidate decision result is missing candidate_id")
    decision = result.get("decision")
    if decision == "promoted":
        _verify_promoted_contribution(store, result)
        return
    if decision == "rejected" and any(
        record.get("audit_type") == "contribution_candidate_rejected"
        and record.get("metadata", {}).get("candidate_id") == candidate_id
        for record in store.audit_records
    ):
        return
    raise ValueError(f"ContributionCandidate decision state not found before save: {candidate_id}")


def _verify_promoted_contribution(store: JsonGraphStorage, result: dict[str, Any]) -> None:
    contribution = result.get("contribution")
    if not isinstance(contribution, dict):
        raise ValueError("promoted ContributionCandidate result is missing contribution")
    contribution_id = contribution.get("id")
    if not isinstance(contribution_id, str) or not contribution_id:
        raise ValueError("promoted ContributionCandidate result is missing contribution id")
    persisted = store.nodes.get(contribution_id)
    if persisted is None:
        raise ValueError(f"promoted Contribution not found before save: {contribution_id}")
    if persisted != contribution:
        raise ValueError(f"promoted Contribution result does not match store before save: {contribution_id}")


def _print_promoted_contribution_candidate(result: dict[str, Any], stdout: TextIO) -> None:
    print(f"decision: {result['decision']}", file=stdout)
    print(f"candidate_id: {result['candidate_id']}", file=stdout)
    print(f"contribution_id: {result['contribution']['id']}", file=stdout)
    print(f"created: {result['created']}", file=stdout)


def _print_rejected_contribution_candidate(result: dict[str, Any], stdout: TextIO) -> None:
    print(f"decision: {result['decision']}", file=stdout)
    print(f"candidate_id: {result['candidate_id']}", file=stdout)
    print(f"reason: {result['reason']}", file=stdout)
