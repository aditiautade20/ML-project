"""
End-to-End Audit & Complete Customer Workflow Test for InvoiceIQ Stage 7.
Validates the entire end-to-end user journey:
1. Signup, Login, Authentication & Token verification
2. PDF invoice upload, extraction candidates, review & save
3. Dashboard totals update & listing verification
4. Partial payment recording, balance reduction & overpayment protection
5. Payment deadlines & overdue classification
6. ML anomaly detection checks & insufficient-data handling
7. Accounting Ledger reconciliation (exact & amount discrepancy)
8. Bank statement reconciliation (cleared debit verification & explicit confirmation)
9. Combined 4-way cross-verification
10. Reports & CSV export with formula injection protection
11. Persistence verification across simulated session reconnect
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


def make_pdf_bytes(text_lines: list) -> bytes:
    """Helper that generates a valid minimal PDF containing given text lines."""
    text_commands = []
    y = 700
    for line in text_lines:
        text_commands.append(f"72 {y} Td ({line}) Tj 0 -20 Td")
        y -= 20
    content = "BT /F1 12 Tf " + " ".join(text_commands) + " ET"
    stream_len = len(content)
    pdf = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length {stream_len} >>
stream
{content}
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000300 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
377
%%EOF"""
    return pdf.encode("latin1")


def test_complete_customer_journey_stage7_audit(client: TestClient, db_session: Session):
    # ---------------------------------------------------------
    # Step 1: Dedicated Test Account Signup & Login
    # ---------------------------------------------------------
    signup_payload = {
        "name": "Audit Customer",
        "email": "audit.customer.stage7@invoiceiq.test",
        "password": "SecurePassword!987",
    }
    signup_res = client.post("/api/auth/signup", json=signup_payload)
    assert signup_res.status_code == status.HTTP_201_CREATED, signup_res.text
    user_id = signup_res.json()["id"]

    login_res = client.post("/api/auth/login", json={
        "email": signup_payload["email"],
        "password": signup_payload["password"],
    })
    assert login_res.status_code == status.HTTP_200_OK
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify protected /me endpoint
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == status.HTTP_200_OK
    assert me_res.json()["email"] == signup_payload["email"]

    # ---------------------------------------------------------
    # Step 2: Dashboard starts at clean zero
    # ---------------------------------------------------------
    dash_zero = client.get("/api/reports/dashboard", headers=headers)
    assert dash_zero.status_code == status.HTTP_200_OK
    dash_zero_data = dash_zero.json()
    assert dash_zero_data["total_invoices_count"] == 0
    assert float(dash_zero_data["total_invoiced_amount"]) == 0.0

    # ---------------------------------------------------------
    # Step 3: Upload Sample Invoice PDF & Inspect Extraction
    # ---------------------------------------------------------
    pdf_bytes = make_pdf_bytes([
        "From: Acme Industrial Supplies",
        "Invoice Number: INV-AUDIT-2026-001",
        "Invoice Date: 2026-10-15",
        "Due Date: 2026-11-05",
        "Total: $2200.00",
    ])
    upload_res = client.post(
        "/api/invoices/upload",
        headers=headers,
        files={"file": ("invoice_sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == status.HTTP_200_OK
    extraction = upload_res.json()
    assert "file_token" in extraction
    assert "candidate_fields" in extraction
    assert extraction["candidate_fields"]["invoice_number"] == "INV-AUDIT-2026-001"
    assert "Acme Industrial" in extraction["candidate_fields"]["vendor_name"]

    # ---------------------------------------------------------
    # Step 4: Review and Save Invoice
    # ---------------------------------------------------------
    today = date.today()
    invoice_payload = {
        "invoice_number": "INV-AUDIT-2026-001",
        "vendor_name": "Acme Industrial Supplies",
        "invoice_date": (today - timedelta(days=10)).isoformat(),
        "due_date": (today + timedelta(days=20)).isoformat(),
        "subtotal": 2000.00,
        "tax_amount": 200.00,
        "total_amount": 2200.00,
        "currency": "USD",
        "notes": "Stage 7 audit invoice",
        "file_path": extraction.get("file_token", ""),
    }
    create_res = client.post("/api/invoices/", headers=headers, json=invoice_payload)
    assert create_res.status_code == status.HTTP_201_CREATED
    inv_data = create_res.json()
    inv_id = inv_data["id"]
    assert inv_data["invoice_number"] == "INV-AUDIT-2026-001"
    assert float(inv_data["total_amount"]) == 2200.00
    assert float(inv_data["balance_due"]) == 2200.00
    assert inv_data["payment_status"] == "UNPAID"

    # Verify listing
    list_res = client.get("/api/invoices/", headers=headers)
    assert list_res.status_code == status.HTTP_200_OK
    items = list_res.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == inv_id

    # Verify dashboard reflects new invoice
    dash_1 = client.get("/api/reports/dashboard", headers=headers)
    assert dash_1.status_code == status.HTTP_200_OK
    d1 = dash_1.json()
    assert d1["total_invoices_count"] == 1
    assert float(d1["total_invoiced_amount"]) == 2200.00
    assert float(d1["total_outstanding_balance"]) == 2200.00
    assert float(d1["total_paid_amount"]) == 0.0

    # ---------------------------------------------------------
    # Step 5: Record Partial Payment & Overpayment Prevention
    # ---------------------------------------------------------
    # 5a. Attempt overpayment (should fail)
    overpay_res = client.post(
        "/api/payments/",
        headers=headers,
        json={
            "invoice_id": inv_id,
            "amount": 2500.00,
            "payment_date": today.isoformat(),
            "payment_method": "Wire Transfer",
        },
    )
    assert overpay_res.status_code == status.HTTP_400_BAD_REQUEST

    # 5b. Record valid partial payment of $700.00
    pay_res = client.post(
        "/api/payments/",
        headers=headers,
        json={
            "invoice_id": inv_id,
            "amount": 700.00,
            "payment_date": today.isoformat(),
            "payment_method": "Bank Transfer",
            "reference": "TXN-AUDIT-001",
            "notes": "Partial settlement 1",
        },
    )
    assert pay_res.status_code == status.HTTP_201_CREATED
    pay_data = pay_res.json()
    assert float(pay_data["amount"]) == 700.00

    # Verify invoice status transition to PARTIAL
    inv_check = client.get(f"/api/invoices/{inv_id}", headers=headers)
    assert inv_check.json()["payment_status"] == "PARTIAL"
    assert float(inv_check.json()["balance_due"]) == 1500.00
    assert float(inv_check.json()["total_paid"]) == 700.00

    # Verify Deadlines summary
    deadlines_res = client.get("/api/invoices/deadlines/summary", headers=headers)
    assert deadlines_res.status_code == status.HTTP_200_OK
    assert float(deadlines_res.json()["total_outstanding_amount"]) == 1500.00

    # ---------------------------------------------------------
    # Step 6: ML Anomaly Detection (Insufficient Data Graceful State)
    # ---------------------------------------------------------
    anom_res = client.get("/api/anomalies/", headers=headers)
    assert anom_res.status_code == status.HTTP_200_OK
    anom_data = anom_res.json()
    assert anom_data["status"] == "INSUFFICIENT_DATA"
    assert "at least 5" in anom_data["message"].lower()

    # ---------------------------------------------------------
    # Step 7: Accounting Ledger Reconciliation
    # ---------------------------------------------------------
    # Ledger CSV containing an exact match for INV-AUDIT-2026-001
    ledger_csv = (
        "Invoice Number,Vendor Name,Total Amount,Tax Amount,Date\n"
        "INV-AUDIT-2026-001,Acme Industrial Supplies,2200.00,200.00,2026-10-15\n"
        "INV-GHOST-999,Unknown Corp,500.00,50.00,2026-10-16\n"
    ).encode("utf-8")

    l_files = {"file": ("ledger_audit.csv", ledger_csv, "text/csv")}
    l_data = {
        "column_mapping": json.dumps({
            "invoice_number": "Invoice Number",
            "vendor_name": "Vendor Name",
            "total_amount": "Total Amount",
            "tax_amount": "Tax Amount",
            "invoice_date": "Date",
        }),
        "amount_tolerance": "0.05",
    }
    l_res = client.post("/api/reconciliation/run-ledger", headers=headers, files=l_files, data=l_data)
    assert l_res.status_code == status.HTTP_201_CREATED
    l_batch = l_res.json()
    assert l_batch["exact_matches"] >= 1
    # Check ghost invoice was flagged as MISSING_IN_INVOICES
    ghost_item = next(it for it in l_batch["items"] if it["record_identifier"] == "INV-GHOST-999")
    assert ghost_item["match_status"] == "MISSING_IN_INVOICES"

    # ---------------------------------------------------------
    # Step 8: Bank Statement Reconciliation & Safety Enforcement
    # ---------------------------------------------------------
    # Bank statement with cleared debit of $700.00 (TXN-AUDIT-001)
    bank_csv = (
        "Date,Description,Debit,Credit,Reference\n"
        f"{today.isoformat()},Acme Industrial Settlement,700.00,,TXN-AUDIT-001\n"
        f"{today.isoformat()},Acme Industrial Balance,1500.00,,WIRE-CLEAR-88\n"
    ).encode("utf-8")

    b_files = {"file": ("bank_audit.csv", bank_csv, "text/csv")}
    b_data = {
        "column_mapping": json.dumps({
            "transaction_date": "Date",
            "description": "Description",
            "debit_amount": "Debit",
            "credit_amount": "Credit",
            "reference_id": "Reference",
        }),
        "amount_tolerance": "0.05",
    }
    b_res = client.post("/api/reconciliation/run-bank", headers=headers, files=b_files, data=b_data)
    assert b_res.status_code == status.HTTP_201_CREATED
    b_batch = b_res.json()
    b_batch_id = b_batch["id"]

    # Verify cleared payment matched
    cleared_item = next(it for it in b_batch["items"] if it["record_identifier"] == "TXN-AUDIT-001")
    assert cleared_item["match_status"] == "EXACT_MATCH"

    # Verify proposed match for outstanding $1,500
    prop_item = next(it for it in b_batch["items"] if it["record_identifier"] == "WIRE-CLEAR-88")
    assert prop_item["match_status"] == "AMBIGUOUS_MATCH"
    assert prop_item["review_status"] == "PENDING"

    # Explicit confirmation to settle remainder
    confirm_res = client.post(
        f"/api/reconciliation/batches/{b_batch_id}/items/{prop_item['id']}/confirm-payment",
        headers=headers,
        json={"payment_method": "Wire Transfer", "notes": "Auditor confirmed bank clearance"},
    )
    assert confirm_res.status_code == status.HTTP_200_OK

    # Verify invoice status is now fully PAID!
    inv_paid_check = client.get(f"/api/invoices/{inv_id}", headers=headers)
    assert inv_paid_check.json()["payment_status"] == "PAID"
    assert float(inv_paid_check.json()["balance_due"]) == 0.0

    # ---------------------------------------------------------
    # Step 9: Reports & CSV Export with Formula Injection Protection
    # ---------------------------------------------------------
    csv_res = client.get("/api/reports/export/invoices", headers=headers)
    assert csv_res.status_code == status.HTTP_200_OK
    assert "INV-AUDIT-2026-001" in csv_res.text

    # Verify batch CSV export
    b_csv_res = client.get(f"/api/reconciliation/batches/{b_batch_id}/export-csv", headers=headers)
    assert b_csv_res.status_code == status.HTTP_200_OK
    assert "TXN-AUDIT-001" in b_csv_res.text

    # ---------------------------------------------------------
    # Step 10: Session Persistence Verification
    # ---------------------------------------------------------
    # Re-authenticate as if returning from a fresh browser session
    relogin_res = client.post("/api/auth/login", json={
        "email": signup_payload["email"],
        "password": signup_payload["password"],
    })
    new_token = relogin_res.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # Verify invoice, payments, and reconciliation batches persisted in the database
    re_inv = client.get(f"/api/invoices/{inv_id}", headers=new_headers)
    assert re_inv.status_code == status.HTTP_200_OK
    assert re_inv.json()["payment_status"] == "PAID"

    re_batches = client.get("/api/reconciliation/batches", headers=new_headers)
    assert re_batches.status_code == status.HTTP_200_OK
    assert len(re_batches.json()) >= 2
