"""
Privacy level management and merging.

Handles privacy boundary classification and restriction ordering.
"""


def most_restrictive(levels: list[str]) -> str:
    """
    Select most restrictive privacy level from a list.

    Privacy levels in order of restriction (most to least):
    - private: Never exported
    - internal: May be shown locally
    - artifact_safe: Safe for resumes, LinkedIn
    - exported: Safe for external systems

    Args:
        levels: List of privacy level strings

    Returns:
        Most restrictive privacy level from the list

    Raises:
        ValueError: If any level is not in PRIVACY_LEVELS

    Examples:
        >>> most_restrictive(["artifact_safe", "private", "internal"])
        'private'
        >>> most_restrictive(["exported", "artifact_safe"])
        'artifact_safe'
    """
    from carrer.domain.enums import PRIVACY_LEVELS

    for level in levels:
        if level not in PRIVACY_LEVELS:
            raise ValueError(f"Invalid privacy level: {level}")

    order = {"private": 0, "internal": 1, "artifact_safe": 2, "exported": 3}
    return min(levels, key=lambda level: order[level])
