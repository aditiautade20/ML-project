from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class LineItemCandidate(BaseModel):
    item_number: Optional[str] = None
    description: str
    hsn_sac: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    line_total: Optional[Decimal] = None


class InvoiceCandidateFields(BaseModel):
    # Core Identification
    invoice_number: Optional[str] = None
    invoice_type: Optional[str] = None

    # Vendor / Seller Details
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    vendor_state: Optional[str] = None
    vendor_state_code: Optional[str] = None
    vendor_gstin: Optional[str] = None

    # Customer / Buyer Details
    customer_name: Optional[str] = None
    customer_billing_address: Optional[str] = None
    customer_shipping_address: Optional[str] = None
    customer_state: Optional[str] = None
    customer_state_code: Optional[str] = None
    customer_gstin: Optional[str] = None
    place_of_supply: Optional[str] = None

    # Dates & Terms
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    payment_terms: Optional[str] = None
    po_number: Optional[str] = None
    reference_number: Optional[str] = None
    payment_status: Optional[str] = None

    # Financial Breakdown
    subtotal: Optional[Decimal] = None
    discounts: Optional[Decimal] = None
    taxable_amount: Optional[Decimal] = None
    tax_rate: Optional[str] = None
    tax_amount: Optional[Decimal] = None
    cgst: Optional[Decimal] = None
    sgst: Optional[Decimal] = None
    igst: Optional[Decimal] = None
    other_charges: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    calculated_total: Optional[Decimal] = None
    currency: Optional[str] = "USD"

    # Line Items
    line_items: List[LineItemCandidate] = Field(default_factory=list)

    # Raw Text & Confidence
    raw_text: Optional[str] = None
    notes: Optional[str] = None
    field_confidence: Dict[str, str] = Field(default_factory=dict)


class InvoiceUploadResponse(BaseModel):
    file_token: str = Field(..., description="Safe server-side file token for the uploaded invoice")
    file_name: str = Field(..., description="Original client-supplied file name")
    file_content_type: str
    file_size_bytes: int
    candidate_fields: InvoiceCandidateFields
    raw_text: Optional[str] = None
    extraction_notes: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)


class InvoiceCreateRequest(BaseModel):
    invoice_number: str = Field(..., min_length=1, max_length=100)
    vendor_name: str = Field(..., min_length=1, max_length=255)
    customer_name: Optional[str] = Field(None, max_length=255)
    invoice_date: date
    due_date: Optional[date] = None
    subtotal: Optional[Decimal] = Field(None, ge=0)
    tax_amount: Optional[Decimal] = Field(None, ge=0)
    total_amount: Decimal = Field(..., gt=0, description="Total amount must be greater than zero")
    currency: str = Field(default="USD", max_length=10)
    status: Optional[str] = Field(None, max_length=50, description="Review status: CONFIRMED, NEEDS_REVIEW, etc.")
    file_token: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("invoice_number", "vendor_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field cannot be empty or whitespace only.")
        return trimmed

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.strip().upper() if v else "USD"


class InvoiceUpdateRequest(BaseModel):
    invoice_number: Optional[str] = Field(None, min_length=1, max_length=100)
    vendor_name: Optional[str] = Field(None, min_length=1, max_length=255)
    customer_name: Optional[str] = Field(None, max_length=255)
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    subtotal: Optional[Decimal] = Field(None, ge=0)
    tax_amount: Optional[Decimal] = Field(None, ge=0)
    total_amount: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = Field(None, max_length=10)
    status: Optional[str] = Field(None, max_length=50, description="Review status: CONFIRMED, NEEDS_REVIEW, etc.")
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("invoice_number", "vendor_name")
    @classmethod
    def strip_whitespace_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Field cannot be empty or whitespace only.")
            return trimmed
        return v


class InvoiceResponse(BaseModel):
    id: int
    user_id: int
    invoice_number: str
    vendor_name: str
    customer_name: Optional[str] = None
    invoice_date: date
    due_date: Optional[date]
    subtotal: Optional[Decimal]
    tax_amount: Optional[Decimal]
    total_amount: Decimal
    currency: str
    status: str
    file_name: Optional[str]
    file_content_type: Optional[str]
    has_file: bool = False
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Calculated Financial Properties (Stage 4 & Stage 8)
    total_paid: Decimal = Decimal("0.00")
    amount_paid: Decimal = Decimal("0.00")
    verified_paid: Decimal = Decimal("0.00")
    unverified_paid: Decimal = Decimal("0.00")
    balance_due: Decimal = Decimal("0.00")
    payment_status: str = "UNPAID"
    granular_status: Optional[str] = None
    actual_payment_date: Optional[date] = None
    days_late: Optional[int] = None
    days_overdue: Optional[int] = None
    days_remaining: Optional[int] = None
    evidence_source: Optional[str] = None
    matched_reference: Optional[str] = None
    mismatch_reason: Optional[str] = None
    reconciliation_status: Optional[str] = None

    # ML Anomaly Screening Properties (Stage 5)
    anomaly_status: Optional[str] = None
    anomaly_explanation: Optional[str] = None

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    items: List[InvoiceResponse]
    total: int
    page: int
    per_page: int
    pages: int


class InvoiceDeadlinesSummaryResponse(BaseModel):
    overdue: List[InvoiceResponse]
    due_today: List[InvoiceResponse]
    due_within_7_days: List[InvoiceResponse]
    due_later: List[InvoiceResponse]
    settled: List[InvoiceResponse] = Field(default_factory=list)

    overdue_count: int
    overdue_total: Decimal
    due_today_count: int
    due_today_total: Decimal
    due_within_7_days_count: int
    due_within_7_days_total: Decimal
    settled_count: int = 0
    total_outstanding_amount: Decimal
