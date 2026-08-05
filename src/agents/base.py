"""Tien ich dung chung cho cac agent.

Quy uoc quan trong cho ca nhom:
  - Agent NHAN facts da trich san, KHONG tu doc CSV.
  - Agent KHONG tinh tien, KHONG so sanh ngay bang LLM. Python da tinh san trong
    CaseFacts; agent chi doc ket qua va suy luan/quy trach nhiem.
  - Agent KHONG BAO GIO raise. LLM hong -> fallback deterministic, set llm_ok=False.
"""

import json

from ..schemas import CaseFacts

JSON_RULE = (
    "Ban la mot agent trong he thong xu ly khieu nai thuong mai dien tu. "
    "CHI tra ve mot JSON object hop le, khong markdown, khong giai thich ngoai JSON. "
    "Chi dung du kien co trong input. TUYET DOI khong bia order_id, item_id, "
    "seller_id hay su kien khong xuat hien trong du lieu."
)


def facts_brief(f: CaseFacts) -> str:
    """Rut gon CaseFacts thanh JSON nho cho prompt - model <= 10B de lac khi input dai."""
    return json.dumps(
        {
            "order_id": f.claimed_order_id,
            "order_found": f.order_found,
            "order_status": f.order_status,
            "delivered_carrier_date": f.order_delivered_carrier_date,
            "delivered_customer_date": f.order_delivered_customer_date,
            "estimated_delivery_date": f.order_estimated_delivery_date,
            "item_count": len(f.items),
            "items": [
                {
                    "order_item_id": i.order_item_id,
                    "seller_id": i.seller_id,
                    "shipping_limit_date": i.shipping_limit_date,
                    "handoff_after_limit": i.handoff_after_limit,
                }
                for i in f.items
            ],
            "payment_row_count": f.payment_row_count,
            "item_total_brl": f.item_total_brl,
            "freight_total_brl": f.freight_total_brl,
            "payment_total_brl": f.payment_total_brl,
            "payment_diff_brl": f.payment_diff_brl,
            "payment_matches": f.payment_matches,
            "delivered_late": f.delivered_late,
            "carrier_handoff_late": f.carrier_handoff_late,
            "late_seller_ids": f.late_seller_ids,
        },
        ensure_ascii=False,
    )
