from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Tuple, Optional, Dict, Any, List
from fastapi import HTTPException, status
from app.models.invoice import Invoice


def calculate_invoice_financials(
    invoice: Invoice, reference_date: Optional[date] = None
) -> Tuple[Decimal, Decimal, str]:
    """
    Calculates total recorded paid, remaining balance due, and high-level payment status
    strictly from database records and verification state.
    Returns: (total_paid, balance_due, payment_status)
    """
    detail = calculate_detailed_invoice_payment_info(invoice, reference_date)
    raw_status = detail["payment_status"]
    if raw_status in ("PAID_ON_TIME", "PAID_LATE"):
        legacy_status = "PAID"
    elif raw_status == "PARTIALLY_PAID_OVERDUE":
        legacy_status = "OVERDUE"
    elif raw_status == "PARTIALLY_PAID":
        legacy_status = "PARTIAL"
    elif raw_status == "OVERDUE_UNCONFIRMED":
        legacy_status = "OVERDUE"
    elif raw_status == "UPCOMING_UNPAID":
        if detail.get("days_remaining") is not None and 0 <= detail["days_remaining"] <= 7:
            legacy_status = "DUE_SOON"
        else:
            legacy_status = "UNPAID"
    elif raw_status == "PAYMENT_UNVERIFIED":
        ref_d = reference_date or date.today()
        inv_due = invoice.due_date.date() if isinstance(invoice.due_date, datetime) else invoice.due_date
        if detail["balance_due"] <= Decimal("0.00"):
            legacy_status = "PAID"
        elif inv_due and inv_due < ref_d:
            legacy_status = "OVERDUE"
        elif detail["total_paid"] > Decimal("0.00"):
            legacy_status = "PARTIAL"
        else:
            legacy_status = "UNPAID"
    else:
        legacy_status = raw_status

    return detail["total_paid"], detail["balance_due"], legacy_status


def calculate_detailed_invoice_payment_info(
    invoice: Invoice, reference_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Evaluates comprehensive payment tracking, verification sources,
    and due-date timing for an invoice.

    Granular Status Logic:
      1. NEEDS_REVIEW: Payment records, ledger entries, or bank statements conflict or have flagged discrepancies.
      2. PAID_ON_TIME: Full invoice amount was verified paid on or before the due date (or no due date specified).
      3. PAID_LATE: Full invoice amount was verified paid after the due date.
      4. PAYMENT_UNVERIFIED: A payment is claimed or recorded, but lacks verified bank/ledger proof.
      5. PARTIALLY_PAID_OVERDUE: A partial payment was verified, but a balance remains past the due date.
      6. PARTIALLY_PAID: Only part of invoice amount was verified paid (due date in future or none).
      7. OVERDUE_UNCONFIRMED: Due date passed, outstanding balance remains, no confirmed payment covers balance.
      8. UPCOMING_UNPAID: Due date in future (or none) and no payment has been recorded.
    """
    ref_date = reference_date or date.today()
    if isinstance(ref_date, datetime):
        ref_date = ref_date.date()

    invoice_total = Decimal(str(invoice.total_amount)).quantize(Decimal("0.01"))

    # Sum payments by verification status
    verified_paid = Decimal("0.00")
    unverified_paid = Decimal("0.00")
    payment_dates: List[date] = []
    evidence_sources = set()
    matched_refs = []
    mismatch_reasons = []
    has_flagged_payment = False

    if hasattr(invoice, "payments") and invoice.payments:
        for p in invoice.payments:
            amt = Decimal(str(p.amount)).quantize(Decimal("0.01"))
            v_status = (getattr(p, "verification_status", None) or "UNVERIFIED").strip().upper()
            if v_status == "VERIFIED":
                verified_paid += amt
            elif v_status == "FLAGGED":
                has_flagged_payment = True
                unverified_paid += amt
            else:
                unverified_paid += amt

            p_date = p.payment_date
            if isinstance(p_date, datetime):
                p_date = p_date.date()
            if p_date:
                payment_dates.append(p_date)

            src = getattr(p, "evidence_source", None)
            if src:
                evidence_sources.add(src)
            m_ref = getattr(p, "matched_reference", None)
            if m_ref:
                matched_refs.append(m_ref)
            m_rsn = getattr(p, "mismatch_reason", None)
            if m_rsn:
                mismatch_reasons.append(m_rsn)

    total_recorded = (verified_paid + unverified_paid).quantize(Decimal("0.01"))

    # Outstanding balance is calculated as remaining unpaid amount after recorded payments
    balance_due = max(Decimal("0.00"), invoice_total - total_recorded).quantize(Decimal("0.01"))

    due_d = invoice.due_date
    if isinstance(due_d, datetime):
        due_d = due_d.date()

    actual_payment_date = max(payment_dates) if payment_dates else None

    # Calculate days timing
    days_late = None
    days_overdue = None
    days_remaining = None

    if due_d:
        if actual_payment_date and verified_paid >= invoice_total:
            if actual_payment_date > due_d:
                days_late = (actual_payment_date - due_d).days
            else:
                days_late = 0
        elif due_d < ref_date:
            days_overdue = (ref_date - due_d).days
        else:
            days_remaining = (due_d - ref_date).days

    # Primary verification source description
    if "BANK_STATEMENT" in evidence_sources:
        primary_evidence = "Bank Statement"
    elif "GENERAL_LEDGER" in evidence_sources:
        primary_evidence = "General Ledger"
    elif "RECEIPT" in evidence_sources:
        primary_evidence = "Payment Receipt"
    elif "MANUAL_ENTRY" in evidence_sources or unverified_paid > Decimal("0.00"):
        primary_evidence = "Manual Entry (Unverified)"
    else:
        primary_evidence = "None"

    # Status Determination Rules:
    # 1. Needs Review: Conflict or discrepancy flagged
    if has_flagged_payment or mismatch_reasons:
        payment_status = "NEEDS_REVIEW"
        status_label = "Needs Review"
    # 2. Fully verified payment: distinguishes Paid on Time vs Paid Late
    elif verified_paid >= invoice_total:
        if due_d and actual_payment_date and actual_payment_date > due_d:
            payment_status = "PAID_LATE"
            status_label = f"Paid Late ({days_late} days)"
        else:
            payment_status = "PAID_ON_TIME"
            status_label = "Paid on Time"
    # 3. Payment Unverified: claimed/recorded, but lacks verified proof
    elif unverified_paid > Decimal("0.00") and verified_paid < invoice_total:
        payment_status = "PAYMENT_UNVERIFIED"
        status_label = "Payment Unverified"
    # 4. Partial verified payment
    elif verified_paid > Decimal("0.00"):
        if due_d and due_d < ref_date:
            payment_status = "PARTIALLY_PAID_OVERDUE"
            status_label = f"Partially Paid — Overdue ({days_overdue} days)"
        else:
            payment_status = "PARTIALLY_PAID"
            status_label = "Partially Paid"
    # 5. Overdue (no payment recorded)
    elif due_d and due_d < ref_date:
        payment_status = "OVERDUE_UNCONFIRMED"
        status_label = f"Overdue — Payment Not Confirmed ({days_overdue} days)"
    # 6. Upcoming / Unpaid
    else:
        payment_status = "UPCOMING_UNPAID"
        status_label = "Upcoming / Unpaid"

    matched_ref_str = ", ".join(matched_refs) if matched_refs else None
    mismatch_str = "; ".join(mismatch_reasons) if mismatch_reasons else None

    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "vendor_name": invoice.vendor_name,
        "customer_name": invoice.customer_name,
        "invoice_date": invoice.invoice_date,
        "due_date": due_d,
        "invoice_total": invoice_total,
        "total_paid": total_recorded,
        "verified_paid": verified_paid,
        "unverified_paid": unverified_paid,
        "balance_due": balance_due,
        "payment_status": payment_status,
        "status_label": status_label,
        "actual_payment_date": actual_payment_date,
        "days_late": days_late,
        "days_overdue": days_overdue,
        "days_remaining": days_remaining,
        "evidence_source": primary_evidence,
        "matched_reference": matched_ref_str,
        "mismatch_reason": mismatch_str,
    }


def validate_payment_bounds(
    invoice: Invoice,
    payment_amount: Decimal,
    exclude_payment_id: Optional[int] = None,
) -> Decimal:
    """Ensures payment amount does not silently exceed the invoice's remaining balance.
    Raises HTTPException(400) if overpayment or invalid amount is attempted.
    """
    if payment_amount is None or payment_amount <= Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment amount must be greater than zero.",
        )

    invoice_total = Decimal(str(invoice.total_amount)).quantize(Decimal("0.01"))

    current_paid = Decimal("0.00")
    if hasattr(invoice, "payments") and invoice.payments:
        for p in invoice.payments:
            if exclude_payment_id is None or p.id != exclude_payment_id:
                current_paid += Decimal(str(p.amount)).quantize(Decimal("0.01"))

    remaining_balance = max(Decimal("0.00"), invoice_total - current_paid).quantize(Decimal("0.01"))

    if payment_amount > remaining_balance:
        currency = invoice.currency or "USD"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment amount ({payment_amount:.2f} {currency}) exceeds the remaining balance ({remaining_balance:.2f} {currency}).",
        )

    return remaining_balance
