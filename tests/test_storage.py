"""
Tests for graph storage abstraction and JSON implementation.

These tests verify storage isolation, format preservation, and contract compliance.
"""

import json
import unittest
from pathlib import Path

from carrer.storage import JsonGraphStorage

ROOT = Path(__file__).resolve().parents[1]


class JsonGraphStorageTest(unittest.TestCase):
    """Tests for JSON graph storage implementation"""

    def setUp(self):
        self.tmp_dir = ROOT / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def test_empty_storage_has_no_nodes_edges_or_audit_records(self):
        """New storage instance should be empty"""
        storage = JsonGraphStorage()

        self.assertEqual(len(storage.nodes), 0)
        self.assertEqual(len(storage.edges), 0)
        self.assertEqual(len(storage.audit_records), 0)

    def test_create_node_adds_new_node(self):
        """create_node should add node and return True"""
        storage = JsonGraphStorage()
        node = {
            "id": "test:1",
            "node_type": "TestNode",
            "created_at": "2024-01-01T00:00:00Z",
            "properties": {"data": "value"},
        }

        result, was_created = storage.create_node(node)

        self.assertTrue(was_created)
        self.assertEqual(result, node)
        self.assertIn("test:1", storage.nodes)

    def test_create_node_deduplicates_by_id(self):
        """create_node should return existing node if ID already exists"""
        storage = JsonGraphStorage()
        node1 = {
            "id": "test:1",
            "node_type": "TestNode",
            "created_at": "2024-01-01T00:00:00Z",
            "properties": {"data": "first"},
        }
        node2 = {
            "id": "test:1",
            "node_type": "TestNode",
            "created_at": "2024-01-01T00:00:00Z",
            "properties": {"data": "second"},
        }

        result1, was_created1 = storage.create_node(node1)
        result2, was_created2 = storage.create_node(node2)

        self.assertTrue(was_created1)
        self.assertFalse(was_created2)
        self.assertEqual(result2["properties"]["data"], "first")

    def test_update_node_modifies_properties(self):
        """update_node should merge properties into existing node"""
        storage = JsonGraphStorage()
        node = {
            "id": "knowledge:1",
            "node_type": "TechnologyKnowledge",
            "created_at": "2024-01-01T00:00:00Z",
            "properties": {"technology": "Java", "statement": "original"},
        }
        storage.create_node(node)

        storage.update_node("knowledge:1", {"statement": "updated"})

        updated = storage.nodes["knowledge:1"]
        self.assertEqual(updated["properties"]["statement"], "updated")
        self.assertEqual(updated["properties"]["technology"], "Java")

    def test_update_node_rejects_evidence_node_mutation(self):
        """update_node must raise ValueError when attempting to update EvidenceNode"""
        storage = JsonGraphStorage()
        evidence = {
            "id": "evidence:1",
            "node_type": "EvidenceNode",
            "created_at": "2024-01-01T00:00:00Z",
            "properties": {"evidence_type": "COMMIT_EXISTS"},
        }
        storage.create_node(evidence)

        with self.assertRaises(ValueError) as ctx:
            storage.update_node("evidence:1", {"evidence_type": "CHANGED"})

        self.assertIn("immutable", str(ctx.exception).lower())

    def test_create_edge_adds_edge_with_stable_hash_id(self):
        """create_edge should add edge with deterministic hash-based ID"""
        storage = JsonGraphStorage()

        storage.create_edge("TEST_EDGE", "node:1", "node:2", prop="value")

        self.assertEqual(len(storage.edges), 1)
        edge = storage.edges[0]
        self.assertEqual(edge["edge_type"], "TEST_EDGE")
        self.assertEqual(edge["from_node_id"], "node:1")
        self.assertEqual(edge["to_node_id"], "node:2")
        self.assertEqual(edge["properties"]["prop"], "value")
        self.assertTrue(edge["id"].startswith("edge:"))

    def test_create_edge_deduplicates_by_content_hash(self):
        """create_edge should deduplicate identical edges"""
        storage = JsonGraphStorage()

        storage.create_edge("TEST_EDGE", "node:1", "node:2", prop="value")
        storage.create_edge("TEST_EDGE", "node:1", "node:2", prop="value")

        self.assertEqual(len(storage.edges), 1)

    def test_nodes_by_type_filters_correctly(self):
        """nodes_by_type should return only nodes matching the type"""
        storage = JsonGraphStorage()
        storage.create_node(
            {"id": "evidence:1", "node_type": "EvidenceNode", "created_at": "2024-01-01T00:00:00Z", "properties": {}}
        )
        storage.create_node(
            {"id": "knowledge:1", "node_type": "KnowledgeNode", "created_at": "2024-01-01T00:00:00Z", "properties": {}}
        )
        storage.create_node(
            {"id": "evidence:2", "node_type": "EvidenceNode", "created_at": "2024-01-01T00:00:00Z", "properties": {}}
        )

        evidence_nodes = storage.nodes_by_type("EvidenceNode")
        knowledge_nodes = storage.nodes_by_type("KnowledgeNode")

        self.assertEqual(len(evidence_nodes), 2)
        self.assertEqual(len(knowledge_nodes), 1)

    def test_append_audit_record_creates_record_with_stable_id(self):
        """append_audit_record should create audit record with hash-based ID"""
        storage = JsonGraphStorage()

        storage.append_audit_record("NODE_REVIEWED", ["knowledge:1"], "approved", {"note": "test"})

        self.assertEqual(len(storage.audit_records), 1)
        record = storage.audit_records[0]
        self.assertEqual(record["audit_type"], "NODE_REVIEWED")
        self.assertEqual(record["result"], "approved")
        self.assertEqual(record["target_refs"], ["knowledge:1"])
        self.assertEqual(record["actor"], "system")
        self.assertTrue(record["id"].startswith("audit:"))

    def test_save_creates_json_with_sorted_keys(self):
        """save should write JSON with sorted keys and 2-space indent"""
        storage = JsonGraphStorage()
        storage.create_node(
            {"id": "test:1", "node_type": "TestNode", "created_at": "2024-01-01T00:00:00Z", "properties": {}}
        )

        path = self.tmp_dir / "test_save.json"
        storage.save(path)

        # Verify file exists and is valid JSON
        self.assertTrue(path.exists())
        data = json.loads(path.read_text(encoding="utf-8"))

        # Verify structure
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertIn("audit_records", data)

        # Verify keys are sorted by checking raw text
        raw = path.read_text(encoding="utf-8")
        audit_idx = raw.index('"audit_records"')
        edges_idx = raw.index('"edges"')
        nodes_idx = raw.index('"nodes"')
        self.assertLess(audit_idx, edges_idx)
        self.assertLess(edges_idx, nodes_idx)

        path.unlink()

    def test_load_reads_json_preserving_structure(self):
        """load should read JSON and restore nodes, edges, and audit_records"""
        # Create test file
        path = self.tmp_dir / "test_load.json"
        data = {
            "nodes": {
                "test:1": {
                    "id": "test:1",
                    "node_type": "TestNode",
                    "created_at": "2024-01-01T00:00:00Z",
                    "properties": {"data": "value"},
                }
            },
            "edges": [
                {
                    "id": "edge:abc123",
                    "edge_type": "TEST_EDGE",
                    "from_node_id": "test:1",
                    "to_node_id": "test:2",
                    "created_at": "2024-01-01T00:00:00Z",
                    "properties": {},
                }
            ],
            "audit_records": [
                {
                    "id": "audit:xyz789",
                    "audit_type": "TEST_AUDIT",
                    "created_at": "2024-01-01T00:00:00Z",
                    "actor": "system",
                    "target_refs": ["test:1"],
                    "result": "success",
                    "metadata": {},
                }
            ],
        }
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

        storage = JsonGraphStorage.load(path)

        self.assertEqual(len(storage.nodes), 1)
        self.assertEqual(len(storage.edges), 1)
        self.assertEqual(len(storage.audit_records), 1)
        self.assertIn("test:1", storage.nodes)

        path.unlink()

    def test_save_load_round_trip_preserves_all_data(self):
        """save then load should preserve all data exactly"""
        storage1 = JsonGraphStorage()
        storage1.create_node(
            {"id": "test:1", "node_type": "TestNode", "created_at": "2024-01-01T00:00:00Z", "properties": {"x": 1}}
        )
        storage1.create_edge("TEST_EDGE", "test:1", "test:2", key="value")
        storage1.append_audit_record("TEST_AUDIT", ["test:1"], "success", {"note": "done"})

        path = self.tmp_dir / "test_round_trip.json"
        storage1.save(path)
        storage2 = JsonGraphStorage.load(path)

        self.assertEqual(storage1.nodes, storage2.nodes)
        self.assertEqual(storage1.edges, storage2.edges)
        self.assertEqual(storage1.audit_records, storage2.audit_records)

        path.unlink()


if __name__ == "__main__":
    unittest.main()
