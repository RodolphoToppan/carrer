"""
Domain layer — Pure domain logic, no I/O, no framework dependencies.

Exports core types, enums, and identity functions.
"""

from carrer.domain.enums import (
    ARTIFACT_PRIVACY_LEVELS,
    ARTIFACT_STATUSES,
    CONFIDENCE_LEVELS,
    PRIVACY_LEVELS,
    REVIEW_STATUSES,
    SOURCE_ENTITY_TYPES,
)
from carrer.domain.hashing import stable_hash
from carrer.domain.identity import (
    canonical_refs,
    career_claim_id,
    contribution_id,
    evidence_content_hash,
    evidence_id,
    knowledge_id,
    observation_id,
)
from carrer.domain.models import (
    career_claim_node,
    contribution_node,
    evidence_node,
    knowledge_node,
    observation_node,
    professional_artifact_contract,
)
from carrer.domain.privacy import derive_privacy, is_publishable, most_restrictive, validate_privacy_level
from carrer.domain.timestamps import now
from carrer.domain.validation import (
    validate_career_claim,
    validate_contribution,
    validate_evidence,
    validate_knowledge,
    validate_observation,
    validate_professional_artifact,
)

__all__ = [
    "ARTIFACT_PRIVACY_LEVELS",
    "ARTIFACT_STATUSES",
    "CONFIDENCE_LEVELS",
    "PRIVACY_LEVELS",
    "REVIEW_STATUSES",
    "SOURCE_ENTITY_TYPES",
    "canonical_refs",
    "career_claim_id",
    "career_claim_node",
    "contribution_id",
    "contribution_node",
    "derive_privacy",
    "evidence_content_hash",
    "evidence_id",
    "evidence_node",
    "is_publishable",
    "knowledge_id",
    "knowledge_node",
    "most_restrictive",
    "now",
    "observation_id",
    "observation_node",
    "professional_artifact_contract",
    "stable_hash",
    "validate_career_claim",
    "validate_contribution",
    "validate_evidence",
    "validate_knowledge",
    "validate_observation",
    "validate_privacy_level",
    "validate_professional_artifact",
]
