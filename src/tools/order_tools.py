import json
from src.data_loader import get_data

def get_order_details(order_id: str) -> str:
    """Truy van thong tin Cung ung cua don hang (P2)."""
    data = get_data()
    # Tuong tu logic data_loader nhung xay dung rieng de lam Tool cho LLM.
    facts = data.build_facts("temp_case", order_id)
    if not facts.order_found:
        return json.dumps({"error": f"Order {order_id} not found."})
    
    items = []
    for item in facts.items:
        items.append({
            "order_item_id": item.order_item_id,
            "product_id": item.product_id,
            "seller_id": item.seller_id,
            "shipping_limit_date": item.shipping_limit_date,
            "price": item.price,
            "freight_value": item.freight_value
        })
        
    result = {
        "order_id": order_id,
        "order_status": facts.order_status,
        "items": items,
        "item_total": facts.item_total_brl,
        "freight_total": facts.freight_total_brl,
        "seller_ids": facts.seller_ids,
        "late_seller_ids": facts.late_seller_ids
    }
    return json.dumps(result, ensure_ascii=False)
