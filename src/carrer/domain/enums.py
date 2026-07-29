"""Domain constants used as real validation contracts."""

# Privacy Levels — control export boundaries
PRIVACY_LEVELS = frozenset({"private", "internal", "artifact_safe", "exported"})
ARTIFACT_PRIVACY_LEVELS = frozenset({"draft_private", "internal_review", "artifact_safe", "exported"})

# Review states preserved from existing ObservationNode/KnowledgeNode behavior,
# with draft added for domain-only Contribution and CareerClaim contracts.
REVIEW_STATUSES = frozenset({"draft", "proposed", "review_required", "accepted", "approved", "rejected", "superseded"})
CONFIDENCE_LEVELS = frozenset({"low", "medium", "high"})
ARTIFACT_STATUSES = frozenset({"draft", "approved", "rejected", "superseded", "exported"})

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
