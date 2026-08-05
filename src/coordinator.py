"""Coordinator Agent - dieu phoi va handoff.

OWNER: P5

Luong mot case:
    input JSON
      -> data_loader tri ch CaseFacts (Python, khong LLM)
      -> Order&Seller Agent  ─┐
      -> Payment Agent       ─┼─> handoff bang chung
      -> Delivery Agent      ─┘
      -> Policy Agent   (chon primary_issue tu bang chung 3 agent tren)
      -> Verifier Agent (tinh lai bang Python, phu quyet neu lech, ghi file)

Moi buoc deu ghi vao logging/trace.jsonl.
"""

import json
from pathlib import Path

from . import config
from .agents import delivery, order_seller, payment, policy, verifier
from .data_loader import get_data
from .schemas import CaseFacts, CaseOutput
from .trace import Tracer


def load_case(path: Path) -> tuple[str, str, str]:
    """Doc input JSON -> (case_id, claimed_order_id, message)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    req = raw.get("customer_request", {})
    return (
        raw.get("case_id", path.stem),
        req.get("claimed_order_id", ""),
        req.get("message", ""),
    )


def process_case(path: Path, tracer: Tracer) -> CaseOutput:
    case_id, order_id, message = load_case(path)
    tracer.log(case_id, "case_start", "coordinator", {"order_id": order_id})

    facts: CaseFacts = get_data().build_facts(case_id, order_id, message)
    tracer.log(
        case_id,
        "facts_extracted",
        "coordinator",
        {
            "order_found": facts.order_found,
            "order_status": facts.order_status,
            "items": len(facts.items),
            "payments": facts.payment_row_count,
            "delivered_late": facts.delivered_late,
            "carrier_handoff_late": facts.carrier_handoff_late,
        },
    )

    # --- Ba agent domain chay doc lap, roi handoff sang Policy ---
    order_v = order_seller.run(facts)
    tracer.handoff(case_id, "order_seller", "policy", order_v.model_dump())

    pay_v = payment.run(facts)
    tracer.handoff(case_id, "payment", "policy", pay_v.model_dump())

    del_v = delivery.run(facts)
    tracer.handoff(case_id, "delivery", "policy", del_v.model_dump())

    # --- Policy quyet dinh primary_issue ---
    policy_v = policy.run(facts, order_v, pay_v, del_v)
    tracer.handoff(case_id, "policy", "verifier", policy_v.model_dump())

    # --- Verifier chot ---
    all_llm_ok = all(v.llm_ok for v in (order_v, pay_v, del_v, policy_v))
    output, report = verifier.run(facts, policy_v, all_llm_ok)
    tracer.log(case_id, "verified", "verifier", report)

    write_output(output)
    tracer.log(case_id, "case_done", "coordinator", {"file": f"{case_id}.json"})
    return output


def write_output(output: CaseOutput) -> Path:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.OUTPUT_DIR / f"{output.case_id}.json"
    path.write_text(
        json.dumps(output.to_json_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
