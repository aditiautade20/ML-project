from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, asc, func

from app.database import get_db
from app.models.user import User
from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentAuditLog
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentUpdateRequest,
    PaymentResponse,
    PaymentListResponse,
    PaymentAuditLogResponse,
    InvoicePaymentSummaryResponse,
)
from app.services.payment_service import (
    calculate_invoice_financials,
    calculate_detailed_invoice_payment_info,
    validate_payment_bounds,
)
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
    Preserves audit logs and defaults manual payments to UNVERIFIED unless verified evidence is linked.
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

    v_status = (payment_in.verification_status or "UNVERIFIED").strip().upper()
    e_source = (payment_in.evidence_source or "MANUAL_ENTRY").strip()
    m_ref = payment_in.matched_reference.strip() if payment_in.matched_reference else None

    new_payment = Payment(
        invoice_id=invoice.id,
        user_id=current_user.id,
        amount=payment_in.amount,
        payment_date=payment_in.payment_date,
        payment_method=payment_in.payment_method,
        reference=payment_in.reference.strip() if payment_in.reference else None,
        notes=payment_in.notes.strip() if payment_in.notes else None,
        verification_status=v_status,
        evidence_source=e_source,
        matched_reference=m_ref,
    )

    db.add(new_payment)
    db.flush()

    # Immutable Audit Log Entry
    audit_entry = PaymentAuditLog(
        payment_id=new_payment.id,
        invoice_id=invoice.id,
        user_id=current_user.id,
        action="CREATED",
        new_amount=new_payment.amount,
        new_payment_date=new_payment.payment_date,
        new_status=new_payment.verification_status,
        evidence_source=new_payment.evidence_source,
        notes=new_payment.notes,
    )
    db.add(audit_entry)
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
    verification_status: Optional[str] = Query(None, description="Filter by verification status: VERIFIED, UNVERIFIED, FLAGGED"),
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

    if verification_status and verification_status.strip():
        query = query.filter(Payment.verification_status == verification_status.strip().upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Payment.reference.ilike(term),
                Payment.notes.ilike(term),
                Invoice.invoice_number.ilike(term),
                Invoice.vendor_name.ilike(term),
                Payment.payment_method.ilike(term),
                Payment.evidence_source.ilike(term),
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
    summary="Get payment history, verification state, and balance calculations for an invoice",
)
@router.get(
    "/invoices/{invoice_id}/summary",
    response_model=InvoicePaymentSummaryResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_invoice_payment_summary(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the invoice financial balance, payment status, evidence sources, and chronological payment history."""
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

    detail = calculate_detailed_invoice_payment_info(invoice)

    # Fetch audit logs for this invoice
    audit_logs = (
        db.query(PaymentAuditLog)
        .filter(PaymentAuditLog.invoice_id == invoice_id, PaymentAuditLog.user_id == current_user.id)
        .order_by(desc(PaymentAuditLog.timestamp))
        .all()
    )

    return InvoicePaymentSummaryResponse(
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        vendor_name=invoice.vendor_name,
        currency=invoice.currency,
        invoice_total=invoice.total_amount,
        total_paid=detail["total_paid"],
        verified_paid=detail["verified_paid"],
        unverified_paid=detail["unverified_paid"],
        amount_paid=detail["total_paid"],
        balance_due=detail["balance_due"],
        payment_status=detail["payment_status"],
        due_date=invoice.due_date,
        actual_payment_date=detail["actual_payment_date"],
        days_late=detail["days_late"],
        days_overdue=detail["days_overdue"],
        days_remaining=detail["days_remaining"],
        evidence_source=detail["evidence_source"],
        matched_reference=detail["matched_reference"],
        mismatch_reason=detail["mismatch_reason"],
        payments=[_build_payment_response(p, invoice) for p in invoice.payments],
        audit_logs=[PaymentAuditLogResponse.model_validate(a) for a in audit_logs],
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
    """Updates a recorded payment, validating balance bounds and recording immutable audit logs."""
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

    old_amount = payment.amount
    old_date = payment.payment_date
    old_status = payment.verification_status

    # If amount is being changed, validate bounds
    if payment_update.amount is not None and payment_update.amount != payment.amount:
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
    if payment_update.verification_status is not None:
        payment.verification_status = payment_update.verification_status.strip().upper()
    if payment_update.evidence_source is not None:
        payment.evidence_source = payment_update.evidence_source.strip()
    if payment_update.matched_reference is not None:
        payment.matched_reference = payment_update.matched_reference.strip() if payment_update.matched_reference else None
    if payment_update.mismatch_reason is not None:
        payment.mismatch_reason = payment_update.mismatch_reason.strip() if payment_update.mismatch_reason else None

    # Immutable Audit Log Entry
    audit_entry = PaymentAuditLog(
        payment_id=payment.id,
        invoice_id=payment.invoice_id,
        user_id=current_user.id,
        action="UPDATED",
        previous_amount=old_amount,
        new_amount=payment.amount,
        previous_payment_date=old_date,
        new_payment_date=payment.payment_date,
        previous_status=old_status,
        new_status=payment.verification_status,
        evidence_source=payment.evidence_source,
        notes=payment.notes,
    )
    db.add(audit_entry)
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
    """Deletes a payment record with strict tenant isolation and preserves audit history."""
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

    # Immutable Audit Log Entry before deletion
    audit_entry = PaymentAuditLog(
        payment_id=None,
        invoice_id=payment.invoice_id,
        user_id=current_user.id,
        action="DELETED",
        previous_amount=payment.amount,
        previous_payment_date=payment.payment_date,
        previous_status=payment.verification_status,
        evidence_source=payment.evidence_source,
        notes=payment.notes,
    )
    db.add(audit_entry)
    db.delete(payment)
    db.commit()
    return None


def _build_payment_response(payment: Payment, invoice: Optional[Invoice] = None) -> PaymentResponse:
    """Helper to assemble PaymentResponse with joined invoice details and audit verification."""
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
        verification_status=payment.verification_status or "UNVERIFIED",
        evidence_source=payment.evidence_source or "MANUAL_ENTRY",
        matched_reference=payment.matched_reference,
        mismatch_reason=payment.mismatch_reason,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
        invoice_number=inv_num,
        vendor_name=vendor,
        currency=curr,
    )
