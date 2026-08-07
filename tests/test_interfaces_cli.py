from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from typing import Any

from carrer.application import CareerWorkflow
from carrer.domain.models import evidence_node
from carrer.interfaces import cli
from carrer.storage.json_graph_storage import JsonGraphStorage

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-01-02T03:04:05+00:00"
NEXT = "2026-01-03T03:04:05+00:00"


def _write_store(path: Path, store: JsonGraphStorage) -> Path:
    store.save(path)
    return path


def _basic_store() -> JsonGraphStorage:
    store = JsonGraphStorage()
    store.create_node(
        {
            "id": "source:test",
            "node_type": "Source",
            "created_at": NOW,
            "properties": {"id": "test", "name": "Test Source", "visibility": "artifact_safe"},
        }
    )
    store.create_node(
        evidence_node(
            source_id="test",
            source_entity_type="work_item",
            source_entity_id="WI-1",
            evidence_type="WORK_ITEM_EXISTS",
            captured_at=NOW,
            occurred_at=NOW,
            privacy_level="artifact_safe",
            metadata={"state": "closed", "title": "CLI read only flow"},
        )
    )
    return store


def _accepted_store(output_dir: Path) -> JsonGraphStorage:
    workflow = CareerWorkflow(_basic_store())
    contribution = workflow.promote_contribution_candidate(
        workflow.discover_contribution_candidates()[0],
        created_at=NOW,
        decision_actor="human",
        status="draft",
    )["contribution"]
    analysis = workflow.accept_contribution_analysis(
        workflow.analyze_contribution(contribution["id"]),
        decision_actor="human",
        decided_at=NOW,
    )["analysis"]
    claim = workflow.accept_career_claim_candidate(
        workflow.generate_career_claim_candidates(analysis["id"])[0],
        decision_actor="human",
        decided_at=NOW,
    )["claim"]
    artifact = workflow.accept_claim_based_artifact(
        workflow.build_claim_based_artifact(
            claim_ids=[claim["id"]],
            artifact_type="resume_claims",
            audience="public",
            created_at=NOW,
        ),
        decision_actor="human",
        decided_at=NOW,
    )["artifact"]
    workflow.accept_export(
        workflow.build_export_candidate(
            artifact["id"],
            export_scope="external",
            export_format="markdown",
            created_at=NEXT,
        ),
        output_directory=output_dir,
        decision_actor="human",
        decided_at=NEXT,
    )
    workflow.store.nodes["artifact:legacy"] = {
        "id": "artifact:legacy",
        "node_type": "ProfessionalArtifact",
        "created_at": NOW,
        "properties": {"source_type": "legacy"},
    }
    return workflow.store


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = cli.run(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def test_parser_accepts_valid_commands(tmp_path: Path) -> None:
    store = tmp_path / "graph.json"
    commands = [
        ["--store", str(store), "status"],
        ["--store", str(store), "contributions", "list"],
        ["--store", str(store), "contributions", "discover"],
        ["--store", str(store), "analyses", "list"],
        ["--store", str(store), "claims", "list"],
        ["--store", str(store), "artifacts", "list"],
        ["--store", str(store), "exports", "list"],
        ["--store", str(store), "integrity", "graph"],
    ]

    for command in commands:
        assert cli.build_parser().parse_args(command).store == store


def test_missing_store_returns_controlled_non_zero_error(tmp_path: Path) -> None:
    code, stdout, stderr = _run(["--store", str(tmp_path / "missing.json"), "status"])

    assert code == 1
    assert stdout == ""
    assert "store not found" in stderr


def test_valid_store_is_loaded_without_mutation(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    before = store_path.read_text(encoding="utf-8")

    code, stdout, stderr = _run(["--store", str(store_path), "status"])

    assert code == 0
    assert stderr == ""
    assert "graph_integrity:" in stdout
    assert store_path.read_text(encoding="utf-8") == before


def test_status_is_deterministic(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _accepted_store(tmp_path / "exports"))

    first = _run(["--store", str(store_path), "--json", "status"])
    second = _run(["--store", str(store_path), "--json", "status"])

    assert first == second
    payload = json.loads(first[1])
    assert payload["counts"]["Contribution"] == 1
    assert payload["counts"]["ContributionAnalysis"] == 1
    assert payload["counts"]["CareerClaim"] == 1
    assert payload["counts"]["ProfessionalArtifact"] == 2
    assert payload["counts"]["ArtifactExportReceipt"] == 1


def test_contributions_list_delegates_to_workflow(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    calls: list[str] = []

    class FakeWorkflow:
        def __init__(self, store: JsonGraphStorage) -> None:
            self.store = store

        def list_contributions(self) -> list[dict[str, Any]]:
            calls.append("list_contributions")
            return [{"id": "contribution:fake", "node_type": "Contribution", "properties": {"status": "draft"}}]

    stdout = io.StringIO()
    code = cli.run(
        ["--store", str(store_path), "--json", "contributions", "list"],
        stdout=stdout,
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,  # type: ignore[arg-type]
    )

    assert code == 0
    assert calls == ["list_contributions"]
    assert json.loads(stdout.getvalue())[0]["id"] == "contribution:fake"


def test_contributions_discover_remains_read_only(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    before = store_path.read_text(encoding="utf-8")

    code, stdout, stderr = _run(["--store", str(store_path), "--json", "contributions", "discover"])

    assert code == 0
    assert stderr == ""
    assert json.loads(stdout)
    assert store_path.read_text(encoding="utf-8") == before


def test_list_commands_return_only_matching_contracts(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _accepted_store(tmp_path / "exports"))

    commands = [
        (["analyses", "list"], {"ContributionAnalysis"}),
        (["claims", "list"], {"CareerClaim"}),
        (["artifacts", "list"], {"ProfessionalArtifact"}),
        (["exports", "list"], {"ArtifactExportReceipt"}),
    ]
    for command, expected_types in commands:
        code, stdout, stderr = _run(["--store", str(store_path), "--json", *command])
        payload = json.loads(stdout)

        assert code == 0
        assert stderr == ""
        assert {item["node_type"] for item in payload} == expected_types
        if command == ["artifacts", "list"]:
            assert all(item["properties"]["source_type"] == "career_claim" for item in payload)


def test_graph_integrity_delegates_to_application_layer(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    calls: list[str] = []

    class FakeWorkflow:
        def __init__(self, store: JsonGraphStorage) -> None:
            self.store = store

        def graph_integrity(self) -> dict[str, Any]:
            calls.append("graph_integrity")
            return {
                "status": "valid",
                "summary": {
                    "node_count": 1,
                    "edge_count": 0,
                    "audit_record_count": 0,
                    "issue_count": 0,
                    "error_count": 0,
                    "warning_count": 0,
                },
                "issues": [],
            }

    stdout = io.StringIO()
    code = cli.run(
        ["--store", str(store_path), "--json", "integrity", "graph"],
        stdout=stdout,
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,  # type: ignore[arg-type]
    )

    assert code == 0
    assert calls == ["graph_integrity"]
    assert json.loads(stdout.getvalue())["status"] == "valid"


def test_json_flag_outputs_valid_json(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())

    code, stdout, stderr = _run(["--json", "--store", str(store_path), "integrity", "graph"])

    assert code == 0
    assert stderr == ""
    assert json.loads(stdout)["status"] == "valid"


def test_application_error_is_not_converted_to_success(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())

    code, stdout, stderr = _run(["--store", str(store_path), "claims", "list", "--claim-type", "unsupported"])

    assert code == 1
    assert stdout == ""
    assert "Invalid claim_type" in stderr


def test_read_only_commands_never_save_or_alter_store_file(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _accepted_store(tmp_path / "exports"))
    before = store_path.read_text(encoding="utf-8")
    commands = [
        ["status"],
        ["contributions", "list"],
        ["contributions", "discover"],
        ["analyses", "list"],
        ["claims", "list"],
        ["artifacts", "list"],
        ["exports", "list"],
        ["integrity", "graph"],
    ]

    for command in commands:
        code, _, stderr = _run(["--store", str(store_path), "--json", *command])
        assert code == 0
        assert stderr == ""
        assert store_path.read_text(encoding="utf-8") == before


def test_legacy_apis_and_scripts_remain_importable() -> None:
    import career_intelligence_mvp

    for script in ("run_mvp.py", "career_pipeline.py", "review.py"):
        spec = importlib.util.spec_from_file_location(script.removesuffix(".py"), ROOT / "scripts" / script)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    assert career_intelligence_mvp.GraphStore is JsonGraphStorage
