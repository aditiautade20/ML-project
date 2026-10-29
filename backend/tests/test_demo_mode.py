from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.anomaly import InvoiceAnomaly
from app.demo_seed import (
    DEMO_USER_EMAIL,
    DEMO_USER_PASSWORD,
    seed_demo_data,
    clean_demo_data,
    get_or_create_demo_user,
)
from app.services.payment_service import calculate_invoice_financials


def test_seed_demo_data_creates_records(db_session: Session):
    """
    Verify that seed_demo_data creates the demo user and exactly 10 curated invoices
    with appropriate financial states and payments.
    """
    demo_user = seed_demo_data(db_session, run_ml_assessment=True)
    assert demo_user is not None
    assert demo_user.email == DEMO_USER_EMAIL

    invoices = db_session.query(Invoice).filter(Invoice.user_id == demo_user.id).all()
    assert len(invoices) == 10

    # Verify presence of key test fixtures
    inv_map = {inv.invoice_number: inv for inv in invoices}
    assert "INV-DEMO-001" in inv_map  # Unpaid
    assert "INV-DEMO-002" in inv_map  # Partially paid
    assert "INV-DEMO-003" in inv_map  # Fully paid
    assert "INV-DEMO-004" in inv_map  # Overdue
    assert "INV-DEMO-005" in inv_map  # No due date
    assert "INV-DEMO-008" in inv_map  # ML Outlier ($12,850)

    # Verify INV-DEMO-005 has no due date
    assert inv_map["INV-DEMO-005"].due_date is None

    # Verify INV-DEMO-002 partial payment financials
    paid_002, bal_002, stat_002 = calculate_invoice_financials(inv_map["INV-DEMO-002"])
    assert stat_002 == "PARTIAL"
    assert paid_002 == Decimal("250.00")
    assert bal_002 == Decimal("370.00")

    # Verify INV-DEMO-003 full payment financials
    paid_003, bal_003, stat_003 = calculate_invoice_financials(inv_map["INV-DEMO-003"])
    assert stat_003 == "PAID"
    assert bal_003 == Decimal("0.00")

    # Verify INV-DEMO-004 is overdue
    paid_004, bal_004, stat_004 = calculate_invoice_financials(inv_map["INV-DEMO-004"])
    assert stat_004 == "OVERDUE"
    assert paid_004 == Decimal("0.00")

    # Verify ML assessment ran and flagged the outlier
    anomalies = db_session.query(InvoiceAnomaly).join(Invoice).filter(Invoice.user_id == demo_user.id).all()
    assert len(anomalies) == 10
    outlier_anomaly = next((a for a in anomalies if a.invoice.invoice_number == "INV-DEMO-008"), None)
    assert outlier_anomaly is not None
    assert outlier_anomaly.status == "POTENTIALLY_UNUSUAL"
    assert "higher than the historical median" in outlier_anomaly.explanation


def test_seed_demo_data_is_idempotent(db_session: Session):
    """
    Calling seed_demo_data multiple times should reset cleanly without creating duplicate records.
    """
    seed_demo_data(db_session, run_ml_assessment=False)
    user = db_session.query(User).filter(User.email == DEMO_USER_EMAIL).first()
    count_1 = db_session.query(Invoice).filter(Invoice.user_id == user.id).count()
    assert count_1 == 10

    # Run seed again
    seed_demo_data(db_session, run_ml_assessment=False)
    user = db_session.query(User).filter(User.email == DEMO_USER_EMAIL).first()
    count_2 = db_session.query(Invoice).filter(Invoice.user_id == user.id).count()
    assert count_2 == 10


def test_clean_demo_data_preserves_real_users(db_session: Session):
    """
    clean_demo_data must remove all demo user invoices and user account,
    while leaving non-demo accounts and invoices completely untouched.
    """
    # Create a real user with an invoice
    real_user = User(name="Real Client", email="real.client@corporate.com", hashed_password="pwd")
    db_session.add(real_user)
    db_session.commit()
    db_session.refresh(real_user)

    real_invoice = Invoice(
        user_id=real_user.id,
        invoice_number="INV-REAL-999",
        vendor_name="Essential Vendor",
        invoice_date=date.today(),
        total_amount=Decimal("1500.00"),
        status="CONFIRMED",
    )
    db_session.add(real_invoice)
    db_session.commit()

    # Seed demo data
    seed_demo_data(db_session, run_ml_assessment=False)

    # Now clean demo data
    cleaned_count = clean_demo_data(db_session)
    assert cleaned_count == 10

    # Verify demo user is gone
    demo_user = db_session.query(User).filter(User.email == DEMO_USER_EMAIL).first()
    assert demo_user is None
    demo_invoices = db_session.query(Invoice).filter(Invoice.invoice_number.startswith("INV-DEMO-")).all()
    assert len(demo_invoices) == 0

    # Verify real user and real invoice are untouched
    still_existing_user = db_session.query(User).filter(User.id == real_user.id).first()
    assert still_existing_user is not None
    still_existing_inv = db_session.query(Invoice).filter(Invoice.id == real_invoice.id).first()
    assert still_existing_inv is not None
    assert still_existing_inv.invoice_number == "INV-REAL-999"


def test_demo_user_authentication_and_api_isolation(client, db_session: Session):
    """
    Verify that the demo user can authenticate via the standard /api/auth/login endpoint,
    access their invoices, and non-demo users never see demo records.
    """
    # 1. Seed demo data
    seed_demo_data(db_session, run_ml_assessment=True)

    # 2. Login as demo user
    login_resp = client.post(
        "/api/auth/login",
        json={"email": DEMO_USER_EMAIL, "password": DEMO_USER_PASSWORD},
    )
    assert login_resp.status_code == 200
    demo_token = login_resp.json()["access_token"]
    demo_headers = {"Authorization": f"Bearer {demo_token}"}

    # 3. Fetch demo invoices (paginated response)
    demo_inv_resp = client.get("/api/invoices", headers=demo_headers)
    assert demo_inv_resp.status_code == 200
    demo_data = demo_inv_resp.json()
    assert demo_data["total"] == 10
    assert len(demo_data["items"]) == 10

    # 4. Check dashboard analytics for demo user
    stats_resp = client.get("/api/reports/dashboard", headers=demo_headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_invoices_count"] == 10
    assert stats["overdue_count"] >= 1
    assert stats["anomalous_invoices_count"] >= 1

    # 5. Register a regular user and verify they see ZERO invoices
    reg_resp = client.post(
        "/api/auth/signup",
        json={"name": "Independent User", "email": "indep@example.com", "password": "SecurePassword123!"},
    )
    assert reg_resp.status_code == 201

    login_user_resp = client.post(
        "/api/auth/login",
        json={"email": "indep@example.com", "password": "SecurePassword123!"},
    )
    assert login_user_resp.status_code == 200
    user_token = login_user_resp.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    user_inv_resp = client.get("/api/invoices", headers=user_headers)
    assert user_inv_resp.status_code == 200
    assert user_inv_resp.json()["total"] == 0
    assert len(user_inv_resp.json()["items"]) == 0
