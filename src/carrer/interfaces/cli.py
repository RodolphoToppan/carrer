"""Command line interface over CareerWorkflow."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

from carrer.application import CareerWorkflow
from carrer.claims import (
    CAREER_CLAIM_DERIVED_FROM_ANALYSIS,
    CAREER_CLAIM_FROM_CONTRIBUTION,
    CAREER_CLAIM_SUPPORTED_BY_EVIDENCE,
    validate_persisted_career_claim,
)
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

    claims = commands.add_parser("claims")
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
        if all(isinstance(item, dict) and "claim_type" in item and "analysis_ref" in item for item in result):
            _print_career_claim_candidates(result, stdout)
            return
        _print_list(result, stdout)
        return
    if isinstance(result, dict) and "counts" in result and "integrity" in result:
        _print_status(result, stdout)
        return
    if isinstance(result, dict) and "issues" in result and "summary" in result:
        _print_integrity(result, stdout)
        return
    if isinstance(result, dict) and result.get("analysis_type") == "deterministic_contribution_analysis":
        _print_contribution_analysis(result, stdout)
        return
    if isinstance(result, dict) and result.get("decision") == "accepted" and "analysis" in result:
        _print_accepted_contribution_analysis(result, stdout)
        return
    if isinstance(result, dict) and result.get("decision") == "accepted" and "claim" in result:
        _print_accepted_career_claim_candidate(result, stdout)
        return
    if isinstance(result, dict) and result.get("decision") == "rejected" and "analysis_ref" in result:
        _print_rejected_career_claim_candidate(result, stdout)
        return
    if isinstance(result, dict) and result.get("decision") == "rejected" and "analysis_id" in result:
        _print_rejected_contribution_analysis(result, stdout)
        return
    if isinstance(result, dict) and result.get("decision") == "promoted":
        _print_promoted_contribution_candidate(result, stdout)
        return
    if isinstance(result, dict) and result.get("decision") == "rejected" and "candidate_id" in result:
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


def _print_promoted_contribution_candidate(result: dict[str, Any], stdout: TextIO) -> None:
    print(f"decision: {result['decision']}", file=stdout)
    print(f"candidate_id: {result['candidate_id']}", file=stdout)
    print(f"contribution_id: {result['contribution']['id']}", file=stdout)
    print(f"created: {result['created']}", file=stdout)


def _print_rejected_contribution_candidate(result: dict[str, Any], stdout: TextIO) -> None:
    print(f"decision: {result['decision']}", file=stdout)
    print(f"candidate_id: {result['candidate_id']}", file=stdout)
    print(f"reason: {result['reason']}", file=stdout)


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


if __name__ == "__main__":
    raise SystemExit(main())
