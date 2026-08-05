import os
import pandas as pd
import math
from typing import Dict, Any

from core.contracts import Customer, Order, OrderItem, Payment, Seller, CaseFacts

class DataLoader:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.load_data()

    def _read_csv(self, filename: str) -> pd.DataFrame:
        return pd.read_csv(os.path.join(self.data_dir, filename))
    
    def _clean_nan(self, val: Any) -> Any:
        if pd.isna(val):
            return None
        return str(val)

    def load_data(self):
        # Read CSVs
        self.orders_df = self._read_csv('olist_orders_dataset.csv')
        self.customers_df = self._read_csv('olist_customers_dataset.csv')
        self.order_items_df = self._read_csv('olist_order_items_dataset.csv')
        self.payments_df = self._read_csv('olist_order_payments_dataset.csv')
        self.sellers_df = self._read_csv('olist_sellers_dataset.csv')

        # Index DataFrames for fast O(1) lookups
        self.orders_idx = self.orders_df.set_index('order_id')
        self.customers_idx = self.customers_df.set_index('customer_id')
        self.sellers_idx = self.sellers_df.set_index('seller_id')
        
        # Group by order_id for items and payments
        # We store these as dictionaries of DataFrames or dicts for fast access
        # Since we just want fast query, grouping to dict of records is very efficient
        
        # Order items
        self.items_by_order = {}
        for order_id, group in self.order_items_df.groupby('order_id'):
            self.items_by_order[order_id] = group.to_dict('records')
            
        # Order payments
        self.payments_by_order = {}
        for order_id, group in self.payments_df.groupby('order_id'):
            self.payments_by_order[order_id] = group.to_dict('records')

    def get_case_facts(self, case_id: str, request_message: str, order_id: str) -> CaseFacts:
        """
        Extract all relevant data for a given order_id and construct a CaseFacts object.
        """
        if order_id not in self.orders_idx.index:
            raise ValueError(f"Order ID {order_id} not found in database.")
            
        order_row = self.orders_idx.loc[order_id]
        customer_id = order_row['customer_id']
        
        # Build Order
        order = Order(
            order_id=order_id,
            customer_id=customer_id,
            order_status=self._clean_nan(order_row.get('order_status')),
            order_purchase_timestamp=self._clean_nan(order_row.get('order_purchase_timestamp')),
            order_approved_at=self._clean_nan(order_row.get('order_approved_at')),
            order_delivered_carrier_date=self._clean_nan(order_row.get('order_delivered_carrier_date')),
            order_delivered_customer_date=self._clean_nan(order_row.get('order_delivered_customer_date')),
            order_estimated_delivery_date=self._clean_nan(order_row.get('order_estimated_delivery_date'))
        )
        
        # Build Customer
        if customer_id in self.customers_idx.index:
            cust_row = self.customers_idx.loc[customer_id]
            customer = Customer(
                customer_id=customer_id,
                customer_unique_id=self._clean_nan(cust_row.get('customer_unique_id')),
                customer_zip_code_prefix=int(cust_row.get('customer_zip_code_prefix', 0)),
                customer_city=self._clean_nan(cust_row.get('customer_city')),
                customer_state=self._clean_nan(cust_row.get('customer_state'))
            )
        else:
            raise ValueError(f"Customer ID {customer_id} not found.")

        # Build Items & collect Seller IDs
        items = []
        seller_ids = set()
        for item_dict in self.items_by_order.get(order_id, []):
            items.append(OrderItem(
                order_id=order_id,
                order_item_id=int(item_dict['order_item_id']),
                product_id=str(item_dict['product_id']),
                seller_id=str(item_dict['seller_id']),
                shipping_limit_date=self._clean_nan(item_dict['shipping_limit_date']),
                price=float(item_dict['price']),
                freight_value=float(item_dict['freight_value'])
            ))
            seller_ids.add(str(item_dict['seller_id']))

        # Build Payments
        payments = []
        for p_dict in self.payments_by_order.get(order_id, []):
            payments.append(Payment(
                order_id=order_id,
                payment_sequential=int(p_dict['payment_sequential']),
                payment_type=str(p_dict['payment_type']),
                payment_installments=int(p_dict['payment_installments']),
                payment_value=float(p_dict['payment_value'])
            ))

        # Build Sellers
        sellers = {}
        for sid in seller_ids:
            if sid in self.sellers_idx.index:
                s_row = self.sellers_idx.loc[sid]
                sellers[sid] = Seller(
                    seller_id=sid,
                    seller_zip_code_prefix=int(s_row.get('seller_zip_code_prefix', 0)),
                    seller_city=self._clean_nan(s_row.get('seller_city')),
                    seller_state=self._clean_nan(s_row.get('seller_state'))
                )

        return CaseFacts(
            case_id=case_id,
            customer_request_message=request_message,
            order=order,
            customer=customer,
            items=items,
            payments=payments,
            sellers=sellers
        )
