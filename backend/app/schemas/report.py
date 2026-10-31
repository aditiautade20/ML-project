from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class MonthlyTrendItem(BaseModel):
    month_key: str  # "YYYY-MM"
    month_label: str  # "May 2026"
    invoiced_amount: Decimal
    invoiced_count: int
    paid_amount: Decimal
    paid_count: int


class RecentInvoiceItem(BaseModel):
    id: int
    invoice_number: str
    vendor_name: str
    invoice_date: date
    due_date: Optional[date] = None
    total_amount: Decimal
    currency: str
    payment_status: str
    balance_due: Decimal
    verification_status: Optional[str] = "CONFIRMED"


class RecentPaymentItem(BaseModel):
    id: int
    invoice_id: int
    invoice_number: str
    vendor_name: str
    amount: Decimal
    currency: Optional[str] = "USD"
    payment_date: date
    payment_method: str
    reference: Optional[str] = None


class ReconciliationSummaryItem(BaseModel):
    total_batches: int = 0
    total_records: int = 0
    matched_count: int = 0
    mismatch_count: int = 0
    missing_count: int = 0
    duplicate_count: int = 0
    pending_review_count: int = 0


class DashboardAnalyticsResponse(BaseModel):
    total_invoices_count: int
    total_invoiced_amount: Decimal
    total_paid_amount: Decimal
    total_outstanding_balance: Decimal
    overdue_count: int
    overdue_amount: Decimal
    due_within_7_days_count: int
    due_within_7_days_amount: Decimal
    anomalous_invoices_count: int
    mismatches_count: int = 0
    upcoming_due_dates_count: int = 0
    verified_invoices_count: int = 0
    needs_review_count: int = 0
    nearest_due_date: Optional[date] = None
    currency: str = "USD"
    has_multiple_currencies: bool = False
    by_currency: Optional[dict] = None
    status_counts: Optional[Dict[str, int]] = None
    monthly_trends: List[MonthlyTrendItem]
    recent_invoices: List[RecentInvoiceItem]
    recent_payments: List[RecentPaymentItem]
    reconciliation_summary: Optional[ReconciliationSummaryItem] = None


class VendorSummaryItem(BaseModel):
    vendor_name: str
    invoice_count: int
    total_invoiced: Decimal
    total_paid: Decimal
    outstanding_balance: Decimal
    overdue_count: int


class ReportInvoiceItem(BaseModel):
    id: int
    invoice_number: str
    vendor_name: str
    invoice_date: date
    due_date: Optional[date] = None
    currency: str = "USD"
    subtotal: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    total_amount: Decimal
    total_paid: Decimal
    balance_due: Decimal
    payment_status: str
    verification_status: Optional[str] = "CONFIRMED"
    notes: Optional[str] = None
    anomaly_status: Optional[str] = None
    anomaly_explanation: Optional[str] = None


class ReportPaymentItem(BaseModel):
    id: int
    payment_date: date
    invoice_number: str
    vendor_name: str
    amount: Decimal
    currency: str = "USD"
    payment_method: str
    reference: Optional[str] = None
    notes: Optional[str] = None


class ReconciliationSummaryItem(BaseModel):
    total_batches: int = 0
    total_records: int = 0
    matched_count: int = 0
    mismatch_count: int = 0
    missing_count: int = 0
    duplicate_count: int = 0
    pending_review_count: int = 0


class ReportReconciliationItem(BaseModel):
    id: int
    batch_title: str
    batch_type: str
    record_identifier: str
    counterparty: Optional[str] = None
    transaction_date: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    discrepancy_amount: Optional[Decimal] = None
    currency: str = "USD"
    match_status: str
    evidence_text: Optional[str] = None
    invoice_id: Optional[int] = None


class ReportSummary(BaseModel):
    period_label: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_invoices_count: int
    total_invoiced_amount: Decimal
    total_payments_count: int
    total_paid_amount: Decimal
    total_outstanding_balance: Decimal
    overdue_count: int
    overdue_amount: Decimal
    anomalous_count: int
    currency: str = "USD"
    has_multiple_currencies: bool = False
    by_currency: Optional[dict] = None
    status_counts: Optional[Dict[str, int]] = None


class ReportsDataResponse(BaseModel):
    summary: ReportSummary
    vendor_breakdown: List[VendorSummaryItem]
    monthly_trends: List[MonthlyTrendItem]
    invoices: List[ReportInvoiceItem] = []
    payments: List[ReportPaymentItem] = []
    reconciliation_summary: Optional[ReconciliationSummaryItem] = None
    reconciliation_items: List[ReportReconciliationItem] = []
