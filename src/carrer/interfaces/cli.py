"""Command line interface over CareerWorkflow."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

from carrer.application import CareerWorkflow
from carrer.storage.json_graph_storage import JsonGraphStorage

COUNTED_NODE_TYPES = (
    "Contribution",
    "ContributionAnalysis",
    "CareerClaim",
    "ProfessionalArtifact",
    "ArtifactExportReceipt",
    "ArtifactExportRepairReceipt",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="carrer")
    parser.add_argument("--store", type=Path, required=True, help="Path to an existing Carrer graph JSON store.")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Print JSON output.")

    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status").set_defaults(handler=_status)

    contributions = commands.add_parser("contributions")
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

    analyses = commands.add_parser("analyses")
    analysis_commands = analyses.add_subparsers(dest="analysis_command", required=True)
    analysis_list = analysis_commands.add_parser("list")
    analysis_list.add_argument("--contribution-ref")
    analysis_list.add_argument("--status")
    analysis_list.set_defaults(handler=_analyses_list)

    claims = commands.add_parser("claims")
    claim_commands = claims.add_subparsers(dest="claim_command", required=True)
    claim_list = claim_commands.add_parser("list")
    claim_list.add_argument("--analysis-ref")
    claim_list.add_argument("--contribution-ref")
    claim_list.add_argument("--claim-type")
    claim_list.add_argument("--status")
    claim_list.set_defaults(handler=_claims_list)

    artifacts = commands.add_parser("artifacts")
    artifact_commands = artifacts.add_subparsers(dest="artifact_command", required=True)
    artifact_list = artifact_commands.add_parser("list")
    artifact_list.add_argument("--claim-ref")
    artifact_list.add_argument("--artifact-type")
    artifact_list.add_argument("--audience")
    artifact_list.add_argument("--status")
    artifact_list.set_defaults(handler=_artifacts_list)

    exports = commands.add_parser("exports")
    export_commands = exports.add_subparsers(dest="export_command", required=True)
    export_list = export_commands.add_parser("list")
    export_list.add_argument("--source-artifact-id")
    export_list.add_argument("--export-scope")
    export_list.add_argument("--export-format")
    export_list.set_defaults(handler=_exports_list)

    integrity = commands.add_parser("integrity")
    integrity_commands = integrity.add_subparsers(dest="integrity_command", required=True)
    integrity_commands.add_parser("graph").set_defaults(handler=_integrity_graph)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv if argv is not None else sys.argv[1:], stdout=sys.stdout, stderr=sys.stderr)


def run(
    argv: Sequence[str],
    *,
    stdout: TextIO,
    stderr: TextIO,
    workflow_factory: Callable[[JsonGraphStorage], CareerWorkflow] = CareerWorkflow,
) -> int:
    argv, json_output = _extract_json_flag(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    args.json_output = args.json_output or json_output

    try:
        store = _load_store(args.store)
        workflow = workflow_factory(store)
        result = args.handler(workflow, args)
        _print_result(result, json_output=args.json_output, stdout=stdout)
    except Exception as exc:
        print(f"error: {exc}", file=stderr)
        return 1
    return 0


def _extract_json_flag(argv: Sequence[str]) -> tuple[list[str], bool]:
    cleaned: list[str] = []
    found = False
    for value in argv:
        if value == "--json":
            found = True
        else:
            cleaned.append(value)
    return cleaned, found


def _load_store(path: Path) -> JsonGraphStorage:
    if not path.exists():
        raise FileNotFoundError(f"store not found: {path}")
    if not path.is_file():
        raise ValueError(f"store is not a file: {path}")
    return JsonGraphStorage.load(path)


def _status(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    integrity = workflow.graph_integrity()
    counts = {node_type: len(workflow.store.nodes_by_type(node_type)) for node_type in COUNTED_NODE_TYPES}
    return {
        "store": str(args.store),
        "counts": counts,
        "integrity": {
            "status": integrity["status"],
            "summary": integrity["summary"],
            "snapshot": integrity["snapshot"],
        },
    }


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


def _analyses_list(workflow: CareerWorkflow, args: argparse.Namespace) -> list[dict[str, Any]]:
    return workflow.list_contribution_analyses(contribution_ref=args.contribution_ref, status=args.status)


def _claims_list(workflow: CareerWorkflow, args: argparse.Namespace) -> list[dict[str, Any]]:
    return workflow.list_career_claims(
        analysis_ref=args.analysis_ref,
        contribution_ref=args.contribution_ref,
        claim_type=args.claim_type,
        status=args.status,
    )


def _artifacts_list(workflow: CareerWorkflow, args: argparse.Namespace) -> list[dict[str, Any]]:
    return workflow.list_claim_based_artifacts(
        claim_ref=args.claim_ref,
        artifact_type=args.artifact_type,
        audience=args.audience,
        status=args.status,
    )


def _exports_list(workflow: CareerWorkflow, args: argparse.Namespace) -> list[dict[str, Any]]:
    return workflow.list_export_receipts(
        source_artifact_id=args.source_artifact_id,
        export_scope=args.export_scope,
        export_format=args.export_format,
    )


def _integrity_graph(workflow: CareerWorkflow, args: argparse.Namespace) -> dict[str, Any]:
    return workflow.graph_integrity()


def _print_result(result: Any, *, json_output: bool, stdout: TextIO) -> None:
    if json_output:
        json.dump(result, stdout, indent=2, sort_keys=True)
        stdout.write("\n")
        return
    if isinstance(result, list):
        _print_list(result, stdout)
        return
    if isinstance(result, dict) and "counts" in result and "integrity" in result:
        _print_status(result, stdout)
        return
    if isinstance(result, dict) and "issues" in result and "summary" in result:
        _print_integrity(result, stdout)
        return
    if isinstance(result, dict) and result.get("decision") == "promoted":
        _print_promoted_contribution_candidate(result, stdout)
        return
    if isinstance(result, dict) and result.get("decision") == "rejected":
        _print_rejected_contribution_candidate(result, stdout)
        return
    json.dump(result, stdout, indent=2, sort_keys=True)
    stdout.write("\n")


def _print_status(result: dict[str, Any], stdout: TextIO) -> None:
    print(f"store: {result['store']}", file=stdout)
    for node_type, count in result["counts"].items():
        print(f"{node_type}: {count}", file=stdout)
    integrity = result["integrity"]
    summary = integrity["summary"]
    print(f"graph_integrity: {integrity['status']}", file=stdout)
    print(
        f"graph_issues: {summary['issue_count']} ({summary['error_count']} error, {summary['warning_count']} warning)",
        file=stdout,
    )


def _print_integrity(report: dict[str, Any], stdout: TextIO) -> None:
    summary = report["summary"]
    print(f"graph_integrity: {report['status']}", file=stdout)
    print(f"nodes: {summary['node_count']}", file=stdout)
    print(f"edges: {summary['edge_count']}", file=stdout)
    print(f"audit_records: {summary['audit_record_count']}", file=stdout)
    print(
        f"issues: {summary['issue_count']} ({summary['error_count']} error, {summary['warning_count']} warning)",
        file=stdout,
    )
    for issue in report["issues"]:
        print(f"- {issue['severity']} {issue['code']} {issue['subject_ref']}", file=stdout)


def _print_list(items: list[dict[str, Any]], stdout: TextIO) -> None:
    print(f"items: {len(items)}", file=stdout)
    for item in items:
        props = item.get("properties", {})
        fields = [item.get("id", "<missing-id>"), f"type={item.get('node_type', '<missing-type>')}"]
        for name in ("status", "privacy_level", "claim_type", "artifact_type", "export_scope", "export_format"):
            value = props.get(name)
            if value is not None:
                fields.append(f"{name}={value}")
        print("- " + " ".join(str(field) for field in fields), file=stdout)


def _print_promoted_contribution_candidate(result: dict[str, Any], stdout: TextIO) -> None:
    print(f"decision: {result['decision']}", file=stdout)
    print(f"candidate_id: {result['candidate_id']}", file=stdout)
    print(f"contribution_id: {result['contribution']['id']}", file=stdout)
    print(f"created: {result['created']}", file=stdout)


def _print_rejected_contribution_candidate(result: dict[str, Any], stdout: TextIO) -> None:
    print(f"decision: {result['decision']}", file=stdout)
    print(f"candidate_id: {result['candidate_id']}", file=stdout)
    print(f"reason: {result['reason']}", file=stdout)


if __name__ == "__main__":
    raise SystemExit(main())
