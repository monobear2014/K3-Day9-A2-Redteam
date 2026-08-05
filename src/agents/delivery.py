"""Delivery Agent.

OWNER: P3

Nhiem vu: so thoi diem giao thuc te voi han giao, va QUY TRACH NHIEM:
  - giao tre + seller ban giao qua han  -> seller
  - giao tre + seller ban giao dung han -> logistics_provider
  - khong tre                            -> none
Handoff sang Policy Agent.

TODO(P3): chu y case order_delivered_customer_date rong (don chua giao / bi huy).
Khi do delivered_late = None, KHONG duoc coi la "khong tre".
"""

from ..llm_client import call_json
from ..schemas import CaseFacts, DeliveryVerdict
from .base import facts_brief
from .workers import DELIVERY_SYSTEM

SYSTEM = DELIVERY_SYSTEM


def _deterministic_attribution(f: CaseFacts) -> str:
    if f.delivered_late and f.carrier_handoff_late:
        return "seller"
    if f.delivered_late and not f.carrier_handoff_late:
        return "logistics_provider"
    return "none"


def run(f: CaseFacts, use_llm: bool = True) -> DeliveryVerdict:
    oid = f.claimed_order_id
    baseline = _deterministic_attribution(f)
    verdict = DeliveryVerdict(
        delivered_late=f.delivered_late,
        attribution=baseline,
        evidence_ids=[f"order:{oid}"] if f.order_found else [],
        notes="fallback deterministic",
        llm_ok=False,
    )

    if not f.order_found:
        verdict.notes = "Khong tim thay order trong CSV."
        return verdict
    if not use_llm:
        verdict.notes = "khong duoc dispatch; dung ket qua deterministic"
        return verdict

    out = call_json(SYSTEM, facts_brief(f))
    if not out:
        return verdict

    attribution = out.get("attribution")
    if attribution in ("seller", "logistics_provider", "none"):
        verdict.attribution = attribution
    verdict.notes = str(out.get("notes", ""))[:300]
    verdict.llm_ok = True
    return verdict
