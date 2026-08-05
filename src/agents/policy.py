"""Policy Agent - ap EC_POLICY_V1 to isolated, cleaned CaseFacts.

OWNER: P4

Day la agent duy nhat THUC SU quyet dinh bang LLM: chon primary_issue tu 6 rule,
dua tren bang chung 3 agent phia truoc handoff sang. Cac thu dan xuat tu
primary_issue (root cause, party, refund, action) deu la anh xa 1-1 nen de Python
suy ra - khong co ly do bat model 7B nho lai bang tra cuu.

The agent never accesses the database/CSV.  Its only inputs are CaseFacts and
the three upstream verdicts.  Python validates the LLM draft against the first
matching rule before any regulated code, refund, party, or action is emitted.
"""

from pathlib import Path

from .. import rules
from ..llm_client import call_json
from ..schemas import (
    CaseFacts,
    DeliveryVerdict,
    OrderSellerVerdict,
    PaymentVerdict,
    PolicyVerdict,
    RankedCause,
    ResponsibleParty,
)
from ..tools.policy_tools import confidence_for_draft, is_priority_consistent
from .base import JSON_RULE, facts_brief

PROMPT_PATH = Path(__file__).with_name("prompts") / "policy.txt"
SYSTEM = f"{JSON_RULE}\n\n{PROMPT_PATH.read_text(encoding='utf-8')}"

VALID_ISSUES = set(rules.ISSUE_MAP.keys())


def run(
    f: CaseFacts,
    order_v: OrderSellerVerdict,
    pay_v: PaymentVerdict,
    del_v: DeliveryVerdict,
) -> PolicyVerdict:
    baseline = rules.decide(f)

    user = (
        f"FACTS:\n{facts_brief(f)}\n\n"
        f"BANG CHUNG TU CAC AGENT:\n"
        f"- order_seller: status={order_v.order_status}, "
        f"breaching_sellers={order_v.breaching_seller_ids}\n"
        f"- payment: split={pay_v.is_split_payment}, reconciled={pay_v.reconciled}\n"
        f"- delivery: late={del_v.delivered_late}, attribution={del_v.attribution}\n"
    )

    chosen, llm_ok = baseline.primary_issue, False
    notes = "fallback deterministic"

    if f.order_found:
        out = call_json(SYSTEM, user)
        if out:
            candidate = out.get("primary_issue")
            if candidate in VALID_ISSUES and is_priority_consistent(
                f, candidate, out.get("matched_rule")
            ):
                chosen = candidate
                llm_ok = True
                notes = str(out.get("notes", ""))[:300]
            else:
                notes = "LLM draft sai thứ tự ưu tiên; dùng fallback deterministic"

    # Refund va action luon suy ra tu primary_issue bang Python (anh xa 1-1).
    decision = _decision_for(chosen, f)

    return PolicyVerdict(
        primary_issue=decision.primary_issue,
        case_status=decision.case_status,
        ranked_causes=[RankedCause(cause_code=decision.root_cause, rank=1)],
        responsible_parties=[ResponsibleParty(**p) for p in decision.responsible_parties],
        recommended_refund_brl=decision.refund_brl,
        resolution_actions=[decision.action],
        evidence_ids=[f"policy:{decision.root_cause}"],
        notes=notes,
        llm_ok=llm_ok,
        confidence=confidence_for_draft(llm_validated=llm_ok),
    )


def _decision_for(issue: str, f: CaseFacts) -> rules.Decision:
    """Dung refund dung voi issue ma LLM chon (Verifier van co quyen phu quyet sau)."""
    if issue in ("canceled_order_paid", "unavailable_order_paid"):
        refund = f.payment_total_brl
    elif issue in ("late_delivery_seller", "late_delivery_logistics"):
        refund = f.freight_total_brl
    else:
        refund = 0.0
    return rules._build(issue, f, refund, rule=0)
