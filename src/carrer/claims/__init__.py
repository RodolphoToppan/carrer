"""Career claim candidate generation, review, and queries."""

from carrer.claims.candidates import (
    career_claim_candidate,
    career_claim_candidate_id,
    supporting_fact_ref,
    supporting_signal_ref,
    validate_career_claim_candidate,
)
from carrer.claims.generation import (
    generate_career_claim_candidates,
    generate_career_claim_candidates_from_analysis,
)
from carrer.claims.queries import get_career_claim, list_career_claims
from carrer.claims.review import (
    CAREER_CLAIM_DERIVED_FROM_ANALYSIS,
    CAREER_CLAIM_FROM_CONTRIBUTION,
    CAREER_CLAIM_SUPPORTED_BY_EVIDENCE,
    accept_career_claim_candidate,
    reject_career_claim_candidate,
    validate_persisted_career_claim,
)

__all__ = [
    "career_claim_candidate",
    "career_claim_candidate_id",
    "accept_career_claim_candidate",
    "get_career_claim",
    "generate_career_claim_candidates",
    "generate_career_claim_candidates_from_analysis",
    "list_career_claims",
    "reject_career_claim_candidate",
    "supporting_fact_ref",
    "supporting_signal_ref",
    "validate_career_claim_candidate",
    "validate_persisted_career_claim",
    "CAREER_CLAIM_DERIVED_FROM_ANALYSIS",
    "CAREER_CLAIM_FROM_CONTRIBUTION",
    "CAREER_CLAIM_SUPPORTED_BY_EVIDENCE",
]
