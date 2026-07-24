from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from career_intelligence_mvp import (
    GraphStore,
    generate_skill_matrix,
    generate_resume_draft,
    generate_linkedin_draft,
    artifact_markdown,
    resume_markdown,
    linkedin_markdown,
    artifact_traceability_markdown,
    validate_artifact,
    artifact_validation_markdown,
)

# Load graph
store = GraphStore.load("data/azure_devops_mcp_export_graph.json")

print("Loading graph and generating artifacts...")

# Generate artifacts
skill_matrix = generate_skill_matrix(store)
resume = generate_resume_draft(store)
linkedin = generate_linkedin_draft(store)

# Save graph
store.save("data/azure_devops_mcp_export_graph.json")

# Write markdown files
Path("data/skill_matrix.md").write_text(artifact_markdown(skill_matrix), encoding="utf-8")
Path("data/resume_draft.md").write_text(resume_markdown(resume), encoding="utf-8")
Path("data/linkedin_draft.md").write_text(linkedin_markdown(linkedin), encoding="utf-8")

# Write traceability
Path("data/skill_matrix_traceability.md").write_text(
    artifact_traceability_markdown(skill_matrix, store), encoding="utf-8"
)
Path("data/resume_traceability.md").write_text(
    artifact_traceability_markdown(resume, store), encoding="utf-8"
)
Path("data/linkedin_traceability.md").write_text(
    artifact_traceability_markdown(linkedin, store), encoding="utf-8"
)

# Write validation
skill_warnings = validate_artifact(skill_matrix, store)
resume_warnings = validate_artifact(resume, store)
linkedin_warnings = validate_artifact(linkedin, store)

Path("data/skill_matrix_validation.md").write_text(
    artifact_validation_markdown(skill_matrix, skill_warnings), encoding="utf-8"
)
Path("data/resume_validation.md").write_text(
    artifact_validation_markdown(resume, resume_warnings), encoding="utf-8"
)
Path("data/linkedin_validation.md").write_text(
    artifact_validation_markdown(linkedin, linkedin_warnings), encoding="utf-8"
)

print(f"Done! Generated {len(skill_matrix['properties']['rows'])} skill matrix rows")
print(f"Resume highlights: {len(resume['properties']['sections']['highlights'])}")
print(f"LinkedIn highlights: {len(linkedin['properties']['sections']['highlights'])}")

