from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.report import DashboardAnalyticsResponse, ReportsDataResponse
from app.utils.security import get_current_user
from app.services.report_service import (
    get_dashboard_analytics,
    get_reports_data,
    generate_invoices_csv,
    generate_payments_csv,
    generate_outstanding_csv,
    generate_reconciliation_csv,
    generate_summary_pdf,
)

router = APIRouter(prefix="/api/reports", tags=["Reports & Analytics"])


@router.get(
    "/dashboard",
    response_model=DashboardAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated dashboard metrics and trends for current user",
)
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns authentic financial summary, monthly trends, and recent activity
    calculated strictly from the authenticated user's records.
    """
    return get_dashboard_analytics(current_user.id, db)


@router.get(
    "/analytics",
    response_model=ReportsDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Get detailed financial reports with period and vendor filters",
)
def get_analytics_report(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    vendor: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns filtered summary metrics, vendor breakdown, monthly trends,
    invoices, payments, and reconciliation summaries for the current user.
    """
    try:
        return get_reports_data(current_user.id, db, start_date, end_date, vendor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/export/invoices",
    status_code=status.HTTP_200_OK,
    summary="Export invoice records as CSV",
)
def export_invoices(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    vendor: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Exports invoices to CSV with spreadsheet formula injection protection.
    Respects date range and vendor filters.
    """
    try:
        csv_data = generate_invoices_csv(current_user.id, db, start_date, end_date, vendor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    today_str = date.today().isoformat()
    filename = f"invoiceiq_invoices_{today_str}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.get(
    "/export/payments",
    status_code=status.HTTP_200_OK,
    summary="Export payment records as CSV",
)
def export_payments(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    vendor: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Exports recorded payments to CSV with spreadsheet formula injection protection.
    Respects date range and vendor filters.
    """
    try:
        csv_data = generate_payments_csv(current_user.id, db, start_date, end_date, vendor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    today_str = date.today().isoformat()
    filename = f"invoiceiq_payments_{today_str}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.get(
    "/export/outstanding",
    status_code=status.HTTP_200_OK,
    summary="Export outstanding and overdue invoices as CSV",
)
def export_outstanding(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    vendor: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Exports outstanding/overdue invoices to CSV with formula injection protection.
    Respects date range and vendor filters.
    """
    try:
        csv_data = generate_outstanding_csv(current_user.id, db, start_date, end_date, vendor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    today_str = date.today().isoformat()
    filename = f"invoiceiq_outstanding_{today_str}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.get(
    "/export/reconciliation",
    status_code=status.HTTP_200_OK,
    summary="Export reconciliation items and discrepancy audit log as CSV",
)
def export_reconciliation(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    vendor: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Exports reconciliation matched records, discrepancies, duplicates,
    and pending review items to CSV with spreadsheet formula injection protection.
    """
    try:
        csv_data = generate_reconciliation_csv(current_user.id, db, start_date, end_date, vendor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    today_str = date.today().isoformat()
    filename = f"invoiceiq_reconciliation_{today_str}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.get(
    "/export/pdf",
    status_code=status.HTTP_200_OK,
    summary="Export executive summary as PDF",
)
def export_pdf(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    vendor: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a PDF financial report including generation date, selected period,
    and status distribution. Respects date range and vendor filters.
    """
    try:
        pdf_bytes = generate_summary_pdf(current_user, db, start_date, end_date, vendor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    today_str = date.today().isoformat()
    filename = f"invoiceiq_report_{today_str}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )
