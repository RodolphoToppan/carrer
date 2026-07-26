import csv
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("import_azure_cards_csv", ROOT / "scripts" / "import_azure_cards_csv.py")
import_azure_cards_csv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(import_azure_cards_csv)


class ImportAzureCardsCsvTest(unittest.TestCase):
    def test_converts_ui_csv_to_source_export(self):
        tmp = ROOT / "tmp" / "test_import_azure_cards_csv"
        tmp.mkdir(parents=True, exist_ok=True)
        input_path = tmp / "cards.csv"
        output_path = tmp / "export.json"
        with input_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "ID",
                    "Work Item Type",
                    "Title",
                    "Assigned To",
                    "State",
                    "Tags",
                    "Created Date",
                    "Target Date",
                    "Closed Date",
                    "Tempo gasto",
                    "Created By",
                    "Description",
                    "Discussion",
                    "Parent",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "ID": "1",
                    "Work Item Type": "Development",
                    "Title": "Fix Java retry",
                    "State": "Closed",
                    "Tags": "backend;RabbitMQ",
                    "Created Date": "2026-01-01T00:00:00Z",
                    "Description": "Root cause analysis",
                    "Discussion": "Chose smaller fix",
                    "Parent": "99",
                }
            )

        result = import_azure_cards_csv.convert(input_path, output_path)
        output = output_path.read_text(encoding="utf-8")

        self.assertEqual(result["records"], 1)
        self.assertIn("ADO-WI-1", output)
        self.assertIn("Root cause analysis", output)
        self.assertIn("ADO-WI-99", output)


if __name__ == "__main__":
    unittest.main()
