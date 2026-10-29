from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class FilePreviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filename: str
    file_type: str
    headers: List[str]
    total_rows: int
    sample_rows: List[Dict[str, Any]]
    suggested_mapping: Dict[str, str]
    mapping_statuses: Dict[str, str] = Field(default_factory=dict)
    mapping_warnings: Dict[str, str] = Field(default_factory=dict)
    ambiguous_columns: Dict[str, List[str]] = Field(default_factory=dict)
    file_hash: str
    is_duplicate_hash: bool = False
    validation_warnings: List[str] = Field(default_factory=list)


class ReconciliationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    item_type: str
    match_status: str
    record_identifier: str
    vendor_or_counterparty: Optional[str] = None
    transaction_date: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    discrepancy_amount: Optional[Decimal] = None
    currency: str = "USD"
    evidence_text: Optional[str] = None
    action_recommendation: Optional[str] = None
    review_status: str
    invoice_id: Optional[int] = None
    payment_id: Optional[int] = None
    created_at: datetime


class ReconciliationBatchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_type: str
    title: str
    status: str
    ledger_filename: Optional[str] = None
    bank_filename: Optional[str] = None
    total_records: int
    exact_matches: int
    mismatches: int
    unmatched_records: int
    amount_tolerance: Decimal
    created_at: datetime


class ReconciliationBatchDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_type: str
    title: str
    status: str
    ledger_filename: Optional[str] = None
    bank_filename: Optional[str] = None
    total_records: int
    exact_matches: int
    mismatches: int
    unmatched_records: int
    amount_tolerance: Decimal
    created_at: datetime
    summary: Dict[str, Any] = Field(default_factory=dict)
    items: List[ReconciliationItemResponse] = Field(default_factory=list)


class ConfirmPaymentActionRequest(BaseModel):
    payment_method: str = Field(default="Bank Transfer", max_length=50)
    payment_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=500)


class UpdateItemStatusRequest(BaseModel):
    review_status: str = Field(..., pattern="^(CONFIRMED|DISMISSED|PENDING)$")
