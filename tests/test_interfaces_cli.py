from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from typing import Any

import pytest

from carrer.application import CareerWorkflow
from carrer.artifacts import (
    PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM,
    PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE,
)
from carrer.claims import (
    CAREER_CLAIM_DERIVED_FROM_ANALYSIS,
    CAREER_CLAIM_FROM_CONTRIBUTION,
    CAREER_CLAIM_SUPPORTED_BY_EVIDENCE,
)
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


def _candidate_id(store_path: Path) -> str:
    return CareerWorkflow(JsonGraphStorage.load(store_path)).discover_contribution_candidates()[0]["id"]


def _promoted_store(path: Path) -> tuple[Path, dict[str, Any]]:
    workflow = CareerWorkflow(_basic_store())
    contribution = workflow.promote_contribution_candidate(
        workflow.discover_contribution_candidates()[0],
        created_at=NOW,
        decision_actor="human",
        status="draft",
    )["contribution"]
    return _write_store(path, workflow.store), contribution


def _claim_ready_store(path: Path) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    workflow = CareerWorkflow(JsonGraphStorage())
    nodes = [
        evidence_node(
            source_id="test",
            source_entity_type="commit",
            source_entity_id="C-1",
            evidence_type="COMMIT_EXISTS",
            captured_at=NOW,
            occurred_at=NOW,
            privacy_level="artifact_safe",
            metadata={"latency_after_ms": 300},
        ),
        evidence_node(
            source_id="test",
            source_entity_type="merge_request",
            source_entity_id="MR-1",
            evidence_type="MERGE_REQUEST_EXISTS",
            captured_at=NOW,
            occurred_at=NOW,
            privacy_level="artifact_safe",
            metadata={"state": "merged"},
        ),
        evidence_node(
            source_id="test",
            source_entity_type="work_item",
            source_entity_id="WI-1",
            evidence_type="WORK_ITEM_EXISTS",
            captured_at=NOW,
            occurred_at=NOW,
            privacy_level="internal",
            metadata={"state": "closed", "title": "CLI claim review"},
        ),
    ]
    for node in reversed(nodes):
        workflow.store.create_node(node)
    contribution = workflow.create_contribution(
        contribution_type="incident_fix",
        created_at=NOW,
        title="Retry fix",
        evidence_refs=[node["id"] for node in nodes],
        actions=["reviewed retry behavior"],
        outcomes=["bug resolved"],
        confidence="medium",
    )["contribution"]
    analysis = workflow.accept_contribution_analysis(
        workflow.analyze_contribution(contribution["id"]),
        decision_actor="human",
        decided_at=NOW,
    )["analysis"]
    candidates = workflow.generate_career_claim_candidates(analysis["id"])
    assert len(candidates) > 1
    return _write_store(path, workflow.store), analysis, candidates


def _artifact_ready_store(path: Path) -> tuple[Path, list[dict[str, Any]]]:
    store_path, _, candidates = _claim_ready_store(path)
    workflow = CareerWorkflow(JsonGraphStorage.load(store_path))
    claims = [
        workflow.accept_career_claim_candidate(candidate, decision_actor="human", decided_at=NOW)["claim"]
        for candidate in candidates[:2]
    ]
    workflow.store.save(store_path)
    return store_path, claims


def test_parser_accepts_valid_commands(tmp_path: Path) -> None:
    store = tmp_path / "graph.json"
    commands = [
        ["--store", str(store), "status"],
        ["--store", str(store), "contributions", "list"],
        ["--store", str(store), "contributions", "discover"],
        [
            "--store",
            str(store),
            "contributions",
            "promote",
            "--candidate-id",
            "c:1",
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ],
        [
            "--store",
            str(store),
            "contributions",
            "reject",
            "--candidate-id",
            "c:1",
            "--actor",
            "human",
            "--decided-at",
            NOW,
            "--reason",
            "no",
        ],
        ["--store", str(store), "analyses", "generate", "--contribution-id", "contribution:1"],
        [
            "--store",
            str(store),
            "analyses",
            "accept",
            "--contribution-id",
            "contribution:1",
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ],
        [
            "--store",
            str(store),
            "analyses",
            "reject",
            "--contribution-id",
            "contribution:1",
            "--actor",
            "human",
            "--decided-at",
            NOW,
            "--reason",
            "no",
        ],
        ["--store", str(store), "analyses", "list"],
        ["--store", str(store), "claims", "generate", "--analysis-id", "contribution_analysis:1"],
        [
            "--store",
            str(store),
            "claims",
            "accept",
            "--analysis-id",
            "contribution_analysis:1",
            "--candidate-id",
            "career_claim_candidate:1",
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ],
        [
            "--store",
            str(store),
            "claims",
            "reject",
            "--analysis-id",
            "contribution_analysis:1",
            "--candidate-id",
            "career_claim_candidate:1",
            "--actor",
            "human",
            "--decided-at",
            NOW,
            "--reason",
            "no",
        ],
        ["--store", str(store), "claims", "list"],
        [
            "--store",
            str(store),
            "artifacts",
            "build",
            "--claim-id",
            "career_claim:1",
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
            "--created-at",
            NOW,
        ],
        [
            "--store",
            str(store),
            "artifacts",
            "accept",
            "--claim-id",
            "career_claim:1",
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
            "--created-at",
            NOW,
            "--actor",
            "human",
            "--decided-at",
            NEXT,
        ],
        [
            "--store",
            str(store),
            "artifacts",
            "reject",
            "--claim-id",
            "career_claim:1",
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
            "--created-at",
            NOW,
            "--actor",
            "human",
            "--decided-at",
            NEXT,
            "--reason",
            "no",
        ],
        ["--store", str(store), "artifacts", "list"],
        ["--store", str(store), "exports", "list"],
        ["--store", str(store), "integrity", "graph"],
    ]

    for command in commands:
        assert cli.build_parser().parse_args(command).store == store


@pytest.mark.parametrize(
    "command",
    [
        ["contributions", "promote", "--actor", "human", "--decided-at", NOW],
        ["contributions", "promote", "--candidate-id", "c:1", "--decided-at", NOW],
        ["contributions", "promote", "--candidate-id", "c:1", "--actor", "human"],
        ["contributions", "reject", "--actor", "human", "--decided-at", NOW, "--reason", "no"],
        ["contributions", "reject", "--candidate-id", "c:1", "--decided-at", NOW, "--reason", "no"],
        ["contributions", "reject", "--candidate-id", "c:1", "--actor", "human", "--reason", "no"],
        ["analyses", "generate"],
        ["analyses", "accept", "--actor", "human", "--decided-at", NOW],
        ["analyses", "accept", "--contribution-id", "contribution:1", "--decided-at", NOW],
        ["analyses", "accept", "--contribution-id", "contribution:1", "--actor", "human"],
        ["analyses", "reject", "--actor", "human", "--decided-at", NOW, "--reason", "no"],
        ["analyses", "reject", "--contribution-id", "contribution:1", "--decided-at", NOW, "--reason", "no"],
        ["analyses", "reject", "--contribution-id", "contribution:1", "--actor", "human", "--reason", "no"],
        ["analyses", "reject", "--contribution-id", "contribution:1", "--actor", "human", "--decided-at", NOW],
        ["claims", "generate"],
        ["claims", "accept", "--candidate-id", "career_claim_candidate:1", "--actor", "human", "--decided-at", NOW],
        ["claims", "accept", "--analysis-id", "contribution_analysis:1", "--actor", "human", "--decided-at", NOW],
        [
            "claims",
            "accept",
            "--analysis-id",
            "contribution_analysis:1",
            "--candidate-id",
            "career_claim_candidate:1",
            "--decided-at",
            NOW,
        ],
        [
            "claims",
            "accept",
            "--analysis-id",
            "contribution_analysis:1",
            "--candidate-id",
            "career_claim_candidate:1",
            "--actor",
            "human",
        ],
        [
            "claims",
            "reject",
            "--candidate-id",
            "career_claim_candidate:1",
            "--actor",
            "human",
            "--decided-at",
            NOW,
            "--reason",
            "no",
        ],
        [
            "claims",
            "reject",
            "--analysis-id",
            "contribution_analysis:1",
            "--actor",
            "human",
            "--decided-at",
            NOW,
            "--reason",
            "no",
        ],
        [
            "claims",
            "reject",
            "--analysis-id",
            "contribution_analysis:1",
            "--candidate-id",
            "career_claim_candidate:1",
            "--decided-at",
            NOW,
            "--reason",
            "no",
        ],
        [
            "claims",
            "reject",
            "--analysis-id",
            "contribution_analysis:1",
            "--candidate-id",
            "career_claim_candidate:1",
            "--actor",
            "human",
            "--reason",
            "no",
        ],
        [
            "claims",
            "reject",
            "--analysis-id",
            "contribution_analysis:1",
            "--candidate-id",
            "career_claim_candidate:1",
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ],
        ["artifacts", "build", "--artifact-type", "resume_claims", "--audience", "internal", "--created-at", NOW],
        ["artifacts", "build", "--claim-id", "career_claim:1", "--audience", "internal", "--created-at", NOW],
        ["artifacts", "build", "--claim-id", "career_claim:1", "--artifact-type", "resume_claims", "--created-at", NOW],
        [
            "artifacts",
            "build",
            "--claim-id",
            "career_claim:1",
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
        ],
        [
            "artifacts",
            "accept",
            "--claim-id",
            "career_claim:1",
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
            "--created-at",
            NOW,
            "--decided-at",
            NEXT,
        ],
        [
            "artifacts",
            "accept",
            "--claim-id",
            "career_claim:1",
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
            "--created-at",
            NOW,
            "--actor",
            "human",
        ],
        [
            "artifacts",
            "reject",
            "--claim-id",
            "career_claim:1",
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
            "--created-at",
            NOW,
            "--actor",
            "human",
            "--decided-at",
            NEXT,
        ],
    ],
)
def test_contribution_decision_required_parser_arguments(tmp_path: Path, command: list[str]) -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--store", str(tmp_path / "graph.json"), *command])


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


def test_contributions_promote_delegates_persists_and_reloads(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    candidate_id = _candidate_id(store_path)

    code, stdout, stderr = _run(
        [
            "--store",
            str(store_path),
            "contributions",
            "promote",
            "--candidate-id",
            candidate_id,
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ]
    )
    reloaded = JsonGraphStorage.load(store_path)
    contribution = reloaded.nodes_by_type("Contribution")[0]

    assert code == 0
    assert stderr == ""
    assert f"candidate_id: {candidate_id}" in stdout
    assert f"contribution_id: {contribution['id']}" in stdout
    assert "title" not in stdout
    assert contribution["properties"]["metadata"]["candidate_id"] == candidate_id
    assert contribution["properties"]["evidence_refs"]
    assert any(record["audit_type"] == "contribution_candidate_promoted" for record in reloaded.audit_records)


def test_contributions_promote_json_outputs_application_result(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    candidate_id = _candidate_id(store_path)

    code, stdout, stderr = _run(
        [
            "--json",
            "--store",
            str(store_path),
            "contributions",
            "promote",
            "--candidate-id",
            candidate_id,
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ]
    )
    payload = json.loads(stdout)

    assert code == 0
    assert stderr == ""
    assert payload["candidate_id"] == candidate_id
    assert payload["decision"] == "promoted"
    assert payload["created"] is True
    assert payload["contribution"]["node_type"] == "Contribution"


def test_contributions_promote_is_idempotent_according_to_domain(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    candidate_id = _candidate_id(store_path)
    command = [
        "--json",
        "--store",
        str(store_path),
        "contributions",
        "promote",
        "--candidate-id",
        candidate_id,
        "--actor",
        "human",
        "--decided-at",
        NOW,
    ]

    first = _run(command)
    second = _run(command)

    assert json.loads(first[1])["created"] is True
    assert json.loads(second[1])["created"] is False
    assert len(JsonGraphStorage.load(store_path).nodes_by_type("Contribution")) == 1


def test_contributions_reject_delegates_persists_only_audit_and_reloads(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    candidate_id = _candidate_id(store_path)

    code, stdout, stderr = _run(
        [
            "--store",
            str(store_path),
            "contributions",
            "reject",
            "--candidate-id",
            candidate_id,
            "--actor",
            "human",
            "--decided-at",
            NOW,
            "--reason",
            "not mine",
        ]
    )
    reloaded = JsonGraphStorage.load(store_path)

    assert code == 0
    assert stderr == ""
    assert "decision: rejected" in stdout
    assert f"candidate_id: {candidate_id}" in stdout
    assert "reason: not mine" in stdout
    assert reloaded.nodes_by_type("Contribution") == []
    assert reloaded.edges == []
    assert [record["audit_type"] for record in reloaded.audit_records] == ["contribution_candidate_rejected"]


def test_missing_contribution_candidate_fails_without_modifying_file(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    before = store_path.read_text(encoding="utf-8")

    code, stdout, stderr = _run(
        [
            "--store",
            str(store_path),
            "contributions",
            "promote",
            "--candidate-id",
            "contribution_candidate:missing",
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ]
    )

    assert code == 1
    assert stdout == ""
    assert "expected exactly one current ContributionCandidate" in stderr
    assert store_path.read_text(encoding="utf-8") == before


def test_contribution_candidate_is_regenerated_instead_of_accepting_input_arbitrarily(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    candidate_id = _candidate_id(store_path)
    calls: list[tuple[str, str]] = []

    class FakeWorkflow(CareerWorkflow):
        def discover_contribution_candidates(self) -> list[dict[str, Any]]:
            calls.append(("discover", ""))
            return super().discover_contribution_candidates()

        def promote_contribution_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            calls.append(("promote", candidate["id"]))
            return super().promote_contribution_candidate(candidate, **kwargs)

    code = cli.run(
        [
            "--store",
            str(store_path),
            "contributions",
            "promote",
            "--candidate-id",
            candidate_id,
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 0
    assert calls == [("discover", ""), ("promote", candidate_id)]


def test_application_error_does_not_save_store(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    candidate_id = _candidate_id(store_path)
    before = store_path.read_text(encoding="utf-8")

    class FakeWorkflow(CareerWorkflow):
        def promote_contribution_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            raise ValueError("application failed")

    code = cli.run(
        [
            "--store",
            str(store_path),
            "contributions",
            "promote",
            "--candidate-id",
            candidate_id,
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert store_path.read_text(encoding="utf-8") == before


def test_inconsistent_promote_result_fails_before_save_and_preserves_file(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    candidate_id = _candidate_id(store_path)
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def promote_contribution_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            return {
                "candidate_id": candidate["id"],
                "decision": "promoted",
                "contribution": {"id": "contribution:not-in-store", "node_type": "Contribution", "properties": {}},
                "created": True,
            }

    code = cli.run(
        [
            "--store",
            str(store_path),
            "contributions",
            "promote",
            "--candidate-id",
            candidate_id,
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before


def test_inconsistent_reject_result_fails_before_save_and_preserves_file(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    candidate_id = _candidate_id(store_path)
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def reject_contribution_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            return {"candidate_id": candidate["id"], "decision": "rejected", "reason": "not mine"}

    code = cli.run(
        [
            "--store",
            str(store_path),
            "contributions",
            "reject",
            "--candidate-id",
            candidate_id,
            "--actor",
            "human",
            "--decided-at",
            NOW,
            "--reason",
            "not mine",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before


def test_persistence_error_does_not_return_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    candidate_id = _candidate_id(store_path)
    before = store_path.read_text(encoding="utf-8")

    def fail_save(self: JsonGraphStorage, path: Path) -> None:
        raise OSError("cannot save")

    monkeypatch.setattr(JsonGraphStorage, "save", fail_save)

    code, stdout, stderr = _run(
        [
            "--store",
            str(store_path),
            "contributions",
            "promote",
            "--candidate-id",
            candidate_id,
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ]
    )

    assert code == 1
    assert stdout == ""
    assert "cannot save" in stderr
    assert store_path.read_text(encoding="utf-8") == before


def test_analyses_generate_delegates_outputs_review_summary_and_is_read_only(tmp_path: Path) -> None:
    store_path, contribution = _promoted_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")
    calls: list[str] = []

    class FakeWorkflow(CareerWorkflow):
        def analyze_contribution(self, contribution_id: str) -> dict[str, Any]:
            calls.append(contribution_id)
            return super().analyze_contribution(contribution_id)

    stdout = io.StringIO()
    code = cli.run(
        ["--store", str(store_path), "analyses", "generate", "--contribution-id", contribution["id"]],
        stdout=stdout,
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 0
    assert calls == [contribution["id"]]
    assert "analysis_id:" in stdout.getvalue()
    assert "contribution_ref:" in stdout.getvalue()
    assert "impact_signals:" in stdout.getvalue()
    assert "title" not in stdout.getvalue()
    assert store_path.read_text(encoding="utf-8") == before


def test_analyses_generate_json_matches_application_result(tmp_path: Path) -> None:
    store_path, contribution = _promoted_store(tmp_path / "graph.json")
    expected = CareerWorkflow(JsonGraphStorage.load(store_path)).analyze_contribution(contribution["id"])

    code, stdout, stderr = _run(
        ["--store", str(store_path), "--json", "analyses", "generate", "--contribution-id", contribution["id"]]
    )

    assert code == 0
    assert stderr == ""
    assert json.loads(stdout) == expected


def test_analyses_generate_missing_contribution_returns_controlled_error(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    before = store_path.read_text(encoding="utf-8")

    code, stdout, stderr = _run(
        ["--store", str(store_path), "analyses", "generate", "--contribution-id", "contribution:missing"]
    )

    assert code == 1
    assert stdout == ""
    assert "Contribution not found" in stderr
    assert store_path.read_text(encoding="utf-8") == before


def test_analyses_accept_regenerates_delegates_persists_edges_and_audit(tmp_path: Path) -> None:
    store_path, contribution = _promoted_store(tmp_path / "graph.json")
    calls: list[tuple[str, str]] = []

    class FakeWorkflow(CareerWorkflow):
        def analyze_contribution(self, contribution_id: str) -> dict[str, Any]:
            calls.append(("analyze", contribution_id))
            return super().analyze_contribution(contribution_id)

        def accept_contribution_analysis(self, analysis: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            calls.append(("accept", analysis["contribution_ref"]))
            return super().accept_contribution_analysis(analysis, **kwargs)

    stdout = io.StringIO()
    code = cli.run(
        [
            "--store",
            str(store_path),
            "analyses",
            "accept",
            "--contribution-id",
            contribution["id"],
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ],
        stdout=stdout,
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )
    reloaded = JsonGraphStorage.load(store_path)
    analysis = reloaded.nodes_by_type("ContributionAnalysis")[0]

    assert code == 0
    assert calls == [("analyze", contribution["id"]), ("accept", contribution["id"])]
    assert f"analysis_id: {analysis['id']}" in stdout.getvalue()
    assert analysis["properties"]["status"] == "accepted"
    assert any(record["audit_type"] == "contribution_analysis_accepted" for record in reloaded.audit_records)
    edge_types = {edge["edge_type"] for edge in reloaded.edges if edge["from_node_id"] == analysis["id"]}
    assert "CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION" in edge_types
    assert "CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE" in edge_types


def test_analyses_accept_reject_do_not_accept_arbitrary_payload_args(tmp_path: Path) -> None:
    store = tmp_path / "graph.json"

    for command in ("accept", "reject"):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(
                [
                    "--store",
                    str(store),
                    "analyses",
                    command,
                    "--contribution-id",
                    "contribution:1",
                    "--actor",
                    "human",
                    "--decided-at",
                    NOW,
                    "--analysis-json",
                    "{}",
                ]
            )


def test_analyses_accept_inconsistent_result_fails_before_save(tmp_path: Path) -> None:
    store_path, contribution = _promoted_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def accept_contribution_analysis(self, analysis: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            return {"decision": "accepted", "analysis": {"id": "contribution_analysis:missing"}, "created": True}

    code = cli.run(
        [
            "--store",
            str(store_path),
            "analyses",
            "accept",
            "--contribution-id",
            contribution["id"],
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before


def test_analyses_accept_requires_audit_from_current_decision(tmp_path: Path) -> None:
    store_path, contribution = _promoted_store(tmp_path / "graph.json")
    workflow = CareerWorkflow(JsonGraphStorage.load(store_path))
    workflow.accept_contribution_analysis(
        workflow.analyze_contribution(contribution["id"]),
        decision_actor="human",
        decided_at=NOW,
    )
    workflow.store.save(store_path)
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def accept_contribution_analysis(self, analysis: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            return {"decision": "accepted", "analysis": self.store.nodes[analysis["id"]], "created": False}

    code = cli.run(
        [
            "--store",
            str(store_path),
            "analyses",
            "accept",
            "--contribution-id",
            contribution["id"],
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before


def test_analyses_reject_regenerates_delegates_persists_only_audit_with_preexisting_analysis(tmp_path: Path) -> None:
    store_path, contribution = _promoted_store(tmp_path / "graph.json")
    workflow = CareerWorkflow(JsonGraphStorage.load(store_path))
    workflow.accept_contribution_analysis(
        workflow.analyze_contribution(contribution["id"]),
        decision_actor="first",
        decided_at=NOW,
    )
    workflow.store.save(store_path)
    before = JsonGraphStorage.load(store_path)
    calls: list[tuple[str, str]] = []

    class FakeWorkflow(CareerWorkflow):
        def analyze_contribution(self, contribution_id: str) -> dict[str, Any]:
            calls.append(("analyze", contribution_id))
            return super().analyze_contribution(contribution_id)

        def reject_contribution_analysis(self, analysis: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            calls.append(("reject", analysis["contribution_ref"]))
            return super().reject_contribution_analysis(analysis, **kwargs)

    code, stdout, stderr = _run(
        [
            "--store",
            str(store_path),
            "analyses",
            "reject",
            "--contribution-id",
            contribution["id"],
            "--actor",
            "human",
            "--decided-at",
            NEXT,
            "--reason",
            "not enough context",
        ]
    )
    reloaded = JsonGraphStorage.load(store_path)

    assert code == 0
    assert stderr == ""
    assert "decision: rejected" in stdout
    assert reloaded.nodes == before.nodes
    assert reloaded.edges == before.edges
    assert [record["audit_type"] for record in reloaded.audit_records].count("contribution_analysis_rejected") == 1
    assert calls == []

    stdout = io.StringIO()
    code = cli.run(
        [
            "--store",
            str(store_path),
            "analyses",
            "reject",
            "--contribution-id",
            contribution["id"],
            "--actor",
            "human",
            "--decided-at",
            NEXT,
            "--reason",
            "not enough context",
        ],
        stdout=stdout,
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )
    assert code == 0
    assert calls == [("analyze", contribution["id"]), ("reject", contribution["id"])]


def test_analyses_reject_inconsistent_result_fails_before_save(tmp_path: Path) -> None:
    store_path, contribution = _promoted_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def reject_contribution_analysis(self, analysis: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            return {"decision": "rejected", "analysis_id": analysis["id"], "contribution_ref": "wrong", "reason": ""}

    code = cli.run(
        [
            "--store",
            str(store_path),
            "analyses",
            "reject",
            "--contribution-id",
            contribution["id"],
            "--actor",
            "human",
            "--decided-at",
            NOW,
            "--reason",
            "no",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before


def test_analyses_reject_detects_nested_graph_mutation_before_save(tmp_path: Path) -> None:
    store_path, contribution = _promoted_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def reject_contribution_analysis(self, analysis: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            self.store.nodes[analysis["contribution_ref"]]["properties"]["metadata"]["unexpected"] = "mutation"
            self.store.append_audit_record(
                "contribution_analysis_rejected",
                [analysis["id"], analysis["contribution_ref"]],
                "rejected",
                {
                    "analysis_id": analysis["id"],
                    "contribution_id": analysis["contribution_ref"],
                    "actor": "human",
                    "decided_at": NOW,
                    "reason": "no",
                },
            )
            return {
                "decision": "rejected",
                "analysis_id": analysis["id"],
                "contribution_ref": analysis["contribution_ref"],
                "reason": "no",
            }

    code = cli.run(
        [
            "--store",
            str(store_path),
            "analyses",
            "reject",
            "--contribution-id",
            contribution["id"],
            "--actor",
            "human",
            "--decided-at",
            NOW,
            "--reason",
            "no",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before


def test_analyses_application_or_save_error_does_not_preserve_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_path, contribution = _promoted_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")

    class FakeWorkflow(CareerWorkflow):
        def accept_contribution_analysis(self, analysis: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            raise ValueError("application failed")

    code = cli.run(
        [
            "--store",
            str(store_path),
            "analyses",
            "accept",
            "--contribution-id",
            contribution["id"],
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert store_path.read_text(encoding="utf-8") == before

    def fail_save(self: JsonGraphStorage, path: Path) -> None:
        raise OSError("cannot save")

    monkeypatch.setattr(JsonGraphStorage, "save", fail_save)
    code, stdout, stderr = _run(
        [
            "--store",
            str(store_path),
            "analyses",
            "accept",
            "--contribution-id",
            contribution["id"],
            "--actor",
            "human",
            "--decided-at",
            NOW,
        ]
    )

    assert code == 1
    assert stdout == ""
    assert "cannot save" in stderr


def test_analyses_accept_is_idempotent_according_to_domain(tmp_path: Path) -> None:
    store_path, contribution = _promoted_store(tmp_path / "graph.json")
    command = [
        "--store",
        str(store_path),
        "--json",
        "analyses",
        "accept",
        "--contribution-id",
        contribution["id"],
        "--actor",
        "human",
        "--decided-at",
        NOW,
    ]

    first = _run(command)
    second = _run(command)

    assert json.loads(first[1])["created"] is True
    assert json.loads(second[1])["created"] is False
    assert len(JsonGraphStorage.load(store_path).nodes_by_type("ContributionAnalysis")) == 1


def test_claims_generate_delegates_outputs_review_summary_and_is_read_only(tmp_path: Path) -> None:
    store_path, analysis, candidates = _claim_ready_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")
    calls: list[str] = []

    class FakeWorkflow(CareerWorkflow):
        def generate_career_claim_candidates(self, analysis_id: str) -> list[dict[str, Any]]:
            calls.append(analysis_id)
            return super().generate_career_claim_candidates(analysis_id)

    stdout = io.StringIO()
    code = cli.run(
        ["--store", str(store_path), "claims", "generate", "--analysis-id", analysis["id"]],
        stdout=stdout,
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 0
    assert calls == [analysis["id"]]
    assert f"items: {len(candidates)}" in stdout.getvalue()
    assert "claim_type=" in stdout.getvalue()
    assert "statement:" in stdout.getvalue()
    assert "CLI claim review" not in stdout.getvalue()
    assert "300" in stdout.getvalue()
    assert store_path.read_text(encoding="utf-8") == before


def test_claims_generate_json_matches_application_result(tmp_path: Path) -> None:
    store_path, analysis, _ = _claim_ready_store(tmp_path / "graph.json")
    expected = CareerWorkflow(JsonGraphStorage.load(store_path)).generate_career_claim_candidates(analysis["id"])

    code, stdout, stderr = _run(
        ["--store", str(store_path), "--json", "claims", "generate", "--analysis-id", analysis["id"]]
    )

    assert code == 0
    assert stderr == ""
    assert json.loads(stdout) == expected


def test_claims_generate_missing_or_unaccepted_analysis_fails_without_save(tmp_path: Path) -> None:
    store_path = _write_store(tmp_path / "graph.json", _basic_store())
    before = store_path.read_text(encoding="utf-8")

    code, stdout, stderr = _run(
        ["--store", str(store_path), "claims", "generate", "--analysis-id", "contribution_analysis:missing"]
    )

    assert code == 1
    assert stdout == ""
    assert "ContributionAnalysis not found" in stderr
    assert store_path.read_text(encoding="utf-8") == before

    promoted_path, contribution = _promoted_store(tmp_path / "unaccepted.json")
    workflow = CareerWorkflow(JsonGraphStorage.load(promoted_path))
    analysis = workflow.analyze_contribution(contribution["id"])
    workflow.store.nodes[analysis["id"]] = {
        "id": analysis["id"],
        "node_type": "ContributionAnalysis",
        "created_at": NOW,
        "properties": {
            **analysis,
            "analysis_version": analysis["metadata"]["analysis_version"],
            "review_actor": "human",
            "reviewed_at": NOW,
        },
    }
    workflow.store.save(promoted_path)
    before = promoted_path.read_text(encoding="utf-8")

    code, stdout, stderr = _run(["--store", str(promoted_path), "claims", "generate", "--analysis-id", analysis["id"]])

    assert code == 1
    assert stdout == ""
    assert "accepted" in stderr
    assert promoted_path.read_text(encoding="utf-8") == before


def test_claims_generate_returns_multiple_candidates_without_auto_selection(tmp_path: Path) -> None:
    store_path, analysis, candidates = _claim_ready_store(tmp_path / "graph.json")

    code, stdout, stderr = _run(
        ["--store", str(store_path), "--json", "claims", "generate", "--analysis-id", analysis["id"]]
    )

    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert len(payload) == len(candidates)
    assert len(JsonGraphStorage.load(store_path).nodes_by_type("CareerClaim")) == 0


def test_claims_accept_regenerates_selects_delegates_persists_claim_edges_and_audit(tmp_path: Path) -> None:
    store_path, analysis, candidates = _claim_ready_store(tmp_path / "graph.json")
    candidate = candidates[0]
    calls: list[tuple[str, str]] = []

    class FakeWorkflow(CareerWorkflow):
        def generate_career_claim_candidates(self, analysis_id: str) -> list[dict[str, Any]]:
            calls.append(("generate", analysis_id))
            return super().generate_career_claim_candidates(analysis_id)

        def accept_career_claim_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            calls.append(("accept", candidate["id"]))
            return super().accept_career_claim_candidate(candidate, **kwargs)

    stdout = io.StringIO()
    code = cli.run(
        [
            "--store",
            str(store_path),
            "claims",
            "accept",
            "--analysis-id",
            analysis["id"],
            "--candidate-id",
            candidate["id"],
            "--actor",
            "human",
            "--decided-at",
            NEXT,
        ],
        stdout=stdout,
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )
    reloaded = JsonGraphStorage.load(store_path)
    claim = reloaded.nodes_by_type("CareerClaim")[0]

    assert code == 0
    assert calls == [("generate", analysis["id"]), ("accept", candidate["id"])]
    assert f"candidate_id: {candidate['id']}" in stdout.getvalue()
    assert f"claim_id: {claim['id']}" in stdout.getvalue()
    assert claim["properties"]["metadata"]["candidate_id"] == candidate["id"]
    assert claim["properties"]["privacy_level"] == candidate["privacy_level"]
    assert any(record["audit_type"] == "career_claim_candidate_accepted" for record in reloaded.audit_records)
    edge_types = {edge["edge_type"] for edge in reloaded.edges if edge["from_node_id"] == claim["id"]}
    assert CAREER_CLAIM_DERIVED_FROM_ANALYSIS in edge_types
    assert CAREER_CLAIM_FROM_CONTRIBUTION in edge_types
    assert CAREER_CLAIM_SUPPORTED_BY_EVIDENCE in edge_types


def test_claims_accept_reject_do_not_accept_arbitrary_payload_args(tmp_path: Path) -> None:
    store = tmp_path / "graph.json"

    for command in ("accept", "reject"):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(
                [
                    "--store",
                    str(store),
                    "claims",
                    command,
                    "--analysis-id",
                    "contribution_analysis:1",
                    "--candidate-id",
                    "career_claim_candidate:1",
                    "--actor",
                    "human",
                    "--decided-at",
                    NOW,
                    "--candidate-json",
                    "{}",
                ]
            )


def test_claims_accept_missing_candidate_fails_before_mutation(tmp_path: Path) -> None:
    store_path, analysis, _ = _claim_ready_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")

    code, stdout, stderr = _run(
        [
            "--store",
            str(store_path),
            "claims",
            "accept",
            "--analysis-id",
            analysis["id"],
            "--candidate-id",
            "career_claim_candidate:missing",
            "--actor",
            "human",
            "--decided-at",
            NEXT,
        ]
    )

    assert code == 1
    assert stdout == ""
    assert "expected exactly one current CareerClaimCandidate" in stderr
    assert store_path.read_text(encoding="utf-8") == before


def test_claims_accept_reject_duplicate_candidate_match_fails_before_mutation(tmp_path: Path) -> None:
    store_path, analysis, candidates = _claim_ready_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")

    class FakeWorkflow(CareerWorkflow):
        def generate_career_claim_candidates(self, analysis_id: str) -> list[dict[str, Any]]:
            current = super().generate_career_claim_candidates(analysis_id)
            return [current[0], current[0], *current[1:]]

    for command in ("accept", "reject"):
        args = [
            "--store",
            str(store_path),
            "claims",
            command,
            "--analysis-id",
            analysis["id"],
            "--candidate-id",
            candidates[0]["id"],
            "--actor",
            "human",
            "--decided-at",
            NEXT,
        ]
        if command == "reject":
            args.extend(["--reason", "duplicate"])

        code = cli.run(
            args,
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            workflow_factory=FakeWorkflow,
        )

        assert code == 1
        assert store_path.read_text(encoding="utf-8") == before


def test_claims_accept_inconsistent_result_fails_before_save(tmp_path: Path) -> None:
    store_path, analysis, candidates = _claim_ready_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def accept_career_claim_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            return {"decision": "accepted", "candidate_id": candidate["id"], "claim": {"id": "career_claim:missing"}}

    code = cli.run(
        [
            "--store",
            str(store_path),
            "claims",
            "accept",
            "--analysis-id",
            analysis["id"],
            "--candidate-id",
            candidates[0]["id"],
            "--actor",
            "human",
            "--decided-at",
            NEXT,
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before


def test_claims_accept_requires_audit_from_current_decision(tmp_path: Path) -> None:
    store_path, analysis, candidates = _claim_ready_store(tmp_path / "graph.json")
    workflow = CareerWorkflow(JsonGraphStorage.load(store_path))
    workflow.accept_career_claim_candidate(candidates[0], decision_actor="first", decided_at=NEXT)
    workflow.store.save(store_path)
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def accept_career_claim_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            claim_id = next(iter(self.store.nodes_by_type("CareerClaim")))["id"]
            return {
                "decision": "accepted",
                "candidate_id": candidate["id"],
                "claim": self.store.nodes[claim_id],
                "created": False,
            }

    code = cli.run(
        [
            "--store",
            str(store_path),
            "claims",
            "accept",
            "--analysis-id",
            analysis["id"],
            "--candidate-id",
            candidates[0]["id"],
            "--actor",
            "human",
            "--decided-at",
            NEXT,
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before


def test_claims_accept_is_idempotent_according_to_domain(tmp_path: Path) -> None:
    store_path, analysis, candidates = _claim_ready_store(tmp_path / "graph.json")
    command = [
        "--store",
        str(store_path),
        "--json",
        "claims",
        "accept",
        "--analysis-id",
        analysis["id"],
        "--candidate-id",
        candidates[0]["id"],
        "--actor",
        "human",
        "--decided-at",
        NEXT,
    ]

    first = _run(command)
    second = _run(command)

    assert json.loads(first[1])["created"] is True
    assert json.loads(second[1])["created"] is False
    reloaded = JsonGraphStorage.load(store_path)
    assert len(reloaded.nodes_by_type("CareerClaim")) == 1
    audits = [record for record in reloaded.audit_records if record["audit_type"] == "career_claim_candidate_accepted"]
    assert [record["metadata"]["created"] for record in audits] == [True, False]


def test_claims_reject_regenerates_delegates_persists_only_audit_with_preexisting_claim(tmp_path: Path) -> None:
    store_path, analysis, candidates = _claim_ready_store(tmp_path / "graph.json")
    workflow = CareerWorkflow(JsonGraphStorage.load(store_path))
    workflow.accept_career_claim_candidate(candidates[0], decision_actor="first", decided_at=NEXT)
    workflow.store.save(store_path)
    before = JsonGraphStorage.load(store_path)
    calls: list[tuple[str, str]] = []

    class FakeWorkflow(CareerWorkflow):
        def generate_career_claim_candidates(self, analysis_id: str) -> list[dict[str, Any]]:
            calls.append(("generate", analysis_id))
            return super().generate_career_claim_candidates(analysis_id)

        def reject_career_claim_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            calls.append(("reject", candidate["id"]))
            return super().reject_career_claim_candidate(candidate, **kwargs)

    code = cli.run(
        [
            "--store",
            str(store_path),
            "claims",
            "reject",
            "--analysis-id",
            analysis["id"],
            "--candidate-id",
            candidates[0]["id"],
            "--actor",
            "human",
            "--decided-at",
            NEXT,
            "--reason",
            "not useful",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )
    reloaded = JsonGraphStorage.load(store_path)

    assert code == 0
    assert calls == [("generate", analysis["id"]), ("reject", candidates[0]["id"])]
    assert reloaded.nodes == before.nodes
    assert reloaded.edges == before.edges
    assert [record["audit_type"] for record in reloaded.audit_records].count("career_claim_candidate_rejected") == 1


def test_claims_reject_detects_nested_graph_mutation_before_save(tmp_path: Path) -> None:
    store_path, analysis, candidates = _claim_ready_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def reject_career_claim_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            self.store.nodes[candidate["contribution_ref"]]["properties"]["metadata"]["unexpected"] = "mutation"
            self.store.append_audit_record(
                "career_claim_candidate_rejected",
                [candidate["id"], candidate["analysis_ref"], candidate["contribution_ref"]],
                "rejected",
                {
                    "candidate_id": candidate["id"],
                    "analysis_id": candidate["analysis_ref"],
                    "contribution_id": candidate["contribution_ref"],
                    "actor": "human",
                    "decided_at": NEXT,
                    "reason": "no",
                },
            )
            return {
                "candidate_id": candidate["id"],
                "analysis_ref": candidate["analysis_ref"],
                "contribution_ref": candidate["contribution_ref"],
                "decision": "rejected",
                "reason": "no",
            }

    code = cli.run(
        [
            "--store",
            str(store_path),
            "claims",
            "reject",
            "--analysis-id",
            analysis["id"],
            "--candidate-id",
            candidates[0]["id"],
            "--actor",
            "human",
            "--decided-at",
            NEXT,
            "--reason",
            "no",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before


def test_claims_reject_requires_audit_from_current_decision(tmp_path: Path) -> None:
    store_path, analysis, candidates = _claim_ready_store(tmp_path / "graph.json")
    workflow = CareerWorkflow(JsonGraphStorage.load(store_path))
    workflow.reject_career_claim_candidate(candidates[0], decision_actor="first", decided_at=NOW, reason="old")
    workflow.store.save(store_path)
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def reject_career_claim_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            return {
                "candidate_id": candidate["id"],
                "analysis_ref": candidate["analysis_ref"],
                "contribution_ref": candidate["contribution_ref"],
                "decision": "rejected",
                "reason": "new",
            }

    code = cli.run(
        [
            "--store",
            str(store_path),
            "claims",
            "reject",
            "--analysis-id",
            analysis["id"],
            "--candidate-id",
            candidates[0]["id"],
            "--actor",
            "human",
            "--decided-at",
            NEXT,
            "--reason",
            "new",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before


def test_claims_application_or_save_error_does_not_preserve_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_path, analysis, candidates = _claim_ready_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")

    class FakeWorkflow(CareerWorkflow):
        def accept_career_claim_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            raise ValueError("application failed")

    code = cli.run(
        [
            "--store",
            str(store_path),
            "claims",
            "accept",
            "--analysis-id",
            analysis["id"],
            "--candidate-id",
            candidates[0]["id"],
            "--actor",
            "human",
            "--decided-at",
            NEXT,
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )

    assert code == 1
    assert store_path.read_text(encoding="utf-8") == before

    def fail_save(self: JsonGraphStorage, path: Path) -> None:
        raise OSError("cannot save")

    monkeypatch.setattr(JsonGraphStorage, "save", fail_save)
    code, stdout, stderr = _run(
        [
            "--store",
            str(store_path),
            "claims",
            "accept",
            "--analysis-id",
            analysis["id"],
            "--candidate-id",
            candidates[0]["id"],
            "--actor",
            "human",
            "--decided-at",
            NEXT,
        ]
    )

    assert code == 1
    assert stdout == ""
    assert "cannot save" in stderr


def test_artifacts_build_delegates_outputs_review_content_and_is_read_only(tmp_path: Path) -> None:
    store_path, claims = _artifact_ready_store(tmp_path / "graph.json")
    claim_ids = [claim["id"] for claim in claims]
    before = store_path.read_text(encoding="utf-8")
    calls: list[list[str]] = []

    class FakeWorkflow(CareerWorkflow):
        def build_claim_based_artifact(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs["claim_ids"])
            return super().build_claim_based_artifact(**kwargs)

    stdout = io.StringIO()
    code = cli.run(
        [
            "--store",
            str(store_path),
            "artifacts",
            "build",
            "--claim-id",
            claim_ids[1],
            "--claim-id",
            claim_ids[0],
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
            "--created-at",
            NEXT,
        ],
        stdout=stdout,
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )
    output = stdout.getvalue()

    assert code == 0
    assert calls == [[claim_ids[1], claim_ids[0]]]
    assert "artifact_id: claim_based_artifact:" in output
    assert "artifact_type: resume_claims" in output
    assert "audience: internal" in output
    assert "status: draft" in output
    assert "privacy_level:" in output
    assert "claim_count: 2" in output
    assert "claim_ids: " in output
    assert "content:" in output
    assert claims[0]["properties"]["statement"] in output
    assert store_path.read_text(encoding="utf-8") == before


def test_artifacts_build_json_matches_application_result(tmp_path: Path) -> None:
    store_path, claims = _artifact_ready_store(tmp_path / "graph.json")
    claim_ids = [claim["id"] for claim in claims]
    expected = CareerWorkflow(JsonGraphStorage.load(store_path)).build_claim_based_artifact(
        claim_ids=list(reversed(claim_ids)),
        artifact_type="resume_claims",
        audience="internal",
        created_at=NEXT,
    )

    code, stdout, stderr = _run(
        [
            "--store",
            str(store_path),
            "--json",
            "artifacts",
            "build",
            "--claim-id",
            claim_ids[1],
            "--claim-id",
            claim_ids[0],
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
            "--created-at",
            NEXT,
        ]
    )

    assert code == 0
    assert stderr == ""
    assert json.loads(stdout) == expected


def test_artifacts_build_errors_do_not_save(tmp_path: Path) -> None:
    store_path, claims = _artifact_ready_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")

    cases = [
        ["--claim-id", "career_claim:missing"],
        ["--claim-id", claims[0]["id"], "--claim-id", claims[0]["id"]],
    ]
    for extra in cases:
        code, stdout, _ = _run(
            [
                "--store",
                str(store_path),
                "artifacts",
                "build",
                *extra,
                "--artifact-type",
                "resume_claims",
                "--audience",
                "internal",
                "--created-at",
                NEXT,
            ]
        )

        assert code == 1
        assert stdout == ""
        assert store_path.read_text(encoding="utf-8") == before

    code, stdout, stderr = _run(
        [
            "--store",
            str(store_path),
            "artifacts",
            "build",
            "--claim-id",
            claims[0]["id"],
            "--artifact-type",
            "resume_claims",
            "--audience",
            "public",
            "--created-at",
            NEXT,
        ]
    )

    assert code == 1
    assert stdout == ""
    assert "privacy is incompatible" in stderr
    assert store_path.read_text(encoding="utf-8") == before


def test_artifacts_do_not_accept_arbitrary_payload_args(tmp_path: Path) -> None:
    store = tmp_path / "graph.json"

    for command in ("accept", "reject"):
        args = [
            "--store",
            str(store),
            "artifacts",
            command,
            "--claim-id",
            "career_claim:1",
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
            "--created-at",
            NOW,
            "--actor",
            "human",
            "--decided-at",
            NEXT,
            "--draft-json",
            "{}",
        ]
        if command == "reject":
            args.extend(["--reason", "no"])
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(args)


def test_artifacts_accept_regenerates_delegates_persists_edges_and_audit(tmp_path: Path) -> None:
    store_path, claims = _artifact_ready_store(tmp_path / "graph.json")
    claim_ids = [claim["id"] for claim in claims]
    calls: list[str] = []

    class FakeWorkflow(CareerWorkflow):
        def build_claim_based_artifact(self, **kwargs: Any) -> dict[str, Any]:
            calls.append("build")
            return super().build_claim_based_artifact(**kwargs)

        def accept_claim_based_artifact(self, artifact: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            calls.append(artifact["id"])
            return super().accept_claim_based_artifact(artifact, **kwargs)

    stdout = io.StringIO()
    code = cli.run(
        [
            "--store",
            str(store_path),
            "artifacts",
            "accept",
            "--claim-id",
            claim_ids[0],
            "--claim-id",
            claim_ids[1],
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
            "--created-at",
            NEXT,
            "--actor",
            "human",
            "--decided-at",
            NEXT,
        ],
        stdout=stdout,
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )
    reloaded = JsonGraphStorage.load(store_path)
    artifact = reloaded.nodes_by_type("ProfessionalArtifact")[0]
    props = artifact["properties"]

    assert code == 0
    assert calls[0] == "build"
    assert calls[1].startswith("claim_based_artifact:")
    assert f"artifact_id: {artifact['id']}" in stdout.getvalue()
    assert props["source_type"] == "career_claim"
    assert props["status"] == "accepted"
    assert props["artifact_type"] == "resume_claims"
    assert props["audience"] == "internal"
    assert props["claim_refs"] == sorted(claim_ids)
    assert any(record["audit_type"] == "claim_based_artifact_accepted" for record in reloaded.audit_records)
    edge_types = {edge["edge_type"] for edge in reloaded.edges if edge["from_node_id"] == artifact["id"]}
    assert PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM in edge_types
    assert PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE in edge_types


def test_artifacts_accept_is_idempotent_according_to_domain(tmp_path: Path) -> None:
    store_path, claims = _artifact_ready_store(tmp_path / "graph.json")
    command = [
        "--store",
        str(store_path),
        "--json",
        "artifacts",
        "accept",
        "--claim-id",
        claims[0]["id"],
        "--artifact-type",
        "resume_claims",
        "--audience",
        "internal",
        "--created-at",
        NEXT,
        "--actor",
        "human",
        "--decided-at",
        NEXT,
    ]

    first = _run(command)
    second = _run(command)

    assert json.loads(first[1])["created"] is True
    assert json.loads(second[1])["created"] is False
    reloaded = JsonGraphStorage.load(store_path)
    assert len(reloaded.nodes_by_type("ProfessionalArtifact")) == 1
    audits = [record for record in reloaded.audit_records if record["audit_type"] == "claim_based_artifact_accepted"]
    assert [record["metadata"]["created"] for record in audits] == [True, False]


def test_artifacts_accept_inconsistent_result_and_old_audit_fail_before_save(tmp_path: Path) -> None:
    store_path, claims = _artifact_ready_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def accept_claim_based_artifact(self, artifact: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            return {"decision": "accepted", "source_artifact_id": artifact["id"], "artifact": {"id": "artifact:nope"}}

    args = [
        "--store",
        str(store_path),
        "artifacts",
        "accept",
        "--claim-id",
        claims[0]["id"],
        "--artifact-type",
        "resume_claims",
        "--audience",
        "internal",
        "--created-at",
        NEXT,
        "--actor",
        "human",
        "--decided-at",
        NEXT,
    ]
    code = cli.run(args, stdout=io.StringIO(), stderr=io.StringIO(), workflow_factory=FakeWorkflow)

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before

    workflow = CareerWorkflow(JsonGraphStorage.load(store_path))
    workflow.accept_claim_based_artifact(
        workflow.build_claim_based_artifact(
            claim_ids=[claims[0]["id"]],
            artifact_type="resume_claims",
            audience="internal",
            created_at=NEXT,
        ),
        decision_actor="old",
        decided_at=NOW,
    )
    workflow.store.save(store_path)
    before = store_path.read_text(encoding="utf-8")

    class OldAuditWorkflow(FakeWorkflow):
        def accept_claim_based_artifact(self, artifact: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            persisted = self.store.nodes_by_type("ProfessionalArtifact")[0]
            return {
                "decision": "accepted",
                "source_artifact_id": artifact["id"],
                "artifact": persisted,
                "created": False,
            }

    code = cli.run(args, stdout=io.StringIO(), stderr=io.StringIO(), workflow_factory=OldAuditWorkflow)

    assert code == 1
    assert store_path.read_text(encoding="utf-8") == before


def test_artifacts_reject_regenerates_delegates_audit_only_with_preexisting_artifact(tmp_path: Path) -> None:
    store_path, claims = _artifact_ready_store(tmp_path / "graph.json")
    workflow = CareerWorkflow(JsonGraphStorage.load(store_path))
    workflow.accept_claim_based_artifact(
        workflow.build_claim_based_artifact(
            claim_ids=[claims[0]["id"]],
            artifact_type="resume_claims",
            audience="internal",
            created_at=NEXT,
        ),
        decision_actor="first",
        decided_at=NOW,
    )
    workflow.store.save(store_path)
    before = JsonGraphStorage.load(store_path)
    calls: list[str] = []

    class FakeWorkflow(CareerWorkflow):
        def build_claim_based_artifact(self, **kwargs: Any) -> dict[str, Any]:
            calls.append("build")
            return super().build_claim_based_artifact(**kwargs)

        def reject_claim_based_artifact(self, artifact: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            calls.append(artifact["id"])
            return super().reject_claim_based_artifact(artifact, **kwargs)

    code = cli.run(
        [
            "--store",
            str(store_path),
            "artifacts",
            "reject",
            "--claim-id",
            claims[0]["id"],
            "--artifact-type",
            "resume_claims",
            "--audience",
            "internal",
            "--created-at",
            NEXT,
            "--actor",
            "human",
            "--decided-at",
            NEXT,
            "--reason",
            "not useful",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        workflow_factory=FakeWorkflow,
    )
    reloaded = JsonGraphStorage.load(store_path)

    assert code == 0
    assert calls[0] == "build"
    assert calls[1].startswith("claim_based_artifact:")
    assert reloaded.nodes == before.nodes
    assert reloaded.edges == before.edges
    assert [record["audit_type"] for record in reloaded.audit_records].count("claim_based_artifact_rejected") == 1


def test_artifacts_reject_detects_nested_mutation_and_old_audit_before_save(tmp_path: Path) -> None:
    store_path, claims = _artifact_ready_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")
    save_called = False

    class FakeStore(JsonGraphStorage):
        def save(self, path: Path) -> None:
            nonlocal save_called
            save_called = True
            super().save(path)

    class FakeWorkflow(CareerWorkflow):
        def __init__(self, store: JsonGraphStorage) -> None:
            super().__init__(FakeStore())
            self.store.nodes = store.nodes
            self.store.edges = store.edges
            self.store.audit_records = store.audit_records

        def reject_claim_based_artifact(self, artifact: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            claim_ref = artifact["traceability"]["claim_refs"][0]
            self.store.nodes[claim_ref]["properties"]["metadata"]["unexpected"] = "mutation"
            self.store.audit_records.append(
                {
                    "id": "audit:fake",
                    "audit_type": "claim_based_artifact_rejected",
                    "created_at": NEXT,
                    "actor": "human",
                    "target_refs": [artifact["id"]],
                    "result": "rejected",
                    "metadata": {
                        "source_artifact_id": artifact["id"],
                        "artifact_type": artifact["artifact_type"],
                        "audience": artifact["audience"],
                        "actor": "human",
                        "decided_at": NEXT,
                    },
                }
            )
            return {
                "source_artifact_id": artifact["id"],
                "artifact_type": artifact["artifact_type"],
                "audience": artifact["audience"],
                "decision": "rejected",
                "reason": "no",
            }

    args = [
        "--store",
        str(store_path),
        "artifacts",
        "reject",
        "--claim-id",
        claims[0]["id"],
        "--artifact-type",
        "resume_claims",
        "--audience",
        "internal",
        "--created-at",
        NEXT,
        "--actor",
        "human",
        "--decided-at",
        NEXT,
        "--reason",
        "no",
    ]
    code = cli.run(args, stdout=io.StringIO(), stderr=io.StringIO(), workflow_factory=FakeWorkflow)

    assert code == 1
    assert save_called is False
    assert store_path.read_text(encoding="utf-8") == before

    workflow = CareerWorkflow(JsonGraphStorage.load(store_path))
    draft = workflow.build_claim_based_artifact(
        claim_ids=[claims[0]["id"]],
        artifact_type="resume_claims",
        audience="internal",
        created_at=NEXT,
    )
    workflow.reject_claim_based_artifact(draft, decision_actor="old", decided_at=NOW, reason="old")
    workflow.store.save(store_path)
    before = store_path.read_text(encoding="utf-8")

    class OldAuditWorkflow(FakeWorkflow):
        def reject_claim_based_artifact(self, artifact: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            return {
                "source_artifact_id": artifact["id"],
                "artifact_type": artifact["artifact_type"],
                "audience": artifact["audience"],
                "decision": "rejected",
                "reason": "new",
            }

    code = cli.run(args, stdout=io.StringIO(), stderr=io.StringIO(), workflow_factory=OldAuditWorkflow)

    assert code == 1
    assert store_path.read_text(encoding="utf-8") == before


def test_artifacts_application_or_save_error_does_not_preserve_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_path, claims = _artifact_ready_store(tmp_path / "graph.json")
    before = store_path.read_text(encoding="utf-8")

    class FakeWorkflow(CareerWorkflow):
        def accept_claim_based_artifact(self, artifact: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            raise ValueError("application failed")

    command = [
        "--store",
        str(store_path),
        "artifacts",
        "accept",
        "--claim-id",
        claims[0]["id"],
        "--artifact-type",
        "resume_claims",
        "--audience",
        "internal",
        "--created-at",
        NEXT,
        "--actor",
        "human",
        "--decided-at",
        NEXT,
    ]
    code = cli.run(command, stdout=io.StringIO(), stderr=io.StringIO(), workflow_factory=FakeWorkflow)

    assert code == 1
    assert store_path.read_text(encoding="utf-8") == before

    def fail_save(self: JsonGraphStorage, path: Path) -> None:
        raise OSError("cannot save")

    monkeypatch.setattr(JsonGraphStorage, "save", fail_save)
    code, stdout, stderr = _run(command)

    assert code == 1
    assert stdout == ""
    assert "cannot save" in stderr


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
    store = _accepted_store(tmp_path / "exports")
    store_path = _write_store(tmp_path / "graph.json", store)
    before = store_path.read_text(encoding="utf-8")
    commands = [
        ["status"],
        ["contributions", "list"],
        ["contributions", "discover"],
        ["analyses", "generate", "--contribution-id", store.nodes_by_type("Contribution")[0]["id"]],
        ["analyses", "list"],
        [
            "claims",
            "generate",
            "--analysis-id",
            store.nodes_by_type("ContributionAnalysis")[0]["id"],
        ],
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
