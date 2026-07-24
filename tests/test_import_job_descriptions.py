from pathlib import Path
import importlib.util
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("import_job_descriptions", ROOT / "scripts" / "import_job_descriptions.py")
import_job_descriptions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(import_job_descriptions)


class ImportJobDescriptionsTest(unittest.TestCase):
    def test_converts_text_files_to_source_export(self):
        tmp = ROOT / "tmp" / "test_import_job_descriptions"
        tmp.mkdir(parents=True, exist_ok=True)
        input_path = tmp / "backend-engineer.md"
        output_path = tmp / "export.json"
        input_path.write_text("# Backend Engineer\nJava Spring Boot RabbitMQ APIs", encoding="utf-8")

        result = import_job_descriptions.convert(tmp, output_path)
        export = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result["records"], 1)
        self.assertEqual(export["records"][0]["source_entity_type"], "job_description")
        self.assertEqual(export["records"][0]["payload"]["title"], "Backend Engineer")
        self.assertIn("Java", export["records"][0]["payload"]["technologies"])

    def test_rejects_empty_job_description_directory(self):
        tmp = ROOT / "tmp" / "test_empty_import_job_descriptions"
        tmp.mkdir(parents=True, exist_ok=True)

        with self.assertRaises(ValueError) as context:
            import_job_descriptions.convert(tmp, tmp / "export.json")

        self.assertIn("No .txt or .md job descriptions found", str(context.exception))

    def test_rejects_unsupported_single_file(self):
        tmp = ROOT / "tmp" / "test_unsupported_import_job_descriptions"
        tmp.mkdir(parents=True, exist_ok=True)
        input_path = tmp / "job.pdf"
        input_path.write_text("Java Spring Boot", encoding="utf-8")

        with self.assertRaises(ValueError) as context:
            import_job_descriptions.convert(input_path, tmp / "export.json")

        self.assertIn("No .txt or .md job descriptions found", str(context.exception))

    def test_rejects_blank_job_description_file(self):
        tmp = ROOT / "tmp" / "test_blank_import_job_descriptions"
        tmp.mkdir(parents=True, exist_ok=True)
        input_path = tmp / "blank.md"
        input_path.write_text("  \n\t", encoding="utf-8")

        with self.assertRaises(ValueError) as context:
            import_job_descriptions.convert(input_path, tmp / "export.json")

        self.assertIn("Empty job description", str(context.exception))


if __name__ == "__main__":
    unittest.main()
