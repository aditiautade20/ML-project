import csv
from datetime import date
import io
import json
import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.database import get_db
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.reconciliation import ReconciliationBatch, ReconciliationItem
from app.models.user import User
from app.schemas.reconciliation import (
    ConfirmPaymentActionRequest,
    FilePreviewResponse,
    ReconciliationBatchDetailResponse,
    ReconciliationBatchSummary,
    ReconciliationItemResponse,
    UpdateItemStatusRequest,
)
from app.services.extractor import parse_date_flexible
from app.services.payment_service import calculate_invoice_financials, validate_payment_bounds
from app.services.reconciliation_parser import (
    auto_map_columns,
    compute_file_hash,
    detect_column_mappings,
    parse_tabular_file,
)
from app.services.reconciliation_service import (
    run_bank_reconciliation,
    run_combined_reconciliation,
    run_ledger_reconciliation,
)
from app.services.report_service import sanitize_for_csv
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit

router = APIRouter(prefix="/api/reconciliation", tags=["Reconciliation Centre"])


@router.post(
    "/preview",
    response_model=FilePreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview uploaded tabular file and get auto-detected column mappings",
)
async def preview_reconciliation_file(
    file: UploadFile = File(...),
    file_type: str = Query("LEDGER", description="LEDGER or BANK"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Parses an uploaded CSV or Excel file, checks for previous duplicate uploads,
    and returns detected headers with suggested column mappings and preview rows.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was uploaded.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes).",
        )
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed limit (10MB).",
        )

    headers, rows, file_hash, errors = parse_tabular_file(content, file.filename)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error parsing file: {'; '.join(errors)}",
        )

    # Check if this exact file hash was already uploaded by this user
    is_duplicate = False
    existing_batch = (
        db.query(ReconciliationBatch)
        .filter(
            ReconciliationBatch.user_id == current_user.id,
            (ReconciliationBatch.ledger_hash == file_hash) | (ReconciliationBatch.bank_hash == file_hash),
        )
        .first()
    )
    warnings = []
    if existing_batch:
        is_duplicate = True
        warnings.append(
            f"Notice: A file with this exact content hash was previously reconciled in batch #{existing_batch.id} "
            f"('{existing_batch.title}' on {existing_batch.created_at.strftime('%Y-%m-%d')})."
        )

    mapping_result = detect_column_mappings(headers, file_type.upper(), rows=rows)

    return FilePreviewResponse(
        filename=file.filename,
        file_type="XLSX" if file.filename.lower().endswith(".xlsx") else "CSV",
        headers=headers,
        total_rows=len(rows),
        sample_rows=rows[:5],
        suggested_mapping=mapping_result["suggested_mapping"],
        mapping_statuses=mapping_result["mapping_statuses"],
        mapping_warnings=mapping_result["mapping_warnings"],
        ambiguous_columns=mapping_result["ambiguous_columns"],
        file_hash=file_hash,
        is_duplicate_hash=is_duplicate,
        validation_warnings=warnings,
    )


@router.post(
    "/run-ledger",
    response_model=ReconciliationBatchDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Accounting Ledger Reconciliation",
)
async def execute_ledger_reconciliation(
    file: UploadFile = File(...),
    column_mapping: Optional[str] = Form(None),
    tolerance: float = Form(0.05),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compares customer's uploaded accounting ledger against saved InvoiceIQ invoices.
    Identifies exact matches, amount mismatches, tax mismatches, missing invoices, and duplicates.
    """
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes).",
        )
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed limit (10MB).",
        )
    mapping_dict = None
    if column_mapping:
        try:
            mapping_dict = json.loads(column_mapping)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON provided in column_mapping.",
            )

    try:
        batch = run_ledger_reconciliation(
            user_id=current_user.id,
            file_content=content,
            filename=file.filename,
            column_mapping=mapping_dict,
            amount_tolerance=Decimal(str(tolerance)),
            db=db,
        )
        return _format_batch_detail_response(batch)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        logger.error(f"Ledger reconciliation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation error: {str(e)}",
        )


@router.post(
    "/run-bank",
    response_model=ReconciliationBatchDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Bank Statement Reconciliation",
)
async def execute_bank_reconciliation(
    file: UploadFile = File(...),
    column_mapping: Optional[str] = Form(None),
    tolerance: float = Form(0.05),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Matches bank statement transactions against recorded payments and open invoice balances.
    Does NOT modify financial records automatically. Proposed settlements require user confirmation.
    """
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes).",
        )
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed limit (10MB).",
        )
    mapping_dict = None
    if column_mapping:
        try:
            mapping_dict = json.loads(column_mapping)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON provided in column_mapping.",
            )

    try:
        batch = run_bank_reconciliation(
            user_id=current_user.id,
            file_content=content,
            filename=file.filename,
            column_mapping=mapping_dict,
            amount_tolerance=Decimal(str(tolerance)),
            db=db,
        )
        return _format_batch_detail_response(batch)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        logger.error(f"Bank reconciliation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation error: {str(e)}",
        )


@router.post(
    "/run-combined",
    response_model=ReconciliationBatchDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Combined 4-Way Reconciliation (Invoice + Ledger + Payment + Bank)",
)
async def execute_combined_reconciliation(
    ledger_file: UploadFile = File(...),
    bank_file: UploadFile = File(...),
    ledger_mapping: Optional[str] = Form(None),
    bank_mapping: Optional[str] = Form(None),
    tolerance: float = Form(0.05),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cross-checks invoice, accounting ledger, payment ledger, and bank statement.
    """
    l_content = await ledger_file.read()
    b_content = await bank_file.read()

    if len(l_content) == 0 or len(b_content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more uploaded files are empty (0 bytes).",
        )
    if len(l_content) > MAX_FILE_SIZE or len(b_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed limit (10MB).",
        )

    l_map = json.loads(ledger_mapping) if ledger_mapping else None
    b_map = json.loads(bank_mapping) if bank_mapping else None

    try:
        batch = run_combined_reconciliation(
            user_id=current_user.id,
            ledger_content=l_content,
            ledger_filename=ledger_file.filename,
            bank_content=b_content,
            bank_filename=bank_file.filename,
            ledger_mapping=l_map,
            bank_mapping=b_map,
            amount_tolerance=Decimal(str(tolerance)),
            db=db,
        )
        return _format_batch_detail_response(batch)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        logger.error(f"Combined reconciliation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Combined reconciliation error: {str(e)}",
        )


@router.get(
    "/batches",
    response_model=List[ReconciliationBatchSummary],
    status_code=status.HTTP_200_OK,
    summary="List all historical reconciliation runs for the current user",
)
def list_reconciliation_batches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns past reconciliation runs for audit review."""
    batches = (
        db.query(ReconciliationBatch)
        .filter(ReconciliationBatch.user_id == current_user.id)
        .order_by(desc(ReconciliationBatch.created_at))
        .all()
    )
    return batches


@router.get(
    "/batches/{batch_id}",
    response_model=ReconciliationBatchDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get detailed reconciliation results with discrepancy items",
)
def get_reconciliation_batch(
    batch_id: int,
    status_filter: Optional[str] = Query(None, description="Filter by match_status"),
    review_filter: Optional[str] = Query(None, description="Filter by review_status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetches a specific reconciliation batch with items scoped to current user."""
    batch = (
        db.query(ReconciliationBatch)
        .filter(ReconciliationBatch.id == batch_id, ReconciliationBatch.user_id == current_user.id)
        .first()
    )
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation batch not found.",
        )

    return _format_batch_detail_response(batch, status_filter, review_filter)


@router.patch(
    "/batches/{batch_id}/items/{item_id}",
    response_model=ReconciliationItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update review status of a discrepancy item (CONFIRMED / DISMISSED)",
)
def update_reconciliation_item_status(
    batch_id: int,
    item_id: int,
    req: UpdateItemStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allows accountant to mark a discrepancy as confirmed or dismissed with audit trail."""
    item = (
        db.query(ReconciliationItem)
        .filter(
            ReconciliationItem.id == item_id,
            ReconciliationItem.batch_id == batch_id,
            ReconciliationItem.user_id == current_user.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation item not found.",
        )

    item.review_status = req.review_status
    db.commit()
    db.refresh(item)
    return item


@router.post(
    "/batches/{batch_id}/items/{item_id}/confirm-payment",
    response_model=ReconciliationItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Explicitly confirm a proposed bank match and record payment in InvoiceIQ",
)
def confirm_and_record_bank_payment(
    batch_id: int,
    item_id: int,
    req: ConfirmPaymentActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    CRITICAL SAFETY ENFORCEMENT:
    Explicit action to record a payment suggested by a bank statement match.
    Validates balance bounds, creates a persistent Payment, recalculates invoice status,
    and updates reconciliation review status to CONFIRMED.
    """
    item = (
        db.query(ReconciliationItem)
        .filter(
            ReconciliationItem.id == item_id,
            ReconciliationItem.batch_id == batch_id,
            ReconciliationItem.user_id == current_user.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation item not found.",
        )

    if not item.invoice_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This bank transaction is not linked to a specific invoice. Cannot create payment.",
        )

    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == item.invoice_id, Invoice.user_id == current_user.id)
        .first()
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated invoice not found.",
        )

    # Determine payment amount from item's actual value
    amount_match = re.search(r"(\d{1,3}(?:,\d{2,3})*\.\d{2}|\d+\.\d{2})", item.actual_value or "")
    if not amount_match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract payment amount from actual bank value.",
        )
    payment_amount = Decimal(amount_match.group(1).replace(",", ""))

    # Validate against overpayment
    validate_payment_bounds(invoice, payment_amount)

    pay_date = req.payment_date or (
        parse_date_flexible(item.transaction_date) or date.today()
    )

    # Create new Payment record
    new_payment = Payment(
        invoice_id=invoice.id,
        user_id=current_user.id,
        amount=payment_amount,
        payment_date=pay_date,
        payment_method=req.payment_method,
        reference=item.record_identifier,
        notes=req.notes or f"Reconciled from bank statement '{item.batch.bank_filename or 'Bank Statement'}'",
    )
    db.add(new_payment)
    db.flush()

    # Update item status
    item.payment_id = new_payment.id
    item.review_status = "CONFIRMED"
    item.match_status = "EXACT_MATCH"
    item.evidence_text = f"Payment of {item.currency} {payment_amount:.2f} explicitly recorded and reconciled."
    item.action_recommendation = "Payment posted to accounts payable ledger."

    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/batches/{batch_id}/export-csv",
    status_code=status.HTTP_200_OK,
    summary="Export reconciliation report to CSV with Formula Injection Sanitization",
)
def export_reconciliation_csv(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Exports reconciliation results to an RFC 4180-compliant CSV.
    Enforces formula injection protection by prepending a single quote to dangerous triggers.
    """
    batch = (
        db.query(ReconciliationBatch)
        .filter(ReconciliationBatch.id == batch_id, ReconciliationBatch.user_id == current_user.id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header
    writer.writerow([
        "Record ID",
        "Type",
        "Match Status",
        "Vendor / Counterparty",
        "Transaction Date",
        "Expected Value",
        "Actual Value",
        "Discrepancy Amount",
        "Currency",
        "Evidence Details",
        "Recommended Action",
        "Review Status",
    ])

    for itm in batch.items:
        writer.writerow([
            sanitize_for_csv(itm.record_identifier),
            sanitize_for_csv(itm.item_type),
            sanitize_for_csv(itm.match_status),
            sanitize_for_csv(itm.vendor_or_counterparty or "N/A"),
            sanitize_for_csv(itm.transaction_date or "N/A"),
            sanitize_for_csv(itm.expected_value or "N/A"),
            sanitize_for_csv(itm.actual_value or "N/A"),
            sanitize_for_csv(f"{itm.discrepancy_amount:.2f}" if itm.discrepancy_amount is not None else "0.00"),
            sanitize_for_csv(itm.currency),
            sanitize_for_csv(itm.evidence_text or ""),
            sanitize_for_csv(itm.action_recommendation or ""),
            sanitize_for_csv(itm.review_status),
        ])

    csv_data = output.getvalue()
    filename = f"reconciliation_batch_{batch_id}_{batch.batch_type.lower()}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/batches/{batch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a reconciliation batch and its items",
)
def delete_reconciliation_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes reconciliation batch and associated items without affecting invoices or payments."""
    batch = (
        db.query(ReconciliationBatch)
        .filter(ReconciliationBatch.id == batch_id, ReconciliationBatch.user_id == current_user.id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")

    db.delete(batch)
    db.commit()
    return None


def _format_batch_detail_response(
    batch: ReconciliationBatch,
    status_filter: Optional[str] = None,
    review_filter: Optional[str] = None,
) -> ReconciliationBatchDetailResponse:
    summary_dict = {}
    if batch.summary_json:
        try:
            summary_dict = json.loads(batch.summary_json)
        except Exception:
            pass

    items_query = batch.items
    if status_filter:
        items_query = [i for i in items_query if i.match_status.upper() == status_filter.upper()]
    if review_filter:
        items_query = [i for i in items_query if i.review_status.upper() == review_filter.upper()]

    return ReconciliationBatchDetailResponse(
        id=batch.id,
        batch_type=batch.batch_type,
        title=batch.title,
        status=batch.status,
        ledger_filename=batch.ledger_filename,
        bank_filename=batch.bank_filename,
        total_records=batch.total_records,
        exact_matches=batch.exact_matches,
        mismatches=batch.mismatches,
        unmatched_records=batch.unmatched_records,
        amount_tolerance=batch.amount_tolerance,
        created_at=batch.created_at,
        summary=summary_dict,
        items=items_query,
    )
