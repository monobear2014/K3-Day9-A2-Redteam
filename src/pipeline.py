"""Pipeline runtime - thuc thi ke hoach do Coordinator Agent giao.

OWNER: P5

File nay KHONG tu quyet dinh agent nao chay. No hoi Coordinator Agent truoc,
roi thi hanh ke hoach do. Khac voi ban dau: thu tu khong con hardcode trong Python.

Luong mot case:
    input JSON
      -> data_loader trich CaseFacts             (Python, khong LLM)
      -> Coordinator Agent lap ke hoach dispatch  (LLM)  <-- GIAO VIEC
      -> cac domain agent duoc dispatch chay      (LLM)  <-- handoff bang chung
      -> Policy Agent chon primary_issue          (LLM)
      -> Verifier Agent tinh lai, phu quyet neu lech, ghi file
      -> Coordinator Agent tong hop ket luan      (LLM)  <-- TONG HOP OUTPUT

Rang buoc Python ap len ke hoach cua Coordinator:
  - policy va verifier LUON chay, khong ai duoc bo.
  - agent khong duoc dispatch van co verdict deterministic, chi la khong goi LLM.
"""

import json
from pathlib import Path

from . import config
from .agents import coordinator, delivery, order_seller, payment, policy, verifier
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

    # --- 1. Trich su that (Python, khong LLM) ---
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

    # --- 2. Coordinator Agent GIAO VIEC ---
    dispatch_plan = coordinator.plan(facts)
    tracer.log(case_id, "dispatch_plan", "coordinator", dispatch_plan.model_dump())
    assigned = set(dispatch_plan.dispatch)

    # --- 3. Domain agent chay va handoff sang Policy ---
    order_v = order_seller.run(facts, use_llm="order_seller" in assigned)
    tracer.handoff(case_id, "order_seller", "policy", order_v.model_dump())

    pay_v = payment.run(facts, use_llm="payment" in assigned)
    tracer.handoff(case_id, "payment", "policy", pay_v.model_dump())

    del_v = delivery.run(facts, use_llm="delivery" in assigned)
    tracer.handoff(case_id, "delivery", "policy", del_v.model_dump())

    # --- 4. Policy Agent quyet dinh primary_issue (luon chay) ---
    policy_v = policy.run(facts, order_v, pay_v, del_v)
    tracer.handoff(case_id, "policy", "verifier", policy_v.model_dump())

    # --- 5. Verifier chot (luon chay, co quyen phu quyet) ---
    # Chi tinh llm_ok tren cac agent THUC SU duoc dispatch - agent bi bo qua
    # theo ke hoach khong phai la loi, khong duoc keo confidence xuong.
    dispatched = [
        v
        for name, v in (
            ("order_seller", order_v),
            ("payment", pay_v),
            ("delivery", del_v),
        )
        if name in assigned
    ]
    all_llm_ok = dispatch_plan.llm_ok and all(
        v.llm_ok for v in [*dispatched, policy_v]
    )

    output, report = verifier.run(facts, policy_v, all_llm_ok)
    report["dispatched"] = sorted(assigned)
    report["dispatch_reason"] = dispatch_plan.notes
    tracer.log(case_id, "verified", "verifier", report)

    # --- 6. Coordinator TONG HOP ---
    summary = coordinator.summarize(
        facts,
        output.assessment.primary_issue,
        output.financial_resolution.recommended_refund_brl,
    )
    tracer.log(case_id, "summary", "coordinator", {"summary": summary})

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
