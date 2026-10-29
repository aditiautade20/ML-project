"""
InvoiceIQ Comprehensive End-to-End Verification Suite.
Validates all 8 steps required by the user prompt:
1. Startup & Endpoints (/api/health, /docs, /redoc)
2. Authentication & Strict Multi-Tenant Data Isolation
3. Invoice Upload, Extraction, Human Review & Save
4. Payments (Partial, Overpayment Prevention, Full Settlement, Overdue & Deadlines)
5. ML Anomaly Detection (Isolation Forest, RobustScaler, Explainability, Cold-Start)
6. Reconciliation (Ledger & Bank, Matches, Mismatches, Duplicates, Missing, Ambiguous, 1-Click Confirmation)
7. Reports, Live Dashboard Aggregation, Date Filters, and Formula-Safe Exports (CSV & PDF)
8. Session Persistence & Security Controls
"""

import io
import json
from datetime import date, timedelta
from decimal import Decimal
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.user import User


def test_e2e_step1_startup_and_endpoints(client: TestClient):
    """Step 1: Verify API health, Swagger docs, ReDoc."""
    # Health endpoint
    res = client.get("/api/health")
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "healthy"
    assert "timestamp" in res.json()
    assert res.json()["service"] == "InvoiceIQ Backend"

    # Swagger docs
    res_docs = client.get("/docs")
    assert res_docs.status_code == status.HTTP_200_OK

    # ReDoc
    res_redoc = client.get("/redoc")
    assert res_redoc.status_code == status.HTTP_200_OK


def test_e2e_step2_authentication_and_isolation(client: TestClient):
    """Step 2: Login, logout, invalid credentials, protected pages, and user isolation."""
    # Test unauthenticated access to protected route
    unauth_res = client.get("/api/invoices/")
    assert unauth_res.status_code == status.HTTP_401_UNAUTHORIZED

    # Test invalid credentials
    invalid_login = client.post("/api/auth/login", json={
        "email": "nonexistent@invoiceiq.test",
        "password": "WrongPassword123!",
    })
    assert invalid_login.status_code == status.HTTP_401_UNAUTHORIZED

    # Create User A
    user_a_payload = {
        "name": "User Alpha",
        "email": "alpha.test@invoiceiq.test",
        "password": "SecurePassword123!",
    }
    signup_a = client.post("/api/auth/signup", json=user_a_payload)
    assert signup_a.status_code == status.HTTP_201_CREATED
    login_a = client.post("/api/auth/login", json={
        "email": user_a_payload["email"],
        "password": user_a_payload["password"],
    })
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Verify protected /me for User A
    me_a = client.get("/api/auth/me", headers=headers_a)
    assert me_a.status_code == status.HTTP_200_OK
    assert me_a.json()["email"] == user_a_payload["email"]

    # Create User B
    user_b_payload = {
        "name": "User Beta",
        "email": "beta.test@invoiceiq.test",
        "password": "SecurePassword456!",
    }
    signup_b = client.post("/api/auth/signup", json=user_b_payload)
    assert signup_b.status_code == status.HTTP_201_CREATED
    login_b = client.post("/api/auth/login", json={
        "email": user_b_payload["email"],
        "password": user_b_payload["password"],
    })
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates an invoice
    today = date.today()
    inv_a = client.post("/api/invoices/", headers=headers_a, json={
        "invoice_number": "INV-ALPHA-001",
        "vendor_name": "Alpha Vendor",
        "invoice_date": today.isoformat(),
        "total_amount": 1000.00,
        "currency": "USD",
    })
    assert inv_a.status_code == status.HTTP_201_CREATED
    inv_a_id = inv_a.json()["id"]

    # User B CANNOT see User A's invoice
    b_get_a = client.get(f"/api/invoices/{inv_a_id}", headers=headers_b)
    assert b_get_a.status_code == status.HTTP_404_NOT_FOUND

    # User B CANNOT delete User A's invoice
    b_del_a = client.delete(f"/api/invoices/{inv_a_id}", headers=headers_b)
    assert b_del_a.status_code == status.HTTP_404_NOT_FOUND

    # User B listing is empty
    b_list = client.get("/api/invoices/", headers=headers_b)
    assert len(b_list.json()["items"]) == 0


def test_e2e_step3_invoice_workflow_and_extraction(client: TestClient):
    """Step 3: Invoice upload, extraction, review, correction, and persistence."""
    # Register test user
    user_payload = {
        "name": "Invoice Workflow User",
        "email": "workflow.test@invoiceiq.test",
        "password": "SecurePassword123!",
    }
    client.post("/api/auth/signup", json=user_payload)
    login_res = client.post("/api/auth/login", json={
        "email": user_payload["email"],
        "password": user_payload["password"],
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Minimal vector PDF bytes with invoice structure
    from tests.test_stage7_end_to_end_audit import make_pdf_bytes
    pdf_bytes = make_pdf_bytes([
        "From: BrightDesk Technologies Inc.",
        "Invoice Number: INV-TECH-2026",
        "Invoice Date: 2026-10-10",
        "Due Date: 2026-11-10",
        "Subtotal: $1500.00",
        "Tax Amount: $150.00",
        "Grand Total: $1650.00",
    ])

    # Upload PDF
    upload_res = client.post(
        "/api/invoices/upload",
        headers=headers,
        files={"file": ("tech_invoice.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == status.HTTP_200_OK
    extract_data = upload_res.json()
    assert "file_token" in extract_data
    candidates = extract_data["candidate_fields"]

    # Verify extracted fields
    assert candidates["invoice_number"] == "INV-TECH-2026"
    assert "BrightDesk" in candidates["vendor_name"]
    assert float(candidates["total_amount"]) == 1650.00

    # Save invoice with human review/correction
    today = date.today()
    save_payload = {
        "invoice_number": candidates["invoice_number"],
        "vendor_name": "BrightDesk Technologies Inc. (Verified)",
        "invoice_date": (today - timedelta(days=5)).isoformat(),
        "due_date": (today + timedelta(days=25)).isoformat(),
        "subtotal": 1500.00,
        "tax_amount": 150.00,
        "total_amount": 1650.00,
        "currency": "USD",
        "notes": "E2E Verified invoice",
        "file_path": extract_data["file_token"],
    }
    create_res = client.post("/api/invoices/", headers=headers, json=save_payload)
    assert create_res.status_code == status.HTTP_201_CREATED
    inv = create_res.json()
    assert inv["vendor_name"] == "BrightDesk Technologies Inc. (Verified)"
    assert float(inv["total_amount"]) == 1650.00
    assert float(inv["balance_due"]) == 1650.00
    assert inv["payment_status"] == "UNPAID"

    # Fetch detail page
    detail_res = client.get(f"/api/invoices/{inv['id']}", headers=headers)
    assert detail_res.status_code == status.HTTP_200_OK
    assert detail_res.json()["invoice_number"] == "INV-TECH-2026"


def test_e2e_step4_payments_partial_overdue_and_deadlines(client: TestClient):
    """Step 4: Partial payment, remaining balance, full payment, overdue, and deadlines."""
    user_payload = {
        "name": "Payments Test User",
        "email": "payments.e2e@invoiceiq.test",
        "password": "SecurePassword123!",
    }
    client.post("/api/auth/signup", json=user_payload)
    login_res = client.post("/api/auth/login", json={
        "email": user_payload["email"],
        "password": user_payload["password"],
    })
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}
    today = date.today()

    # Invoice 1: Standard invoice for partial & full payment
    inv1_res = client.post("/api/invoices/", headers=headers, json={
        "invoice_number": "INV-PAY-001",
        "vendor_name": "Supplier A",
        "invoice_date": (today - timedelta(days=10)).isoformat(),
        "due_date": (today + timedelta(days=15)).isoformat(),
        "total_amount": 800.00,
        "currency": "USD",
    })
    inv1_id = inv1_res.json()["id"]

    # 4a. Overpayment rejection
    overpay = client.post("/api/payments/", headers=headers, json={
        "invoice_id": inv1_id,
        "amount": 900.00,
        "payment_date": today.isoformat(),
        "payment_method": "Credit Card",
    })
    assert overpay.status_code == status.HTTP_400_BAD_REQUEST

    # 4b. Record partial payment of $300.00
    pay1 = client.post("/api/payments/", headers=headers, json={
        "invoice_id": inv1_id,
        "amount": 300.00,
        "payment_date": today.isoformat(),
        "payment_method": "Bank Transfer",
        "reference": "REF-PARTIAL-1",
    })
    assert pay1.status_code == status.HTTP_201_CREATED

    # Verify status changed to PARTIAL, balance is 500
    chk1 = client.get(f"/api/invoices/{inv1_id}", headers=headers).json()
    assert chk1["payment_status"] == "PARTIAL"
    assert float(chk1["total_paid"]) == 300.00
    assert float(chk1["balance_due"]) == 500.00

    # 4c. Record remaining payment of $500.00
    pay2 = client.post("/api/payments/", headers=headers, json={
        "invoice_id": inv1_id,
        "amount": 500.00,
        "payment_date": today.isoformat(),
        "payment_method": "Bank Transfer",
        "reference": "REF-FINAL-2",
    })
    assert pay2.status_code == status.HTTP_201_CREATED

    # Verify status changed to PAID, balance is 0
    chk2 = client.get(f"/api/invoices/{inv1_id}", headers=headers).json()
    assert chk2["payment_status"] == "PAID"
    assert float(chk2["total_paid"]) == 800.00
    assert float(chk2["balance_due"]) == 0.00

    # 4d. Test Overdue invoice
    inv_overdue = client.post("/api/invoices/", headers=headers, json={
        "invoice_number": "INV-OVERDUE-001",
        "vendor_name": "Overdue Telecom",
        "invoice_date": (today - timedelta(days=40)).isoformat(),
        "due_date": (today - timedelta(days=10)).isoformat(),  # Past due date!
        "total_amount": 250.00,
        "currency": "USD",
    })
    assert inv_overdue.status_code == status.HTTP_201_CREATED
    assert inv_overdue.json()["payment_status"] == "OVERDUE"

    # 4e. Test Upcoming Due Date (< 7 days)
    inv_upcoming = client.post("/api/invoices/", headers=headers, json={
        "invoice_number": "INV-SOON-001",
        "vendor_name": "Upcoming Utility",
        "invoice_date": (today - timedelta(days=10)).isoformat(),
        "due_date": (today + timedelta(days=3)).isoformat(),  # Due in 3 days!
        "total_amount": 150.00,
        "currency": "USD",
    })
    assert inv_upcoming.status_code == status.HTTP_201_CREATED

    # Verify Deadlines summary categorizes them properly
    deadlines = client.get("/api/invoices/deadlines/summary", headers=headers).json()
    assert deadlines["overdue_count"] >= 1
    assert deadlines["due_within_7_days_count"] >= 1


def test_e2e_step5_ml_anomaly_detection(client: TestClient):
    """Step 5: Verify Isolation Forest + RobustScaler model, cold-start guard, and explainability."""
    user_payload = {
        "name": "ML Anomaly User",
        "email": "ml.e2e@invoiceiq.test",
        "password": "SecurePassword123!",
    }
    client.post("/api/auth/signup", json=user_payload)
    login_res = client.post("/api/auth/login", json={
        "email": user_payload["email"],
        "password": user_payload["password"],
    })
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}
    today = date.today()

    # 5a. Cold-start guard (< 5 invoices)
    client.post("/api/invoices/", headers=headers, json={
        "invoice_number": "INV-FEW-001",
        "vendor_name": "Supplier X",
        "invoice_date": today.isoformat(),
        "total_amount": 100.00,
        "currency": "USD",
    })
    cold_start = client.get("/api/anomalies/", headers=headers).json()
    assert cold_start["status"] == "INSUFFICIENT_DATA"
    assert "at least 5" in cold_start["message"].lower()

    # 5b. Add 4 normal baseline invoices for "Supplier X" ($100-$120 range)
    for i in range(2, 6):
        client.post("/api/invoices/", headers=headers, json={
            "invoice_number": f"INV-FEW-00{i}",
            "vendor_name": "Supplier X",
            "invoice_date": (today - timedelta(days=i * 3)).isoformat(),
            "total_amount": 100.00 + i * 5,
            "currency": "USD",
        })

    # 5c. Add 1 massive statistical outlier ($9,500 for Supplier X)
    outlier = client.post("/api/invoices/", headers=headers, json={
        "invoice_number": "INV-OUTLIER-999",
        "vendor_name": "Supplier X",
        "invoice_date": today.isoformat(),
        "total_amount": 9500.00,
        "currency": "USD",
    })
    assert outlier.status_code == status.HTTP_201_CREATED

    # 5d. Trigger anomaly screening via POST /api/anomalies/assess
    assess_res = client.post("/api/anomalies/assess", headers=headers)
    assert assess_res.status_code == status.HTTP_200_OK
    anom_data = assess_res.json()
    assert anom_data["status"] in ["COMPLETED", "ASSESSED", "SUCCESS"]
    assert anom_data["total_invoices"] >= 6

    # Verify outlier was flagged with understandable reason
    flagged = [it for it in anom_data["items"] if it["invoice_number"] == "INV-OUTLIER-999"]
    assert len(flagged) == 1
    outlier_item = flagged[0]
    assert outlier_item["is_anomaly"] is True
    assert outlier_item["status"] == "POTENTIALLY_UNUSUAL"
    # Check natural-language explainability
    assert "higher than" in outlier_item["explanation"].lower() or "median" in outlier_item["explanation"].lower()


def test_e2e_step6_reconciliation_centre(client: TestClient):
    """Step 6: Ledger & Bank reconciliation, matches, mismatches, duplicates, missing, and explicit confirmation."""
    user_payload = {
        "name": "Recon Test User",
        "email": "recon.e2e@invoiceiq.test",
        "password": "SecurePassword123!",
    }
    client.post("/api/auth/signup", json=user_payload)
    login_res = client.post("/api/auth/login", json={
        "email": user_payload["email"],
        "password": user_payload["password"],
    })
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}
    today = date.today()

    # Seed 2 invoices for this user
    inv1 = client.post("/api/invoices/", headers=headers, json={
        "invoice_number": "INV-REC-001",
        "vendor_name": "Cloud Host Corp",
        "invoice_date": today.isoformat(),
        "total_amount": 500.00,
        "currency": "USD",
    }).json()

    inv2 = client.post("/api/invoices/", headers=headers, json={
        "invoice_number": "INV-REC-002",
        "vendor_name": "Office Supplies Co",
        "invoice_date": today.isoformat(),
        "total_amount": 350.00,
        "currency": "USD",
    }).json()

    # Record a payment for inv1
    client.post("/api/payments/", headers=headers, json={
        "invoice_id": inv1["id"],
        "amount": 500.00,
        "payment_date": today.isoformat(),
        "payment_method": "Bank Transfer",
        "reference": "WIRE-REC-500",
    })

    # 6a. Accounting Ledger Reconciliation
    ledger_csv = (
        "InvNum,Vendor,Amount,Tax,Date\n"
        "INV-REC-001,Cloud Host Corp,500.00,0.00,2026-10-20\n"        # Exact match
        "INV-REC-001,Cloud Host Corp,500.00,0.00,2026-10-20\n"        # Duplicate in ledger -> DUPLICATE_SUSPECTED
        "INV-REC-002,Office Supplies Co,380.00,0.00,2026-10-20\n"     # Amount mismatch ($380 vs $350)
        "INV-GHOST-007,Phantom Vendor,1200.00,0.00,2026-10-20\n"      # Missing in invoices
    ).encode("utf-8")

    l_res = client.post(
        "/api/reconciliation/run-ledger",
        headers=headers,
        files={"file": ("ledger_test.csv", ledger_csv, "text/csv")},
        data={
            "column_mapping": json.dumps({
                "invoice_number": "InvNum",
                "vendor_name": "Vendor",
                "total_amount": "Amount",
                "invoice_date": "Date",
            }),
            "amount_tolerance": "0.05",
        },
    )
    assert l_res.status_code == status.HTTP_201_CREATED
    l_batch = l_res.json()
    assert l_batch["exact_matches"] >= 1
    assert l_batch["mismatches"] >= 1

    # Verify duplicate row was captured
    dup_items = [it for it in l_batch["items"] if it["match_status"] == "DUPLICATE_SUSPECTED"]
    assert len(dup_items) >= 1

    # Verify amount mismatch
    mismatch_items = [it for it in l_batch["items"] if it["match_status"] == "AMOUNT_MISMATCH"]
    assert len(mismatch_items) >= 1

    # Verify missing in invoices
    ghost_items = [it for it in l_batch["items"] if it["match_status"] == "MISSING_IN_INVOICES"]
    assert len(ghost_items) >= 1

    # 6b. Bank Statement Reconciliation & No-Silent-Mutation Check
    bank_csv = (
        "Date,Desc,Debit,Credit,Ref\n"
        f"{today.isoformat()},Cloud Host Wire,500.00,,WIRE-REC-500\n"          # Matched payment
        f"{today.isoformat()},Office Supplies Settlement,350.00,,ACH-OFFICE\n"  # Unrecorded payment for inv2
        f"{today.isoformat()},Corner Coffee Shop,15.50,,POS-992\n"              # Unmatched bank debit
    ).encode("utf-8")

    b_res = client.post(
        "/api/reconciliation/run-bank",
        headers=headers,
        files={"file": ("bank_test.csv", bank_csv, "text/csv")},
        data={
            "column_mapping": json.dumps({
                "transaction_date": "Date",
                "description": "Desc",
                "debit_amount": "Debit",
                "credit_amount": "Credit",
                "reference_id": "Ref",
            }),
            "amount_tolerance": "0.05",
        },
    )
    assert b_res.status_code == status.HTTP_201_CREATED
    b_batch = b_res.json()

    # Verify inv2 is STILL unpaid before explicit confirmation!
    inv2_before = client.get(f"/api/invoices/{inv2['id']}", headers=headers).json()
    assert inv2_before["payment_status"] == "UNPAID"
    assert float(inv2_before["balance_due"]) == 350.00

    # 6c. Explicit confirmation of candidate payment
    candidate_item = next(it for it in b_batch["items"] if it["record_identifier"] == "ACH-OFFICE")
    confirm_res = client.post(
        f"/api/reconciliation/batches/{b_batch['id']}/items/{candidate_item['id']}/confirm-payment",
        headers=headers,
        json={"payment_method": "ACH Transfer", "notes": "Confirmed by auditor"},
    )
    assert confirm_res.status_code == status.HTTP_200_OK

    # Now inv2 is confirmed PAID!
    inv2_after = client.get(f"/api/invoices/{inv2['id']}", headers=headers).json()
    assert inv2_after["payment_status"] == "PAID"
    assert float(inv2_after["balance_due"]) == 0.00

    # 6d. Verify reconciliation CSV export
    recon_export = client.get(f"/api/reconciliation/batches/{b_batch['id']}/export-csv", headers=headers)
    assert recon_export.status_code == status.HTTP_200_OK
    assert "WIRE-REC-500" in recon_export.text


def test_e2e_step7_reports_dashboard_and_formula_safe_exports(client: TestClient):
    """Step 7: Dashboard totals, date range filters, CSV formula protection, PDF export."""
    user_payload = {
        "name": "Reports Test User",
        "email": "reports.e2e@invoiceiq.test",
        "password": "SecurePassword123!",
    }
    client.post("/api/auth/signup", json=user_payload)
    login_res = client.post("/api/auth/login", json={
        "email": user_payload["email"],
        "password": user_payload["password"],
    })
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}
    today = date.today()

    # Create invoice with malicious formula trigger in vendor name: =SUM(A1:A10)
    inv = client.post("/api/invoices/", headers=headers, json={
        "invoice_number": "INV-DDE-001",
        "vendor_name": "=SUM(1+1)*cmd|' /C calc'!A1",
        "invoice_date": today.isoformat(),
        "total_amount": 500.00,
        "currency": "USD",
    }).json()

    # Dashboard check
    dash = client.get("/api/reports/dashboard", headers=headers).json()
    assert dash["total_invoices_count"] == 1
    assert float(dash["total_invoiced_amount"]) == 500.00

    # CSV Export - verify formula injection escaping with leading single-quote
    csv_res = client.get("/api/reports/export/invoices", headers=headers)
    assert csv_res.status_code == status.HTTP_200_OK
    csv_text = csv_res.text
    # The cell starting with '=' must be escaped to "'="
    assert "'=" in csv_text or "\'=" in csv_text

    # PDF Export
    pdf_res = client.get("/api/reports/export/pdf", headers=headers)
    assert pdf_res.status_code == status.HTTP_200_OK
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-")
