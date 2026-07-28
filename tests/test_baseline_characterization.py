"""Characterization baseline for end-to-end behavior with synthetic source_export_v1."""

import unittest
from pathlib import Path

from career_intelligence_mvp import (
    GraphStore,
    artifact_traceability,
    generate_knowledge,
    generate_resume_draft,
    generate_skill_matrix,
    infer_observations,
    ingest_fixture,
    load_source_input,
    review_items,
    set_knowledge_privacy,
    stable_hash,
    validate_artifact,
)
from carrer.domain.privacy import most_restrictive

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "characterization_source_export.json"


def ingest_baseline() -> tuple[GraphStore, dict]:
    fixture = load_source_input(FIXTURE)
    store = GraphStore()
    result = ingest_fixture(fixture, store)
    return store, result


def build_with_knowledge(accept_knowledge: bool = True, artifact_safe: bool = False) -> GraphStore:
    store, _ = ingest_baseline()
    infer_observations(store)
    review_items(store, "approve", "ObservationNode", "baseline observation approval", "test")
    generate_knowledge(store)
    if accept_knowledge:
        review_items(store, "approve", "KnowledgeNode", "baseline knowledge approval", "test")
    if artifact_safe:
        for item in store.nodes_by_type("KnowledgeNode"):
            props = item["properties"]
            if props.get("status") == "accepted":
                set_knowledge_privacy(store, item["id"], "artifact_safe", "baseline export check", "test")
    return store


class IngestionCharacterizationTest(unittest.TestCase):
    def test_validation_and_normalization_of_source_export(self):
        fixture = load_source_input(FIXTURE)
        self.assertEqual(sorted(fixture.keys()), ["captured_at", "engineer", "records", "source"])
        self.assertGreaterEqual(len(fixture["records"]), 10)
        for record in fixture["records"]:
            self.assertEqual(
                sorted(record.keys()), ["external_id", "occurred_at", "payload", "privacy_level", "source", "type"]
            )

    def test_ingestion_supports_expected_record_types(self):
        store, _ = ingest_baseline()
        evidence_types = {node["properties"]["evidence_type"] for node in store.nodes_by_type("EvidenceNode")}
        self.assertTrue(
            {
                "WORK_ITEM_EXISTS",
                "COMMIT_EXISTS",
                "BRANCH_EXISTS",
                "MERGE_REQUEST_EXISTS",
                "REVIEW_COMMENT_CREATED",
                "DOCUMENTATION_EXISTS",
                "JOB_DESCRIPTION_EXISTS",
            }.issubset(evidence_types)
        )

    def test_identical_duplicate_record_is_deduplicated(self):
        _, result = ingest_baseline()
        self.assertEqual(result["records_created"], 11)
        self.assertEqual(result["records_reused"], 1)

    def test_updated_entity_capture_creates_distinct_evidence(self):
        store, _ = ingest_baseline()
        commit_nodes = [
            node
            for node in store.nodes_by_type("EvidenceNode")
            if node["properties"]["source_entity_id"] == "abc123def456"
        ]
        self.assertEqual(len(commit_nodes), 2)
        hashes = {node["properties"]["content_hash"] for node in commit_nodes}
        self.assertEqual(len(hashes), 2)

    def test_stable_hash_behavior_for_changed_payload(self):
        fixture = load_source_input(FIXTURE)
        commits = [record for record in fixture["records"] if record["external_id"] == "abc123def456"]
        self.assertEqual(len(commits), 2)
        self.assertNotEqual(stable_hash(commits[0]["payload"]), stable_hash(commits[1]["payload"]))


class GraphCharacterizationTest(unittest.TestCase):
    def test_graph_contains_core_nodes_and_relationships(self):
        store, _ = ingest_baseline()
        self.assertEqual(len(store.nodes_by_type("Engineer")), 1)
        self.assertGreaterEqual(len(store.nodes_by_type("Source")), 1)
        self.assertGreaterEqual(len(store.nodes_by_type("SourceIdentity")), 1)
        self.assertGreaterEqual(len(store.nodes_by_type("EvidenceNode")), 1)
        edge_types = {edge["edge_type"] for edge in store.edges}
        self.assertIn("ENGINEER_HAS_IDENTITY", edge_types)
        self.assertIn("EVIDENCE_DESCRIBES_ENTITY", edge_types)

    def test_pipeline_graph_has_no_broken_references(self):
        store, _ = ingest_baseline()
        node_ids = set(store.nodes.keys())
        for edge in store.edges:
            self.assertIn(edge["from_node_id"], node_ids)
            self.assertIn(edge["to_node_id"], node_ids)

    def test_graph_persistence_round_trip(self):
        store, _ = ingest_baseline()
        path = ROOT / "tmp" / "test_characterization_graph_reload.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            store.save(path)
            loaded = GraphStore.load(path)
            self.assertEqual(len(store.nodes), len(loaded.nodes))
            self.assertEqual(len(store.edges), len(loaded.edges))
            self.assertEqual(len(store.audit_records), len(loaded.audit_records))
        finally:
            if path.exists():
                path.unlink()

    def test_evidence_nodes_remain_immutable(self):
        store, _ = ingest_baseline()
        evidence = store.nodes_by_type("EvidenceNode")[0]
        with self.assertRaises(ValueError):
            store.update_node(evidence["id"], {"metadata": {"title": "changed"}})

    def test_created_edge_preserves_provided_node_references(self):
        store = GraphStore()
        store.create_node({"id": "node:1", "node_type": "Test", "created_at": "2024-01-01T00:00:00Z", "properties": {}})
        store.create_node({"id": "node:2", "node_type": "Test", "created_at": "2024-01-01T00:00:00Z", "properties": {}})
        store.create_edge("TEST_EDGE", "node:1", "node:2")
        edge = store.edges[0]
        self.assertEqual(edge["from_node_id"], "node:1")
        self.assertEqual(edge["to_node_id"], "node:2")


class PrivacyCharacterizationTest(unittest.TestCase):
    def test_privacy_levels_are_preserved_in_evidence(self):
        store, _ = ingest_baseline()
        levels = {node["properties"]["privacy_level"] for node in store.nodes_by_type("EvidenceNode")}
        self.assertIn("private", levels)
        self.assertIn("internal", levels)
        self.assertIn("artifact_safe", levels)

    def test_most_restrictive_rule_matches_current_contract(self):
        self.assertEqual(most_restrictive(["artifact_safe", "internal"]), "internal")
        self.assertEqual(most_restrictive(["private", "artifact_safe"]), "private")

    def test_mixed_evidence_uses_most_restrictive_privacy(self):
        store, _ = ingest_baseline()
        observations = infer_observations(store)
        python_obs = [
            obs for obs in observations if obs["properties"].get("metadata", {}).get("technology") == "Python"
        ]
        self.assertEqual(len(python_obs), 1)
        self.assertEqual(python_obs[0]["properties"]["privacy_level"], "private")

    def test_non_artifact_safe_knowledge_is_excluded_from_publishable_artifact(self):
        store = build_with_knowledge(accept_knowledge=True, artifact_safe=False)
        artifact = generate_skill_matrix(store)
        self.assertEqual(artifact["properties"]["rows"], [])


class InferenceCharacterizationTest(unittest.TestCase):
    def test_inference_detects_technology_and_domain_patterns(self):
        store, _ = ingest_baseline()
        observations = infer_observations(store)
        technologies = {
            obs["properties"].get("metadata", {}).get("technology")
            for obs in observations
            if obs["properties"]["observation_type"] == "TECHNOLOGY_USAGE_PATTERN"
        }
        domains = {
            obs["properties"].get("metadata", {}).get("domain")
            for obs in observations
            if obs["properties"]["observation_type"] == "DOMAIN_EXPERIENCE_PATTERN"
        }
        self.assertIn("Python", technologies)
        self.assertTrue(any("marketplace" in (domain or "").lower() for domain in domains))

    def test_contextual_metric_and_incidental_number_current_behavior(self):
        fixture = load_source_input(FIXTURE)
        descriptions = [record["payload"].get("description", "") for record in fixture["records"]]
        self.assertTrue(any("25M orders per quarter" in text for text in descriptions))
        self.assertTrue(any("order ID 12345" in record["payload"].get("message", "") for record in fixture["records"]))

        store = build_with_knowledge(accept_knowledge=True, artifact_safe=True)
        skill = generate_skill_matrix(store)
        statements = "\n".join(row["statement"] for row in skill["properties"]["rows"])
        self.assertNotIn("12345", statements)

    def test_impact_signal_observation_is_generated_when_supported(self):
        store, _ = ingest_baseline()
        observations = infer_observations(store)
        impact = [obs for obs in observations if obs["properties"]["observation_type"] == "IMPACT_SIGNAL_PATTERN"]
        self.assertGreaterEqual(len(impact), 1)


class ArtifactCharacterizationTest(unittest.TestCase):
    def test_skill_matrix_validation_and_traceability(self):
        store = build_with_knowledge(accept_knowledge=True, artifact_safe=True)
        artifact = generate_skill_matrix(store)

        self.assertGreaterEqual(len(artifact["properties"]["rows"]), 1)
        warnings = validate_artifact(artifact, store)
        blockers = [warning for warning in warnings if warning.get("severity") == "blocker"]
        self.assertEqual(blockers, [])

        trace = artifact_traceability(artifact, store)
        self.assertEqual(len(trace), len(artifact["properties"]["rows"]))
        public_text = "\n".join(row["statement"] for row in artifact["properties"]["rows"])
        self.assertNotIn("Phoenix", public_text)
        self.assertNotIn("Confidential Corp", public_text)
        self.assertNotIn("internal-api.company.local", public_text)

    def test_non_accepted_knowledge_is_not_used_in_artifact(self):
        store = build_with_knowledge(accept_knowledge=False, artifact_safe=False)
        artifact = generate_skill_matrix(store)
        self.assertEqual(artifact["properties"]["rows"], [])

    def test_resume_generator_returns_structured_artifact(self):
        store = build_with_knowledge(accept_knowledge=True, artifact_safe=True)
        artifact = generate_resume_draft(store)
        sections = artifact["properties"]["sections"]
        self.assertEqual(artifact["node_type"], "ProfessionalArtifact")
        self.assertIn("summary", sections)
        self.assertIn("highlights", sections)
        self.assertIsInstance(sections["summary"], str)
        self.assertIsInstance(sections["highlights"], list)


if __name__ == "__main__":
    unittest.main()
