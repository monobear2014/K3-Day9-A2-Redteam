"""Order & Seller Agent.

OWNER: P2

Nhiem vu: xac dinh trang thai don, cac item, seller trong don, va SELLER NAO
ban giao qua shipping_limit_date. Handoff ket qua sang Policy Agent.

TODO(P2): tinh chinh prompt. Cho vai case that vao rồi xem model co chon dung
breaching seller khong. Neu model hay nham, them 1-2 vi du ngan vao SYSTEM.
"""

from ..llm_client import call_json
from ..schemas import CaseFacts, OrderSellerVerdict
from .base import JSON_RULE, facts_brief

SYSTEM = f"""{JSON_RULE}

Vai tro cua ban: Order & Seller Analyst.
Doc du lieu don hang da duoc trich san va tra loi:
- Don o trang thai gi (delivered / canceled / unavailable / khac).
- Seller nao ban giao hang tre? Chi ke seller co "handoff_after_limit": true.

Truong "handoff_after_limit" DA duoc he thong tinh san. Dung tu tinh lai ngay thang.

Tra ve JSON dung dang:
{{"order_status": "<chuoi>", "breaching_seller_ids": ["<seller_id>"], "notes": "<mot cau tieng Viet>"}}
"""


def run(f: CaseFacts, use_llm: bool = True) -> OrderSellerVerdict:
    oid = f.claimed_order_id
    item_ids = [f"{oid}:{i.order_item_id}" for i in f.items]

    # Ket qua deterministic - dung lam fallback va lam moc doi chieu.
    verdict = OrderSellerVerdict(
        order_status=f.order_status,
        has_items=len(f.items) > 0,
        item_ids=item_ids,
        seller_ids=f.seller_ids,
        breaching_seller_ids=f.late_seller_ids,
        evidence_ids=[f"order:{oid}"] if f.order_found else [],
        notes="fallback deterministic",
        llm_ok=False,
    )

    if not f.order_found:
        verdict.notes = "Khong tim thay order trong CSV."
        return verdict
    if not use_llm:
        # Coordinator khong dispatch agent nay -> giu ket qua deterministic.
        verdict.notes = "khong duoc dispatch; dung ket qua deterministic"
        return verdict

    out = call_json(SYSTEM, facts_brief(f))
    if not out:
        return verdict

    # Chi nhan seller_id CO THAT trong don - chan model bia ID.
    claimed = [s for s in out.get("breaching_seller_ids", []) if s in f.seller_ids]
    verdict.breaching_seller_ids = claimed or f.late_seller_ids
    verdict.notes = str(out.get("notes", ""))[:300]
    verdict.llm_ok = True
    return verdict
