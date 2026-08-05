"""Pure policy helpers for P4.

This module deliberately has no database, CSV, network, or LLM dependency.  It
only maps an already-cleaned ``CaseFacts`` object to EC_POLICY_V1 outputs.
"""

from dataclasses import dataclass

from .. import rules
from ..schemas import CaseFacts


@dataclass(frozen=True)
class PolicyMapping:
    root_cause_code: str
    resolution_action: str


def map_policy_codes(primary_issue: str) -> PolicyMapping:
    """Map a valid primary issue to its regulated cause/action codes."""
    try:
        root_cause, _party_type, _party_id, action = rules.ISSUE_MAP[primary_issue]
    except KeyError as exc:
        raise ValueError(f"Unknown primary_issue: {primary_issue}") from exc
    return PolicyMapping(root_cause_code=root_cause, resolution_action=action)


def expected_decision(facts: CaseFacts) -> rules.Decision:
    """Evaluate all six §4 rows in their mandatory priority order."""
    return rules.decide(facts)


def is_priority_consistent(
    facts: CaseFacts, primary_issue: object, matched_rule: object
) -> bool:
    """Accept an LLM draft only when it selected the first matching rule.

    Merely checking that an issue belongs to the enum is insufficient: a model
    can otherwise select rule 5 after rule 3 already matched (the MAST failure).
    ``bool`` is rejected for matched_rule because it is an ``int`` subclass.
    """
    expected = expected_decision(facts)
    return (
        isinstance(primary_issue, str)
        and primary_issue == expected.primary_issue
        and isinstance(matched_rule, int)
        and not isinstance(matched_rule, bool)
        and matched_rule == expected.matched_rule
    )


def confidence_for_draft(*, llm_validated: bool) -> float:
    """Policy-stage confidence; Verifier may adjust final output confidence."""
    return 0.95 if llm_validated else 0.80

