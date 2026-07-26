"""
Focused characterization tests for Carrer MVP baseline behavior.

These tests complement existing test_mvp_flow.py and test_career_pipeline.py
by adding targeted coverage for:
- Core stability guarantees (hashing, immutability)
- Determinism verification
- Key behavior protection before modularization

They do NOT fix business logic - they document current behavior.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import (
    GraphStore,
    stable_hash,
)


class CoreStabilityTest(unittest.TestCase):
    """Core stability tests for baseline protection"""

    def test_stable_hash_is_deterministic(self):
        """Stable hash must produce same output for same input"""
        data = {"key": "value", "list": [1, 2, 3], "nested": {"a": "b"}}

        hash1 = stable_hash(data)
        hash2 = stable_hash(data)

        self.assertEqual(hash1, hash2)
        self.assertIsInstance(hash1, str)
        self.assertGreater(len(hash1), 0)

    def test_stable_hash_is_key_order_independent(self):
        """Stable hash must ignore dict key ordering"""
        data1 = {"z": 1, "a": 2, "m": 3}
        data2 = {"a": 2, "m": 3, "z": 1}

        self.assertEqual(stable_hash(data1), stable_hash(data2))

    def test_stable_hash_detects_value_changes(self):
        """Stable hash must change when values change"""
        data1 = {"key": "value1"}
        data2 = {"key": "value2"}

        self.assertNotEqual(stable_hash(data1), stable_hash(data2))

    def test_evidence_node_immutability_is_enforced(self):
        """Evidence nodes must not be modifiable after creation"""
        store = GraphStore()
        evidence = {
            "id": "evidence:test-immutable",
            "node_type": "EvidenceNode",
            "created_at": "2024-01-01T00:00:00Z",
            "properties": {"evidence_type": "COMMIT_EXISTS", "metadata": {"message": "original"}},
        }
        store.create_node(evidence)

        with self.assertRaises(ValueError) as ctx:
            store.update_node("evidence:test-immutable", {"metadata": {"message": "modified"}})

        self.assertIn("immutable", str(ctx.exception).lower())

    def test_non_evidence_nodes_are_mutable(self):
        """Non-evidence nodes must remain mutable"""
        store = GraphStore()
        knowledge = {
            "id": "knowledge:test",
            "node_type": "TechnologyKnowledge",
            "created_at": "2024-01-01T00:00:00Z",
            "properties": {"technology": "Java", "statement": "original"},
        }
        store.create_node(knowledge)

        # Should not raise
        store.update_node("knowledge:test", {"statement": "updated"})

        updated = store.nodes["knowledge:test"]
        self.assertEqual(updated["properties"]["statement"], "updated")

    def test_graph_serialization_round_trip(self):
        """Graph save/load must preserve all data"""
        store1 = GraphStore()
        store1.create_node(
            {
                "id": "test:node1",
                "node_type": "TestNode",
                "created_at": "2024-01-01T00:00:00Z",
                "properties": {"data": "value"},
            }
        )
        store1.create_edge("TEST_EDGE", "test:node1", "test:node1", prop="value")

        tmp_path = ROOT / "tmp" / "test_serialization.json"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)

        store1.save(tmp_path)
        store2 = GraphStore.load(tmp_path)

        self.assertEqual(len(store1.nodes), len(store2.nodes))
        self.assertEqual(len(store1.edges), len(store2.edges))
        self.assertEqual(store1.nodes["test:node1"], store2.nodes["test:node1"])

        tmp_path.unlink()

    def test_edge_references_must_point_to_existing_nodes(self):
        """Edge validation: from/to nodes must exist"""
        store = GraphStore()

        # Create nodes
        store.create_node({"id": "node:1", "node_type": "Test", "created_at": "2024-01-01T00:00:00Z", "properties": {}})
        store.create_node({"id": "node:2", "node_type": "Test", "created_at": "2024-01-01T00:00:00Z", "properties": {}})

        # Create edge
        store.create_edge("TEST_EDGE", "node:1", "node:2")

        # Verify edge references valid nodes
        for edge in store.edges:
            self.assertIn(edge["from_node_id"], store.nodes)
            self.assertIn(edge["to_node_id"], store.nodes)


if __name__ == "__main__":
    unittest.main()
