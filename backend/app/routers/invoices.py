from datetime import date, timedelta
from decimal import Decimal
import os
from pathlib import Path
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, asc, func

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.models.invoice import Invoice
from app.schemas.invoice import (
    InvoiceUploadResponse,
    InvoiceCreateRequest,
    InvoiceUpdateRequest,
    InvoiceResponse,
    InvoiceListResponse,
    InvoiceDeadlinesSummaryResponse,
)
from app.services.extractor import process_invoice_file
from app.services.payment_service import (
    calculate_invoice_financials,
    calculate_detailed_invoice_payment_info,
)
from app.utils.security import get_current_user

router = APIRouter(prefix="/api/invoices", tags=["Invoices"])
settings = get_settings()

SUPPORTED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


@router.post(
    "/upload",
    response_model=InvoiceUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload an invoice file (PDF or image) and extract candidate fields",
)
async def upload_invoice(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Securely uploads an invoice file, validates format and size,
    and extracts candidate fields for review.
    Does NOT save to the database automatically.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was provided for upload.",
        )

    # 1. Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Supported formats: PDF, JPEG, PNG, WEBP.",
        )

    # 2. Validate MIME type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in SUPPORTED_MIME_TYPES and file_ext != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported content type '{content_type}'.",
        )

    # 3. Read content and validate size
    contents = await file.read()
    file_size = len(contents)
    max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes).",
        )

    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )

    # 4. Validate magic bytes / file content signature (reject malformed or spoofed files)
    def _validate_content_signature(data: bytes, ext: str) -> bool:
        trimmed = data.lstrip()
        if ext == ".pdf":
            return trimmed.startswith(b"%PDF")
        elif ext in [".jpg", ".jpeg"]:
            return data.startswith(b"\xff\xd8\xff")
        elif ext == ".png":
            return data.startswith(b"\x89PNG\r\n\x1a\n")
        elif ext == ".webp":
            return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        return False

    if not _validate_content_signature(contents, file_ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file content does not match the '{file_ext}' file signature. Malformed or spoofed files are rejected.",
        )

    # 5. Generate safe server-side file name (prevents path traversal)
    safe_token = f"inv_{uuid.uuid4().hex}{file_ext}"
    upload_dir = settings.resolved_upload_dir
    destination = upload_dir / safe_token

    # Write file securely
    with open(destination, "wb") as f:
        f.write(contents)

    # 5. Extract candidate metadata
    candidates, notes = process_invoice_file(destination, content_type)

    validation_warnings = []
    if candidates.total_amount is None:
        validation_warnings.append("Total amount was not detected automatically. Please verify the amount.")
    if candidates.invoice_number is None:
        validation_warnings.append("Invoice number was not detected automatically.")
    if candidates.vendor_name is None:
        validation_warnings.append("Supplier / Vendor name was not detected automatically.")
    if candidates.invoice_date is None:
        validation_warnings.append("Invoice date was not detected automatically.")
    if candidates.invoice_date and candidates.due_date and candidates.due_date < candidates.invoice_date:
        validation_warnings.append(f"Date sequence warning: Due date ({candidates.due_date}) is earlier than invoice date ({candidates.invoice_date}).")
    for note in notes:
        if "Arithmetic Discrepancy" in note or "exceeds Grand Total" in note:
            if note not in validation_warnings:
                validation_warnings.append(note)

    # Check for potential duplicate invoice in user's account
    if candidates.invoice_number and candidates.vendor_name:
        existing_dup = (
            db.query(Invoice)
            .filter(
                Invoice.user_id == current_user.id,
                func.lower(func.trim(Invoice.invoice_number)) == func.lower(candidates.invoice_number.strip()),
                func.lower(func.trim(Invoice.vendor_name)) == func.lower(candidates.vendor_name.strip()),
            )
            .first()
        )
        if existing_dup:
            validation_warnings.append(
                f"Duplicate warning: Invoice #{candidates.invoice_number} from '{candidates.vendor_name}' already exists in your account (ID: #{existing_dup.id})."
            )

    return InvoiceUploadResponse(
        file_token=safe_token,
        file_name=Path(file.filename).name,
        file_content_type=content_type,
        file_size_bytes=file_size,
        candidate_fields=candidates,
        extraction_notes=notes,
        validation_warnings=validation_warnings,
    )


@router.post(
    "/",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a reviewed invoice to persistent storage",
)
def create_invoice(
    invoice_in: InvoiceCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validates user-reviewed invoice fields, checks for duplicate invoice numbers,
    and commits the record to the database.
    """
    # Check for duplicate invoice number from the same vendor for this user (case-insensitive & whitespace-trimmed)
    existing = (
        db.query(Invoice)
        .filter(
            Invoice.user_id == current_user.id,
            func.lower(func.trim(Invoice.invoice_number)) == func.lower(invoice_in.invoice_number.strip()),
            func.lower(func.trim(Invoice.vendor_name)) == func.lower(invoice_in.vendor_name.strip()),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice #{invoice_in.invoice_number} from '{invoice_in.vendor_name}' already exists in your account.",
        )

    # Determine review status: respect explicit status or check validation issues
    if invoice_in.status and invoice_in.status.strip():
        inv_status = invoice_in.status.strip().upper()
    else:
        has_arithmetic_issue = False
        if invoice_in.subtotal is not None and invoice_in.tax_amount is not None:
            diff = abs((invoice_in.subtotal + invoice_in.tax_amount) - invoice_in.total_amount)
            if diff > Decimal("0.05"):
                has_arithmetic_issue = True
        has_date_issue = bool(invoice_in.due_date and invoice_in.invoice_date and invoice_in.due_date < invoice_in.invoice_date)

        if has_arithmetic_issue or has_date_issue:
            inv_status = "NEEDS_REVIEW"
        else:
            inv_status = "CONFIRMED"

    # Verify file_token safety if attached
    safe_file_path = None
    if invoice_in.file_token:
        token_clean = Path(invoice_in.file_token).name
        token_path = settings.resolved_upload_dir / token_clean
        if token_path.is_file():
            safe_file_path = token_clean

    new_invoice = Invoice(
        user_id=current_user.id,
        invoice_number=invoice_in.invoice_number,
        vendor_name=invoice_in.vendor_name,
        customer_name=invoice_in.customer_name,
        invoice_date=invoice_in.invoice_date,
        due_date=invoice_in.due_date,
        subtotal=invoice_in.subtotal,
        tax_amount=invoice_in.tax_amount,
        total_amount=invoice_in.total_amount,
        currency=invoice_in.currency,
        status=inv_status,
        file_path=safe_file_path,
        file_name=token_clean if safe_file_path else None,
        notes=invoice_in.notes,
    )

    db.add(new_invoice)
    db.commit()
    db.refresh(new_invoice)

    return _build_invoice_response(new_invoice)


@router.get(
    "/",
    response_model=InvoiceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all invoices with search, filtering, and sorting",
)
def list_invoices(
    search: Optional[str] = Query(None, description="Search by invoice number or vendor"),
    vendor: Optional[str] = Query(None, description="Filter by exact vendor name"),
    payment_status: Optional[str] = Query(None, description="Filter by payment status (PAID, OVERDUE, DUE_SOON, PARTIAL, UNPAID)"),
    due_date_from: Optional[date] = Query(None, description="Filter invoices due on or after date"),
    due_date_to: Optional[date] = Query(None, description="Filter invoices due on or before date"),
    sort_by: str = Query("invoice_date", pattern="^(invoice_date|total_amount|vendor_name|created_at|due_date)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns a paginated list of invoices strictly belonging to the authenticated user."""
    query = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments))
        .filter(Invoice.user_id == current_user.id)
    )

    # 1. Search filter
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Invoice.invoice_number.ilike(term),
                Invoice.vendor_name.ilike(term),
                Invoice.notes.ilike(term),
            )
        )

    # 2. Vendor filter
    if vendor and vendor.strip():
        query = query.filter(Invoice.vendor_name == vendor.strip())

    # 3. Due Date range filters
    if due_date_from:
        query = query.filter(Invoice.due_date >= due_date_from)
    if due_date_to:
        query = query.filter(Invoice.due_date <= due_date_to)

    # 4. Sorting
    sort_column = getattr(Invoice, sort_by, Invoice.invoice_date)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    # 5. Fetch and apply dynamic payment_status filter
    all_invoices = query.all()
    today = date.today()

    if payment_status and payment_status.strip():
        req_st = payment_status.strip().upper()
        status_map = {
            "PAID": ["PAID", "PAID_ON_TIME", "PAID_LATE"],
            "PAID_ON_TIME": ["PAID_ON_TIME"],
            "PAID ON TIME": ["PAID_ON_TIME"],
            "PAID_LATE": ["PAID_LATE"],
            "PAID LATE": ["PAID_LATE"],
            "OVERDUE": ["OVERDUE", "OVERDUE_UNCONFIRMED", "PARTIALLY_PAID_OVERDUE"],
            "OVERDUE_UNCONFIRMED": ["OVERDUE_UNCONFIRMED", "OVERDUE"],
            "OVERDUE — PAYMENT NOT CONFIRMED": ["OVERDUE_UNCONFIRMED", "OVERDUE"],
            "OVERDUE - PAYMENT NOT CONFIRMED": ["OVERDUE_UNCONFIRMED", "OVERDUE"],
            "PARTIAL": ["PARTIAL", "PARTIALLY_PAID", "PARTIALLY_PAID_OVERDUE"],
            "PARTIALLY PAID": ["PARTIAL", "PARTIALLY_PAID", "PARTIALLY_PAID_OVERDUE"],
            "PARTIALLY_PAID": ["PARTIAL", "PARTIALLY_PAID"],
            "PARTIALLY_PAID_OVERDUE": ["PARTIALLY_PAID_OVERDUE"],
            "PARTIALLY PAID — OVERDUE": ["PARTIALLY_PAID_OVERDUE"],
            "PARTIALLY PAID - OVERDUE": ["PARTIALLY_PAID_OVERDUE"],
            "UNPAID": ["UNPAID", "UPCOMING_UNPAID"],
            "UPCOMING": ["UPCOMING_UNPAID", "DUE_SOON"],
            "UPCOMING / UNPAID": ["UPCOMING_UNPAID", "UNPAID"],
            "UPCOMING/UNPAID": ["UPCOMING_UNPAID", "UNPAID"],
            "UPCOMING_UNPAID": ["UPCOMING_UNPAID", "UNPAID"],
            "PAYMENT_UNVERIFIED": ["PAYMENT_UNVERIFIED"],
            "PAYMENT UNVERIFIED": ["PAYMENT_UNVERIFIED"],
            "UNVERIFIED": ["PAYMENT_UNVERIFIED"],
            "NEEDS_REVIEW": ["NEEDS_REVIEW"],
            "NEEDS REVIEW": ["NEEDS_REVIEW"],
            "DUE_SOON": ["DUE_SOON", "UPCOMING_UNPAID"],
            "DUE SOON": ["DUE_SOON", "UPCOMING_UNPAID"],
            "MISMATCH": ["MISMATCH"],
            "MISMATCHES": ["MISMATCH"],
            "VERIFIED": ["CONFIRMED"],
            "CONFIRMED": ["CONFIRMED"],
        }
        allowed = status_map.get(req_st, [req_st])
        matched_invoices = []
        for inv in all_invoices:
            _, _, st = calculate_invoice_financials(inv, today)
            is_match = st in allowed
            if not is_match and req_st in ["DUE_SOON", "DUE SOON"]:
                if inv.due_date and today <= inv.due_date <= (today + timedelta(days=7)) and st in ["UPCOMING_UNPAID", "UNPAID"]:
                    is_match = True
            elif not is_match and req_st in ["NEEDS_REVIEW", "NEEDS REVIEW"]:
                if inv.status == "NEEDS_REVIEW" or any(p.mismatch_reason for p in (inv.payments or [])):
                    is_match = True
            elif not is_match and req_st in ["MISMATCH", "MISMATCHES"]:
                if (inv.anomaly and inv.anomaly.is_anomaly) or (inv.status == "NEEDS_REVIEW") or any(p.mismatch_reason for p in (inv.payments or [])):
                    is_match = True
            elif not is_match and req_st in ["CONFIRMED", "VERIFIED"]:
                if inv.status == "CONFIRMED":
                    is_match = True
            if is_match:
                matched_invoices.append(inv)
        total = len(matched_invoices)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        invoices = matched_invoices[(page - 1) * per_page : page * per_page]
    else:
        total = len(all_invoices)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        invoices = all_invoices[(page - 1) * per_page : page * per_page]

    return InvoiceListResponse(
        items=[_build_invoice_response(inv) for inv in invoices],
        total=total,
        page=page,
        per_page=per_page,
        pages=total_pages,
    )


@router.get(
    "/deadlines/summary",
    response_model=InvoiceDeadlinesSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get categorized payment deadlines: overdue, due today, next 7 days, and upcoming",
)
def get_deadlines_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculates upcoming and overdue invoice deadlines based on actual due dates and balances."""
    today = date.today()
    next_7_days = today + timedelta(days=7)

    invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments))
        .filter(Invoice.user_id == current_user.id)
        .all()
    )

    overdue = []
    due_today = []
    due_within_7_days = []
    due_later = []
    settled = []

    overdue_total = Decimal("0.00")
    due_today_total = Decimal("0.00")
    due_7_total = Decimal("0.00")
    total_outstanding = Decimal("0.00")

    for inv in invoices:
        total_paid, balance_due, status_label = calculate_invoice_financials(inv, today)
        inv_resp = _build_invoice_response(inv, today)

        if balance_due <= Decimal("0.00"):
            settled.append(inv_resp)
            continue  # Paid invoices don't have pending deadlines

        total_outstanding += balance_due

        # Categorize strictly based on actual due dates
        if inv.due_date is None:
            due_later.append(inv_resp)
        elif inv.due_date < today:
            overdue.append(inv_resp)
            overdue_total += balance_due
        elif inv.due_date == today:
            due_today.append(inv_resp)
            due_today_total += balance_due
        elif today < inv.due_date <= next_7_days:
            due_within_7_days.append(inv_resp)
            due_7_total += balance_due
        else:
            due_later.append(inv_resp)

    # Sort overdue by oldest due date first (most urgent)
    overdue.sort(key=lambda x: x.due_date or today)
    due_within_7_days.sort(key=lambda x: x.due_date or next_7_days)
    due_later.sort(key=lambda x: (x.due_date is None, x.due_date or next_7_days))
    settled.sort(key=lambda x: x.due_date or today, reverse=True)

    return InvoiceDeadlinesSummaryResponse(
        overdue=overdue,
        due_today=due_today,
        due_within_7_days=due_within_7_days,
        due_later=due_later,
        settled=settled,
        settled_count=len(settled),
        overdue_count=len(overdue),
        overdue_total=overdue_total,
        due_today_count=len(due_today),
        due_today_total=due_today_total,
        due_within_7_days_count=len(due_within_7_days),
        due_within_7_days_total=due_7_total,
        total_outstanding_amount=total_outstanding,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get detailed invoice by ID",
)
def get_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetches single invoice record with strict tenant isolation."""
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
    return _build_invoice_response(invoice)


@router.put(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update invoice details",
)
def update_invoice(
    invoice_id: int,
    invoice_update: InvoiceUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates invoice fields for the authenticated owner."""
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

    # Check for duplicate if invoice_number or vendor_name changed (case-insensitive & trimmed)
    new_num = invoice_update.invoice_number or invoice.invoice_number
    new_vendor = invoice_update.vendor_name or invoice.vendor_name

    if new_num != invoice.invoice_number or new_vendor != invoice.vendor_name:
        duplicate = (
            db.query(Invoice)
            .filter(
                Invoice.user_id == current_user.id,
                Invoice.id != invoice.id,
                func.lower(func.trim(Invoice.invoice_number)) == func.lower(new_num.strip()),
                func.lower(func.trim(Invoice.vendor_name)) == func.lower(new_vendor.strip()),
            )
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An invoice with number '{new_num}' already exists for vendor '{new_vendor}'.",
            )

    # Validate that total amount is not reduced below sum of already-paid amounts
    if invoice_update.total_amount is not None:
        total_paid = sum((p.amount for p in invoice.payments), Decimal("0.00"))
        if invoice_update.total_amount < total_paid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reduce invoice total to ${invoice_update.total_amount} because ${total_paid} has already been paid against this invoice.",
            )

    update_data = invoice_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(invoice, field, value)

    # Update review status: respect explicit status or check validation issues
    if invoice_update.status is not None:
        invoice.status = invoice_update.status.strip().upper()
    elif (
        invoice_update.total_amount is not None
        or invoice_update.subtotal is not None
        or invoice_update.tax_amount is not None
        or invoice_update.due_date is not None
        or invoice_update.invoice_date is not None
    ):
        subtotal = invoice.subtotal
        tax_amt = invoice.tax_amount
        total_amt = invoice.total_amount
        inv_date = invoice.invoice_date
        due_date = invoice.due_date

        has_arithmetic_issue = False
        if subtotal is not None and tax_amt is not None:
            diff = abs((subtotal + tax_amt) - total_amt)
            if diff > Decimal("0.05"):
                has_arithmetic_issue = True
        has_date_issue = bool(due_date and inv_date and due_date < inv_date)

        if has_arithmetic_issue or has_date_issue:
            invoice.status = "NEEDS_REVIEW"
        elif invoice.status == "NEEDS_REVIEW":
            invoice.status = "CONFIRMED"

    db.commit()
    db.refresh(invoice)
    return _build_invoice_response(invoice)


@router.delete(
    "/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an invoice",
)
def delete_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes invoice and any associated stored file."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )

    # Delete file from storage if present
    if invoice.file_path:
        file_to_del = settings.resolved_upload_dir / invoice.file_path
        if file_to_del.is_file():
            try:
                os.remove(file_to_del)
            except OSError:
                pass

    db.delete(invoice)
    db.commit()
    return None


@router.get(
    "/{invoice_id}/file",
    summary="Download or view the uploaded invoice document",
)
def get_invoice_file(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Securely streams the invoice attachment with path traversal and tenant checks."""
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        .first()
    )
    if not invoice or not invoice.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice file attachment not found.",
        )

    # Strictly verify path is contained within upload directory (prevents path traversal)
    clean_token = Path(invoice.file_path).name
    target_file = (settings.resolved_upload_dir / clean_token).resolve()
    upload_root = settings.resolved_upload_dir.resolve()

    if not target_file.is_relative_to(upload_root) or not target_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice file attachment not found on disk.",
        )

    media_type = invoice.file_content_type or "application/octet-stream"
    return FileResponse(
        path=str(target_file),
        media_type=media_type,
        filename=invoice.file_name or clean_token,
    )


def _build_invoice_response(invoice: Invoice, ref_date: Optional[date] = None) -> InvoiceResponse:
    """Helper to construct safe InvoiceResponse including dynamically calculated financial properties, audit evidence, and ML screening."""
    detail = calculate_detailed_invoice_payment_info(invoice, ref_date)
    legacy_status = calculate_invoice_financials(invoice, ref_date)[2]
    anomaly_status = invoice.anomaly.status if invoice.anomaly else None
    anomaly_explanation = invoice.anomaly.explanation if invoice.anomaly else None

    return InvoiceResponse(
        id=invoice.id,
        user_id=invoice.user_id,
        invoice_number=invoice.invoice_number,
        vendor_name=invoice.vendor_name,
        customer_name=invoice.customer_name,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        status=invoice.status,
        file_name=invoice.file_name,
        file_content_type=invoice.file_content_type,
        has_file=bool(invoice.file_path),
        notes=invoice.notes,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        total_paid=detail["total_paid"],
        amount_paid=detail["total_paid"],
        verified_paid=detail["verified_paid"],
        unverified_paid=detail["unverified_paid"],
        balance_due=detail["balance_due"],
        payment_status=legacy_status,
        granular_status=detail["payment_status"],
        actual_payment_date=detail["actual_payment_date"],
        days_late=detail["days_late"],
        days_overdue=detail["days_overdue"],
        days_remaining=detail["days_remaining"],
        evidence_source=detail["evidence_source"],
        matched_reference=detail["matched_reference"],
        mismatch_reason=detail["mismatch_reason"],
        reconciliation_status=invoice.status,
        anomaly_status=anomaly_status,
        anomaly_explanation=anomaly_explanation,
    )
