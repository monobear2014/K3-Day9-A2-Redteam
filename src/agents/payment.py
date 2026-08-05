"""Payment Agent.

OWNER: P3

Nhiem vu: doi soat tong payment voi item + freight (sai so 0.10 BRL),
xac dinh co phai split payment hop le khong. Handoff sang Policy Agent.

TODO(P3): kiem tra ky case co payment_row_count >= 2 nhung KHONG khop -
truong hop do KHONG phai valid_split_payment, phai roi xuong rule khac.
"""

from .. import config
from ..llm_client import call_json
from ..schemas import CaseFacts, PaymentVerdict
from .base import JSON_RULE, facts_brief

SYSTEM = f"""{JSON_RULE}

Vai tro cua ban: Payment Reconciliation Analyst.
He thong da tinh san: payment_total_brl, item_total_brl, freight_total_brl,
payment_diff_brl (= |payment_total - (item_total + freight_total)|) va payment_matches.
DUNG tu cong lai cac so nay.

Tra loi:
- is_split_payment: true neu payment_row_count >= 2.
- reconciled: true neu payment_diff_brl <= {config.PAYMENT_TOLERANCE_BRL} BRL.

Tra ve JSON dung dang:
{{"is_split_payment": <bool>, "reconciled": <bool>, "notes": "<mot cau tieng Viet>"}}
"""


def run(f: CaseFacts) -> PaymentVerdict:
    oid = f.claimed_order_id
    verdict = PaymentVerdict(
        payment_ids=[f"{oid}:{p.payment_sequential}" for p in f.payments],
        is_split_payment=f.payment_row_count >= 2,
        reconciled=f.payment_matches,
        evidence_ids=[f"payment:{oid}:{p.payment_sequential}" for p in f.payments],
        notes="fallback deterministic",
        llm_ok=False,
    )

    if not f.order_found:
        verdict.notes = "Khong tim thay order trong CSV."
        return verdict

    out = call_json(SYSTEM, facts_brief(f))
    if not out:
        return verdict

    # LLM chi duoc mo ta, khong duoc doi ket luan so hoc cua Python.
    verdict.notes = str(out.get("notes", ""))[:300]
    verdict.llm_ok = True
    return verdict
