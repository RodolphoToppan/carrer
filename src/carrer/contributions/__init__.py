"""Explicit Contribution creation, queries, and candidate discovery."""

from carrer.contributions.candidates import contribution_candidate, contribution_candidate_id
from carrer.contributions.clustering import cluster_evidence, find_contribution_candidates
from carrer.contributions.queries import get_contribution, list_contributions
from carrer.contributions.service import create_contribution

__all__ = [
    "cluster_evidence",
    "contribution_candidate",
    "contribution_candidate_id",
    "create_contribution",
    "find_contribution_candidates",
    "get_contribution",
    "list_contributions",
]
