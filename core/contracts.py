import os
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class Customer(BaseModel):
    customer_id: str
    customer_unique_id: str
    customer_zip_code_prefix: int
    customer_city: str
    customer_state: str

class Order(BaseModel):
    order_id: str
    customer_id: str
    order_status: str
    order_purchase_timestamp: str
    order_approved_at: Optional[str] = None
    order_delivered_carrier_date: Optional[str] = None
    order_delivered_customer_date: Optional[str] = None
    order_estimated_delivery_date: Optional[str] = None

class OrderItem(BaseModel):
    order_id: str
    order_item_id: int
    product_id: str
    seller_id: str
    shipping_limit_date: str
    price: float
    freight_value: float

class Payment(BaseModel):
    order_id: str
    payment_sequential: int
    payment_type: str
    payment_installments: int
    payment_value: float

class Seller(BaseModel):
    seller_id: str
    seller_zip_code_prefix: int
    seller_city: str
    seller_state: str

class CaseFacts(BaseModel):
    """
    Standardized dataclass representing all verified facts about a single order.
    Agents consume this instead of querying raw DataFrames.
    """
    case_id: str  # Input JSON's case_id (e.g., EC_001)
    customer_request_message: str  # The message from the customer
    order: Order
    customer: Customer
    items: List[OrderItem] = Field(default_factory=list)
    payments: List[Payment] = Field(default_factory=list)
    sellers: Dict[str, Seller] = Field(default_factory=dict)
