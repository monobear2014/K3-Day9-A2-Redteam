"""Coordinator Agent - agent dieu phoi cac agent khac.

OWNER: P5

README muc 7 giao cho Coordinator ba viec: NHAN case, GIAO VIEC, TONG HOP output.
File nay lam phan "giao viec" va "tong hop" bang LLM that, khong hardcode thu tu.

Coordinator doc trieu chung cua case roi quyet dinh dispatch agent nao. Quyet dinh
do CO HIEU LUC THAT - agent khong duoc dispatch thi khong chay, tiet kiem call
(50 case x 5 agent = 250 call trong 2h30).

An toan: bo sot agent chi mat phan dien giai, KHONG bao gio lam sai so tien,
vi CaseFacts da duoc Python tinh day du tu truoc va Verifier tinh lai lan nua.
Rang buoc cung do Python ap:
  - policy + verifier LUON chay, khong ai duoc bo.
  - dispatch rong hoac khong hop le -> chay ca 3 domain agent.
"""

from ..llm_client import call_json
from ..schemas import CaseFacts, DispatchPlan
from .base import JSON_RULE, facts_brief

DOMAIN_AGENTS = ["order_seller", "payment", "delivery"]

SYSTEM = f"""{JSON_RULE}

Vai tro cua ban: Coordinator - truong nhom xu ly khieu nai.
Ban KHONG tu ket luan. Viec cua ban la doc trieu chung cua case roi GIAO VIEC cho
dung chuyen vien can thiet, de khong lang phi thoi gian dieu tra thu khong lien quan.

Cac chuyen vien co the giao:
- "order_seller": trang thai don, danh sach item, seller nao ban giao qua han.
- "payment"     : doi soat tien thanh toan voi gia tri item + phi van chuyen.
- "delivery"    : so ngay giao thuc te voi han giao, quy trach nhiem tre.

Huong dan giao viec:
- delivered_late = true HOAC null -> BAT BUOC co "delivery" trong danh sach.
  Day la quy tac cung, khong duoc bo qua.
- Don "canceled" hoac "unavailable": can order_seller va payment.
- payment_row_count >= 2: bat buoc co "payment".
- Khi phan van: giao ca ba.

Tra ve JSON dung dang:
{{"dispatch": ["order_seller", "payment"], "focus": "order_status|delivery|payment|unknown", "notes": "<mot cau tieng Viet giai thich vi sao giao nhu vay>"}}
"""


def plan(f: CaseFacts) -> DispatchPlan:
    """Quyet dinh dispatch agent nao cho case nay."""
    fallback = DispatchPlan(
        dispatch=list(DOMAIN_AGENTS),
        focus="unknown",
        notes="fallback: giao ca ba agent",
        llm_ok=False,
    )

    if not f.order_found:
        fallback.notes = "Khong tim thay order, van giao ca ba de ghi nhan bang chung."
        return fallback

    out = call_json(SYSTEM, facts_brief(f))
    if not out:
        return fallback

    chosen = [a for a in out.get("dispatch", []) if a in DOMAIN_AGENTS]
    forced: list[str] = []
    if not chosen:
        # Model tra rong hoac bia ten agent -> khong tin, chay het.
        chosen, forced = list(DOMAIN_AGENTS), list(DOMAIN_AGENTS)

    # San cung: co trieu chung nao thi agent tuong ung phai chay, du model quen.
    # Luot chay dau tien cho thay model chi giao "delivery" 2/50 lan trong khi co
    # 16 case giao tre - de mac model tu quyet la agent do gan nhu khong duoc dung.
    required: list[str] = []
    if f.delivered_late is not False:  # true hoac None (chua giao)
        required.append("delivery")
    if f.payment_row_count >= 2:
        required.append("payment")
    if f.order_status in ("canceled", "unavailable"):
        required.append("order_seller")

    for agent in required:
        if agent not in chosen:
            chosen.append(agent)
            forced.append(agent)

    focus = out.get("focus")
    return DispatchPlan(
        dispatch=chosen,
        focus=focus if focus in ("order_status", "delivery", "payment") else "unknown",
        forced_back=forced,
        notes=str(out.get("notes", ""))[:300],
        llm_ok=True,
    )


SUMMARY_SYSTEM = f"""{JSON_RULE}

Vai tro cua ban: Coordinator - tong hop ket qua cuoi cung cho ho so.
Ban da nhan ket luan da duoc xac minh. KHONG duoc doi ket luan, KHONG doi so tien.
Chi viet mot cau tieng Viet ngan gon giai thich cho khach hang vi sao co ket luan do.

Tra ve JSON dung dang:
{{"summary": "<mot cau tieng Viet>"}}
"""


def summarize(f: CaseFacts, primary_issue: str, refund_brl: float) -> str:
    """Tong hop cuoi cung (README muc 7: Coordinator 'tong hop output')."""
    out = call_json(
        SUMMARY_SYSTEM,
        f"order_id={f.claimed_order_id}\n"
        f"primary_issue={primary_issue}\n"
        f"recommended_refund_brl={refund_brl}\n"
        f"order_status={f.order_status}\n"
        f"delivered_late={f.delivered_late}\n"
        f"carrier_handoff_late={f.carrier_handoff_late}\n",
    )
    if out and isinstance(out.get("summary"), str):
        return out["summary"][:300]
    return f"{primary_issue}: hoan {refund_brl:.2f} BRL."
