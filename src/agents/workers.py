"""Worker-agent prompts and capability boundaries.

Each worker receives only the facts that belong to its domain.  The prompts
explicitly forbid invoking or reasoning about another worker's tools; this is
the guard against domain confusion when a small model is used.
"""

from dataclasses import dataclass

from .base import JSON_RULE


@dataclass(frozen=True)
class WorkerSpec:
    """A deliberately small tool contract for one domain expert."""

    name: str
    allowed_tools: tuple[str, ...]
    system_prompt: str


DATABASE_WORKER = WorkerSpec(
    name="database_worker",
    allowed_tools=("read_order_sql",),
    system_prompt=f"""{JSON_RULE}

You are Database_Worker. Your only permitted capability is read_order_sql.
Use only supplied SQL-read facts about order status, item rows and sellers.
Never call, propose, or simulate an API; never calculate payments or delivery
dates. If a requested fact is outside these rows, say it is unavailable.
""",
)

API_WORKER = WorkerSpec(
    name="api_worker",
    allowed_tools=("call_shipping_api",),
    system_prompt=f"""{JSON_RULE}

You are API_Worker. Your only permitted capability is call_shipping_api.
Use only supplied shipping API facts. Never read SQL, invent database rows, or
reconcile payments. If the API facts do not answer the question, say so.
""",
)

ORDER_SELLER_SYSTEM = f"""{DATABASE_WORKER.system_prompt}

Act as the Order & Seller Analyst. Report the supplied order status and only
sellers whose supplied handoff_after_limit value is true. Do not recalculate
dates or mention payment/delivery conclusions.
Return: {{"order_status": "<string|null>", "breaching_seller_ids": ["<id>"], "notes": "<Vietnamese sentence>"}}"""

PAYMENT_SYSTEM = f"""{JSON_RULE}

You are Payment_Worker. Your only permitted capability is read_payment_sql.
Use only supplied payment reconciliation facts; never read order/shipping data
or recompute totals. A split payment is payment_row_count >= 2; reconciled is
the supplied payment_matches value.
Return: {{"is_split_payment": <bool>, "reconciled": <bool>, "notes": "<Vietnamese sentence>"}}"""

DELIVERY_SYSTEM = f"""{API_WORKER.system_prompt}

Act as Delivery Analyst. Use supplied delivered_late and carrier_handoff_late
only. Attribute seller only when both are true, logistics_provider only when
delivered_late is true and carrier_handoff_late is false, otherwise none.
Return: {{"attribution": "seller|logistics_provider|none", "notes": "<Vietnamese sentence>"}}"""
