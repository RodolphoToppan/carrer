"""Command line interface over CareerWorkflow."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

from carrer.application import CareerWorkflow
from carrer.interfaces.commands import analyses, artifacts, claims, contributions
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

    contributions.register(commands)
    analyses.register(commands)
    claims.register(commands)
    artifacts.register(commands)

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
    if contributions.print_result(result, stdout):
        return
    if analyses.print_result(result, stdout):
        return
    if claims.print_result(result, stdout):
        return
    if artifacts.print_result(result, stdout):
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


if __name__ == "__main__":
    raise SystemExit(main())
