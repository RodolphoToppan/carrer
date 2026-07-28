"""Domain constants used as real validation contracts."""

# Privacy Levels — control export boundaries
PRIVACY_LEVELS = frozenset({"private", "internal", "artifact_safe", "exported"})

# Source Entity Types — valid external record types
SOURCE_ENTITY_TYPES = frozenset(
    {
        "work_item",
        "pull_request",
        "merge_request",
        "commit",
        "review_comment",
        "documentation",
        "job_description",
        "branch",
    }
)
