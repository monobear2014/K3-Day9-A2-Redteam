"""Nap 9 file CSV va trich CaseFacts cho tung order.

OWNER: P1 (Data & Contracts)

Nguyen tac: TAT CA phep cong tien va so sanh ngay nam o day, bang Python.
Khong con so nao duoc giao cho LLM tinh - model <= 10B cong sai va so ngay sai.
"""

from datetime import datetime
from functools import lru_cache
from typing import Optional

import pandas as pd

from . import config
from .schemas import CaseFacts, ItemFact, PaymentFact

_TS_FMT = "%Y-%m-%d %H:%M:%S"


def _parse_ts(value) -> Optional[datetime]:
    """CSV timestamp -> datetime. So sanh nguyen gia tri, khong doi mui gio."""
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    try:
        return datetime.strptime(str(value).strip(), _TS_FMT)
    except ValueError:
        parsed = pd.to_datetime(value, errors="coerce")
        return None if pd.isna(parsed) else parsed.to_pydatetime()


def _ts_str(value) -> Optional[str]:
    dt = _parse_ts(value)
    return dt.strftime(_TS_FMT) if dt else None


def _money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


class OlistData:
    """Nap CSV mot lan, index theo order_id de tra cuu O(1)."""

    def __init__(self, data_dir=None):
        d = data_dir or config.DATA_DIR
        self.orders = pd.read_csv(d / "olist_orders_dataset.csv")
        self.items = pd.read_csv(d / "olist_order_items_dataset.csv")
        self.payments = pd.read_csv(d / "olist_order_payments_dataset.csv")
        self.sellers = pd.read_csv(d / "olist_sellers_dataset.csv")

        self._orders_by_id = {r["order_id"]: r for r in self.orders.to_dict("records")}
        self._items_by_order: dict[str, list[dict]] = {}
        for r in self.items.to_dict("records"):
            self._items_by_order.setdefault(r["order_id"], []).append(r)
        self._payments_by_order: dict[str, list[dict]] = {}
        for r in self.payments.to_dict("records"):
            self._payments_by_order.setdefault(r["order_id"], []).append(r)
        self._seller_ids = set(self.sellers["seller_id"].tolist())

    # ---------------------------------------------------------------
    def order_exists(self, order_id: str) -> bool:
        return order_id in self._orders_by_id

    def seller_exists(self, seller_id: str) -> bool:
        return seller_id in self._seller_ids

    def build_facts(
        self, case_id: str, order_id: str, customer_message: str = ""
    ) -> CaseFacts:
        """Trich toan bo su that kiem chung duoc cua mot case."""
        order = self._orders_by_id.get(order_id)
        if order is None:
            return CaseFacts(
                case_id=case_id,
                claimed_order_id=order_id,
                customer_message=customer_message,
                order_found=False,
            )

        raw_items = sorted(
            self._items_by_order.get(order_id, []), key=lambda r: r["order_item_id"]
        )
        raw_payments = sorted(
            self._payments_by_order.get(order_id, []),
            key=lambda r: r["payment_sequential"],
        )

        delivered_carrier = _parse_ts(order.get("order_delivered_carrier_date"))
        delivered_customer = _parse_ts(order.get("order_delivered_customer_date"))
        estimated = _parse_ts(order.get("order_estimated_delivery_date"))

        # --- Items + phat hien seller ban giao muon ---
        items: list[ItemFact] = []
        late_sellers: list[str] = []
        seller_ids: list[str] = []
        for r in raw_items:
            limit = _parse_ts(r.get("shipping_limit_date"))
            # README muc 4: seller muon neu order_delivered_carrier_date > shipping_limit_date
            handoff_late = (
                bool(delivered_carrier > limit)
                if (delivered_carrier and limit)
                else None
            )
            items.append(
                ItemFact(
                    order_item_id=int(r["order_item_id"]),
                    product_id=str(r["product_id"]),
                    seller_id=str(r["seller_id"]),
                    shipping_limit_date=_ts_str(r.get("shipping_limit_date")),
                    price=_money(r["price"]),
                    freight_value=_money(r["freight_value"]),
                    handoff_after_limit=handoff_late,
                )
            )
            sid = str(r["seller_id"])
            if sid not in seller_ids:
                seller_ids.append(sid)
            if handoff_late and sid not in late_sellers:
                late_sellers.append(sid)

        payments = [
            PaymentFact(
                payment_sequential=int(r["payment_sequential"]),
                payment_type=str(r["payment_type"]),
                payment_installments=int(r["payment_installments"]),
                payment_value=_money(r["payment_value"]),
            )
            for r in raw_payments
        ]

        item_total = _money(sum(i.price for i in items))
        freight_total = _money(sum(i.freight_value for i in items))
        payment_total = _money(sum(p.payment_value for p in payments))
        diff = _money(abs(payment_total - (item_total + freight_total)))

        delivered_late = (
            bool(delivered_customer > estimated)
            if (delivered_customer and estimated)
            else None
        )

        return CaseFacts(
            case_id=case_id,
            claimed_order_id=order_id,
            customer_message=customer_message,
            order_found=True,
            order_status=str(order.get("order_status")),
            order_purchase_timestamp=_ts_str(order.get("order_purchase_timestamp")),
            order_approved_at=_ts_str(order.get("order_approved_at")),
            order_delivered_carrier_date=_ts_str(
                order.get("order_delivered_carrier_date")
            ),
            order_delivered_customer_date=_ts_str(
                order.get("order_delivered_customer_date")
            ),
            order_estimated_delivery_date=_ts_str(
                order.get("order_estimated_delivery_date")
            ),
            items=items,
            payments=payments,
            item_total_brl=item_total,
            freight_total_brl=freight_total,
            payment_total_brl=payment_total,
            payment_row_count=len(payments),
            payment_diff_brl=diff,
            payment_matches=diff <= config.PAYMENT_TOLERANCE_BRL,
            delivered_late=delivered_late,
            carrier_handoff_late=len(late_sellers) > 0,
            late_seller_ids=late_sellers,
            seller_ids=seller_ids,
        )


@lru_cache(maxsize=1)
def get_data() -> OlistData:
    """Singleton: 50 case dung chung mot lan nap CSV."""
    return OlistData()
