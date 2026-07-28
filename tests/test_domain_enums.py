"""Tests for domain constants used as validation contracts."""

import unittest

from carrer.domain.enums import PRIVACY_LEVELS, SOURCE_ENTITY_TYPES


class PrivacyLevelsTest(unittest.TestCase):
    """Tests for PRIVACY_LEVELS constant"""

    def test_contains_expected_levels(self):
        """Privacy levels must include all expected values"""
        expected = {"private", "internal", "artifact_safe", "exported"}
        self.assertEqual(PRIVACY_LEVELS, expected)

    def test_is_immutable(self):
        """Privacy levels must be immutable (frozenset)"""
        self.assertIsInstance(PRIVACY_LEVELS, frozenset)


class SourceEntityTypesTest(unittest.TestCase):
    """Tests for SOURCE_ENTITY_TYPES constant"""

    def test_contains_expected_types(self):
        """Source entity types must include all expected values"""
        expected = {
            "work_item",
            "pull_request",
            "merge_request",
            "commit",
            "review_comment",
            "documentation",
            "job_description",
            "branch",
        }
        self.assertEqual(SOURCE_ENTITY_TYPES, expected)

    def test_is_immutable(self):
        """Source entity types must be immutable (frozenset)"""
        self.assertIsInstance(SOURCE_ENTITY_TYPES, frozenset)


if __name__ == "__main__":
    unittest.main()
