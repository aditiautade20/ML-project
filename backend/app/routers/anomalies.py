import json
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.user import User
from app.models.invoice import Invoice
from app.models.anomaly import InvoiceAnomaly
from app.schemas.anomaly import (
    AnomalySummaryResponse,
    InvoiceAnomalyResponse,
    ReviewAnomalyRequest,
)
from app.utils.security import get_current_user
from app.services.anomaly_service import (
    assess_user_invoices,
    MIN_INVOICES_FOR_ANOMALY_MODEL,
    DISCLAIMER_TEXT,
)

router = APIRouter(prefix="/api/anomalies", tags=["ML Anomaly Detection"])


def _extract_rule_warnings(factors_json: Optional[str]) -> List[str]:
    """Helper to extract rule warnings from JSON-encoded factors."""
    if not factors_json:
        return []
    try:
        factors = json.loads(factors_json)
        return factors.get("rule_warnings", [])
    except Exception:
        return []


def _build_anomaly_response(anomaly: InvoiceAnomaly) -> InvoiceAnomalyResponse:
    """Builds a standardized InvoiceAnomalyResponse schema."""
    inv = anomaly.invoice
    return InvoiceAnomalyResponse(
        id=anomaly.id,
        invoice_id=inv.id if inv else anomaly.invoice_id,
        invoice_number=inv.invoice_number if inv else "N/A",
        vendor_name=inv.vendor_name if inv else "N/A",
        invoice_date=inv.invoice_date,
        total_amount=inv.total_amount,
        currency=inv.currency or "USD",
        is_anomaly=anomaly.is_anomaly,
        anomaly_score=anomaly.anomaly_score,
        status=anomaly.status,
        risk_level=getattr(anomaly, "risk_level", "LOW") or "LOW",
        is_reviewed=bool(getattr(anomaly, "is_reviewed", False)),
        reviewed_at=getattr(anomaly, "reviewed_at", None),
        review_notes=getattr(anomaly, "review_notes", None),
        rule_warnings=_extract_rule_warnings(anomaly.factors_json),
        explanation=anomaly.explanation,
        model_version=anomaly.model_version,
        assessed_at=anomaly.assessed_at,
    )


@router.post(
    "/assess",
    response_model=AnomalySummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Run or refresh ML anomaly assessment for user's invoices",
)
def run_anomaly_assessment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Fits Isolation Forest machine learning model on all invoices belonging
    to the authenticated user and persists anomaly screening results.
    Strictly isolated per-user; never leaks or trains on other users' records.
    """
    summary = assess_user_invoices(current_user.id, db)
    return summary


@router.get(
    "/",
    response_model=AnomalySummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get saved anomaly assessments for current user",
)
def get_anomaly_assessments(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves persistently stored anomaly assessment results for current user.
    Supports filtering by status (POTENTIALLY_UNUSUAL, NO_UNUSUAL_PATTERN, REVIEWED, UNREVIEWED)
    and searching by invoice number or vendor name.
    """
    # Count total invoices for this user
    total_invoices = (
        db.query(Invoice).filter(Invoice.user_id == current_user.id).count()
    )

    if total_invoices < MIN_INVOICES_FOR_ANOMALY_MODEL:
        return AnomalySummaryResponse(
            status="INSUFFICIENT_DATA",
            message=(
                f"Insufficient data: At least {MIN_INVOICES_FOR_ANOMALY_MODEL} saved invoices "
                f"are required for machine learning analysis (currently have {total_invoices}). "
                f"Please add {MIN_INVOICES_FOR_ANOMALY_MODEL - total_invoices} more invoice(s) to enable assessment."
            ),
            total_invoices=total_invoices,
            assessed_count=0,
            anomalous_count=0,
            normal_count=0,
            reviewed_count=0,
            unreviewed_anomalous_count=0,
            min_required=MIN_INVOICES_FOR_ANOMALY_MODEL,
            disclaimer=DISCLAIMER_TEXT,
            items=[],
        )

    # Fetch stored anomalies joined with invoices
    query = (
        db.query(InvoiceAnomaly)
        .options(joinedload(InvoiceAnomaly.invoice))
        .join(Invoice, InvoiceAnomaly.invoice_id == Invoice.id)
        .filter(InvoiceAnomaly.user_id == current_user.id)
    )

    # Filter by anomaly status if requested
    if status_filter:
        sf = status_filter.upper()
        if sf in ["POTENTIALLY_UNUSUAL", "NO_UNUSUAL_PATTERN"]:
            query = query.filter(InvoiceAnomaly.status == sf)
        elif sf == "REVIEWED":
            query = query.filter(InvoiceAnomaly.is_reviewed.is_(True))
        elif sf == "UNREVIEWED":
            query = query.filter(InvoiceAnomaly.is_reviewed.is_(False))

    # Search filter
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.filter(
            (Invoice.invoice_number.ilike(term)) | (Invoice.vendor_name.ilike(term))
        )

    # Order: Anomalies first, then unreviewed first, then most recent assessment
    anomalies = query.order_by(
        InvoiceAnomaly.is_anomaly.desc(),
        InvoiceAnomaly.is_reviewed.asc(),
        InvoiceAnomaly.assessed_at.desc(),
    ).all()

    # Aggregate counts across all user's assessed records
    all_user_anomalies = (
        db.query(InvoiceAnomaly)
        .filter(InvoiceAnomaly.user_id == current_user.id)
        .all()
    )
    anomalous_count = sum(1 for a in all_user_anomalies if a.is_anomaly)
    normal_count = sum(1 for a in all_user_anomalies if not a.is_anomaly)
    reviewed_count = sum(1 for a in all_user_anomalies if a.is_reviewed)
    unreviewed_anomalous_count = sum(
        1 for a in all_user_anomalies if a.is_anomaly and not a.is_reviewed
    )

    items = [_build_anomaly_response(a) for a in anomalies]

    assessment_status = "COMPLETED" if all_user_anomalies else "NOT_ASSESSED"
    message = (
        f"Displaying {len(items)} assessed invoice(s). "
        f"{anomalous_count} flagged as potentially unusual ({reviewed_count} reviewed)."
        if all_user_anomalies
        else "No assessments have been run yet. Click 'Run Assessment' to analyze invoices."
    )

    return AnomalySummaryResponse(
        status=assessment_status,
        message=message,
        total_invoices=total_invoices,
        assessed_count=len(all_user_anomalies),
        anomalous_count=anomalous_count,
        normal_count=normal_count,
        reviewed_count=reviewed_count,
        unreviewed_anomalous_count=unreviewed_anomalous_count,
        min_required=MIN_INVOICES_FOR_ANOMALY_MODEL,
        disclaimer=DISCLAIMER_TEXT,
        items=items,
    )


@router.get(
    "/invoice/{invoice_id}",
    response_model=Optional[InvoiceAnomalyResponse],
    status_code=status.HTTP_200_OK,
    summary="Get anomaly assessment for a specific invoice",
)
def get_single_invoice_anomaly(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the anomaly screening record for a single invoice.
    Strict tenant isolation applied.
    """
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        .first()
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )

    anomaly = (
        db.query(InvoiceAnomaly)
        .options(joinedload(InvoiceAnomaly.invoice))
        .filter(InvoiceAnomaly.invoice_id == invoice_id, InvoiceAnomaly.user_id == current_user.id)
        .first()
    )

    if not anomaly:
        return None

    return _build_anomaly_response(anomaly)


@router.patch(
    "/invoice/{invoice_id}/review",
    response_model=InvoiceAnomalyResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark anomaly reviewed by invoice ID",
)
@router.post(
    "/invoice/{invoice_id}/review",
    response_model=InvoiceAnomalyResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark anomaly reviewed by invoice ID (POST alias)",
)
def mark_invoice_anomaly_reviewed(
    invoice_id: int,
    payload: Optional[ReviewAnomalyRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    anomaly = (
        db.query(InvoiceAnomaly)
        .options(joinedload(InvoiceAnomaly.invoice))
        .filter(InvoiceAnomaly.invoice_id == invoice_id, InvoiceAnomaly.user_id == current_user.id)
        .first()
    )
    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anomaly assessment record not found for invoice.",
        )

    now = datetime.now(timezone.utc)
    anomaly.is_reviewed = True
    anomaly.reviewed_at = now
    if payload and payload.review_notes:
        anomaly.review_notes = payload.review_notes.strip()

    db.commit()
    db.refresh(anomaly)
    return _build_anomaly_response(anomaly)


@router.delete(
    "/invoice/{invoice_id}/review",
    response_model=InvoiceAnomalyResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset review status by invoice ID",
)
def unmark_invoice_anomaly_reviewed(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    anomaly = (
        db.query(InvoiceAnomaly)
        .options(joinedload(InvoiceAnomaly.invoice))
        .filter(InvoiceAnomaly.invoice_id == invoice_id, InvoiceAnomaly.user_id == current_user.id)
        .first()
    )
    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anomaly assessment record not found for invoice.",
        )

    anomaly.is_reviewed = False
    anomaly.reviewed_at = None
    anomaly.review_notes = None

    db.commit()
    db.refresh(anomaly)
    return _build_anomaly_response(anomaly)


@router.patch(
    "/{anomaly_id}/review",
    response_model=InvoiceAnomalyResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark an invoice anomaly assessment as reviewed",
)
@router.post(
    "/{anomaly_id}/review",
    response_model=InvoiceAnomalyResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark an invoice anomaly assessment as reviewed (POST alias)",
)
def mark_anomaly_reviewed(
    anomaly_id: int,
    payload: Optional[ReviewAnomalyRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Allows customers/auditors to confirm manual review of a flagged invoice anomaly.
    
    Guarantees:
    - User data isolation: Operates strictly on current user's records.
    - Financial integrity: Never alters invoice amounts, balances, or payment statuses.
    - Audit tracking: Records reviewed_at timestamp and reviewer notes.
    """
    # Lookup by anomaly ID or invoice ID
    anomaly = (
        db.query(InvoiceAnomaly)
        .options(joinedload(InvoiceAnomaly.invoice))
        .filter(InvoiceAnomaly.id == anomaly_id, InvoiceAnomaly.user_id == current_user.id)
        .first()
    )
    if not anomaly:
        # Fallback to check if anomaly_id was supplied as invoice_id
        anomaly = (
            db.query(InvoiceAnomaly)
            .options(joinedload(InvoiceAnomaly.invoice))
            .filter(InvoiceAnomaly.invoice_id == anomaly_id, InvoiceAnomaly.user_id == current_user.id)
            .first()
        )

    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anomaly assessment record not found.",
        )

    now = datetime.now(timezone.utc)
    anomaly.is_reviewed = True
    anomaly.reviewed_at = now
    if payload and payload.review_notes:
        anomaly.review_notes = payload.review_notes.strip()

    db.commit()
    db.refresh(anomaly)

    return _build_anomaly_response(anomaly)


@router.delete(
    "/{anomaly_id}/review",
    response_model=InvoiceAnomalyResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset review status on an invoice anomaly",
)
def unmark_anomaly_reviewed(
    anomaly_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resets the review status for an anomaly back to unreviewed."""
    anomaly = (
        db.query(InvoiceAnomaly)
        .options(joinedload(InvoiceAnomaly.invoice))
        .filter(InvoiceAnomaly.id == anomaly_id, InvoiceAnomaly.user_id == current_user.id)
        .first()
    )
    if not anomaly:
        anomaly = (
            db.query(InvoiceAnomaly)
            .options(joinedload(InvoiceAnomaly.invoice))
            .filter(InvoiceAnomaly.invoice_id == anomaly_id, InvoiceAnomaly.user_id == current_user.id)
            .first()
        )

    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anomaly assessment record not found.",
        )

    anomaly.is_reviewed = False
    anomaly.reviewed_at = None
    anomaly.review_notes = None

    db.commit()
    db.refresh(anomaly)

    return _build_anomaly_response(anomaly)
