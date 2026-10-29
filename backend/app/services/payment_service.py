from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Tuple, Optional
from fastapi import HTTPException, status
from app.models.invoice import Invoice


def calculate_invoice_financials(
    invoice: Invoice, reference_date: Optional[date] = None
) -> Tuple[Decimal, Decimal, str]:
    """Calculates total paid, remaining balance due, and payment status strictly from database records.
    Returns: (total_paid, balance_due, payment_status)
    Supported payment statuses:
      - 'PAID': Remaining balance is 0.00
      - 'OVERDUE': Balance > 0 and due date is strictly in the past (< reference_date)
      - 'DUE_SOON': Balance > 0, unpaid, and due date is within the next 7 days (today <= due_date <= today + 7)
      - 'PARTIAL': Partial payment recorded (> 0) and balance > 0 (not overdue)
      - 'UNPAID': No payment recorded, balance == total, not overdue and not due soon (or no due date)
    """
    ref_date = reference_date or date.today()
    if isinstance(ref_date, datetime):
        ref_date = ref_date.date()

    invoice_total = Decimal(str(invoice.total_amount)).quantize(Decimal("0.01"))

    # Sum valid recorded payments
    total_paid = Decimal("0.00")
    if hasattr(invoice, "payments") and invoice.payments:
        for p in invoice.payments:
            total_paid += Decimal(str(p.amount)).quantize(Decimal("0.01"))

    balance_due = max(Decimal("0.00"), invoice_total - total_paid).quantize(Decimal("0.01"))

    due_d = invoice.due_date
    if isinstance(due_d, datetime):
        due_d = due_d.date()

    # Determine status according to exact business rules:
    # 1. Fully paid invoices show PAID
    if balance_due <= Decimal("0.00") or total_paid >= invoice_total:
        status_label = "PAID"
    # 2. Overdue if unpaid balance and actual due date is strictly in the past (< ref_date)
    elif due_d is not None and due_d < ref_date:
        status_label = "OVERDUE"
    # 3. Due soon if unpaid balance, no payments recorded yet, and due date is within next 7 days
    elif due_d is not None and ref_date <= due_d <= (ref_date + timedelta(days=7)) and total_paid == Decimal("0.00"):
        status_label = "DUE_SOON"
    # 4. Partial if some payment was recorded (> 0) and balance remains
    elif total_paid > Decimal("0.00"):
        status_label = "PARTIAL"
    # 5. Otherwise UNPAID (even if due date is missing or > 7 days away)
    else:
        status_label = "UNPAID"

    return total_paid, balance_due, status_label


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
