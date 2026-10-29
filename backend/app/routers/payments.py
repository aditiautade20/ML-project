from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, asc, func

from app.database import get_db
from app.models.user import User
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentUpdateRequest,
    PaymentResponse,
    PaymentListResponse,
    InvoicePaymentSummaryResponse,
)
from app.services.payment_service import calculate_invoice_financials, validate_payment_bounds
from app.utils.security import get_current_user

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment against an invoice",
)
def record_payment(
    payment_in: PaymentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Records a full or partial payment against a verified invoice owned by the user.
    Prevents overpayments beyond the outstanding balance.
    """
    # Verify invoice exists and belongs to current user
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments))
        .filter(Invoice.id == payment_in.invoice_id, Invoice.user_id == current_user.id)
        .first()
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found or unauthorized.",
        )

    # Validate payment amount against remaining balance (prevent overpayment)
    validate_payment_bounds(invoice, payment_in.amount)

    # Prevent duplicate payment records
    dup_query = db.query(Payment).filter(
        Payment.invoice_id == invoice.id,
        Payment.user_id == current_user.id,
        Payment.amount == payment_in.amount,
        Payment.payment_date == payment_in.payment_date,
    )
    if payment_in.reference and payment_in.reference.strip():
        dup_query = dup_query.filter(Payment.reference == payment_in.reference.strip())
    else:
        dup_query = dup_query.filter(Payment.payment_method == payment_in.payment_method)

    if dup_query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A duplicate payment with the same amount and date already exists for this invoice.",
        )

    new_payment = Payment(
        invoice_id=invoice.id,
        user_id=current_user.id,
        amount=payment_in.amount,
        payment_date=payment_in.payment_date,
        payment_method=payment_in.payment_method,
        reference=payment_in.reference.strip() if payment_in.reference else None,
        notes=payment_in.notes.strip() if payment_in.notes else None,
    )

    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)

    return _build_payment_response(new_payment, invoice)


@router.get(
    "/",
    response_model=PaymentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all recorded payments with search and filtering",
)
def list_payments(
    invoice_id: Optional[int] = Query(None, description="Filter by invoice ID"),
    search: Optional[str] = Query(None, description="Search by reference, notes, invoice number, or vendor"),
    sort_by: str = Query("payment_date", pattern="^(payment_date|amount|created_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns a paginated list of recorded payments strictly for the authenticated user."""
    query = (
        db.query(Payment)
        .join(Payment.invoice)
        .filter(Payment.user_id == current_user.id)
    )

    if invoice_id is not None:
        query = query.filter(Payment.invoice_id == invoice_id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Payment.reference.ilike(term),
                Payment.notes.ilike(term),
                Invoice.invoice_number.ilike(term),
                Invoice.vendor_name.ilike(term),
                Payment.payment_method.ilike(term),
            )
        )

    # Sorting
    sort_column = getattr(Payment, sort_by, Payment.payment_date)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column), desc(Payment.id))
    else:
        query = query.order_by(asc(sort_column), asc(Payment.id))

    total = query.count()
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    # Total amount across matching payments
    total_amount_sum = (
        query.with_entities(func.sum(Payment.amount)).scalar() or Decimal("0.00")
    )

    payments = query.options(joinedload(Payment.invoice)).offset((page - 1) * per_page).limit(per_page).all()

    return PaymentListResponse(
        items=[_build_payment_response(p, p.invoice) for p in payments],
        total=total,
        page=page,
        per_page=per_page,
        pages=total_pages,
        total_amount_recorded=Decimal(str(total_amount_sum)).quantize(Decimal("0.01")),
    )


@router.get(
    "/invoice/{invoice_id}/summary",
    response_model=InvoicePaymentSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get payment history and balance calculations for an invoice",
)
def get_invoice_payment_summary(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the invoice financial balance, payment status, and chronological payment history."""
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments))
        .filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        .first()
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )

    total_paid, balance_due, payment_status = calculate_invoice_financials(invoice)

    return InvoicePaymentSummaryResponse(
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        vendor_name=invoice.vendor_name,
        currency=invoice.currency,
        invoice_total=invoice.total_amount,
        total_paid=total_paid,
        amount_paid=total_paid,
        balance_due=balance_due,
        payment_status=payment_status,
        due_date=invoice.due_date,
        payments=[_build_payment_response(p, invoice) for p in invoice.payments],
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single payment by ID",
)
def get_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves single payment with tenant isolation."""
    payment = (
        db.query(Payment)
        .options(joinedload(Payment.invoice))
        .filter(Payment.id == payment_id, Payment.user_id == current_user.id)
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )
    return _build_payment_response(payment, payment.invoice)


@router.put(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update payment details",
)
def update_payment(
    payment_id: int,
    payment_update: PaymentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates a recorded payment, validating that any new amount does not exceed the remaining balance."""
    payment = (
        db.query(Payment)
        .options(joinedload(Payment.invoice))
        .filter(Payment.id == payment_id, Payment.user_id == current_user.id)
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )

    # If amount is being changed, validate bounds
    if payment_update.amount is not None and payment_update.amount != payment.amount:
        # Load invoice with all payments to check bounds
        invoice = (
            db.query(Invoice)
            .options(joinedload(Invoice.payments))
            .filter(Invoice.id == payment.invoice_id, Invoice.user_id == current_user.id)
            .first()
        )
        validate_payment_bounds(invoice, payment_update.amount, exclude_payment_id=payment.id)
        payment.amount = payment_update.amount

    if payment_update.payment_date is not None:
        payment.payment_date = payment_update.payment_date
    if payment_update.payment_method is not None:
        payment.payment_method = payment_update.payment_method.strip() or payment.payment_method
    if payment_update.reference is not None:
        payment.reference = payment_update.reference.strip() if payment_update.reference else None
    if payment_update.notes is not None:
        payment.notes = payment_update.notes.strip() if payment_update.notes else None

    db.commit()
    db.refresh(payment)
    return _build_payment_response(payment, payment.invoice)


@router.delete(
    "/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a payment",
)
def delete_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes a payment record with strict tenant isolation."""
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id, Payment.user_id == current_user.id)
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )

    db.delete(payment)
    db.commit()
    return None


def _build_payment_response(payment: Payment, invoice: Optional[Invoice] = None) -> PaymentResponse:
    """Helper to assemble PaymentResponse with joined invoice details."""
    inv_num = invoice.invoice_number if invoice else None
    vendor = invoice.vendor_name if invoice else None
    curr = invoice.currency if invoice else "USD"

    return PaymentResponse(
        id=payment.id,
        invoice_id=payment.invoice_id,
        user_id=payment.user_id,
        amount=payment.amount,
        payment_date=payment.payment_date,
        payment_method=payment.payment_method,
        reference=payment.reference,
        notes=payment.notes,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
        invoice_number=inv_num,
        vendor_name=vendor,
        currency=curr,
    )
