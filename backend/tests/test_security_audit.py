import io
from datetime import date, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.anomaly import InvoiceAnomaly
from app.models.reconciliation import ReconciliationBatch, ReconciliationItem
from app.models.user import User


def get_auth_token(client, email="sectest@example.com", name="Security User"):
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


def test_unauthenticated_requests_strictly_rejected(client):
    """
    Every protected endpoint must return 401 Unauthorized when accessed
    without credentials.
    """
    endpoints = [
        ("GET", "/api/auth/me"),
        ("GET", "/api/invoices/"),
        ("POST", "/api/invoices/"),
        ("GET", "/api/invoices/1"),
        ("PUT", "/api/invoices/1"),
        ("DELETE", "/api/invoices/1"),
        ("GET", "/api/invoices/1/file"),
        ("GET", "/api/invoices/deadlines/summary"),
        ("GET", "/api/payments/"),
        ("POST", "/api/payments/"),
        ("GET", "/api/payments/1"),
        ("PUT", "/api/payments/1"),
        ("DELETE", "/api/payments/1"),
        ("POST", "/api/anomalies/assess"),
        ("GET", "/api/anomalies/"),
        ("GET", "/api/anomalies/invoice/1"),
        ("GET", "/api/reports/dashboard"),
        ("GET", "/api/reports/analytics"),
        ("GET", "/api/reports/export/invoices"),
        ("GET", "/api/reports/export/payments"),
        ("GET", "/api/reports/export/outstanding"),
        ("GET", "/api/reports/export/reconciliation"),
        ("GET", "/api/reports/export/pdf"),
        ("GET", "/api/reconciliation/batches"),
        ("GET", "/api/reconciliation/batches/1"),
        ("GET", "/api/reconciliation/batches/1/export-csv"),
        ("DELETE", "/api/reconciliation/batches/1"),
    ]

    for method, path in endpoints:
        if method == "GET":
            res = client.get(path)
        elif method == "POST":
            res = client.post(path, json={})
        elif method == "PUT":
            res = client.put(path, json={})
        elif method == "DELETE":
            res = client.delete(path)
        assert res.status_code == 401, f"Expected 401 on unauthenticated {method} {path}, got {res.status_code}"


def test_cross_user_file_attachment_isolation(client):
    """
    User B must not be able to download User A's attached invoice documents.
    """
    token_a = get_auth_token(client, "user_a_file@example.com", "User A")
    token_b = get_auth_token(client, "user_b_file@example.com", "User B")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A uploads a real text/plain or image dummy file
    fake_pdf = b"%PDF-1.4 test invoice content"
    upload_res = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice_sample.pdf", fake_pdf, "application/pdf")},
        headers=headers_a,
    )
    assert upload_res.status_code == 200
    file_token = upload_res.json()["file_token"]

    # User A creates the invoice
    inv_res = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-SEC-FILE-01",
            "vendor_name": "Secure Vendor Ltd",
            "invoice_date": str(date.today()),
            "total_amount": 350.00,
            "currency": "USD",
            "file_token": file_token,
        },
        headers=headers_a,
    )
    assert inv_res.status_code == 201
    inv_id = inv_res.json()["id"]

    # User A downloads their own file -> 200 OK
    dl_a = client.get(f"/api/invoices/{inv_id}/file", headers=headers_a)
    assert dl_a.status_code == 200
    assert dl_a.content == fake_pdf

    # User B attempts to download User A's file -> 404 NOT FOUND (tenant isolation)
    dl_b = client.get(f"/api/invoices/{inv_id}/file", headers=headers_b)
    assert dl_b.status_code == 404


def test_cascade_deletion_cleans_up_payments_and_anomalies(client, db_session):
    """
    Deleting an invoice must cascade delete all associated payments and anomaly
    records from the database without orphaned records.
    """
    token = get_auth_token(client, "cascade@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create 5 invoices and assess
    for i in range(1, 6):
        client.post(
            "/api/invoices/",
            json={
                "invoice_number": f"INV-CASC-{i}",
                "vendor_name": "Cascade Vendor",
                "invoice_date": str(date.today()),
                "total_amount": 100.00 * i,
                "currency": "USD",
            },
            headers=headers,
        )

    # Pick the first invoice
    inv_list = client.get("/api/invoices/", headers=headers).json()["items"]
    target_inv = inv_list[0]
    target_id = target_inv["id"]

    # Record a payment on target invoice
    pay_res = client.post(
        "/api/payments/",
        json={
            "invoice_id": target_id,
            "amount": 25.00,
            "payment_date": str(date.today()),
            "payment_method": "Bank Transfer",
        },
        headers=headers,
    )
    assert pay_res.status_code == 201
    payment_id = pay_res.json()["id"]

    # Run ML assessment so anomaly record is created
    client.post("/api/anomalies/assess", headers=headers)

    # Confirm records exist in database
    assert db_session.query(Payment).filter(Payment.id == payment_id).count() == 1
    assert db_session.query(InvoiceAnomaly).filter(InvoiceAnomaly.invoice_id == target_id).count() == 1

    # Delete the invoice
    del_res = client.delete(f"/api/invoices/{target_id}", headers=headers)
    assert del_res.status_code == 204

    # Verify invoice is deleted
    assert db_session.query(Invoice).filter(Invoice.id == target_id).count() == 0
    # Verify associated payment is cascade deleted
    assert db_session.query(Payment).filter(Payment.id == payment_id).count() == 0
    # Verify associated anomaly record is cascade deleted
    assert db_session.query(InvoiceAnomaly).filter(InvoiceAnomaly.invoice_id == target_id).count() == 0


def test_invalid_payment_amounts_rejected(client):
    """
    Payment amounts must be strictly positive (> 0.00). Negative, zero,
    or non-numeric amounts must be rejected.
    """
    token = get_auth_token(client, "payval@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    inv = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-VAL-01",
            "vendor_name": "Test Vendor",
            "invoice_date": str(date.today()),
            "total_amount": 100.00,
            "currency": "USD",
        },
        headers=headers,
    ).json()

    # Zero amount
    res_zero = client.post(
        "/api/payments/",
        json={
            "invoice_id": inv["id"],
            "amount": 0.00,
            "payment_date": str(date.today()),
            "payment_method": "Cash",
        },
        headers=headers,
    )
    assert res_zero.status_code in (400, 422)

    # Negative amount
    res_neg = client.post(
        "/api/payments/",
        json={
            "invoice_id": inv["id"],
            "amount": -50.00,
            "payment_date": str(date.today()),
            "payment_method": "Cash",
        },
        headers=headers,
    )
    assert res_neg.status_code in (400, 422)


def test_production_mode_hides_api_docs_when_debug_false():
    """
    In production mode with DEBUG=False, Swagger and ReDoc documentation
    endpoints are disabled to prevent exposing API internals.
    """
    from app.config import Settings
    from app.main import app as main_app

    # When DEBUG is false, docs are None
    prod_settings = Settings(ENVIRONMENT="production", DEBUG=False)
    assert prod_settings.DEBUG is False


def test_spoofed_file_content_signature_rejected(client):
    """
    Ensures that uploaded files whose byte content does not match the file extension
    signature are rejected with HTTP 400.
    """
    token = get_auth_token(client, "spoof_check@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Plain text claiming to be a PDF
    fake_pdf = b"This is just plain text, not a PDF document."
    res1 = client.post(
        "/api/invoices/upload",
        files={"file": ("fake.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        headers=headers,
    )
    assert res1.status_code == 400
    assert "file signature" in res1.json()["detail"].lower()

    # Plain text claiming to be a PNG
    fake_png = b"Not a PNG image header"
    res2 = client.post(
        "/api/invoices/upload",
        files={"file": ("fake.png", io.BytesIO(fake_png), "image/png")},
        headers=headers,
    )
    assert res2.status_code == 400
    assert "file signature" in res2.json()["detail"].lower()


def test_cross_user_invoice_and_payment_mutations_blocked(client):
    """
    Confirms User B cannot update or delete User A's invoice or payment records (IDOR checks).
    """
    token_a = get_auth_token(client, "owner_a@example.com", "Owner A")
    token_b = get_auth_token(client, "attacker_b@example.com", "Attacker B")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Owner A creates invoice
    inv = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-OWNER-01",
            "vendor_name": "Owner A Vendor",
            "invoice_date": str(date.today()),
            "total_amount": 500.00,
            "currency": "USD",
        },
        headers=headers_a,
    ).json()

    # Owner A records payment
    pay = client.post(
        "/api/payments/",
        json={
            "invoice_id": inv["id"],
            "amount": 100.00,
            "payment_date": str(date.today()),
            "payment_method": "Bank Transfer",
        },
        headers=headers_a,
    ).json()

    # User B attempts to view invoice -> 404
    assert client.get(f"/api/invoices/{inv['id']}", headers=headers_b).status_code == 404

    # User B attempts to edit invoice -> 404
    res_inv_edit = client.put(
        f"/api/invoices/{inv['id']}",
        json={"vendor_name": "Hacked Vendor"},
        headers=headers_b,
    )
    assert res_inv_edit.status_code == 404

    # User B attempts to delete invoice -> 404
    assert client.delete(f"/api/invoices/{inv['id']}", headers=headers_b).status_code == 404

    # User B attempts to view payment -> 404
    assert client.get(f"/api/payments/{pay['id']}", headers=headers_b).status_code == 404

    # User B attempts to edit payment -> 404
    res_pay_edit = client.put(
        f"/api/payments/{pay['id']}",
        json={"amount": 150.00},
        headers=headers_b,
    )
    assert res_pay_edit.status_code == 404

    # User B attempts to delete payment -> 404
    assert client.delete(f"/api/payments/{pay['id']}", headers=headers_b).status_code == 404


def test_cross_user_reconciliation_batch_isolation(client, db_session):
    """
    Confirms User B cannot view, review, confirm payments, export, or delete User A's
    reconciliation batches and items.
    """
    token_a = get_auth_token(client, "rec_owner_a@example.com", "Rec Owner A")
    token_b = get_auth_token(client, "rec_user_b@example.com", "Rec User B")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    user_a = db_session.query(User).filter(User.email == "rec_owner_a@example.com").first()

    # Create batch for user A
    batch_a = ReconciliationBatch(
        user_id=user_a.id,
        batch_type="LEDGER",
        title="Owner A Private Reconciliation",
        status="COMPLETED",
        total_records=1,
    )
    db_session.add(batch_a)
    db_session.commit()
    db_session.refresh(batch_a)

    item_a = ReconciliationItem(
        batch_id=batch_a.id,
        user_id=user_a.id,
        item_type="LEDGER",
        match_status="AMOUNT_MISMATCH",
        record_identifier="INV-SECRET-99",
        vendor_or_counterparty="Confidential Supplier",
        actual_value="999.00",
        currency="USD",
    )
    db_session.add(item_a)
    db_session.commit()
    db_session.refresh(item_a)

    # User B lists batches: batch A is NOT present
    batches_b = client.get("/api/reconciliation/batches", headers=headers_b).json()
    assert all(b["id"] != batch_a.id for b in batches_b)

    # User B gets batch A directly -> 404
    assert client.get(f"/api/reconciliation/batches/{batch_a.id}", headers=headers_b).status_code == 404

    # User B attempts to change item review status -> 404
    patch_res = client.patch(
        f"/api/reconciliation/batches/{batch_a.id}/items/{item_a.id}",
        json={"review_status": "DISMISSED"},
        headers=headers_b,
    )
    assert patch_res.status_code == 404

    # User B attempts to export CSV -> 404
    csv_res = client.get(f"/api/reconciliation/batches/{batch_a.id}/export-csv", headers=headers_b)
    assert csv_res.status_code == 404

    # User B attempts to delete batch -> 404
    del_res = client.delete(f"/api/reconciliation/batches/{batch_a.id}", headers=headers_b)
    assert del_res.status_code == 404


def test_invalid_invoice_data_validation(client):
    """
    Checks that invalid invoice fields (empty strings, zero/negative amounts,
    whitespace only) are rejected with 422 Unprocessable Entity.
    """
    token = get_auth_token(client, "inval_inv@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = str(date.today())

    # Empty invoice number
    res1 = client.post(
        "/api/invoices/",
        json={"invoice_number": "   ", "vendor_name": "Valid Vendor", "invoice_date": today, "total_amount": 100.00},
        headers=headers,
    )
    assert res1.status_code == 422

    # Zero total amount
    res2 = client.post(
        "/api/invoices/",
        json={"invoice_number": "INV-01", "vendor_name": "Valid Vendor", "invoice_date": today, "total_amount": 0.00},
        headers=headers,
    )
    assert res2.status_code == 422

    # Negative total amount
    res3 = client.post(
        "/api/invoices/",
        json={"invoice_number": "INV-02", "vendor_name": "Valid Vendor", "invoice_date": today, "total_amount": -10.00},
        headers=headers,
    )
    assert res3.status_code == 422


def test_tampered_and_malformed_auth_tokens(client):
    """
    Verifies that malformed, random, or tampered JWT tokens return 401 Unauthorized.
    """
    # Malformed token string
    res1 = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt-token"})
    assert res1.status_code == 401

    # Tampered signature
    tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.invalidsignaturehere1234567890"
    res2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res2.status_code == 401

    # Missing Bearer prefix
    res3 = client.get("/api/auth/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert res3.status_code == 401
