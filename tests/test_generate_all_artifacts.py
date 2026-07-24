from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_all_artifacts import validation_summary_lines


class GenerateAllArtifactsTest(unittest.TestCase):
    def test_validation_summary_lines_include_counts_and_total(self):
        lines = validation_summary_lines(
            [
                ("Resume", [{"code": "knowledge_not_accepted"}, {"code": "possible_unsupported_metric"}]),
                ("LinkedIn", []),
                ("Gap Analysis", [{"code": "missing_evidence_refs"}]),
            ]
        )

        self.assertEqual(lines[0], "\n=== Validation ===")
        self.assertIn("Resume: 2 (1 blocker, 1 review) warnings", lines)
        self.assertIn("LinkedIn: 0 (0 blockers, 0 reviews) warnings", lines)
        self.assertIn("Gap Analysis: 1 (1 blocker, 0 reviews) warning", lines)
        self.assertEqual(lines[-1], "Total validation warnings: 3")


if __name__ == "__main__":
    unittest.main()
