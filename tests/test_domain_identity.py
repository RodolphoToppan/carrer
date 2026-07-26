"""
Unit tests for domain identity functions.

Tests deterministic hashing, timestamp generation, and privacy level merging.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from carrer.domain.hashing import most_restrictive, stable_hash
from carrer.domain.timestamps import now


class StableHashTest(unittest.TestCase):
    """Tests for stable_hash() determinism and behavior"""

    def test_deterministic_output(self):
        """Stable hash must produce same output for same input"""
        data = {"key": "value", "list": [1, 2, 3], "nested": {"a": "b"}}

        hash1 = stable_hash(data)
        hash2 = stable_hash(data)

        self.assertEqual(hash1, hash2)
        self.assertIsInstance(hash1, str)
        self.assertEqual(len(hash1), 64)  # SHA256 hex length

    def test_key_order_independence(self):
        """Stable hash must ignore dict key ordering"""
        data1 = {"z": 1, "a": 2, "m": 3}
        data2 = {"a": 2, "m": 3, "z": 1}

        self.assertEqual(stable_hash(data1), stable_hash(data2))

    def test_value_sensitivity(self):
        """Stable hash must change when values change"""
        data1 = {"key": "value1"}
        data2 = {"key": "value2"}

        self.assertNotEqual(stable_hash(data1), stable_hash(data2))

    def test_nested_structure_determinism(self):
        """Stable hash must handle deeply nested structures"""
        data = {
            "level1": {
                "level2": {
                    "level3": ["a", "b", "c"],
                },
            },
        }

        hash1 = stable_hash(data)
        hash2 = stable_hash(data)

        self.assertEqual(hash1, hash2)

    def test_list_order_sensitivity(self):
        """Stable hash must detect list order changes"""
        data1 = [1, 2, 3]
        data2 = [3, 2, 1]

        self.assertNotEqual(stable_hash(data1), stable_hash(data2))

    def test_empty_structures(self):
        """Stable hash must handle empty structures"""
        self.assertIsInstance(stable_hash({}), str)
        self.assertIsInstance(stable_hash([]), str)
        self.assertIsInstance(stable_hash(""), str)

    def test_primitive_types(self):
        """Stable hash must handle primitive types"""
        self.assertIsInstance(stable_hash("string"), str)
        self.assertIsInstance(stable_hash(42), str)
        self.assertIsInstance(stable_hash(3.14), str)
        self.assertIsInstance(stable_hash(True), str)
        self.assertIsInstance(stable_hash(None), str)


class MostRestrictiveTest(unittest.TestCase):
    """Tests for most_restrictive() privacy level merging"""

    def test_private_is_most_restrictive(self):
        """private should win over all other levels"""
        result = most_restrictive(["artifact_safe", "private", "internal"])
        self.assertEqual(result, "private")

    def test_internal_more_restrictive_than_artifact_safe(self):
        """internal should win over artifact_safe and exported"""
        result = most_restrictive(["exported", "artifact_safe", "internal"])
        self.assertEqual(result, "internal")

    def test_artifact_safe_more_restrictive_than_exported(self):
        """artifact_safe should win over exported"""
        result = most_restrictive(["exported", "artifact_safe"])
        self.assertEqual(result, "artifact_safe")

    def test_single_level_returns_itself(self):
        """Single level should return itself"""
        self.assertEqual(most_restrictive(["private"]), "private")
        self.assertEqual(most_restrictive(["internal"]), "internal")
        self.assertEqual(most_restrictive(["artifact_safe"]), "artifact_safe")
        self.assertEqual(most_restrictive(["exported"]), "exported")

    def test_invalid_level_raises(self):
        """Invalid privacy level should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            most_restrictive(["invalid", "private"])

        self.assertIn("invalid", str(ctx.exception).lower())


class TimestampTest(unittest.TestCase):
    """Tests for now() timestamp generation"""

    def test_returns_iso8601_format(self):
        """now() must return ISO8601 timestamp"""
        timestamp = now()

        self.assertIsInstance(timestamp, str)
        self.assertIn("T", timestamp)
        self.assertIn("+", timestamp)

    def test_contains_timezone(self):
        """Timestamp must include timezone information"""
        timestamp = now()

        # Should end with +00:00 or similar timezone
        self.assertTrue(timestamp.endswith("+00:00") or "+" in timestamp[-6:])

    def test_sequential_timestamps_increase(self):
        """Sequential calls must produce increasing timestamps"""
        timestamp1 = now()
        timestamp2 = now()

        # Timestamps should be ordered (string comparison works for ISO8601)
        self.assertGreaterEqual(timestamp2, timestamp1)


if __name__ == "__main__":
    unittest.main()
