from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class ReviewAnomalyRequest(BaseModel):
    review_notes: Optional[str] = None


class InvoiceAnomalyResponse(BaseModel):
    id: Optional[int] = None
    invoice_id: int
    invoice_number: str
    vendor_name: str
    invoice_date: date
    total_amount: Decimal
    currency: str = "USD"
    is_anomaly: bool
    anomaly_score: float
    status: str  # "POTENTIALLY_UNUSUAL" | "NO_UNUSUAL_PATTERN"
    risk_level: str = "LOW"  # "LOW" | "MEDIUM" | "HIGH"
    is_reviewed: bool = False
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    rule_warnings: List[str] = []
    explanation: str
    model_version: str
    assessed_at: datetime

    model_config = {"from_attributes": True}


class AnomalySummaryResponse(BaseModel):
    status: str  # "COMPLETED" | "INSUFFICIENT_DATA" | "ERROR" | "NOT_ASSESSED"
    message: str
    total_invoices: int
    assessed_count: int
    anomalous_count: int
    normal_count: int
    reviewed_count: int = 0
    unreviewed_anomalous_count: int = 0
    min_required: int
    disclaimer: str
    items: List[InvoiceAnomalyResponse]
