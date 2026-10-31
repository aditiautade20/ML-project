from datetime import date, datetime, timedelta
from decimal import Decimal
import os
import pytest

from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentAuditLog
from app.models.user import User
from app.services.auth_service import hash_password
from app.services.payment_service import (
    calculate_detailed_invoice_payment_info,
    calculate_invoice_financials,
)
from app.services.reconciliation_service import run_bank_reconciliation


@pytest.fixture()
def test_user(db_session):
    user = User(
        email="test_audit_model_user@example.com",
        name="Test Audit User",
        hashed_password=hash_password("Password123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def get_auth_token(client, email="pay_audit_user@example.com", name="Audit User"):
    """Helper to register and login a user, returning the Bearer token."""
    client.post(
        "/api/auth/signup",
        json={"name": name, "email": email, "password": "Password123!"},
    )
    login_res = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return login_res.json()["access_token"]


def create_invoice(client, headers, invoice_number, total="500.00", due_date=None, customer_name=None):
    """Helper to create an invoice for testing."""
    payload = {
        "invoice_number": invoice_number,
        "vendor_name": "Acme Supplier Inc",
        "customer_name": customer_name,
        "invoice_date": str(date.today() - timedelta(days=10)),
        "due_date": due_date,
        "total_amount": total,
    }
    res = client.post("/api/invoices/", json=payload, headers=headers)
    assert res.status_code == 201
    return res.json()


# -------------------------------------------------------------------------
# 1. Paid on Time vs Paid Late vs Overdue logic
# -------------------------------------------------------------------------

def test_invoice_paid_before_due_date_is_paid_on_time(db_session, test_user):
    """Invoice fully paid before its due date must be marked PAID_ON_TIME."""
    due = date.today() + timedelta(days=10)
    pay_d = date.today() - timedelta(days=2)

    inv = Invoice(
        user_id=test_user.id,
        invoice_number="INV-ONT-01",
        vendor_name="Global Tech Supplies",
        invoice_date=date.today() - timedelta(days=5),
        due_date=due,
        total_amount=Decimal("1200.00"),
        currency="USD",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    payment = Payment(
        invoice_id=inv.id,
        user_id=test_user.id,
        amount=Decimal("1200.00"),
        payment_date=pay_d,
        payment_method="Wire Transfer",
        reference="WIRE-9901",
        verification_status="VERIFIED",
        evidence_source="BANK_STATEMENT",
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(inv)

    detail = calculate_detailed_invoice_payment_info(inv)
    assert detail["payment_status"] == "PAID_ON_TIME"
    assert detail["verified_paid"] == Decimal("1200.00")
    assert detail["balance_due"] == Decimal("0.00")
    assert detail["actual_payment_date"] == pay_d
    assert detail["days_late"] == 0


def test_invoice_paid_on_exact_due_date_is_paid_on_time(db_session, test_user):
    """Invoice paid exactly on the due date is considered PAID_ON_TIME."""
    due = date.today()

    inv = Invoice(
        user_id=test_user.id,
        invoice_number="INV-ONT-02",
        vendor_name="Acme Parts",
        invoice_date=date.today() - timedelta(days=30),
        due_date=due,
        total_amount=Decimal("450.00"),
        currency="USD",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    payment = Payment(
        invoice_id=inv.id,
        user_id=test_user.id,
        amount=Decimal("450.00"),
        payment_date=due,
        payment_method="Bank Transfer",
        verification_status="VERIFIED",
        evidence_source="BANK_STATEMENT",
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(inv)

    detail = calculate_detailed_invoice_payment_info(inv)
    assert detail["payment_status"] == "PAID_ON_TIME"
    assert detail["balance_due"] == Decimal("0.00")
    assert detail["days_late"] == 0


def test_invoice_paid_after_due_date_is_paid_late(db_session, test_user):
    """Invoice paid after the due date must be marked PAID_LATE with accurate days_late."""
    due = date.today() - timedelta(days=12)
    pay_d = date.today() - timedelta(days=2)  # 10 days late

    inv = Invoice(
        user_id=test_user.id,
        invoice_number="INV-LATE-01",
        vendor_name="Vendor Solutions",
        invoice_date=date.today() - timedelta(days=40),
        due_date=due,
        total_amount=Decimal("800.00"),
        currency="USD",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    payment = Payment(
        invoice_id=inv.id,
        user_id=test_user.id,
        amount=Decimal("800.00"),
        payment_date=pay_d,
        payment_method="ACH",
        verification_status="VERIFIED",
        evidence_source="BANK_STATEMENT",
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(inv)

    detail = calculate_detailed_invoice_payment_info(inv)
    assert detail["payment_status"] == "PAID_LATE"
    assert detail["days_late"] == 10
    assert detail["actual_payment_date"] == pay_d
    assert detail["balance_due"] == Decimal("0.00")


def test_invoice_unpaid_after_due_date_is_overdue_unconfirmed(db_session, test_user):
    """Invoice with past due date and no verified payments is OVERDUE_UNCONFIRMED."""
    due = date.today() - timedelta(days=7)

    inv = Invoice(
        user_id=test_user.id,
        invoice_number="INV-OVD-01",
        vendor_name="Overdue Vendor Ltd",
        invoice_date=date.today() - timedelta(days=37),
        due_date=due,
        total_amount=Decimal("950.00"),
        currency="USD",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    detail = calculate_detailed_invoice_payment_info(inv)
    assert detail["payment_status"] == "OVERDUE_UNCONFIRMED"
    assert detail["days_overdue"] == 7
    assert detail["balance_due"] == Decimal("950.00")
    assert detail["verified_paid"] == Decimal("0.00")


# -------------------------------------------------------------------------
# 2. Partial Payments & Dynamic Transitions
# -------------------------------------------------------------------------

def test_partial_payment_before_and_after_due_date(db_session, test_user):
    """Partial payment before due date is PARTIALLY_PAID; past due date is PARTIALLY_PAID_OVERDUE."""
    # Future due date
    future_due = date.today() + timedelta(days=15)
    inv = Invoice(
        user_id=test_user.id,
        invoice_number="INV-PART-01",
        vendor_name="Partial Supplier",
        invoice_date=date.today() - timedelta(days=5),
        due_date=future_due,
        total_amount=Decimal("1000.00"),
        currency="USD",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    # 1. Partial payment of $400 verified
    p1 = Payment(
        invoice_id=inv.id,
        user_id=test_user.id,
        amount=Decimal("400.00"),
        payment_date=date.today(),
        payment_method="Bank Transfer",
        verification_status="VERIFIED",
        evidence_source="BANK_STATEMENT",
    )
    db_session.add(p1)
    db_session.commit()
    db_session.refresh(inv)

    detail1 = calculate_detailed_invoice_payment_info(inv)
    assert detail1["payment_status"] == "PARTIALLY_PAID"
    assert detail1["verified_paid"] == Decimal("400.00")
    assert detail1["balance_due"] == Decimal("600.00")

    # 2. Change due date to the past
    inv.due_date = date.today() - timedelta(days=5)
    db_session.commit()
    db_session.refresh(inv)

    detail2 = calculate_detailed_invoice_payment_info(inv)
    assert detail2["payment_status"] == "PARTIALLY_PAID_OVERDUE"
    assert detail2["days_overdue"] == 5
    assert detail2["balance_due"] == Decimal("600.00")


def test_multiple_payments_completing_invoice(db_session, test_user):
    """Multiple partial payments completing total balance transition to PAID_ON_TIME."""
    due = date.today() + timedelta(days=5)
    inv = Invoice(
        user_id=test_user.id,
        invoice_number="INV-MULTI-01",
        vendor_name="Multi-Pay Supplier",
        invoice_date=date.today() - timedelta(days=10),
        due_date=due,
        total_amount=Decimal("1500.00"),
        currency="USD",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    # Payment 1: $500
    db_session.add(Payment(
        invoice_id=inv.id, user_id=test_user.id, amount=Decimal("500.00"),
        payment_date=date.today() - timedelta(days=3), verification_status="VERIFIED", evidence_source="BANK_STATEMENT"
    ))
    # Payment 2: $600
    db_session.add(Payment(
        invoice_id=inv.id, user_id=test_user.id, amount=Decimal("600.00"),
        payment_date=date.today() - timedelta(days=2), verification_status="VERIFIED", evidence_source="BANK_STATEMENT"
    ))
    # Payment 3: $400
    db_session.add(Payment(
        invoice_id=inv.id, user_id=test_user.id, amount=Decimal("400.00"),
        payment_date=date.today() - timedelta(days=1), verification_status="VERIFIED", evidence_source="BANK_STATEMENT"
    ))
    db_session.commit()
    db_session.refresh(inv)

    detail = calculate_detailed_invoice_payment_info(inv)
    assert detail["payment_status"] == "PAID_ON_TIME"
    assert detail["verified_paid"] == Decimal("1500.00")
    assert detail["balance_due"] == Decimal("0.00")
    assert detail["actual_payment_date"] == date.today() - timedelta(days=1)


# -------------------------------------------------------------------------
# 3. Manual Payment & Verification Separation
# -------------------------------------------------------------------------

def test_manual_payment_defaults_to_unverified(client):
    """API payment recording defaults to UNVERIFIED and tracks claims separately."""
    token = get_auth_token(client, "unverified_test@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    inv = create_invoice(client, headers, "INV-UNVER-01", "750.00", due_date=str(date.today() + timedelta(days=7)))

    # Record manual payment
    res = client.post(
        "/api/payments/",
        json={
            "invoice_id": inv["id"],
            "amount": "750.00",
            "payment_date": str(date.today()),
            "payment_method": "Check",
            "reference": "CHK-8819",
            "notes": "Sent via mail",
        },
        headers=headers,
    )
    assert res.status_code == 201
    pay_data = res.json()
    assert pay_data["verification_status"] == "UNVERIFIED"
    assert pay_data["evidence_source"] == "MANUAL_ENTRY"

    # Verify invoice summary: unverified is tracked as a separate claim, status is PAYMENT_UNVERIFIED
    summary_res = client.get(f"/api/payments/invoice/{inv['id']}/summary", headers=headers)
    assert summary_res.status_code == 200
    s_data = summary_res.json()
    assert s_data["payment_status"] == "PAYMENT_UNVERIFIED"
    assert float(s_data["unverified_paid"]) == 750.00
    assert float(s_data["verified_paid"]) == 0.00
    assert float(s_data["balance_due"]) == 0.00


def test_payment_audit_trail_created_updated_deleted(client):
    """Payment operations create complete audit log records with action history."""
    token = get_auth_token(client, "audit_trail_user@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    inv = create_invoice(client, headers, "INV-AUD-01", "600.00")

    # 1. Create payment
    c_res = client.post("/api/payments/", json={
        "invoice_id": inv["id"],
        "amount": "200.00",
        "payment_date": str(date.today()),
        "payment_method": "Credit Card",
        "reference": "CC-901",
    }, headers=headers)
    assert c_res.status_code == 201
    payment_id = c_res.json()["id"]

    # 2. Update payment
    u_res = client.put(f"/api/payments/{payment_id}", json={
        "amount": "300.00",
        "payment_date": str(date.today()),
        "payment_method": "Bank Transfer",
        "reference": "WIRE-44",
        "notes": "Adjusted amount",
    }, headers=headers)
    assert u_res.status_code == 200

    # 3. Check audit logs via summary endpoint
    summary = client.get(f"/api/payments/invoices/{inv['id']}/summary", headers=headers).json()
    actions = [log["action"] for log in summary["audit_logs"]]
    assert "CREATED" in actions
    assert "UPDATED" in actions

    # 4. Delete payment
    d_res = client.delete(f"/api/payments/{payment_id}", headers=headers)
    assert d_res.status_code in (200, 204)

    # Verify DELETED action recorded in audit log
    summary2 = client.get(f"/api/payments/invoices/{inv['id']}/summary", headers=headers).json()
    actions2 = [log["action"] for log in summary2["audit_logs"]]
    assert "DELETED" in actions2


# -------------------------------------------------------------------------
# 4. Bank Reconciliation Evidence Verification
# -------------------------------------------------------------------------

def test_bank_reconciliation_verifies_payment_and_creates_audit_log(db_session, test_user):
    """Bank statement reconciliation matches debit, marks payment VERIFIED, and logs audit."""
    inv = Invoice(
        user_id=test_user.id,
        invoice_number="INV-BNK-01",
        vendor_name="Hardware Corp",
        invoice_date=date.today() - timedelta(days=10),
        due_date=date.today() + timedelta(days=5),
        total_amount=Decimal("1500.00"),
        currency="USD",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    # Initial manual unverified payment
    pay = Payment(
        invoice_id=inv.id,
        user_id=test_user.id,
        amount=Decimal("1500.00"),
        payment_date=date.today(),
        payment_method="Wire Transfer",
        reference="REF-7711",
        verification_status="UNVERIFIED",
        evidence_source="MANUAL_ENTRY",
    )
    db_session.add(pay)
    db_session.commit()
    db_session.refresh(pay)

    # Bank statement CSV with matching debit
    bank_csv = (
        "Date,Description,Debit,Credit,Reference\n"
        f"{date.today()},Hardware Corp payment,1500.00,,REF-7711\n"
    ).encode("utf-8")

    batch = run_bank_reconciliation(
        user_id=test_user.id,
        file_content=bank_csv,
        filename="october_bank_statement.csv",
        db=db_session,
    )

    assert batch.exact_matches >= 1

    # Reload payment
    db_session.refresh(pay)
    assert pay.verification_status == "VERIFIED"
    assert pay.evidence_source == "BANK_STATEMENT"
    assert pay.matched_reference == "REF-7711"

    # Verify audit log exists
    audit = (
        db_session.query(PaymentAuditLog)
        .filter(PaymentAuditLog.payment_id == pay.id, PaymentAuditLog.action == "VERIFIED")
        .first()
    )
    assert audit is not None
    assert audit.verification_status == "VERIFIED"
    assert audit.evidence_source == "BANK_STATEMENT"

    # Invoice should now be PAID_ON_TIME with 0 balance
    detail = calculate_detailed_invoice_payment_info(inv)
    assert detail["payment_status"] == "PAID_ON_TIME"
    assert detail["balance_due"] == Decimal("0.00")
    assert detail["verified_paid"] == Decimal("1500.00")


def test_bank_credit_matches_customer_invoice_receipt(db_session, test_user):
    """Customer invoice matches incoming bank credit (deposit) and settles correctly."""
    inv = Invoice(
        user_id=test_user.id,
        invoice_number="INV-CUST-99",
        vendor_name="Our Company",
        customer_name="Mega Client LLC",
        invoice_date=date.today() - timedelta(days=20),
        due_date=date.today() + timedelta(days=10),
        total_amount=Decimal("3200.00"),
        currency="USD",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    pay = Payment(
        invoice_id=inv.id,
        user_id=test_user.id,
        amount=Decimal("3200.00"),
        payment_date=date.today(),
        payment_method="Wire Transfer",
        reference="DEPOSIT-MEGA-01",
        verification_status="UNVERIFIED",
        evidence_source="MANUAL_ENTRY",
    )
    db_session.add(pay)
    db_session.commit()
    db_session.refresh(pay)

    # Bank statement CSV with incoming credit
    bank_csv = (
        "Date,Description,Debit,Credit,Reference\n"
        f"{date.today()},Mega Client LLC deposit,,3200.00,DEPOSIT-MEGA-01\n"
    ).encode("utf-8")

    batch = run_bank_reconciliation(
        user_id=test_user.id,
        file_content=bank_csv,
        filename="bank_incoming_deposits.csv",
        db=db_session,
    )

    assert batch.exact_matches >= 1
    db_session.refresh(pay)
    assert pay.verification_status == "VERIFIED"
    assert pay.evidence_source == "BANK_STATEMENT"


# -------------------------------------------------------------------------
# 5. UI Pay Button Removal Assertion
# -------------------------------------------------------------------------

def test_non_functional_pay_button_removed_from_ui():
    """Verifies the non-functional 'Pay' button and gateway actions were removed from UI source code."""
    frontend_deadlines_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "src", "pages", "PaymentDeadlines.jsx"
    )
    assert os.path.exists(frontend_deadlines_path), f"File not found: {frontend_deadlines_path}"

    with open(frontend_deadlines_path, "r", encoding="utf-8") as f:
        content = f.read()

    # The non-functional standalone "<span>Pay</span>" button must NOT exist
    assert "<span>Pay</span>" not in content, "Found non-functional '<span>Pay</span>' button in PaymentDeadlines.jsx"

    # Must contain "Record Payment" and "View Details"
    assert "Record Payment" in content, "Expected 'Record Payment' in PaymentDeadlines.jsx"
    assert "View Details" in content, "Expected 'View Details' in PaymentDeadlines.jsx"
    assert "Upload Payment Evidence" in content, "Expected 'Upload Payment Evidence' in PaymentDeadlines.jsx"
    assert "View Reconciliation" in content, "Expected 'View Reconciliation' in PaymentDeadlines.jsx"
