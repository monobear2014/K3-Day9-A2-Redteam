"""Test engine deterministic - phan chiem 45% diem va de sai thu tu uu tien nhat.

    pytest -q

TODO(P4): moi khi phat hien case that bi cham sai, them mot test o day truoc khi sua.
"""

import pytest

from src import rules
from src.schemas import CaseFacts, ItemFact, PaymentFact
from src.tools.policy_tools import is_priority_consistent, map_policy_codes


def make_facts(**kw) -> CaseFacts:
    base = dict(
        case_id="EC_TEST",
        claimed_order_id="order_x",
        order_found=True,
        order_status="delivered",
        payment_matches=True,
    )
    base.update(kw)
    return CaseFacts(**base)


def item(seller="seller_a", item_id=1, price=100.0, freight=15.0, late=False):
    return ItemFact(
        order_item_id=item_id,
        product_id="prod_1",
        seller_id=seller,
        shipping_limit_date="2018-01-01 00:00:00",
        price=price,
        freight_value=freight,
        handoff_after_limit=late,
    )


def payment(seq=1, value=115.0):
    return PaymentFact(
        payment_sequential=seq,
        payment_type="credit_card",
        payment_installments=1,
        payment_value=value,
    )


# --- 6 nhanh rule -------------------------------------------------------
def test_rule1_canceled_paid_refunds_full_payment():
    d = rules.decide(make_facts(order_status="canceled", payment_total_brl=115.0))
    assert d.primary_issue == "canceled_order_paid"
    assert d.refund_brl == 115.0
    assert d.action == "issue_full_refund"
    assert d.case_status == "action_required"
    assert d.responsible_parties == [
        {"party_type": "platform", "party_id": "OLIST_PLATFORM"}
    ]


def test_rule2_unavailable_paid_refunds_full_payment():
    d = rules.decide(make_facts(order_status="unavailable", payment_total_brl=99.5))
    assert d.primary_issue == "unavailable_order_paid"
    assert d.refund_brl == 99.5
    assert d.root_cause == "ORDER_UNAVAILABLE_AFTER_PAYMENT"


def test_rule3_late_and_seller_handoff_late_blames_seller():
    d = rules.decide(
        make_facts(
            delivered_late=True,
            carrier_handoff_late=True,
            late_seller_ids=["seller_a"],
            freight_total_brl=15.0,
        )
    )
    assert d.primary_issue == "late_delivery_seller"
    assert d.refund_brl == 15.0
    assert d.action == "refund_freight"
    assert d.responsible_parties == [{"party_type": "seller", "party_id": "seller_a"}]


def test_rule4_late_but_seller_on_time_blames_logistics():
    d = rules.decide(
        make_facts(
            delivered_late=True, carrier_handoff_late=False, freight_total_brl=22.5
        )
    )
    assert d.primary_issue == "late_delivery_logistics"
    assert d.refund_brl == 22.5
    assert d.responsible_parties == [
        {"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}
    ]


def test_rule5_split_payment_reconciled_no_refund():
    d = rules.decide(
        make_facts(delivered_late=False, payment_row_count=2, payment_matches=True)
    )
    assert d.primary_issue == "valid_split_payment"
    assert d.refund_brl == 0.0
    assert d.case_status == "no_action"
    assert d.action == "explain_valid_split_payment"
    assert d.responsible_parties == []


def test_rule6_on_time_delivery_rejects_claim():
    d = rules.decide(
        make_facts(delivered_late=False, payment_row_count=1, payment_matches=True)
    )
    assert d.primary_issue == "unsupported_late_claim"
    assert d.action == "reject_late_refund"
    assert d.root_cause == "DELIVERY_WITHIN_ESTIMATE"


# --- THU TU UU TIEN: phan de sai nhat ------------------------------------
def test_canceled_beats_late_delivery():
    """Don bi huy + giao tre -> rule 1 thang, khong phai rule 3."""
    d = rules.decide(
        make_facts(
            order_status="canceled",
            payment_total_brl=115.0,
            delivered_late=True,
            carrier_handoff_late=True,
            late_seller_ids=["seller_a"],
            freight_total_brl=15.0,
        )
    )
    assert d.primary_issue == "canceled_order_paid"
    assert d.refund_brl == 115.0


def test_late_delivery_beats_split_payment():
    """Giao tre + co 2 payment khop -> rule 3/4 thang, khong phai rule 5."""
    d = rules.decide(
        make_facts(
            delivered_late=True,
            carrier_handoff_late=False,
            payment_row_count=2,
            payment_matches=True,
            freight_total_brl=15.0,
        )
    )
    assert d.primary_issue == "late_delivery_logistics"


def test_split_payment_beats_unsupported_claim():
    """Giao dung han + 2 payment khop -> rule 5 thang rule 6."""
    d = rules.decide(
        make_facts(delivered_late=False, payment_row_count=2, payment_matches=True)
    )
    assert d.primary_issue == "valid_split_payment"


def test_policy_rejects_valid_but_lower_priority_llm_choice():
    f = make_facts(
        delivered_late=True,
        carrier_handoff_late=False,
        payment_row_count=2,
        payment_matches=True,
    )
    assert not is_priority_consistent(f, "valid_split_payment", 5)
    assert is_priority_consistent(f, "late_delivery_logistics", 4)


def test_policy_requires_matching_rule_number():
    f = make_facts(order_status="canceled", payment_total_brl=115.0)
    assert not is_priority_consistent(f, "canceled_order_paid", 2)
    assert not is_priority_consistent(f, "canceled_order_paid", True)


def test_policy_code_mapping():
    mapped = map_policy_codes("late_delivery_seller")
    assert mapped.root_cause_code == "SELLER_HANDOFF_AFTER_LIMIT"
    assert mapped.resolution_action == "refund_freight"


def test_split_payment_not_reconciled_falls_through():
    """2 payment nhung KHONG khop -> khong duoc coi la valid_split_payment."""
    d = rules.decide(
        make_facts(delivered_late=False, payment_row_count=2, payment_matches=False)
    )
    assert d.primary_issue != "valid_split_payment"


def test_undelivered_order_is_not_treated_as_on_time():
    """delivered_late = None (chua giao) KHONG duoc coi la giao dung han."""
    d = rules.decide(
        make_facts(delivered_late=None, payment_row_count=1, payment_matches=True)
    )
    assert d.matched_rule == 0  # roi vao nhanh an toan, khong phai rule 6


# --- Evidence ------------------------------------------------------------
def test_evidence_ids_only_reference_real_rows():
    f = make_facts(
        items=[item(item_id=1), item(item_id=2)],
        payments=[payment(seq=1)],
        seller_ids=["seller_a"],
    )
    ev = rules.build_evidence(f, "DELIVERY_WITHIN_ESTIMATE")
    assert "order:order_x" in ev
    assert "item:order_x:1" in ev and "item:order_x:2" in ev
    assert "payment:order_x:1" in ev
    assert "seller:seller_a" in ev
    assert "policy:DELIVERY_WITHIN_ESTIMATE" in ev
    assert "item:order_x:3" not in ev  # khong bia item khong ton tai


def test_evidence_capped_at_ten():
    f = make_facts(
        items=[item(item_id=i) for i in range(1, 9)],
        payments=[payment(seq=i) for i in range(1, 6)],
        seller_ids=["seller_a", "seller_b"],
    )
    assert len(rules.build_evidence(f, "DELIVERY_WITHIN_ESTIMATE")) <= 10


def test_entity_ids_capped_at_five():
    f = make_facts(
        items=[item(item_id=i) for i in range(1, 9)],
        payments=[payment(seq=i) for i in range(1, 9)],
        seller_ids=[f"s{i}" for i in range(8)],
    )
    e = rules.entity_ids(f)
    assert all(len(v) <= 5 for v in e.values())


@pytest.mark.parametrize("issue", list(rules.ISSUE_MAP))
def test_every_issue_maps_to_valid_codes(issue):
    cause, _, _, action = rules.ISSUE_MAP[issue]
    assert cause in {
        "SELLER_HANDOFF_AFTER_LIMIT",
        "CARRIER_DELIVERED_AFTER_ESTIMATE",
        "ORDER_CANCELED_AFTER_PAYMENT",
        "ORDER_UNAVAILABLE_AFTER_PAYMENT",
        "MULTIPLE_PAYMENTS_RECONCILED",
        "DELIVERY_WITHIN_ESTIMATE",
    }
    assert action in {
        "issue_full_refund",
        "refund_freight",
        "explain_valid_split_payment",
        "reject_late_refund",
    }
