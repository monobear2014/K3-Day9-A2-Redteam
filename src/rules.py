"""EC_POLICY_V1 - engine deterministic.

OWNER: P4 (Policy)

Day la "su that nen" de doi chieu voi ket luan cua LLM. Policy Agent van suy luan
that bang LLM, nhung Verifier dung ket qua o day de phu quyet khi LLM sai
(README muc 7: Verifier kiem tra ID, so tien va schema truoc khi ghi file).

THU TU UU TIEN LA BAT BUOC - README muc 4 noi ro "ap dung theo thu tu duoi day".
Doi thu tu 2 nhanh la sai ca primary_issue lan refund lan action.
"""

from dataclasses import dataclass, field

from . import config
from .schemas import CaseFacts

# Ban do: primary_issue -> (root_cause, party_type, party_id, action)
ISSUE_MAP = {
    "canceled_order_paid": (
        "ORDER_CANCELED_AFTER_PAYMENT",
        "platform",
        "OLIST_PLATFORM",
        "issue_full_refund",
    ),
    "unavailable_order_paid": (
        "ORDER_UNAVAILABLE_AFTER_PAYMENT",
        "platform",
        "OLIST_PLATFORM",
        "issue_full_refund",
    ),
    "late_delivery_seller": (
        "SELLER_HANDOFF_AFTER_LIMIT",
        "seller",
        None,  # dien seller_id vi pham
        "refund_freight",
    ),
    "late_delivery_logistics": (
        "CARRIER_DELIVERED_AFTER_ESTIMATE",
        "logistics_provider",
        "LOGISTICS_PROVIDER",
        "refund_freight",
    ),
    "valid_split_payment": (
        "MULTIPLE_PAYMENTS_RECONCILED",
        None,
        None,
        "explain_valid_split_payment",
    ),
    "unsupported_late_claim": (
        "DELIVERY_WITHIN_ESTIMATE",
        None,
        None,
        "reject_late_refund",
    ),
}


@dataclass
class Decision:
    primary_issue: str
    case_status: str
    root_cause: str
    refund_brl: float
    action: str
    responsible_parties: list[dict] = field(default_factory=list)
    matched_rule: int = 0


def decide(f: CaseFacts) -> Decision:
    """Ap 6 rule theo dung thu tu uu tien cua README muc 4."""

    # --- Rule 1: canceled + da thanh toan ---
    if f.order_status == "canceled" and f.payment_total_brl > 0:
        return _build("canceled_order_paid", f, f.payment_total_brl, rule=1)

    # --- Rule 2: unavailable + da thanh toan ---
    if f.order_status == "unavailable" and f.payment_total_brl > 0:
        return _build("unavailable_order_paid", f, f.payment_total_brl, rule=2)

    # --- Rule 3: giao tre + seller ban giao qua han ---
    if f.delivered_late and f.carrier_handoff_late:
        return _build("late_delivery_seller", f, f.freight_total_brl, rule=3)

    # --- Rule 4: giao tre + seller ban giao dung han -> loi van chuyen ---
    if f.delivered_late and not f.carrier_handoff_late:
        return _build("late_delivery_logistics", f, f.freight_total_brl, rule=4)

    # --- Rule 5: split payment hop le ---
    if f.payment_row_count >= 2 and f.payment_matches:
        return _build("valid_split_payment", f, 0.0, rule=5)

    # --- Rule 6: giao dung han + payment khop -> bac claim ---
    if f.delivered_late is False and f.payment_matches:
        return _build("unsupported_late_claim", f, 0.0, rule=6)

    # --- Khong rule nao khop: bac claim, khong hoan tien ---
    # README noi bo 50 case chinh thuc khong co tinh huong mo ho, nen nhanh nay
    # chi la luoi an toan de khong bao gio ghi file rong -> tranh hard gate.
    return _build("unsupported_late_claim", f, 0.0, rule=0)


def _build(issue: str, f: CaseFacts, refund: float, rule: int) -> Decision:
    cause, party_type, party_id, action = ISSUE_MAP[issue]
    parties: list[dict] = []
    if party_type == "seller":
        for sid in f.late_seller_ids[: config.MAX_RESPONSIBLE_PARTIES]:
            parties.append({"party_type": "seller", "party_id": sid})
    elif party_type:
        parties.append({"party_type": party_type, "party_id": party_id})

    refund = round(refund + 1e-9, 2)
    return Decision(
        primary_issue=issue,
        case_status="action_required" if refund > 0 else "no_action",
        root_cause=cause,
        refund_brl=refund,
        action=action,
        responsible_parties=parties,
        matched_rule=rule,
    )


# =====================================================================
# Evidence ID - chi dung ID dung duoc truc tiep tu CSV (README muc 5).
# Evidence bia hoac sai dinh dang bi tinh false positive.
# =====================================================================
def build_evidence(f: CaseFacts, root_cause: str) -> list[str]:
    oid = f.claimed_order_id
    ev: list[str] = []
    if f.order_found:
        ev.append(f"order:{oid}")
    ev.append(f"policy:{root_cause}")
    for it in f.items:
        ev.append(f"item:{oid}:{it.order_item_id}")
    for p in f.payments:
        ev.append(f"payment:{oid}:{p.payment_sequential}")
    for sid in f.seller_ids:
        ev.append(f"seller:{sid}")
    return ev[: config.MAX_EVIDENCE]


def entity_ids(f: CaseFacts) -> dict[str, list[str]]:
    oid = f.claimed_order_id
    return {
        "order_ids": [oid] if f.order_found else [],
        "item_ids": [f"{oid}:{i.order_item_id}" for i in f.items][
            : config.MAX_IDS_PER_ENTITY
        ],
        "seller_ids": f.seller_ids[: config.MAX_IDS_PER_ENTITY],
        "payment_ids": [f"{oid}:{p.payment_sequential}" for p in f.payments][
            : config.MAX_IDS_PER_ENTITY
        ],
    }
