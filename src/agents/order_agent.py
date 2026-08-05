"""Order & Seller Agent voi Tool Calling (P2)."""
import json
import os
from src.llm_client import get_client
from src.schemas import CaseFacts, OrderSellerVerdict
from src import config
from src.tools.order_tools import get_order_details

def run(f: CaseFacts, use_llm: bool = True) -> OrderSellerVerdict:
    oid = f.claimed_order_id
    
    # Deterministic fallback
    verdict = OrderSellerVerdict(
        agent="order_seller",
        order_status=f.order_status,
        has_items=len(f.items) > 0,
        item_ids=[f"{oid}:{i.order_item_id}" for i in f.items],
        seller_ids=f.seller_ids,
        breaching_seller_ids=f.late_seller_ids,
        evidence_ids=[f"order:{oid}"] if f.order_found else [],
        notes="fallback deterministic",
        llm_ok=False,
    )
    
    if not f.order_found or not use_llm:
        verdict.notes = "khong the chay LLM hoac order_found=False"
        return verdict

    # Load prompt
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "order_agent.txt")
    with open(prompt_path, "r", encoding="utf-8") as file:
        system_prompt = file.read()

    client = get_client()
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_order_details",
                "description": "Lấy thông tin chi tiết của đơn hàng từ CSDL (item_total, freight_total, sellers, items).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "Mã đơn hàng (order_id) cần tra cứu."
                        }
                    },
                    "required": ["order_id"]
                }
            }
        }
    ]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Hãy phân tích đơn hàng: {oid}"}
    ]

    try:
        # Vong 1: LLM quyet dinh goi tool
        resp1 = client.chat.completions.create(
            model=config.MODEL_NAME,
            temperature=0.0,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=500
        )
        msg1 = resp1.choices[0].message
        
        msg1_dict = {"role": "assistant", "content": msg1.content}
        if msg1.tool_calls:
            msg1_dict["tool_calls"] = [
                {
                    "id": t.id,
                    "type": "function",
                    "function": {
                        "name": t.function.name,
                        "arguments": t.function.arguments
                    }
                } for t in msg1.tool_calls
            ]
        messages.append(msg1_dict)

        # Kiem tra xem co goi tool khong
        if msg1.tool_calls:
            for tool_call in msg1.tool_calls:
                if tool_call.function.name == "get_order_details":
                    args = json.loads(tool_call.function.arguments)
                    tool_result = get_order_details(args.get("order_id", oid))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": tool_result
                    })
            
            # Vong 2: LLM tra ve ket qua JSON dua tren tool output
            resp2 = client.chat.completions.create(
                model=config.MODEL_NAME,
                temperature=0.0,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=500
            )
            final_text = resp2.choices[0].message.content or ""
            
            try:
                out = json.loads(final_text)
                verdict.order_status = out.get("order_status", f.order_status)
                verdict.breaching_seller_ids = out.get("breaching_seller_ids", f.late_seller_ids)
                verdict.evidence_ids = out.get("evidence_ids", [])
                
                # Cap nhat nguoc lai CaseFacts tu ket qua Parse (nhu yeu cau)
                if "item_total" in out:
                    f.item_total_brl = float(out["item_total"])
                if "freight_total" in out:
                    f.freight_total_brl = float(out["freight_total"])
                    
                verdict.notes = "LLM used Tool Calling successfully."
                verdict.llm_ok = True
                
            except json.JSONDecodeError:
                verdict.notes = "LLM final output is not valid JSON."
        else:
            verdict.notes = "LLM did not call any tools."
            
    except Exception as e:
        verdict.notes = f"LLM error: {str(e)}"

    return verdict
