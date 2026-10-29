import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, desc, asc

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.anomaly import InvoiceAnomaly
from app.models.reconciliation import ReconciliationBatch, ReconciliationItem
from app.models.user import User
from app.services.payment_service import calculate_invoice_financials


def sanitize_for_csv(val: Any) -> str:
    """
    Prevents spreadsheet formula injection (CSV Injection / DDE).
    If a value begins with '=', '+', '-', '@', '\\t', or '\\r',
    it is prepended with a single quote (') so spreadsheet applications
    treat it strictly as text.
    """
    if val is None:
        return ""
    s = str(val)
    if not s:
        return ""
    # Check if raw string or space-stripped string starts with dangerous formula prefixes
    dangerous_triggers = ("=", "+", "-", "@", "\t", "\r")
    if s[0] in dangerous_triggers or (s.lstrip(" ") and s.lstrip(" ")[0] in dangerous_triggers):
        return f"'{s}"
    return s


def format_currency_decimal(val: Any) -> str:
    """Formats numeric value to 2 decimal places safely."""
    try:
        dec = Decimal(str(val or "0.00"))
        return f"{dec:.2f}"
    except Exception:
        return "0.00"


def get_dashboard_analytics(user_id: int, db: Session) -> Dict[str, Any]:
    """
    Calculates dynamic financial summary, monthly trends, status distributions,
    and recent activity for the authenticated user strictly from database records.
    """
    today = date.today()
    next_7_days = today + timedelta(days=7)

    # 1. Fetch user's invoices with payments and anomaly relationships
    invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments), joinedload(Invoice.anomaly))
        .filter(Invoice.user_id == user_id)
        .all()
    )

    total_invoices_count = len(invoices)
    total_invoiced_amount = Decimal("0.00")
    total_paid_amount = Decimal("0.00")
    total_outstanding_balance = Decimal("0.00")

    overdue_count = 0
    overdue_amount = Decimal("0.00")
    due_within_7_days_count = 0
    due_within_7_days_amount = Decimal("0.00")
    anomalous_invoices_count = 0

    status_counts: Dict[str, int] = {
        "PAID": 0,
        "PARTIAL": 0,
        "UNPAID": 0,
        "DUE_SOON": 0,
        "OVERDUE": 0,
    }

    # Multi-currency grouping
    currencies = list({(inv.currency or "USD").upper() for inv in invoices})
    primary_currency = (
        currencies[0]
        if len(currencies) == 1
        else ("USD" if "USD" in currencies else (currencies[0] if currencies else "USD"))
    )
    has_multiple_currencies = len(currencies) > 1

    by_currency: Dict[str, Dict[str, Any]] = {}

    # Categorize and aggregate
    for inv in invoices:
        curr = (inv.currency or "USD").upper()
        if curr not in by_currency:
            by_currency[curr] = {
                "currency": curr,
                "total_invoices_count": 0,
                "total_invoiced_amount": Decimal("0.00"),
                "total_paid_amount": Decimal("0.00"),
                "total_outstanding_balance": Decimal("0.00"),
                "overdue_count": 0,
                "overdue_amount": Decimal("0.00"),
                "due_within_7_days_count": 0,
                "due_within_7_days_amount": Decimal("0.00"),
                "status_counts": {
                    "PAID": 0,
                    "PARTIAL": 0,
                    "UNPAID": 0,
                    "DUE_SOON": 0,
                    "OVERDUE": 0,
                },
            }

        total_invoiced_amount += inv.total_amount
        paid, bal, status = calculate_invoice_financials(inv, today)
        total_paid_amount += paid
        total_outstanding_balance += bal

        # Increment status distributions
        status_counts[status] = status_counts.get(status, 0) + 1

        b = by_currency[curr]
        b["total_invoices_count"] += 1
        b["total_invoiced_amount"] += inv.total_amount
        b["total_paid_amount"] += paid
        b["total_outstanding_balance"] += bal
        b["status_counts"][status] = b["status_counts"].get(status, 0) + 1

        if status == "OVERDUE":
            overdue_count += 1
            overdue_amount += bal
            b["overdue_count"] += 1
            b["overdue_amount"] += bal
        elif bal > Decimal("0.00") and inv.due_date and today <= inv.due_date <= next_7_days:
            due_within_7_days_count += 1
            due_within_7_days_amount += bal
            b["due_within_7_days_count"] += 1
            b["due_within_7_days_amount"] += bal

        if inv.anomaly and inv.anomaly.is_anomaly:
            anomalous_invoices_count += 1

    # 2. Compute Monthly Trends (past 6 months)
    monthly_buckets: Dict[str, Dict[str, Any]] = {}
    current_month_start = date(today.year, today.month, 1)

    for i in range(5, -1, -1):
        m = current_month_start.month - i
        y = current_month_start.year
        while m <= 0:
            m += 12
            y -= 1
        key = f"{y:04d}-{m:02d}"
        label = date(y, m, 1).strftime("%b %Y")
        monthly_buckets[key] = {
            "month_key": key,
            "month_label": label,
            "invoiced_amount": Decimal("0.00"),
            "invoiced_count": 0,
            "paid_amount": Decimal("0.00"),
            "paid_count": 0,
        }

    # Populate invoice buckets
    for inv in invoices:
        k = f"{inv.invoice_date.year:04d}-{inv.invoice_date.month:02d}"
        if k in monthly_buckets:
            monthly_buckets[k]["invoiced_amount"] += inv.total_amount
            monthly_buckets[k]["invoiced_count"] += 1

    # Fetch all payments for user
    payments = (
        db.query(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .filter(Payment.user_id == user_id)
        .order_by(desc(Payment.payment_date), desc(Payment.id))
        .all()
    )

    for p in payments:
        k = f"{p.payment_date.year:04d}-{p.payment_date.month:02d}"
        if k in monthly_buckets:
            monthly_buckets[k]["paid_amount"] += p.amount
            monthly_buckets[k]["paid_count"] += 1

    monthly_trends = list(monthly_buckets.values())

    # 3. Recent Activity
    sorted_invoices = sorted(invoices, key=lambda x: (x.invoice_date, x.id), reverse=True)[:5]
    recent_invoices = []
    for inv in sorted_invoices:
        paid, bal, status = calculate_invoice_financials(inv, today)
        recent_invoices.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "vendor_name": inv.vendor_name,
            "invoice_date": inv.invoice_date,
            "due_date": inv.due_date,
            "total_amount": inv.total_amount,
            "currency": inv.currency,
            "payment_status": status,
            "balance_due": bal,
        })

    recent_payments = []
    for p in payments[:5]:
        inv = p.invoice
        recent_payments.append({
            "id": p.id,
            "invoice_id": p.invoice_id,
            "invoice_number": inv.invoice_number if inv else "N/A",
            "vendor_name": inv.vendor_name if inv else "N/A",
            "amount": p.amount,
            "currency": (inv.currency if inv and inv.currency else "USD"),
            "payment_date": p.payment_date,
            "payment_method": p.payment_method,
            "reference": p.reference,
        })

    return {
        "total_invoices_count": total_invoices_count,
        "total_invoiced_amount": total_invoiced_amount,
        "total_paid_amount": total_paid_amount,
        "total_outstanding_balance": total_outstanding_balance,
        "overdue_count": overdue_count,
        "overdue_amount": overdue_amount,
        "due_within_7_days_count": due_within_7_days_count,
        "due_within_7_days_amount": due_within_7_days_amount,
        "anomalous_invoices_count": anomalous_invoices_count,
        "currency": primary_currency,
        "has_multiple_currencies": has_multiple_currencies,
        "by_currency": by_currency,
        "status_counts": status_counts,
        "monthly_trends": monthly_trends,
        "recent_invoices": recent_invoices,
        "recent_payments": recent_payments,
    }


def get_reports_data(
    user_id: int,
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    vendor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Computes comprehensive filtered analytics, vendor breakdowns, invoice reports,
    payment reports, and reconciliation results for the authenticated user.
    """
    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date cannot be after end date.")

    today = date.today()

    query = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments), joinedload(Invoice.anomaly))
        .filter(Invoice.user_id == user_id)
    )

    if start_date:
        query = query.filter(Invoice.invoice_date >= start_date)
    if end_date:
        query = query.filter(Invoice.invoice_date <= end_date)
    if vendor and vendor.strip():
        query = query.filter(Invoice.vendor_name == vendor.strip())

    invoices = query.order_by(desc(Invoice.invoice_date), desc(Invoice.id)).all()

    total_invoices_count = len(invoices)
    total_invoiced_amount = Decimal("0.00")
    total_paid_amount = Decimal("0.00")
    total_outstanding_balance = Decimal("0.00")
    overdue_count = 0
    overdue_amount = Decimal("0.00")
    anomalous_count = 0

    status_counts: Dict[str, int] = {
        "PAID": 0,
        "PARTIAL": 0,
        "UNPAID": 0,
        "DUE_SOON": 0,
        "OVERDUE": 0,
    }

    # Currencies breakdown
    currencies = list({(inv.currency or "USD").upper() for inv in invoices})
    primary_currency = (
        currencies[0]
        if len(currencies) == 1
        else ("USD" if "USD" in currencies else (currencies[0] if currencies else "USD"))
    )
    has_multiple_currencies = len(currencies) > 1
    by_currency: Dict[str, Dict[str, Any]] = {}

    vendor_map: Dict[str, Dict[str, Any]] = {}
    report_invoices: List[Dict[str, Any]] = []

    for inv in invoices:
        curr = (inv.currency or "USD").upper()
        if curr not in by_currency:
            by_currency[curr] = {
                "currency": curr,
                "total_invoices_count": 0,
                "total_invoiced_amount": Decimal("0.00"),
                "total_paid_amount": Decimal("0.00"),
                "total_outstanding_balance": Decimal("0.00"),
                "overdue_count": 0,
                "overdue_amount": Decimal("0.00"),
                "status_counts": {
                    "PAID": 0,
                    "PARTIAL": 0,
                    "UNPAID": 0,
                    "DUE_SOON": 0,
                    "OVERDUE": 0,
                },
            }

        total_invoiced_amount += inv.total_amount
        paid, bal, status = calculate_invoice_financials(inv, today)
        total_paid_amount += paid
        total_outstanding_balance += bal

        status_counts[status] = status_counts.get(status, 0) + 1

        b = by_currency[curr]
        b["total_invoices_count"] += 1
        b["total_invoiced_amount"] += inv.total_amount
        b["total_paid_amount"] += paid
        b["total_outstanding_balance"] += bal
        b["status_counts"][status] = b["status_counts"].get(status, 0) + 1

        if status == "OVERDUE":
            overdue_count += 1
            overdue_amount += bal
            b["overdue_count"] += 1
            b["overdue_amount"] += bal

        if inv.anomaly and inv.anomaly.is_anomaly:
            anomalous_count += 1

        # Detailed invoice report row
        report_invoices.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "vendor_name": inv.vendor_name,
            "invoice_date": inv.invoice_date,
            "due_date": inv.due_date,
            "currency": inv.currency or "USD",
            "total_amount": inv.total_amount,
            "total_paid": paid,
            "balance_due": bal,
            "payment_status": status,
        })

        # Vendor aggregation
        v_name = inv.vendor_name.strip()
        if v_name not in vendor_map:
            vendor_map[v_name] = {
                "vendor_name": v_name,
                "invoice_count": 0,
                "total_invoiced": Decimal("0.00"),
                "total_paid": Decimal("0.00"),
                "outstanding_balance": Decimal("0.00"),
                "overdue_count": 0,
            }
        v_item = vendor_map[v_name]
        v_item["invoice_count"] += 1
        v_item["total_invoiced"] += inv.total_amount
        v_item["total_paid"] += paid
        v_item["outstanding_balance"] += bal
        if status == "OVERDUE":
            v_item["overdue_count"] += 1

    vendor_breakdown = sorted(
        vendor_map.values(), key=lambda x: x["total_invoiced"], reverse=True
    )

    # Payments query
    pay_query = (
        db.query(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .filter(Payment.user_id == user_id)
    )
    if start_date:
        pay_query = pay_query.filter(Payment.payment_date >= start_date)
    if end_date:
        pay_query = pay_query.filter(Payment.payment_date <= end_date)
    if vendor and vendor.strip():
        pay_query = pay_query.filter(Invoice.vendor_name == vendor.strip())

    payments = pay_query.order_by(desc(Payment.payment_date), desc(Payment.id)).all()
    payments_count = len(payments)

    report_payments: List[Dict[str, Any]] = []
    for p in payments:
        inv = p.invoice
        report_payments.append({
            "id": p.id,
            "payment_date": p.payment_date,
            "invoice_number": inv.invoice_number if inv else "N/A",
            "vendor_name": inv.vendor_name if inv else "N/A",
            "amount": p.amount,
            "currency": (inv.currency if inv and inv.currency else "USD"),
            "payment_method": p.payment_method,
            "reference": p.reference or "",
            "notes": p.notes or "",
        })

    # Period label
    if start_date and end_date:
        period_label = f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
    elif start_date:
        period_label = f"From {start_date.strftime('%b %d, %Y')}"
    elif end_date:
        period_label = f"Until {end_date.strftime('%b %d, %Y')}"
    else:
        period_label = "All Time"

    summary = {
        "period_label": period_label,
        "start_date": start_date,
        "end_date": end_date,
        "total_invoices_count": total_invoices_count,
        "total_invoiced_amount": total_invoiced_amount,
        "total_payments_count": payments_count,
        "total_paid_amount": total_paid_amount,
        "total_outstanding_balance": total_outstanding_balance,
        "overdue_count": overdue_count,
        "overdue_amount": overdue_amount,
        "anomalous_count": anomalous_count,
        "currency": primary_currency,
        "has_multiple_currencies": has_multiple_currencies,
        "by_currency": by_currency,
        "status_counts": status_counts,
    }

    # Monthly trends for this filtered period
    monthly_buckets: Dict[str, Dict[str, Any]] = {}
    for inv in invoices:
        k = f"{inv.invoice_date.year:04d}-{inv.invoice_date.month:02d}"
        if k not in monthly_buckets:
            monthly_buckets[k] = {
                "month_key": k,
                "month_label": inv.invoice_date.strftime("%b %Y"),
                "invoiced_amount": Decimal("0.00"),
                "invoiced_count": 0,
                "paid_amount": Decimal("0.00"),
                "paid_count": 0,
            }
        monthly_buckets[k]["invoiced_amount"] += inv.total_amount
        monthly_buckets[k]["invoiced_count"] += 1

    for p in payments:
        k = f"{p.payment_date.year:04d}-{p.payment_date.month:02d}"
        if k not in monthly_buckets:
            monthly_buckets[k] = {
                "month_key": k,
                "month_label": p.payment_date.strftime("%b %Y"),
                "invoiced_amount": Decimal("0.00"),
                "invoiced_count": 0,
                "paid_amount": Decimal("0.00"),
                "paid_count": 0,
            }
        monthly_buckets[k]["paid_amount"] += p.amount
        monthly_buckets[k]["paid_count"] += 1

    sorted_trends = sorted(monthly_buckets.values(), key=lambda x: x["month_key"])

    # Reconciliation data aggregation
    batches = (
        db.query(ReconciliationBatch)
        .filter(ReconciliationBatch.user_id == user_id)
        .order_by(desc(ReconciliationBatch.created_at))
        .all()
    )

    reconcile_items_query = (
        db.query(ReconciliationItem)
        .options(joinedload(ReconciliationItem.batch))
        .filter(ReconciliationItem.user_id == user_id)
    )
    if vendor and vendor.strip():
        reconcile_items_query = reconcile_items_query.filter(
            ReconciliationItem.vendor_or_counterparty.ilike(f"%{vendor.strip()}%")
        )

    all_reconcile_items = (
        reconcile_items_query.order_by(desc(ReconciliationItem.created_at), desc(ReconciliationItem.id))
        .limit(200)
        .all()
    )

    total_records = len(all_reconcile_items)
    matched_count = sum(1 for item in all_reconcile_items if item.match_status == "MATCHED")
    mismatch_count = sum(
        1 for item in all_reconcile_items if item.match_status in ("AMOUNT_MISMATCH", "MISMATCH")
    )
    missing_count = sum(
        1
        for item in all_reconcile_items
        if item.match_status in ("MISSING_IN_FILE", "MISSING_IN_LEDGER", "MISSING_IN_BANK")
    )
    duplicate_count = sum(
        1 for item in all_reconcile_items if item.match_status == "DUPLICATE_ENTRY"
    )
    pending_review_count = sum(
        1
        for item in all_reconcile_items
        if item.review_status == "PENDING" or item.match_status == "PENDING_REVIEW"
    )

    reconciliation_summary = {
        "total_batches": len(batches),
        "total_records": total_records,
        "matched_count": matched_count,
        "mismatch_count": mismatch_count,
        "missing_count": missing_count,
        "duplicate_count": duplicate_count,
        "pending_review_count": pending_review_count,
    }

    report_reconciliation_items = []
    for item in all_reconcile_items:
        batch_title = item.batch.title if item.batch else f"Batch #{item.batch_id}"
        batch_type = item.item_type or (item.batch.batch_type if item.batch else "LEDGER")
        report_reconciliation_items.append({
            "id": item.id,
            "batch_title": batch_title,
            "batch_type": batch_type,
            "record_identifier": item.record_identifier,
            "counterparty": item.vendor_or_counterparty or "N/A",
            "transaction_date": item.transaction_date,
            "expected_value": item.expected_value,
            "actual_value": item.actual_value,
            "discrepancy_amount": item.discrepancy_amount,
            "currency": item.currency or "USD",
            "match_status": item.match_status,
        })

    return {
        "summary": summary,
        "vendor_breakdown": vendor_breakdown,
        "monthly_trends": sorted_trends,
        "invoices": report_invoices,
        "payments": report_payments,
        "reconciliation_summary": reconciliation_summary,
        "reconciliation_items": report_reconciliation_items,
    }


def generate_invoices_csv(
    user_id: int,
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    vendor: Optional[str] = None,
) -> str:
    """
    Generates CSV export of invoices with spreadsheet formula injection protection.
    Respects date range and vendor filters.
    """
    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date cannot be after end date.")

    today = date.today()
    query = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments), joinedload(Invoice.anomaly))
        .filter(Invoice.user_id == user_id)
    )
    if start_date:
        query = query.filter(Invoice.invoice_date >= start_date)
    if end_date:
        query = query.filter(Invoice.invoice_date <= end_date)
    if vendor and vendor.strip():
        query = query.filter(Invoice.vendor_name == vendor.strip())

    invoices = query.order_by(desc(Invoice.invoice_date), desc(Invoice.id)).all()

    output = io.StringIO()
    # Write UTF-8 BOM so Excel opens with proper character encoding
    output.write("\ufeff")
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Column headers
    writer.writerow([
        "Invoice Number",
        "Supplier / Vendor",
        "Invoice Date",
        "Due Date",
        "Currency",
        "Subtotal",
        "Tax / GST",
        "Total Amount",
        "Total Paid",
        "Balance Due",
        "Payment Status",
        "Anomaly Assessment",
        "Notes",
    ])

    for inv in invoices:
        paid, bal, status = calculate_invoice_financials(inv, today)
        anom = inv.anomaly.status if inv.anomaly else "NOT_ASSESSED"

        writer.writerow([
            sanitize_for_csv(inv.invoice_number),
            sanitize_for_csv(inv.vendor_name),
            sanitize_for_csv(inv.invoice_date),
            sanitize_for_csv(inv.due_date if inv.due_date else ""),
            sanitize_for_csv(inv.currency),
            format_currency_decimal(inv.subtotal),
            format_currency_decimal(inv.tax_amount),
            format_currency_decimal(inv.total_amount),
            format_currency_decimal(paid),
            format_currency_decimal(bal),
            sanitize_for_csv(status),
            sanitize_for_csv(anom),
            sanitize_for_csv(inv.notes or ""),
        ])

    return output.getvalue()


def generate_payments_csv(
    user_id: int,
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    vendor: Optional[str] = None,
) -> str:
    """
    Generates CSV export of payment records with formula injection protection.
    Respects date range and vendor filters.
    """
    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date cannot be after end date.")

    query = (
        db.query(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .filter(Payment.user_id == user_id)
    )
    if start_date:
        query = query.filter(Payment.payment_date >= start_date)
    if end_date:
        query = query.filter(Payment.payment_date <= end_date)
    if vendor and vendor.strip():
        query = query.filter(Invoice.vendor_name == vendor.strip())

    payments = query.order_by(desc(Payment.payment_date), desc(Payment.id)).all()

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    writer.writerow([
        "Payment ID",
        "Payment Date",
        "Invoice Number",
        "Supplier / Vendor",
        "Amount Paid",
        "Payment Method",
        "Reference ID",
        "Notes",
    ])

    for p in payments:
        inv = p.invoice
        writer.writerow([
            sanitize_for_csv(p.id),
            sanitize_for_csv(p.payment_date),
            sanitize_for_csv(inv.invoice_number if inv else "N/A"),
            sanitize_for_csv(inv.vendor_name if inv else "N/A"),
            format_currency_decimal(p.amount),
            sanitize_for_csv(p.payment_method),
            sanitize_for_csv(p.reference or ""),
            sanitize_for_csv(p.notes or ""),
        ])

    return output.getvalue()


def generate_outstanding_csv(
    user_id: int,
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    vendor: Optional[str] = None,
) -> str:
    """
    Generates CSV export of unpaid, partially paid, and overdue invoices.
    Respects date range and vendor filters.
    """
    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date cannot be after end date.")

    today = date.today()
    query = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments))
        .filter(Invoice.user_id == user_id)
    )
    if start_date:
        query = query.filter(Invoice.invoice_date >= start_date)
    if end_date:
        query = query.filter(Invoice.invoice_date <= end_date)
    if vendor and vendor.strip():
        query = query.filter(Invoice.vendor_name == vendor.strip())

    invoices = query.order_by(asc(Invoice.due_date), desc(Invoice.invoice_date)).all()

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    writer.writerow([
        "Invoice Number",
        "Supplier / Vendor",
        "Invoice Date",
        "Due Date",
        "Total Amount",
        "Total Paid",
        "Balance Due",
        "Payment Status",
        "Days Overdue",
    ])

    for inv in invoices:
        paid, bal, status = calculate_invoice_financials(inv, today)
        if bal <= Decimal("0.00"):
            continue  # Only outstanding / pending records

        days_overdue = ""
        if status == "OVERDUE" and inv.due_date:
            days_overdue = str((today - inv.due_date).days)

        writer.writerow([
            sanitize_for_csv(inv.invoice_number),
            sanitize_for_csv(inv.vendor_name),
            sanitize_for_csv(inv.invoice_date),
            sanitize_for_csv(inv.due_date if inv.due_date else "Not specified"),
            format_currency_decimal(inv.total_amount),
            format_currency_decimal(paid),
            format_currency_decimal(bal),
            sanitize_for_csv(status),
            sanitize_for_csv(days_overdue),
        ])

    return output.getvalue()


def generate_reconciliation_csv(
    user_id: int,
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    vendor: Optional[str] = None,
) -> str:
    """
    Generates CSV export of reconciliation results (matched records, mismatches,
    missing entries, duplicates, items awaiting review) with formula injection protection.
    """
    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date cannot be after end date.")

    query = (
        db.query(ReconciliationItem)
        .options(joinedload(ReconciliationItem.batch))
        .filter(ReconciliationItem.user_id == user_id)
    )
    if vendor and vendor.strip():
        query = query.filter(ReconciliationItem.vendor_or_counterparty.ilike(f"%{vendor.strip()}%"))

    items = query.order_by(desc(ReconciliationItem.created_at), desc(ReconciliationItem.id)).all()

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    writer.writerow([
        "Batch Title",
        "Batch Type",
        "Record ID",
        "Counterparty / Vendor",
        "Transaction Date",
        "Expected Value",
        "Actual Value",
        "Discrepancy Amount",
        "Currency",
        "Match Status",
        "Review Status",
        "Audit Evidence",
    ])

    for item in items:
        batch_title = item.batch.title if item.batch else f"Batch #{item.batch_id}"
        batch_type = item.item_type or (item.batch.batch_type if item.batch else "LEDGER")
        discrepancy = format_currency_decimal(item.discrepancy_amount) if item.discrepancy_amount is not None else ""

        writer.writerow([
            sanitize_for_csv(batch_title),
            sanitize_for_csv(batch_type),
            sanitize_for_csv(item.record_identifier),
            sanitize_for_csv(item.vendor_or_counterparty or "N/A"),
            sanitize_for_csv(item.transaction_date or ""),
            sanitize_for_csv(item.expected_value or ""),
            sanitize_for_csv(item.actual_value or ""),
            discrepancy,
            sanitize_for_csv(item.currency or "USD"),
            sanitize_for_csv(item.match_status),
            sanitize_for_csv(item.review_status),
            sanitize_for_csv(item.evidence_text or ""),
        ])

    return output.getvalue()


def generate_summary_pdf(
    user: User,
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    vendor: Optional[str] = None,
) -> bytes:
    """
    Generates a PDF financial summary report using reportlab.
    Includes generation timestamp, selected reporting period, executive summary,
    status distribution, vendor breakdown, and audit metadata.
    """
    reports_data = get_reports_data(user.id, db, start_date, end_date, vendor)
    summary = reports_data["summary"]
    status_counts = summary.get("status_counts") or {}
    vendor_breakdown = reports_data["vendor_breakdown"][:8]  # Top 8 vendors

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=14,
        spaceAfter=6,
    )

    meta_style = ParagraphStyle(
        "MetaText",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )

    cell_style = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )

    cell_header = ParagraphStyle(
        "CellHeader",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0f172a"),
    )

    story = []

    # 1. Header
    story.append(Paragraph("InvoiceIQ Financial & Analytics Report", title_style))
    gen_time_str = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    period_str = summary["period_label"]
    vendor_suffix = f" &bull; Vendor Filter: <b>{vendor.strip()}</b>" if vendor and vendor.strip() else ""
    story.append(
        Paragraph(
            f"Account: <b>{user.name}</b> ({user.email}) &bull; Reporting Period: <b>{period_str}</b>{vendor_suffix} &bull; Generated: {gen_time_str}",
            subtitle_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0"), spaceAfter=14))

    # 2. Executive Summary Metrics Table
    story.append(Paragraph("Executive Financial Summary", section_heading))

    summary_data = [
        [
            Paragraph("Total Invoices", cell_header),
            Paragraph("Total Invoiced", cell_header),
            Paragraph("Total Paid", cell_header),
            Paragraph("Outstanding Balance", cell_header),
            Paragraph("Overdue Amount", cell_header),
        ],
        [
            Paragraph(str(summary["total_invoices_count"]), cell_style),
            Paragraph(f"${summary['total_invoiced_amount']:,.2f}", cell_style),
            Paragraph(f"${summary['total_paid_amount']:,.2f}", cell_style),
            Paragraph(f"${summary['total_outstanding_balance']:,.2f}", cell_style),
            Paragraph(f"${summary['overdue_amount']:,.2f} ({summary['overdue_count']} inv)", cell_style),
        ],
    ]

    t_summary = Table(summary_data, colWidths=[90, 110, 110, 115, 115])
    t_summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 10))

    # 3. Status Distribution Table
    story.append(Paragraph("Invoice Status Distribution", section_heading))
    status_data = [
        [
            Paragraph("Paid", cell_header),
            Paragraph("Partially Paid", cell_header),
            Paragraph("Unpaid", cell_header),
            Paragraph("Due Soon (<= 7 days)", cell_header),
            Paragraph("Overdue", cell_header),
        ],
        [
            Paragraph(f"{status_counts.get('PAID', 0)} invoices", cell_style),
            Paragraph(f"{status_counts.get('PARTIAL', 0)} invoices", cell_style),
            Paragraph(f"{status_counts.get('UNPAID', 0)} invoices", cell_style),
            Paragraph(f"{status_counts.get('DUE_SOON', 0)} invoices", cell_style),
            Paragraph(f"{status_counts.get('OVERDUE', 0)} invoices", cell_style),
        ],
    ]
    t_status = Table(status_data, colWidths=[108, 108, 108, 108, 108])
    t_status.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t_status)
    story.append(Spacer(1, 10))

    # 4. Vendor Breakdown Table
    story.append(Paragraph("Vendor / Supplier Summary", section_heading))
    if not vendor_breakdown:
        story.append(Paragraph("No vendor activity recorded for this period.", meta_style))
    else:
        vendor_data = [
            [
                Paragraph("Vendor Name", cell_header),
                Paragraph("Invoices", cell_header),
                Paragraph("Total Invoiced", cell_header),
                Paragraph("Total Paid", cell_header),
                Paragraph("Balance Due", cell_header),
                Paragraph("Overdue", cell_header),
            ]
        ]
        for v in vendor_breakdown:
            vendor_data.append([
                Paragraph(v["vendor_name"], cell_style),
                Paragraph(str(v["invoice_count"]), cell_style),
                Paragraph(f"${v['total_invoiced']:,.2f}", cell_style),
                Paragraph(f"${v['total_paid']:,.2f}", cell_style),
                Paragraph(f"${v['outstanding_balance']:,.2f}", cell_style),
                Paragraph(str(v["overdue_count"]), cell_style),
            ])

        t_vendor = Table(vendor_data, colWidths=[150, 60, 85, 85, 85, 75])
        t_vendor.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_vendor)

    # 5. Footer Note
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=6))
    story.append(
        Paragraph(
            "InvoiceIQ Financial Management &bull; Generated from live database records &bull; Confidential",
            meta_style,
        )
    )

    doc.build(story)
    return buffer.getvalue()
