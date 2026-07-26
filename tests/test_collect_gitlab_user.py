import importlib.util
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("collect_gitlab_user", ROOT / "scripts" / "collect_gitlab_user.py")
collect_gitlab_user = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collect_gitlab_user)


class CollectGitLabUserTest(unittest.TestCase):
    def test_push_event_creates_commit_and_branch_records(self):
        records = collect_gitlab_user.push_records(
            {
                "project_id": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "push_data": {"commit_to": "abc123", "commit_title": "Fix retry flow", "ref": "feature/retry"},
            }
        )

        self.assertEqual([record["source_entity_type"] for record in records], ["commit", "branch"])
        self.assertEqual(records[0]["external_id"], "GL-COMMIT-1-abc123")

    def test_push_event_extracts_technologies_from_commit_title(self):
        records = collect_gitlab_user.push_records(
            {
                "project_id": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "push_data": {
                    "commit_to": "abc123",
                    "commit_title": "Fix Java RabbitMQ retry flow",
                    "ref": "feature/retry",
                },
            }
        )

        self.assertEqual(records[0]["payload"]["technologies"], ["Java", "RabbitMQ"])

    def test_merge_request_extracts_technologies_from_title(self):
        record = collect_gitlab_user.mr_record(
            {
                "id": 101,
                "project_id": 1,
                "title": "Add Spring Boot Docker support",
                "source_branch": "feature/docker",
                "target_branch": "main",
                "state": "merged",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        )

        self.assertEqual(record["payload"]["technologies"], ["Docker", "Spring Boot"])

    def test_missing_gitlab_env_fails_fast(self):
        with self.assertRaises(SystemExit) as context:
            collect_gitlab_user.require_env(
                {"GITLAB_API_URL": "https://gitlab.example/api/v4"}, "GITLAB_API_URL", "GITLAB_PERSONAL_ACCESS_TOKEN"
            )

        self.assertIn("GITLAB_PERSONAL_ACCESS_TOKEN", str(context.exception))

    def test_redact_sensitive_hides_tokens(self):
        text = collect_gitlab_user.redact_sensitive({"PRIVATE-TOKEN": "secret-token", "header": "Bearer abc123"})

        self.assertIn("<redacted>", text)
        self.assertNotIn("secret-token", text)
        self.assertNotIn("abc123", text)

    def test_gitlab_auth_error_is_clear(self):
        gitlab = collect_gitlab_user.GitLab(
            {"GITLAB_API_URL": "https://gitlab.example/api/v4", "GITLAB_PERSONAL_ACCESS_TOKEN": "secret-token"}
        )
        error = urllib.error.HTTPError("https://gitlab.example/api/v4/user", 401, "Unauthorized", {}, None)

        with patch("urllib.request.urlopen", side_effect=error), self.assertRaises(RuntimeError) as context:
            gitlab.get("/user")

        self.assertIn("GitLab authentication failed (401)", str(context.exception))
        self.assertNotIn("secret-token", str(context.exception))

    def test_missing_export_creates_gitlab_source_export(self):
        missing_path = ROOT / "tmp" / "missing_gitlab_export_base.json"
        if missing_path.exists():
            missing_path.unlink()

        export = collect_gitlab_user.load_or_create_export(
            missing_path, {"id": 7, "username": "rtoppan", "name": "Rodolpho"}
        )

        self.assertEqual(export["format"], "source_export_v1")
        self.assertEqual(export["source"]["type"], "gitlab_user_api")
        self.assertEqual(export["engineer"]["display_name"], "Rodolpho")
        self.assertEqual(export["records"], [])

    def test_write_export_creates_parent_directory(self):
        export_path = ROOT / "tmp" / "gitlab_write_export" / "career_source_export.json"
        if export_path.exists():
            export_path.unlink()

        export = collect_gitlab_user.new_export({"id": 7, "username": "rtoppan"})
        collect_gitlab_user.write_export(export_path, export)

        self.assertTrue(export_path.exists())
        self.assertEqual(collect_gitlab_user.load_or_create_export(export_path, {})["format"], "source_export_v1")

    def test_write_export_validates_source_export_contract(self):
        export_path = ROOT / "tmp" / "gitlab_invalid_export" / "career_source_export.json"

        with self.assertRaises(ValueError) as context:
            collect_gitlab_user.write_export(export_path, {"format": "source_export_v1", "records": []})

        self.assertIn("Invalid source_export_v1", str(context.exception))

    def test_merge_records_tags_new_records_with_source(self):
        export = collect_gitlab_user.new_export({"id": 7, "username": "rtoppan"})
        source = {"id": "gitlab-user-rtoppan", "type": "gitlab_user_api", "name": "GitLab", "visibility": "private"}
        records = collect_gitlab_user.push_records(
            {
                "project_id": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "push_data": {"commit_to": "abc123", "commit_title": "Fix Java", "ref": "main"},
            }
        )

        merged = collect_gitlab_user.merge_records(export, records, source)

        self.assertTrue(all(record["source"] == source for record in merged["records"]))

    def test_merge_records_returns_deterministic_order(self):
        export = collect_gitlab_user.new_export({"id": 7, "username": "rtoppan"})
        records = [
            {
                "source_entity_type": "merge_request",
                "external_id": "2",
                "occurred_at": "2026-01-01T00:00:00Z",
                "privacy_level": "internal",
                "payload": {},
            },
            {
                "source_entity_type": "commit",
                "external_id": "1",
                "occurred_at": "2026-01-01T00:00:00Z",
                "privacy_level": "internal",
                "payload": {},
            },
            {
                "source_entity_type": "merge_request",
                "external_id": "1",
                "occurred_at": "2026-01-01T00:00:00Z",
                "privacy_level": "internal",
                "payload": {},
            },
        ]

        merged = collect_gitlab_user.merge_records(export, records)

        self.assertEqual(
            [(record["source_entity_type"], record["external_id"]) for record in merged["records"]],
            [("commit", "1"), ("merge_request", "1"), ("merge_request", "2")],
        )

    def test_merge_records_validates_existing_export_contract(self):
        with self.assertRaises(ValueError) as context:
            collect_gitlab_user.merge_records({"format": "source_export_v1", "records": []}, [])

        self.assertIn("Invalid source_export_v1", str(context.exception))


if __name__ == "__main__":
    unittest.main()
