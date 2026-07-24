import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import (
    artifact_markdown,
    artifact_validation_markdown,
    career_timeline_markdown,
    cluster_technology_knowledge,
    cover_letter_markdown,
    extract_context_signals,
    GraphStore,
    artifact_traceability,
    artifact_traceability_markdown,
    generate_career_timeline_draft,
    generate_cover_letter_draft,
    generate_gap_analysis_draft,
    generate_knowledge,
    generate_interview_answers_draft,
    job_requirement_matches,
    generate_linkedin_draft,
    generate_resume_draft,
    generate_skill_matrix,
    generate_star_stories_draft,
    gap_analysis_markdown,
    infer_observations,
    ingest_fixture,
    interview_answers_markdown,
    linkedin_markdown,
    load_fixture,
    load_source_input,
    review_node,
    review_items,
    reviewable_items,
    run_pipeline,
    resume_markdown,
    set_knowledge_privacy,
    star_stories_markdown,
    validate_artifact,
    validate_source_export_v1,
)


def approve_all_proposed(store: GraphStore):
    for item in reviewable_items(store):
        review_node(store, item["id"], "approve", "test approval")
    generate_knowledge(store)
    for item in reviewable_items(store):
        review_node(store, item["id"], "approve", "test approval")
    return generate_skill_matrix(store)


def write_tmp_json(name: str, payload: dict) -> Path:
    path = ROOT / "tmp" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class MvpFlowTest(unittest.TestCase):
    def test_ingestion_deduplicates_evidence(self):
        store = GraphStore()
        fixture = load_fixture(ROOT / "examples" / "mvp_fixture.json")

        result = ingest_fixture(fixture, store)

        self.assertEqual(result["records_created"], 6)
        self.assertEqual(result["records_reused"], 1)

    def test_ingestion_links_related_work_item_evidence(self):
        store = GraphStore()
        fixture = {
            "captured_at": "2026-01-01T00:00:00Z",
            "engineer": {"id": "engineer-1", "display_name": "Rodolpho", "primary_email_hash": "hash"},
            "source": {"id": "azure", "type": "azure_devops_export", "name": "Azure", "visibility": "private"},
            "records": [
                {
                    "type": "work_item",
                    "external_id": "ADO-WI-1",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "privacy_level": "internal",
                    "payload": {"title": "Child card", "relationships": [{"type": "System.LinkTypes.Hierarchy-Reverse", "external_id": "ADO-WI-2"}]},
                },
                {
                    "type": "work_item",
                    "external_id": "ADO-WI-2",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "privacy_level": "internal",
                    "payload": {"title": "Parent feature"},
                },
            ],
        }

        ingest_fixture(fixture, store)

        edges = [edge for edge in store.edges if edge["edge_type"] == "EVIDENCE_RELATED_TO_EVIDENCE"]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["properties"]["source_relation_type"], "System.LinkTypes.Hierarchy-Reverse")

    def test_evidence_is_immutable(self):
        store = GraphStore()
        fixture = load_fixture(ROOT / "examples" / "mvp_fixture.json")
        ingest_fixture(fixture, store)
        evidence_id = store.nodes_by_type("EvidenceNode")[0]["id"]

        with self.assertRaises(ValueError):
            store.update_node(evidence_id, {"statement": "changed"})

    def test_pipeline_generates_traceable_artifact_safe_skill_matrix(self):
        store, artifact = run_pipeline(ROOT / "examples" / "mvp_fixture.json")

        self.assertEqual(artifact["properties"]["rows"], [])
        artifact = approve_all_proposed(store)
        rows = artifact["properties"]["rows"]

        self.assertGreaterEqual(len(rows), 4)
        self.assertTrue(all(row["evidence_refs"] for row in rows))
        self.assertTrue(all(row["evidence_context"]["evidence_count"] == len(row["evidence_refs"]) for row in rows))
        self.assertFalse(any("InternalToolX" in row["statement"] for row in rows))
        self.assertIn("records;", artifact_markdown(artifact))

        knowledge_ids = {row["knowledge_id"] for row in rows}
        artifact_edges = [
            edge for edge in store.edges
            if edge["edge_type"] == "ARTIFACT_GENERATED_FROM_KNOWLEDGE"
        ]
        self.assertTrue(knowledge_ids.issubset({edge["to_node_id"] for edge in artifact_edges}))

    def test_graph_store_persists_pipeline_output(self):
        path = ROOT / "tmp" / "test_mvp_graph.json"
        if path.exists():
            path.unlink()

        store, artifact = run_pipeline(ROOT / "examples" / "mvp_fixture.json", path)
        loaded = GraphStore.load(path)

        self.assertEqual(loaded.nodes[artifact["id"]], artifact)
        self.assertEqual(len(loaded.nodes), len(store.nodes))
        self.assertEqual(len(loaded.edges), len(store.edges))
        self.assertEqual(len(loaded.audit_records), len(store.audit_records))

        run_pipeline(ROOT / "examples" / "mvp_fixture.json", path)
        reloaded = GraphStore.load(path)

        self.assertEqual(len(reloaded.nodes_by_type("EvidenceNode")), 6)

    def test_source_export_v1_normalizes_azure_devops_records(self):
        fixture = load_source_input(ROOT / "examples" / "azure_devops_export_sample.json")
        self.assertEqual(fixture["source"]["type"], "azure_devops_export")
        self.assertEqual(fixture["records"][0]["type"], "work_item")

        store, artifact = run_pipeline(ROOT / "examples" / "azure_devops_export_sample.json")
        artifact = approve_all_proposed(store)
        evidence_types = {item["properties"]["evidence_type"] for item in store.nodes_by_type("EvidenceNode")}
        rows = artifact["properties"]["rows"]

        self.assertIn("MERGE_REQUEST_EXISTS", evidence_types)
        self.assertIn("REVIEW_COMMENT_CREATED", evidence_types)
        # Check for enriched domain (marketplace integrations -> E-commerce Marketplace Integration)
        self.assertTrue(any("Marketplace Integration" in row["statement"] for row in rows))
        self.assertFalse(any("InternalToolX" in row["statement"] for row in rows))

    def test_source_export_v1_preserves_record_level_source(self):
        export = {
            "format": "source_export_v1",
            "captured_at": "2026-01-01T00:00:00Z",
            "engineer": {"id": "engineer-1", "display_name": "Rodolpho", "primary_email_hash": "hash"},
            "source": {"id": "azure", "type": "azure_devops_export", "name": "Azure", "visibility": "private"},
            "records": [
                {
                    "source_entity_type": "commit",
                    "external_id": "GL-COMMIT-1",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "privacy_level": "internal",
                    "source": {"id": "gitlab", "type": "gitlab_user_api", "name": "GitLab", "visibility": "private"},
                    "payload": {"message": "Fix Java task", "technologies": ["Java"]},
                }
            ],
        }
        normalized = load_source_input(write_tmp_json("mixed_source_export.json", export))
        store = GraphStore()

        ingest_fixture(normalized, store)

        evidence = store.nodes_by_type("EvidenceNode")[0]
        self.assertEqual(evidence["properties"]["source_id"], "gitlab")
        self.assertTrue(store.nodes.get("source:gitlab"))

    def test_source_export_v1_validation_rejects_missing_required_fields(self):
        with self.assertRaises(ValueError) as context:
            validate_source_export_v1(
                {
                    "format": "source_export_v1",
                    "captured_at": "2026-01-01T00:00:00Z",
                    "engineer": {"id": "engineer-1"},
                    "source": {"id": "source-1"},
                    "records": [{"source_entity_type": "work_item", "payload": {}}],
                }
            )
        message = str(context.exception)
        self.assertIn("missing engineer field: display_name", message)
        self.assertIn("missing source field: type", message)
        self.assertIn("records[0] missing field: external_id", message)

    def test_source_export_v1_validation_rejects_unsupported_record_values(self):
        with self.assertRaises(ValueError) as context:
            validate_source_export_v1(
                {
                    "format": "source_export_v1",
                    "captured_at": "2026-01-01T00:00:00Z",
                    "engineer": {"id": "engineer-1", "display_name": "Rodolpho", "primary_email_hash": "hash"},
                    "source": {"id": "source-1", "type": "azure_devops_export", "name": "Azure", "visibility": "private"},
                    "records": [
                        {
                            "source_entity_type": "unknown",
                            "external_id": "X-1",
                            "occurred_at": "2026-01-01T00:00:00Z",
                            "privacy_level": "top_secret",
                            "payload": {},
                        }
                    ],
                }
            )
        message = str(context.exception)
        self.assertIn("unsupported source_entity_type", message)
        self.assertIn("unsupported privacy_level", message)

    def test_source_export_v1_allows_legacy_type_field(self):
        export_path = ROOT / "tmp" / "legacy_source_export_test.json"
        fixture = {
            "format": "source_export_v1",
            "captured_at": "2026-01-01T00:00:00Z",
            "engineer": {"id": "engineer-1", "display_name": "Rodolpho", "primary_email_hash": "hash"},
            "source": {"id": "source-1", "type": "azure_devops_export", "name": "Azure", "visibility": "private"},
            "records": [
                {
                    "type": "work_item",
                    "external_id": "X-1",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "privacy_level": "internal",
                    "payload": {"title": "Legacy record"},
                }
            ],
        }
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(fixture), encoding="utf-8")
        try:
            normalized = load_source_input(export_path)
            self.assertEqual(normalized["records"][0]["type"], "work_item")
        finally:
            if export_path.exists():
                export_path.unlink()

    def test_source_export_v1_normalization_infers_technologies_when_missing(self):
        export_path = ROOT / "tmp" / "normalized_source_export_test.json"
        fixture = {
            "format": "source_export_v1",
            "captured_at": "2026-01-01T00:00:00Z",
            "engineer": {"id": "engineer-1", "display_name": "Rodolpho", "primary_email_hash": "hash"},
            "source": {"id": "source-1", "type": "gitlab_export", "name": "GitLab", "visibility": "private"},
            "records": [
                {
                    "source_entity_type": "commit",
                    "external_id": "GL-COMMIT-1",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "privacy_level": "internal",
                    "payload": {"message": "Fix Java RabbitMQ retry flow in backend"},
                },
                {
                    "source_entity_type": "commit",
                    "external_id": "GL-COMMIT-2",
                    "occurred_at": "2026-01-02T00:00:00Z",
                    "privacy_level": "internal",
                    "payload": {"message": "Improve Java queue handling with RabbitMQ"},
                },
            ],
        }
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(fixture), encoding="utf-8")
        try:
            normalized = load_source_input(export_path)
            self.assertEqual(normalized["records"][0]["payload"]["technologies"], ["Java", "RabbitMQ"])
            self.assertEqual(normalized["records"][0]["payload"]["domain"], "code delivery")

            store, _ = run_pipeline(export_path)
            for item in reviewable_items(store, node_type="ObservationNode"):
                review_node(store, item["id"], "approve", "supported")
            generate_knowledge(store)
            for item in reviewable_items(store, node_type="KnowledgeNode"):
                review_node(store, item["id"], "approve", "approved")
            for item in store.nodes_by_type("KnowledgeNode"):
                if item["properties"].get("status") == "accepted":
                    set_knowledge_privacy(store, item["id"], "artifact_safe", "safe for artifact")
            artifact = generate_skill_matrix(store)

            # Check for enriched statement (includes evidence count now)
            self.assertTrue(any("Practical experience with Java" in row["statement"] for row in artifact["properties"]["rows"]))
        finally:
            if export_path.exists():
                export_path.unlink()

    def test_job_descriptions_do_not_create_experience_observations(self):
        fixture = {
            "format": "source_export_v1",
            "captured_at": "2026-01-01T00:00:00Z",
            "engineer": {"id": "engineer-1", "display_name": "Rodolpho", "primary_email_hash": "hash"},
            "source": {"id": "job-descriptions-local", "type": "job_descriptions", "name": "Job Descriptions", "visibility": "artifact_safe"},
            "records": [
                {
                    "source_entity_type": "job_description",
                    "external_id": "JD-1",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "privacy_level": "artifact_safe",
                    "payload": {"title": "Backend Engineer", "description": "Java Spring Boot RabbitMQ"},
                },
                {
                    "source_entity_type": "job_description",
                    "external_id": "JD-2",
                    "occurred_at": "2026-01-02T00:00:00Z",
                    "privacy_level": "artifact_safe",
                    "payload": {"title": "Software Engineer", "description": "Java APIs Redis"},
                },
            ],
        }
        store = GraphStore()
        ingest_fixture(load_source_input(write_tmp_json("job_descriptions_export_test.json", fixture)), store)

        observations = infer_observations(store)

        self.assertEqual(observations, [])

    def test_review_decision_controls_knowledge_and_artifacts(self):
        store, artifact = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        proposed_observation = reviewable_items(store)[0]

        self.assertEqual(artifact["properties"]["rows"], [])
        review_node(store, proposed_observation["id"], "approve", "supported by evidence")
        knowledge = generate_knowledge(store)
        self.assertTrue(knowledge)
        self.assertTrue(all(item["properties"]["status"] == "proposed" for item in knowledge))

        artifact = generate_skill_matrix(store)
        self.assertEqual(artifact["properties"]["rows"], [])
        review_node(store, knowledge[0]["id"], "approve", "approved for artifact")
        artifact = generate_skill_matrix(store)

        self.assertEqual(len(artifact["properties"]["rows"]), 1)
        self.assertTrue(any(record["audit_type"] == "review_decision" for record in store.audit_records))

    def test_rejected_observation_does_not_create_knowledge(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        proposed_observation = reviewable_items(store)[0]

        review_node(store, proposed_observation["id"], "reject", "not accurate")
        knowledge = generate_knowledge(store)

        self.assertFalse(any(proposed_observation["id"] in item["properties"]["observation_refs"] for item in knowledge))

    def test_artifact_traceability_explains_each_claim(self):
        store, _ = run_pipeline(ROOT / "examples" / "azure_devops_export_sample.json")
        artifact = approve_all_proposed(store)

        traces = artifact_traceability(artifact, store)
        markdown = artifact_traceability_markdown(artifact, store)

        self.assertEqual(len(traces), len(artifact["properties"]["rows"]))
        self.assertTrue(all(trace["knowledge"]["id"] for trace in traces))
        self.assertTrue(all(trace["observations"] for trace in traces))
        self.assertTrue(all(trace["evidence"] for trace in traces))
        self.assertIn("Knowledge:", markdown)
        self.assertIn("Observation:", markdown)
        self.assertIn("ADO-WI-1001", markdown)

    def test_batch_review_approves_items_by_type(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")

        observation_reviews = review_items(store, "approve", "ObservationNode", "batch observation approval")
        knowledge = generate_knowledge(store)
        knowledge_reviews = review_items(store, "approve", "KnowledgeNode", "batch knowledge approval")
        artifact = generate_skill_matrix(store)

        self.assertEqual(len(observation_reviews), 7)
        self.assertEqual(len(knowledge_reviews), len(knowledge))
        self.assertGreaterEqual(len(artifact["properties"]["rows"]), 4)

    def test_knowledge_privacy_review_can_unlock_artifact_rows(self):
        fixture = {
            "captured_at": "2026-01-01T00:00:00Z",
            "engineer": {"id": "engineer-1", "display_name": "Rodolpho", "primary_email_hash": "hash"},
            "source": {"id": "azure", "type": "azure_devops_export", "name": "Azure", "visibility": "private"},
            "records": [
                {
                    "type": "work_item",
                    "external_id": "ADO-WI-1",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "privacy_level": "internal",
                    "payload": {"title": "Java integration card", "domain": "integration", "technologies": ["Java"]},
                },
                {
                    "type": "work_item",
                    "external_id": "ADO-WI-2",
                    "occurred_at": "2026-01-02T00:00:00Z",
                    "privacy_level": "internal",
                    "payload": {"title": "Java retry card", "domain": "integration", "technologies": ["Java"]},
                },
            ],
        }
        store = GraphStore()
        ingest_fixture(fixture, store)
        infer_observations(store)

        for item in reviewable_items(store, node_type="ObservationNode"):
            review_node(store, item["id"], "approve", "supported")
        generate_knowledge(store)
        for item in reviewable_items(store, node_type="KnowledgeNode"):
            review_node(store, item["id"], "approve", "approved")

        artifact = generate_skill_matrix(store)
        self.assertEqual(artifact["properties"]["rows"], [])

        knowledge_id = store.nodes_by_type("KnowledgeNode")[0]["id"]
        set_knowledge_privacy(store, knowledge_id, "artifact_safe", "safe after review")
        generate_knowledge(store)
        artifact = generate_skill_matrix(store)

        self.assertEqual(store.nodes[knowledge_id]["properties"]["privacy_level"], "artifact_safe")
        self.assertTrue(any(row["knowledge_id"] == knowledge_id for row in artifact["properties"]["rows"]))
        self.assertTrue(any(record["audit_type"] == "privacy_review_decision" for record in store.audit_records))

    def test_resume_draft_is_generated_from_accepted_artifact_safe_knowledge(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        resume = generate_resume_draft(store)

        highlights = resume["properties"]["sections"]["highlights"]
        self.assertTrue(highlights)
        self.assertEqual(resume["properties"]["artifact_type"], "Resume")
        self.assertTrue(all(item["support_strength"] in {"strong", "moderate", "weak"} for item in highlights))
        self.assertTrue(all(item["evidence_context"]["evidence_count"] == len(item["evidence_refs"]) for item in highlights))
        highlight_order = [(item["support_strength"], item["evidence_context"]["evidence_count"]) for item in highlights]
        expected_order = sorted(highlight_order, key=lambda item: ({"strong": 0, "moderate": 1, "weak": 2}[item[0]], -item[1]))
        self.assertEqual(highlight_order, expected_order)
        self.assertFalse(any("InternalToolX" in item["statement"] for item in highlights))

        traces = artifact_traceability(resume, store)
        self.assertEqual(len(traces), len(highlights))
        markdown = resume_markdown(resume)
        self.assertIn("# Resume Draft", markdown)
        self.assertIn("records;", markdown)

    def test_linkedin_draft_is_generated_from_accepted_artifact_safe_knowledge(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        linkedin = generate_linkedin_draft(store)

        highlights = linkedin["properties"]["sections"]["highlights"]
        self.assertTrue(highlights)
        self.assertEqual(linkedin["properties"]["artifact_type"], "LinkedIn")
        self.assertIn("headline", linkedin["properties"]["sections"])
        self.assertIn("about", linkedin["properties"]["sections"])
        self.assertTrue(all(item["evidence_context"]["evidence_count"] == len(item["evidence_refs"]) for item in highlights))
        highlight_order = [(item["support_strength"], item["evidence_context"]["evidence_count"]) for item in highlights]
        expected_order = sorted(highlight_order, key=lambda item: ({"strong": 0, "moderate": 1, "weak": 2}[item[0]], -item[1]))
        self.assertEqual(highlight_order, expected_order)
        self.assertFalse(any("InternalToolX" in item["statement"] for item in highlights))

        traces = artifact_traceability(linkedin, store)
        self.assertEqual(len(traces), len(highlights))
        markdown = linkedin_markdown(linkedin)
        self.assertIn("# LinkedIn Draft", markdown)
        self.assertIn("records;", markdown)

    def test_star_stories_are_generated_from_accepted_artifact_safe_knowledge(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        artifact = generate_star_stories_draft(store)

        stories = artifact["properties"]["sections"]["stories"]
        self.assertTrue(stories)
        self.assertEqual(artifact["properties"]["artifact_type"], "STAR Stories")
        self.assertTrue(all(story["knowledge_id"] for story in stories))
        self.assertTrue(all(story["evidence_refs"] for story in stories))
        self.assertTrue(all(story["evidence_context"]["evidence_count"] == len(story["evidence_refs"]) for story in stories))
        story_order = [(story["support_strength"], story["evidence_context"]["evidence_count"]) for story in stories]
        expected_order = sorted(story_order, key=lambda item: ({"strong": 0, "moderate": 1, "weak": 2}[item[0]], -item[1]))
        self.assertEqual(story_order, expected_order)
        self.assertTrue(all(story["review_notes"] for story in stories))
        self.assertTrue(all("unsupported metric" in story["result"] for story in stories))
        self.assertFalse(any("InternalToolX" in story["action"] for story in stories))
        self.assertEqual(validate_artifact(artifact, store), [])
        self.assertEqual(len(artifact_traceability(artifact, store)), len(stories))
        markdown = star_stories_markdown(artifact)
        self.assertIn("# STAR Stories Draft", markdown)
        self.assertIn("- Evidence:", markdown)
        self.assertIn("- Review note:", markdown)
        self.assertNotIn("T09:00:00", markdown)

    def test_interview_answers_are_generated_from_accepted_artifact_safe_knowledge(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        artifact = generate_interview_answers_draft(store)

        answers = artifact["properties"]["sections"]["answers"]
        self.assertTrue(answers)
        self.assertEqual(artifact["properties"]["artifact_type"], "Interview Answers")
        self.assertTrue(all(answer["knowledge_id"] for answer in answers))
        self.assertTrue(all(answer["evidence_refs"] for answer in answers))
        self.assertTrue(all(answer["evidence_context"]["evidence_count"] == len(answer["evidence_refs"]) for answer in answers))
        answer_order = [(answer["support_strength"], answer["evidence_context"]["evidence_count"]) for answer in answers]
        expected_order = sorted(answer_order, key=lambda item: ({"strong": 0, "moderate": 1, "weak": 2}[item[0]], -item[1]))
        self.assertEqual(answer_order, expected_order)
        self.assertTrue(all(answer["review_notes"] for answer in answers))
        self.assertTrue(all("specific metrics" in answer["answer"] for answer in answers))
        self.assertFalse(any("InternalToolX" in answer["answer"] for answer in answers))
        self.assertEqual(validate_artifact(artifact, store), [])
        self.assertEqual(len(artifact_traceability(artifact, store)), len(answers))
        markdown = interview_answers_markdown(artifact)
        self.assertIn("# Interview Answers Draft", markdown)
        self.assertIn("- Evidence:", markdown)
        self.assertIn("- Review note:", markdown)
        self.assertNotIn("T09:00:00", markdown)

    def test_cover_letter_is_generated_from_accepted_artifact_safe_knowledge(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        artifact = generate_cover_letter_draft(store)

        claims = artifact["properties"]["sections"]["claims"]
        markdown = cover_letter_markdown(artifact)
        self.assertTrue(claims)
        self.assertLessEqual(len(claims), 5)
        self.assertEqual(artifact["properties"]["artifact_type"], "Cover Letter")
        self.assertTrue(all(claim["knowledge_id"] for claim in claims))
        self.assertTrue(all(claim["evidence_refs"] for claim in claims))
        self.assertTrue(all(claim["evidence_context"]["evidence_count"] == len(claim["evidence_refs"]) for claim in claims))
        claim_order = [(claim["support_strength"], claim["evidence_context"]["evidence_count"]) for claim in claims]
        expected_order = sorted(claim_order, key=lambda item: ({"strong": 0, "moderate": 1, "weak": 2}[item[0]], -item[1]))
        self.assertEqual(claim_order, expected_order)
        self.assertFalse("InternalToolX" in markdown)
        self.assertIn("unsupported metrics", markdown)
        self.assertIn("## Evidence-backed Claims", markdown)
        self.assertEqual(validate_artifact(artifact, store), [])
        self.assertEqual(len(artifact_traceability(artifact, store)), len(claims))

    def test_career_timeline_is_generated_from_evidence_dates(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        artifact = generate_career_timeline_draft(store)

        milestones = artifact["properties"]["sections"]["milestones"]
        dates = [milestone["occurred_at"] for milestone in milestones]
        self.assertTrue(milestones)
        self.assertEqual(artifact["properties"]["artifact_type"], "Career Timeline")
        self.assertEqual(dates, sorted(dates))
        self.assertTrue(all(milestone["knowledge_id"] for milestone in milestones))
        self.assertTrue(all(milestone["evidence_refs"] for milestone in milestones))
        self.assertTrue(all(milestone["evidence_context"]["evidence_count"] == len(milestone["evidence_refs"]) for milestone in milestones))
        markdown = career_timeline_markdown(artifact)
        self.assertFalse("InternalToolX" in markdown)
        self.assertIn("records;", markdown)
        self.assertNotIn("T09:00:00", markdown)
        self.assertEqual(validate_artifact(artifact, store), [])
        self.assertEqual(len(artifact_traceability(artifact, store)), len(milestones))

    def test_gap_analysis_is_generated_from_accepted_artifact_safe_knowledge(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        artifact = generate_gap_analysis_draft(store)

        sections = artifact["properties"]["sections"]
        claims = sections["strengths"] + sections["weak_evidence"]
        markdown = gap_analysis_markdown(artifact)
        self.assertTrue(claims)
        self.assertEqual(artifact["properties"]["artifact_type"], "Gap Analysis")
        self.assertTrue(all(claim["knowledge_id"] for claim in claims))
        self.assertTrue(all(claim["evidence_refs"] for claim in claims))
        self.assertTrue(all(claim["evidence_context"]["evidence_count"] == len(claim["evidence_refs"]) for claim in claims))
        strength_counts = [claim["evidence_context"]["evidence_count"] for claim in sections["strengths"]]
        self.assertEqual(strength_counts, sorted(strength_counts, reverse=True))
        self.assertIn("Missing evidence is not treated as missing ability.", markdown)
        self.assertIn("records;", markdown)
        self.assertFalse("InternalToolX" in markdown)
        self.assertEqual(validate_artifact(artifact, store), [])
        self.assertEqual(len(artifact_traceability(artifact, store)), len(claims))

    def test_gap_analysis_compares_job_description_requirements(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        job_export = {
            "format": "source_export_v1",
            "captured_at": "2026-01-01T00:00:00Z",
            "engineer": {"id": "engineer-1", "display_name": "Rodolpho", "primary_email_hash": "hash"},
            "source": {"id": "job-descriptions-local", "type": "job_descriptions", "name": "Job Descriptions", "visibility": "artifact_safe"},
            "records": [
                {
                    "source_entity_type": "job_description",
                    "external_id": "JD-1",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "privacy_level": "artifact_safe",
                    "payload": {
                        "title": "Backend Engineer",
                        "description": "Java Spring Boot Kubernetes",
                        "domain": "job market requirements",
                        "technologies": ["Java", "Spring Boot", "Kubernetes"],
                    },
                }
            ],
        }
        ingest_fixture(load_source_input(write_tmp_json("gap_job_descriptions_export_test.json", job_export)), store)

        artifact = generate_gap_analysis_draft(store)
        sections = artifact["properties"]["sections"]
        markdown = gap_analysis_markdown(artifact)

        self.assertIn("Java", [row["requirement"] for row in sections["matched_requirements"]])
        self.assertIn("Kubernetes", [row["requirement"] for row in sections["unmatched_requirements"]])
        self.assertIn("## Job Requirement Matches", markdown)
        self.assertIn("## Job Requirements Needing Evidence", markdown)
        self.assertEqual(validate_artifact(artifact, store), [])

        matched, unmatched = job_requirement_matches(store)
        self.assertIn("Java", [row["requirement"] for row in matched])
        self.assertIn("Kubernetes", [row["requirement"] for row in unmatched])

    def test_artifact_validation_warns_when_claim_references_non_accepted_knowledge(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        artifact = generate_skill_matrix(store)
        claim = artifact["properties"]["rows"][0]
        knowledge_id = claim["knowledge_id"]
        store.update_node(knowledge_id, {"status": "proposed"})

        warnings = validate_artifact(artifact, store)
        markdown = artifact_validation_markdown(artifact, warnings)

        self.assertTrue(any(item["code"] == "knowledge_not_accepted" for item in warnings))
        self.assertIn("# Skill Matrix Validation", markdown)
        self.assertIn("- status: REVIEW", markdown)
        self.assertIn("- warnings: 1 (1 blocker, 0 reviews)", markdown)
        self.assertIn("- readiness: Resolve validation warnings before export review.", markdown)
        self.assertIn("blocker: knowledge_not_accepted", markdown)

    def test_artifact_validation_accepts_skill_matrix_clusters(self):
        store = GraphStore()
        store.create_node({"id": "observation:1", "node_type": "ObservationNode", "properties": {}})
        store.create_node({"id": "evidence:1", "node_type": "EvidenceNode", "properties": {}})
        artifact = {
            "properties": {
                "artifact_type": "Skill Matrix",
                "rows": [
                    {
                        "knowledge_id": "cluster:api_development",
                        "statement": "API Development cluster.",
                        "observation_refs": ["observation:1"],
                        "evidence_refs": ["evidence:1"],
                    }
                ],
            }
        }

        warnings = validate_artifact(artifact, store)
        markdown = artifact_validation_markdown(artifact, warnings)

        self.assertEqual(warnings, [])
        self.assertIn("- status: PASS", markdown)
        self.assertIn("- warnings: 0 (0 blockers, 0 reviews)", markdown)
        self.assertIn("- readiness: Ready for human export review.", markdown)

    def test_artifact_validation_warns_for_unsupported_metrics_and_private_details(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        artifact = generate_star_stories_draft(store)
        story = artifact["properties"]["sections"]["stories"][0]
        story["result"] = "Reduced latency by 50% while handling ADO-WI-123."

        warnings = validate_artifact(artifact, store)
        markdown = artifact_validation_markdown(artifact, warnings)

        self.assertTrue(any(item["code"] == "possible_unsupported_metric" for item in warnings))
        self.assertTrue(any(item["code"] == "possible_private_source_detail" for item in warnings))
        self.assertIn("review: possible_unsupported_metric", markdown)
        self.assertIn("blocker: possible_private_source_detail", markdown)

    def test_artifact_validation_checks_text_before_missing_knowledge_short_circuit(self):
        artifact = {
            "properties": {
                "artifact_type": "STAR Stories",
                "sections": {
                    "stories": [
                        {
                            "title": "Risky claim",
                            "result": "Reduced latency by 50% while handling ADO-WI-123.",
                            "observation_refs": [],
                            "evidence_refs": [],
                        }
                    ]
                },
            }
        }

        warnings = validate_artifact(artifact, GraphStore())
        codes = {item["code"] for item in warnings}

        self.assertIn("missing_knowledge_ref", codes)
        self.assertIn("possible_unsupported_metric", codes)
        self.assertIn("possible_private_source_detail", codes)

    def test_artifact_validation_warns_for_evidence_context_mismatch(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        artifact = generate_star_stories_draft(store)
        story = artifact["properties"]["sections"]["stories"][0]
        story["evidence_context"]["evidence_count"] = len(story["evidence_refs"]) + 1

        warnings = validate_artifact(artifact, store)

        self.assertTrue(any(item["code"] == "evidence_context_count_mismatch" for item in warnings))

    def test_artifact_validation_warns_for_broken_traceability_refs(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        artifact = generate_star_stories_draft(store)
        story = artifact["properties"]["sections"]["stories"][0]
        story["observation_refs"] = ["observation:missing"]
        story["evidence_refs"] = ["evidence:missing"]
        story["evidence_context"]["evidence_count"] = 1

        warnings = validate_artifact(artifact, store)
        codes = {item["code"] for item in warnings}

        self.assertIn("observation_ref_not_found", codes)
        self.assertIn("evidence_ref_not_found", codes)

    def test_artifact_validation_warns_when_claim_refs_are_not_backed_by_knowledge(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        store.create_node({"id": "observation:extra", "node_type": "ObservationNode", "properties": {}})
        store.create_node({"id": "evidence:extra", "node_type": "EvidenceNode", "properties": {}})
        artifact = generate_star_stories_draft(store)
        story = artifact["properties"]["sections"]["stories"][0]
        story["observation_refs"] = ["observation:extra"]
        story["evidence_refs"] = ["evidence:extra"]
        story["evidence_context"]["evidence_count"] = 1

        warnings = validate_artifact(artifact, store)
        codes = {item["code"] for item in warnings}

        self.assertIn("observation_ref_not_in_knowledge", codes)
        self.assertIn("evidence_ref_not_in_knowledge", codes)

    def test_artifact_validation_warns_for_wrong_traceability_ref_types(self):
        store, _ = run_pipeline(ROOT / "examples" / "mvp_fixture.json")
        approve_all_proposed(store)
        artifact = generate_star_stories_draft(store)
        story = artifact["properties"]["sections"]["stories"][0]
        store.nodes[story["observation_refs"][0]]["node_type"] = "EvidenceNode"
        store.nodes[story["evidence_refs"][0]]["node_type"] = "ObservationNode"

        warnings = validate_artifact(artifact, store)
        codes = {item["code"] for item in warnings}

        self.assertIn("observation_ref_wrong_type", codes)
        self.assertIn("evidence_ref_wrong_type", codes)

    def test_artifact_traceability_handles_invalid_refs_for_review(self):
        artifact = {
            "properties": {
                "artifact_type": "STAR Stories",
                "sections": {
                    "stories": [
                        {
                            "title": "Needs review",
                            "statement": "Needs review",
                            "knowledge_id": "knowledge:missing",
                            "observation_refs": ["observation:missing"],
                            "evidence_refs": ["evidence:missing"],
                        }
                    ]
                },
            }
        }

        markdown = artifact_traceability_markdown(artifact, GraphStore())

        self.assertIn("# STAR Stories Traceability", markdown)
        self.assertIn("- Knowledge: UNKNOWN (missing)", markdown)

    def test_artifact_context_outputs_are_deterministic(self):
        evidence = [
            {"properties": {"evidence_type": "WORK_ITEM_EXISTS", "metadata": {"title": "Amazon Java API", "technologies": ["Java"]}}},
            {"properties": {"evidence_type": "WORK_ITEM_EXISTS", "metadata": {"title": "Magalu Java API", "technologies": ["Redis"]}}},
        ]
        signals = extract_context_signals(evidence)

        self.assertEqual(signals["marketplaces_seen"], ["Amazon", "Magalu"])
        self.assertEqual(signals["technologies_seen"], ["Java", "Redis"])

        clustered = cluster_technology_knowledge(
            [
                {"properties": {"statement": "Practical experience with Shopee Integration.", "evidence_refs": ["e2", "e1"], "observation_refs": ["o2"]}},
                {"properties": {"statement": "Practical experience with Magalu Integration.", "evidence_refs": ["e1", "e3"], "observation_refs": ["o1"]}},
            ]
        )

        self.assertEqual(clustered[0]["evidence_refs"], ["e1", "e2", "e3"])
        self.assertEqual(clustered[0]["observation_refs"], ["o1", "o2"])

    def test_knowledge_deduplication_merges_similar_observations(self):
        """Test that multiple observations with same statement generate single knowledge"""
        fixture = {
            "captured_at": "2026-01-01T00:00:00Z",
            "engineer": {"id": "engineer-1", "display_name": "Test", "primary_email_hash": "hash"},
            "source": {"id": "test", "type": "test_export", "name": "Test", "visibility": "private"},
            "records": [
                {
                    "type": "work_item",
                    "external_id": "WI-1",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "privacy_level": "artifact_safe",
                    "payload": {"title": "Java task 1", "technologies": ["Java"]},
                },
                {
                    "type": "work_item",
                    "external_id": "WI-2",
                    "occurred_at": "2026-01-02T00:00:00Z",
                    "privacy_level": "artifact_safe",
                    "payload": {"title": "Java task 2", "technologies": ["Java"]},
                },
                {
                    "type": "commit",
                    "external_id": "C-1",
                    "occurred_at": "2026-01-03T00:00:00Z",
                    "privacy_level": "artifact_safe",
                    "payload": {"message": "Java commit", "technologies": ["Java"]},
                },
            ],
        }
        store = GraphStore()
        ingest_fixture(fixture, store)
        infer_observations(store)

        # Approve all observations
        for item in reviewable_items(store, node_type="ObservationNode"):
            review_node(store, item["id"], "approve", "test")

        # Generate knowledge twice to test deduplication
        knowledge1 = generate_knowledge(store)
        knowledge2 = generate_knowledge(store)

        # Should have only 1 unique knowledge despite multiple observations
        knowledge_statements = {k["properties"]["statement"] for k in knowledge1}
        self.assertEqual(len(knowledge_statements), 1)
        self.assertIn("Practical experience with Java.", knowledge_statements)

        # Second generation should return same knowledge, not create duplicates
        self.assertEqual(len(knowledge1), len(knowledge2))

        # Knowledge should have multiple observation refs
        java_knowledge = knowledge1[0]
        self.assertGreaterEqual(len(java_knowledge["properties"]["observation_refs"]), 1)
        self.assertGreaterEqual(len(java_knowledge["properties"]["evidence_refs"]), 3)


if __name__ == "__main__":
    unittest.main()
