"""Contract dung chung giua cac agent.

DAY LA FILE PHAI DONG BANG TRUOC KHI CA NHOM CODE SONG SONG.
Sua field o day = pha code cua 4 nguoi con lai, nen bao ca nhom truoc khi doi.

Luong: CaseFacts (Python trich xuat, khong qua LLM)
         -> OrderSellerVerdict / PaymentVerdict / DeliveryVerdict  (LLM)
         -> PolicyVerdict                                          (LLM)
         -> CaseOutput                                             (Verifier chot)
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from . import config

PrimaryIssue = Literal[
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
]

RootCauseCode = Literal[
    "SELLER_HANDOFF_AFTER_LIMIT",
    "CARRIER_DELIVERED_AFTER_ESTIMATE",
    "ORDER_CANCELED_AFTER_PAYMENT",
    "ORDER_UNAVAILABLE_AFTER_PAYMENT",
    "MULTIPLE_PAYMENTS_RECONCILED",
    "DELIVERY_WITHIN_ESTIMATE",
]

ResolutionAction = Literal[
    "issue_full_refund",
    "refund_freight",
    "explain_valid_split_payment",
    "reject_late_refund",
]

PartyType = Literal["platform", "seller", "logistics_provider"]


# =====================================================================
# 1. FACTS - Python trich tu CSV. Khong con so nao trong day do LLM tinh.
# =====================================================================
class ItemFact(BaseModel):
    order_item_id: int
    product_id: str
    seller_id: str
    shipping_limit_date: Optional[str]
    price: float
    freight_value: float
    # Python tinh san, agent chi doc:
    handoff_after_limit: Optional[bool] = None


class PaymentFact(BaseModel):
    payment_sequential: int
    payment_type: str
    payment_installments: int
    payment_value: float


class CaseFacts(BaseModel):
    """Toan bo su that kiem chung duoc cua mot case. Do data_loader dung."""

    case_id: str
    claimed_order_id: str
    customer_message: str = ""

    order_found: bool
    order_status: Optional[str] = None
    order_purchase_timestamp: Optional[str] = None
    order_approved_at: Optional[str] = None
    order_delivered_carrier_date: Optional[str] = None
    order_delivered_customer_date: Optional[str] = None
    order_estimated_delivery_date: Optional[str] = None

    items: list[ItemFact] = Field(default_factory=list)
    payments: list[PaymentFact] = Field(default_factory=list)

    # --- Tong hop, da lam tron 2 chu so ---
    item_total_brl: float = 0.0
    freight_total_brl: float = 0.0
    payment_total_brl: float = 0.0
    payment_row_count: int = 0
    payment_diff_brl: float = 0.0
    payment_matches: bool = False

    # --- So sanh ngay, Python quyet dinh ---
    delivered_late: Optional[bool] = None
    carrier_handoff_late: Optional[bool] = None
    late_seller_ids: list[str] = Field(default_factory=list)
    seller_ids: list[str] = Field(default_factory=list)


# =====================================================================
# 2. VERDICT - moi agent tra ve mot cai. Day la don vi handoff.
# =====================================================================
class BaseVerdict(BaseModel):
    agent: str
    notes: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    llm_ok: bool = True  # False = LLM fail, da fallback sang deterministic


class DispatchPlan(BaseVerdict):
    """Ke hoach giao viec do Coordinator Agent quyet dinh (README muc 7: 'giao viec')."""

    agent: str = "coordinator"
    dispatch: list[Literal["order_seller", "payment", "delivery"]] = Field(
        default_factory=list
    )
    focus: Literal["order_status", "delivery", "payment", "unknown"] = "unknown"
    forced_back: list[str] = Field(default_factory=list)  # Python bo sung lai


class OrderSellerVerdict(BaseVerdict):
    agent: str = "order_seller"
    order_status: Optional[str] = None
    has_items: bool = False
    item_ids: list[str] = Field(default_factory=list)  # "<order_id>:<order_item_id>"
    seller_ids: list[str] = Field(default_factory=list)
    breaching_seller_ids: list[str] = Field(default_factory=list)


class PaymentVerdict(BaseVerdict):
    agent: str = "payment"
    payment_ids: list[str] = Field(default_factory=list)  # "<order_id>:<sequential>"
    is_split_payment: bool = False
    reconciled: bool = False


class DeliveryVerdict(BaseVerdict):
    agent: str = "delivery"
    delivered_late: Optional[bool] = None
    attribution: Literal["seller", "logistics_provider", "none"] = "none"


class ResponsibleParty(BaseModel):
    party_type: PartyType
    party_id: str


class RankedCause(BaseModel):
    cause_code: RootCauseCode
    rank: int


class PolicyVerdict(BaseVerdict):
    agent: str = "policy"
    primary_issue: PrimaryIssue
    case_status: Literal["action_required", "no_action"]
    ranked_causes: list[RankedCause] = Field(default_factory=list)
    responsible_parties: list[ResponsibleParty] = Field(default_factory=list)
    recommended_refund_brl: float = 0.0
    resolution_actions: list[ResolutionAction] = Field(default_factory=list)
    confidence: float = Field(default=0.80, ge=0.0, le=1.0)


# =====================================================================
# 3. OUTPUT - dung schema README muc 6. Validator chan hard gate.
# =====================================================================
class Assessment(BaseModel):
    primary_issue: PrimaryIssue
    case_status: Literal["action_required", "no_action"]
    confidence: float = Field(ge=0.0, le=1.0)


class AffectedEntities(BaseModel):
    order_ids: list[str] = Field(default_factory=list)
    item_ids: list[str] = Field(default_factory=list)
    seller_ids: list[str] = Field(default_factory=list)
    payment_ids: list[str] = Field(default_factory=list)

    @field_validator("order_ids", "item_ids", "seller_ids", "payment_ids")
    @classmethod
    def _cap(cls, v: list[str]) -> list[str]:
        return v[: config.MAX_IDS_PER_ENTITY]


class RootCauseAnalysis(BaseModel):
    ranked_causes: list[RankedCause] = Field(default_factory=list)
    responsible_parties: list[ResponsibleParty] = Field(default_factory=list)

    @field_validator("ranked_causes")
    @classmethod
    def _cap_causes(cls, v: list[RankedCause]) -> list[RankedCause]:
        return v[: config.MAX_ROOT_CAUSES]

    @field_validator("responsible_parties")
    @classmethod
    def _cap_parties(cls, v: list[ResponsibleParty]) -> list[ResponsibleParty]:
        return v[: config.MAX_RESPONSIBLE_PARTIES]


class FinancialResolution(BaseModel):
    currency: Literal["BRL"] = "BRL"
    item_total_brl: float
    freight_total_brl: float
    payment_total_brl: float
    recommended_refund_brl: float


class CaseOutput(BaseModel):
    case_id: str
    assessment: Assessment
    affected_entities: AffectedEntities
    root_cause_analysis: RootCauseAnalysis
    evidence_ids: list[str] = Field(default_factory=list)
    financial_resolution: FinancialResolution
    resolution_actions: list[ResolutionAction] = Field(default_factory=list)

    @field_validator("evidence_ids")
    @classmethod
    def _cap_evidence(cls, v: list[str]) -> list[str]:
        return v[: config.MAX_EVIDENCE]

    @field_validator("resolution_actions")
    @classmethod
    def _cap_actions(cls, v: list[ResolutionAction]) -> list[ResolutionAction]:
        return v[: config.MAX_ACTIONS]

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
