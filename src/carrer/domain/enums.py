"""
Domain enums and constants.

Defines core types, privacy levels, and entity classifications used
throughout the system.
"""

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

# Node Types — graph node classifications
NODE_TYPES = frozenset(
    {
        "Engineer",
        "Source",
        "SourceIdentity",
        "EvidenceNode",
        "ObservationNode",
        "KnowledgeNode",
        "ProfessionalArtifact",
        "JobDescription",
    }
)

# Evidence Types — factual evidence classifications
EVIDENCE_TYPES = frozenset(
    {
        "WORK_ITEM_EXISTS",
        "WORK_ITEM_CLOSED",
        "WORK_ITEM_ASSIGNED",
        "COMMIT_EXISTS",
        "COMMIT_AUTHORED",
        "MERGE_REQUEST_EXISTS",
        "MERGE_REQUEST_MERGED",
        "MERGE_REQUEST_APPROVED",
        "PULL_REQUEST_EXISTS",
        "PULL_REQUEST_MERGED",
        "PULL_REQUEST_REVIEWED",
        "REVIEW_COMMENT_EXISTS",
        "DOCUMENTATION_EXISTS",
        "JOB_DESCRIPTION_EXISTS",
        "BRANCH_EXISTS",
    }
)

# Knowledge Types — inferred knowledge classifications
KNOWLEDGE_TYPES = frozenset(
    {
        "TechnologyKnowledge",
        "DomainKnowledge",
        "ImpactKnowledge",
        "ArchitectureKnowledge",
        "BusinessValueKnowledge",
        "DocumentationKnowledge",
    }
)

# Observation Types — pattern detection classifications
OBSERVATION_TYPES = frozenset(
    {
        "TECHNOLOGY_USAGE_PATTERN",
        "DOMAIN_EXPERIENCE_PATTERN",
        "DOCUMENTATION_PATTERN",
        "IMPACT_SIGNAL_PATTERN",
        "ARCHITECTURE_PATTERN",
        "BUSINESS_VALUE_PATTERN",
    }
)
