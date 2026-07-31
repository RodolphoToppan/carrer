"""Read-only CareerClaimCandidate generation."""

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

__all__ = [
    "career_claim_candidate",
    "career_claim_candidate_id",
    "generate_career_claim_candidates",
    "generate_career_claim_candidates_from_analysis",
    "supporting_fact_ref",
    "supporting_signal_ref",
    "validate_career_claim_candidate",
]
