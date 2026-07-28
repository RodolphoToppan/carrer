import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from career_intelligence_mvp import GraphStore, warning_summary

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("career_pipeline", ROOT / "scripts" / "career_pipeline.py")
career_pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(career_pipeline)


class CareerPipelineTest(unittest.TestCase):
    def test_summarize_export_uses_canonical_file(self):
        tmp_export = ROOT / "tmp" / "test_export.json"
        tmp_export.parent.mkdir(parents=True, exist_ok=True)
        fixture_data = {
            "format": "source_export_v1",
            "records": [
                {"source_entity_type": "work_item", "title": "Test Item"},
                {"source_entity_type": "commit", "title": "Test Commit"},
                {"source_entity_type": "work_item", "title": "Another Item"},
            ],
        }
        tmp_export.write_text(json.dumps(fixture_data), encoding="utf-8")

        with patch.object(career_pipeline, "EXPORT_PATH", tmp_export):
            summary = career_pipeline.summarize_export()

        self.assertIn("records:", summary)
        self.assertIn("work_item", summary)

    def test_write_artifact_outputs_materializes_markdown_files(self):
        artifact = {
            "id": "artifact:test",
            "properties": {
                "artifact_type": "Skill Matrix",
                "rows": [],
            },
        }
        output_dir = ROOT / "tmp"
        artifact_path = output_dir / "skill_matrix_test.md"
        traceability_path = output_dir / "skill_matrix_traceability_test.md"
        if artifact_path.exists():
            artifact_path.unlink()
        if traceability_path.exists():
            traceability_path.unlink()

        written_artifact_path, written_traceability_path = career_pipeline.write_artifact_outputs(
            GraphStore(),
            artifact,
            artifact_path,
            traceability_path,
        )

        self.assertTrue(written_artifact_path.exists())
        self.assertTrue(written_traceability_path.exists())
        self.assertIn("# Skill Matrix", written_artifact_path.read_text(encoding="utf-8"))
        self.assertIn("# Skill Matrix Traceability", written_traceability_path.read_text(encoding="utf-8"))

    def test_write_validation_output_materializes_validation_file(self):
        artifact = {
            "id": "artifact:test",
            "properties": {"artifact_type": "Skill Matrix", "rows": []},
        }
        output_dir = ROOT / "tmp"
        validation_path = output_dir / "skill_matrix_validation_test.md"
        if validation_path.exists():
            validation_path.unlink()

        written_path = career_pipeline.write_validation_output(artifact, [], validation_path)

        self.assertTrue(written_path.exists())
        self.assertIn("# Skill Matrix Validation", written_path.read_text(encoding="utf-8"))

    def test_validation_warning_summary_includes_severity_counts(self):
        summary = warning_summary([{"code": "knowledge_not_accepted"}, {"code": "possible_unsupported_metric"}])

        self.assertEqual(summary, "2 (1 blocker, 1 review)")

    def test_ingest_job_descriptions_adds_job_evidence_to_store(self):
        tmp = ROOT / "tmp" / "test_career_pipeline_job_descriptions"
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / "backend.md").write_text("# Backend Engineer\nJava Spring Boot Kubernetes", encoding="utf-8")
        store = GraphStore()

        result = career_pipeline.ingest_job_descriptions(tmp, store)

        self.assertEqual(result["records"], 1)
        self.assertTrue(
            any(
                item["properties"]["evidence_type"] == "JOB_DESCRIPTION_EXISTS"
                for item in store.nodes_by_type("EvidenceNode")
            )
        )


if __name__ == "__main__":
    unittest.main()
