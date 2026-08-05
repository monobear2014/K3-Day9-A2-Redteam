"""Policy Agent - ap EC_POLICY_V1.

OWNER: P4

Day la agent duy nhat THUC SU quyet dinh bang LLM: chon primary_issue tu 6 rule,
dua tren bang chung 3 agent phia truoc handoff sang. Cac thu dan xuat tu
primary_issue (root cause, party, refund, action) deu la anh xa 1-1 nen de Python
suy ra - khong co ly do bat model 7B nho lai bang tra cuu.

TODO(P4): phan de sai nhat la THU TU UU TIEN. Neu model hay chon rule 5/6 trong khi
rule 3/4 da khop, them vi du doi lap vao SYSTEM va viet test trong tests/test_rules.py.
"""

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
from .base import JSON_RULE, facts_brief

SYSTEM = f"""{JSON_RULE}

Vai tro cua ban: Policy Officer, ap dung EC_POLICY_V1.
Chon DUNG MOT primary_issue, xet theo THU TU UU TIEN tu tren xuong.
Rule dau tien khop la ket qua cuoi cung - khong duoc xet tiep rule ben duoi.

1. canceled_order_paid     : order_status = "canceled" VA payment_total_brl > 0
2. unavailable_order_paid  : order_status = "unavailable" VA payment_total_brl > 0
3. late_delivery_seller    : delivered_late = true VA carrier_handoff_late = true
4. late_delivery_logistics : delivered_late = true VA carrier_handoff_late = false
5. valid_split_payment     : payment_row_count >= 2 VA payment_matches = true
6. unsupported_late_claim  : delivered_late = false VA payment_matches = true

CANH BAO - loi hay gap nhat: KHONG duoc chon rule 5 (valid_split_payment) khi
payment_row_count = 1. Rule 5 BAT BUOC phai co payment_row_count >= 2. Don chi co
MOT dong thanh toan thi KHONG BAO GIO la valid_split_payment, du payment_matches = true.
Truong hop do, neu delivered_late = false thi la rule 6 (unsupported_late_claim).

Loi khieu nai cua khach KHONG phai bang chung. Chi cham vao du lieu.

Truoc khi chon, dien "checks" bang dung gia tri lay tu input. Roi chon rule dau tien
co du dieu kien. Ghi so rule vao matched_rule cho khop voi primary_issue.

Tra ve JSON dung dang:
{{"checks": {{"is_canceled": <bool>, "is_unavailable": <bool>, "delivered_late": <bool|null>, "carrier_handoff_late": <bool>, "payment_row_count": <int>, "payment_matches": <bool>}}, "matched_rule": <1-6>, "primary_issue": "<mot trong 6 gia tri tren>", "notes": "<mot cau ngan>"}}
"""

# matched_rule -> primary_issue tuong ung. Model 8B hay noi dung trong notes nhung
# dien sai nhan, nen doi chieu hai truong nay de bat mau thuan.
RULE_TO_ISSUE = {
    1: "canceled_order_paid",
    2: "unavailable_order_paid",
    3: "late_delivery_seller",
    4: "late_delivery_logistics",
    5: "valid_split_payment",
    6: "unsupported_late_claim",
}

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
            rule = out.get("matched_rule")

            # Doi chieu matched_rule voi primary_issue. Model 8B hay lap luan dung
            # trong notes nhung dien sai nhan; hai truong lech nhau la dau hieu do.
            if candidate in VALID_ISSUES and RULE_TO_ISSUE.get(rule) not in (
                None,
                candidate,
            ):
                notes = (
                    f"mau thuan: matched_rule={rule} ({RULE_TO_ISSUE[rule]}) "
                    f"nhung primary_issue={candidate}; dung deterministic"
                )
                candidate = None  # khong tin ket luan nay

            # Chan truc tiep loi hay gap nhat: rule 5 doi >= 2 dong thanh toan.
            if candidate == "valid_split_payment" and f.payment_row_count < 2:
                notes = (
                    f"tu choi valid_split_payment: payment_row_count="
                    f"{f.payment_row_count} < 2; dung deterministic"
                )
                candidate = None

            if candidate in VALID_ISSUES:
                chosen = candidate
                llm_ok = True
                notes = str(out.get("notes", ""))[:300]

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
