from datetime import date, timedelta
from decimal import Decimal
import os
import pytest

from app.models.invoice import Invoice
from app.models.reconciliation import ReconciliationBatch, ReconciliationItem
from app.models.user import User
from app.services.auth_service import hash_password
from app.services.report_service import get_dashboard_analytics


@pytest.fixture()
def test_user(db_session):
    user = User(
        email="simplify_user@example.com",
        name="Simplify Test User",
        hashed_password=hash_password("Password123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def get_auth_token(client, email="simplify_jwt@example.com"):
    client.post(
        "/api/auth/signup",
        json={"name": "Simplify User", "email": email, "password": "Password123!"},
    )
    login_res = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return login_res.json()["access_token"]


# -------------------------------------------------------------------------
# 1. Simplified Dashboard: Prioritized Metrics
# -------------------------------------------------------------------------

def test_dashboard_prioritized_metrics_and_verification_status(db_session, test_user):
    """
    Dashboard prioritizes:
    1. Total invoice expenses
    2. Number of invoices processed
    3. Number of mismatches found
    4. Number of upcoming due dates
    5. Recent invoices with verification status
    """
    today = date.today()

    # Invoice 1: Valid & Confirmed, upcoming due date in 3 days
    inv1 = Invoice(
        user_id=test_user.id,
        invoice_number="INV-SIMP-01",
        vendor_name="Acme Corp",
        invoice_date=today - timedelta(days=2),
        due_date=today + timedelta(days=3),
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("10.00"),
        total_amount=Decimal("110.00"),
        status="CONFIRMED",
    )
    # Invoice 2: Needs Review (arithmetic discrepancy: 200 + 10 != 220), due today
    inv2 = Invoice(
        user_id=test_user.id,
        invoice_number="INV-SIMP-02",
        vendor_name="Beta Services",
        invoice_date=today - timedelta(days=5),
        due_date=today,
        subtotal=Decimal("200.00"),
        tax_amount=Decimal("10.00"),
        total_amount=Decimal("220.00"),
        status="NEEDS_REVIEW",
    )
    # Invoice 3: No due date specified
    inv3 = Invoice(
        user_id=test_user.id,
        invoice_number="INV-SIMP-03",
        vendor_name="Gamma Supplies",
        invoice_date=today - timedelta(days=1),
        due_date=None,
        subtotal=Decimal("50.00"),
        tax_amount=Decimal("5.00"),
        total_amount=Decimal("55.00"),
        status="CONFIRMED",
    )
    db_session.add_all([inv1, inv2, inv3])
    db_session.commit()

    # Add a reconciliation batch with 2 mismatches
    batch = ReconciliationBatch(
        user_id=test_user.id,
        batch_type="LEDGER",
        title="Ledger Batch 1",
        total_records=5,
        exact_matches=3,
        mismatches=2,
        unmatched_records=0,
    )
    db_session.add(batch)
    db_session.commit()

    # Query dashboard analytics service directly
    res = get_dashboard_analytics(test_user.id, db_session)

    # 1. Total invoice expenses
    assert res["total_invoiced_amount"] == Decimal("385.00")
    # 2. Number of invoices processed
    assert res["total_invoices_count"] == 3
    # 3. Number of mismatches found (reconciliation mismatches + needs_review invoices)
    assert res["mismatches_count"] >= 2
    # 4. Number of upcoming due dates (due_date >= today: inv1 and inv2)
    assert res["upcoming_due_dates_count"] == 2

    # 5. Recent invoices with verification status
    recent = res["recent_invoices"]
    assert len(recent) == 3
    simp02 = next((i for i in recent if i["invoice_number"] == "INV-SIMP-02"), None)
    assert simp02 is not None
    assert simp02["verification_status"] == "NEEDS_REVIEW"

    simp01 = next((i for i in recent if i["invoice_number"] == "INV-SIMP-01"), None)
    assert simp01 is not None
    assert simp01["verification_status"] == "CONFIRMED"


# -------------------------------------------------------------------------
# 2. Duplicate Invoice Prevention: Single Source of Truth
# -------------------------------------------------------------------------

def test_duplicate_invoices_prevented_and_not_double_counted(client):
    """Attempting to post duplicate invoices results in 409 Conflict, avoiding double counting."""
    token = get_auth_token(client, "dup_prevent@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "invoice_number": "INV-NO-DUP",
        "vendor_name": "Unique Supplier",
        "invoice_date": str(date.today()),
        "total_amount": 500.00,
    }

    # First creation succeeds
    res1 = client.post("/api/invoices/", json=payload, headers=headers)
    assert res1.status_code == 201

    # Second creation with identical number and vendor fails with 409
    res2 = client.post("/api/invoices/", json=payload, headers=headers)
    assert res2.status_code == 409

    # Verify total invoiced expenses on dashboard counts it exactly once
    dash_res = client.get("/api/reports/dashboard", headers=headers)
    assert dash_res.status_code == 200
    d_data = dash_res.json()
    assert float(d_data["total_invoiced_amount"]) == 500.00
    assert d_data["total_invoices_count"] == 1


# -------------------------------------------------------------------------
# 3. Due Date Reminder Rules & Payment Independence
# -------------------------------------------------------------------------

def test_due_date_does_not_infer_payment_status(client):
    """
    Invoices with past due dates are not automatically classified as 'never paid' or 'unpaid'
    by inference; due date is strictly a timing indicator.
    """
    token = get_auth_token(client, "due_date_test@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    past_due = str(date.today() - timedelta(days=10))
    inv_res = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-DUE-01",
            "vendor_name": "Timing Vendor",
            "invoice_date": str(date.today() - timedelta(days=20)),
            "due_date": past_due,
            "total_amount": 250.00,
        },
        headers=headers,
    )
    assert inv_res.status_code == 201
    inv_data = inv_res.json()

    # The invoice details correctly report the due date without payment gatekeeping
    assert inv_data["due_date"] == past_due
    assert inv_data["vendor_name"] == "Timing Vendor"
    assert inv_data["total_amount"] == "250.00"
    assert inv_data["status"] == "CONFIRMED"


# -------------------------------------------------------------------------
# 4. Due Date Helper JavaScript Rules File Verification
# -------------------------------------------------------------------------

def test_due_date_helper_module_exists_and_implements_rules():
    """Verify frontend/src/utils/dueDateHelper.js exists and exports getDueDateReminder."""
    helper_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "src", "utils", "dueDateHelper.js"
    )
    assert os.path.exists(helper_path), f"File not found: {helper_path}"

    with open(helper_path, "r", encoding="utf-8") as f:
        code = f.read()

    assert "getDueDateReminder" in code
    assert "Due date not found" in code
    assert "Due today" in code
    assert "Due date passed" in code
    assert "Due in " in code
