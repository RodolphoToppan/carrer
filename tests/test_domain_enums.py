"""
Unit tests for domain enums and constants.

Tests that domain constants are properly defined and accessible.
"""

import unittest

from carrer.domain.enums import (
    EVIDENCE_TYPES,
    KNOWLEDGE_TYPES,
    NODE_TYPES,
    OBSERVATION_TYPES,
    PRIVACY_LEVELS,
    SOURCE_ENTITY_TYPES,
)


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


class NodeTypesTest(unittest.TestCase):
    """Tests for NODE_TYPES constant"""

    def test_contains_core_node_types(self):
        """Node types must include all core graph node types"""
        required = {
            "Engineer",
            "Source",
            "SourceIdentity",
            "EvidenceNode",
            "ObservationNode",
            "KnowledgeNode",
            "ProfessionalArtifact",
        }
        self.assertTrue(required.issubset(NODE_TYPES))

    def test_is_immutable(self):
        """Node types must be immutable (frozenset)"""
        self.assertIsInstance(NODE_TYPES, frozenset)


class EvidenceTypesTest(unittest.TestCase):
    """Tests for EVIDENCE_TYPES constant"""

    def test_contains_factual_evidence_types(self):
        """Evidence types must include factual evidence classifications"""
        expected_patterns = [
            "EXISTS",
            "CLOSED",
            "ASSIGNED",
            "AUTHORED",
            "MERGED",
            "APPROVED",
            "REVIEWED",
        ]

        for pattern in expected_patterns:
            self.assertTrue(
                any(pattern in evidence_type for evidence_type in EVIDENCE_TYPES),
                f"Expected evidence type pattern '{pattern}' not found",
            )

    def test_is_immutable(self):
        """Evidence types must be immutable (frozenset)"""
        self.assertIsInstance(EVIDENCE_TYPES, frozenset)


class KnowledgeTypesTest(unittest.TestCase):
    """Tests for KNOWLEDGE_TYPES constant"""

    def test_contains_knowledge_categories(self):
        """Knowledge types must include key knowledge categories"""
        expected = {
            "TechnologyKnowledge",
            "DomainKnowledge",
            "ImpactKnowledge",
        }
        self.assertTrue(expected.issubset(KNOWLEDGE_TYPES))

    def test_is_immutable(self):
        """Knowledge types must be immutable (frozenset)"""
        self.assertIsInstance(KNOWLEDGE_TYPES, frozenset)


class ObservationTypesTest(unittest.TestCase):
    """Tests for OBSERVATION_TYPES constant"""

    def test_contains_pattern_types(self):
        """Observation types must include pattern detection types"""
        expected = {
            "TECHNOLOGY_USAGE_PATTERN",
            "DOMAIN_EXPERIENCE_PATTERN",
            "DOCUMENTATION_PATTERN",
        }
        self.assertTrue(expected.issubset(OBSERVATION_TYPES))

    def test_is_immutable(self):
        """Observation types must be immutable (frozenset)"""
        self.assertIsInstance(OBSERVATION_TYPES, frozenset)


if __name__ == "__main__":
    unittest.main()
