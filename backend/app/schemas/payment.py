from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class PaymentCreateRequest(BaseModel):
    invoice_id: int = Field(..., gt=0, description="Target invoice ID")
    amount: Decimal = Field(..., gt=0, description="Payment amount must be greater than zero")
    payment_date: date = Field(..., description="Date payment was executed")
    payment_method: str = Field(default="Bank Transfer", min_length=1, max_length=50)
    reference: Optional[str] = Field(None, max_length=100, description="Transaction or check reference number")
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("payment_method")
    @classmethod
    def clean_payment_method(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            return "Bank Transfer"
        return trimmed


class PaymentUpdateRequest(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0)
    payment_date: Optional[date] = None
    payment_method: Optional[str] = Field(None, min_length=1, max_length=50)
    reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=1000)


class PaymentResponse(BaseModel):
    id: int
    invoice_id: int
    user_id: int
    amount: Decimal
    payment_date: date
    payment_method: str
    reference: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Associated invoice details for display in payment lists
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    currency: Optional[str] = "USD"

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    items: List[PaymentResponse]
    total: int
    page: int
    per_page: int
    pages: int
    total_amount_recorded: Decimal


class InvoicePaymentSummaryResponse(BaseModel):
    invoice_id: int
    invoice_number: str
    vendor_name: str
    currency: str
    invoice_total: Decimal
    total_paid: Decimal
    amount_paid: Decimal = Decimal("0.00")
    balance_due: Decimal
    payment_status: str
    due_date: Optional[date]
    payments: List[PaymentResponse]
