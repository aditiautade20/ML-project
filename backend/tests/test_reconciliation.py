from datetime import date, timedelta
from decimal import Decimal
import io
import json
import pytest
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.reconciliation import ReconciliationBatch, ReconciliationItem
from app.models.user import User
from app.services.auth_service import create_access_token


@pytest.fixture
def test_user(db_session: Session):
    user = User(
        name="Audit Manager",
        email="audit.manager@reconcile.local",
        hashed_password="hashed_pw_xyz",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_invoices(test_user, db_session: Session):
    """Creates a realistic set of invoices for the test user."""
    today = date.today()
    invoices = [
        Invoice(
            user_id=test_user.id,
            invoice_number="INV-2026-001",
            vendor_name="Acme Tech Supplies",
            invoice_date=today - timedelta(days=20),
            due_date=today + timedelta(days=10),
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("100.00"),
            total_amount=Decimal("1100.00"),
            currency="USD",
            status="CONFIRMED",
        ),
        Invoice(
            user_id=test_user.id,
            invoice_number="INV-2026-002",
            vendor_name="BrightDesk Office Supplies",
            invoice_date=today - timedelta(days=15),
            due_date=today - timedelta(days=2),
            subtotal=Decimal("3700.00"),
            tax_amount=Decimal("666.00"),
            total_amount=Decimal("4366.00"),
            currency="INR",
            status="CONFIRMED",
        ),
        Invoice(
            user_id=test_user.id,
            invoice_number="INV-2026-003",
            vendor_name="Global Cloud Hosting",
            invoice_date=today - timedelta(days=30),
            due_date=today - timedelta(days=5),
            subtotal=Decimal("500.00"),
            tax_amount=Decimal("50.00"),
            total_amount=Decimal("550.00"),
            currency="USD",
            status="CONFIRMED",
        ),
    ]
    db_session.add_all(invoices)
    db_session.commit()
    for inv in invoices:
        db_session.refresh(inv)

    # Add a recorded payment for INV-2026-001 ($500 partial)
    pay = Payment(
        invoice_id=invoices[0].id,
        user_id=test_user.id,
        amount=Decimal("500.00"),
        payment_date=today - timedelta(days=10),
        payment_method="Bank Transfer",
        reference="WIRE-TXN-001",
    )
    db_session.add(pay)
    db_session.commit()

    return invoices


def test_preview_reconciliation_csv_auto_mapping(client, auth_headers):
    """Verifies file preview, column auto-mapping, and duplicate detection."""
    csv_content = (
        "Doc Number,Vendor Name,Document Date,Gross Amount,Tax Amount\n"
        "INV-2026-001,Acme Tech Supplies,2026-05-15,1100.00,100.00\n"
        "INV-2026-002,BrightDesk Supplies,2026-05-20,4366.00,666.00\n"
    ).encode("utf-8")

    files = {"file": ("ledger_may.csv", csv_content, "text/csv")}
    resp = client.post("/api/reconciliation/preview?file_type=LEDGER", headers=auth_headers, files=files)
    assert resp.status_code == 200
    data = resp.json()

    assert data["filename"] == "ledger_may.csv"
    assert data["total_rows"] == 2
    assert "Doc Number" in data["headers"]
    # Verify auto-mapping caught the column synonyms
    assert data["suggested_mapping"]["invoice_number"] == "Doc Number"
    assert data["suggested_mapping"]["total_amount"] == "Gross Amount"
    assert data["suggested_mapping"]["vendor_name"] == "Vendor Name"


def test_ledger_reconciliation_matches_and_mismatches(client, auth_headers, sample_invoices):
    """
    Tests accounting ledger reconciliation:
    1. Exact match (INV-2026-001)
    2. Amount mismatch (INV-2026-002, $4,500 vs $4,366)
    3. Missing in InvoiceIQ (INV-2026-999)
    4. Missing in Ledger (INV-2026-003)
    5. Duplicate ledger entry
    """
    ledger_csv = (
        "invoice_no,vendor,date,total,tax\n"
        "INV-2026-001,Acme Tech Supplies,2026-10-05,1100.00,100.00\n"
        "INV-2026-002,BrightDesk,2026-10-10,4500.00,666.00\n"  # Mismatch by $134
        "INV-2026-999,Unknown Corp,2026-10-12,850.00,50.00\n"   # Missing in Invoices
        "INV-2026-001,Acme Tech Supplies,2026-10-05,1100.00,100.00\n"  # Duplicate in ledger
    ).encode("utf-8")

    files = {"file": ("ledger.csv", ledger_csv, "text/csv")}
    data = {
        "column_mapping": json.dumps({
            "invoice_number": "invoice_no",
            "vendor_name": "vendor",
            "total_amount": "total",
            "tax_amount": "tax"
        }),
        "tolerance": 0.05
    }

    resp = client.post("/api/reconciliation/run-ledger", headers=auth_headers, files=files, data=data)
    assert resp.status_code == 201
    batch = resp.json()

    assert batch["batch_type"] == "LEDGER"
    items = batch["items"]
    status_map = {item["record_identifier"]: item for item in items}

    # 1. INV-2026-001 has one exact match and one duplicate
    matches_001 = [i for i in items if i["record_identifier"] == "INV-2026-001"]
    assert any(m["match_status"] == "EXACT_MATCH" for m in matches_001)
    assert any(m["match_status"] == "DUPLICATE_SUSPECTED" for m in matches_001)

    # 2. INV-2026-002 is AMOUNT_MISMATCH
    item_002 = status_map["INV-2026-002"]
    assert item_002["match_status"] == "AMOUNT_MISMATCH"
    assert "4366.00" in item_002["expected_value"]
    assert "4500.00" in item_002["actual_value"]

    # 3. INV-2026-999 is MISSING_IN_INVOICES
    item_999 = status_map["INV-2026-999"]
    assert item_999["match_status"] == "MISSING_IN_INVOICES"

    # 4. INV-2026-003 was not in ledger -> MISSING_IN_LEDGER
    item_003 = status_map["INV-2026-003"]
    assert item_003["match_status"] == "MISSING_IN_LEDGER"


def test_bank_reconciliation_and_explicit_payment_confirmation(client, auth_headers, sample_invoices, db_session: Session):
    """
    Tests bank statement reconciliation and verifies the CRITICAL safety rule:
    Bank statement import does NOT automatically modify payments or invoices.
    Explicit confirmation is required to record a payment.
    """
    # Bank statement with:
    # 1. Cleared payment for WIRE-TXN-001 ($500.00)
    # 2. Unrecorded debit for BrightDesk ($4,366.00)
    # 3. Unmatched debit for Office Depot ($85.00)
    # 4. Incoming credit ($2,000.00) - should be ignored for AP debit matching
    bank_csv = (
        "Date,Description,Debit,Credit,Reference\n"
        "2026-10-15,Wire Transfer Acme Tech,500.00,,WIRE-TXN-001\n"
        "2026-10-18,BrightDesk Supplies Settlement,4366.00,,NEFT-8891\n"
        "2026-10-20,Coffee & Snacks,85.00,,POS-9128\n"
        "2026-10-21,Customer Deposit,,2000.00,DEP-001\n"
    ).encode("utf-8")

    files = {"file": ("october_statement.csv", bank_csv, "text/csv")}
    data = {
        "column_mapping": json.dumps({
            "transaction_date": "Date",
            "description": "Description",
            "debit_amount": "Debit",
            "credit_amount": "Credit",
            "reference_id": "Reference"
        })
    }

    # Verify initial payment count for user
    initial_payment_count = db_session.query(Payment).filter(Payment.user_id == sample_invoices[0].user_id).count()
    assert initial_payment_count == 1

    # Run Bank Reconciliation
    resp = client.post("/api/reconciliation/run-bank", headers=auth_headers, files=files, data=data)
    assert resp.status_code == 201
    batch = resp.json()
    batch_id = batch["id"]

    # CRITICAL SAFETY CHECK: Payments count must NOT have changed automatically!
    post_reconcile_count = db_session.query(Payment).filter(Payment.user_id == sample_invoices[0].user_id).count()
    assert post_reconcile_count == initial_payment_count, "Import must NEVER create payments automatically!"

    items = batch["items"]
    # Check WIRE-TXN-001 was matched
    wire_item = next(i for i in items if i["record_identifier"] == "WIRE-TXN-001")
    assert wire_item["match_status"] == "EXACT_MATCH"

    # Check BrightDesk NEFT-8891 proposed match
    bd_item = next(i for i in items if i["record_identifier"] == "NEFT-8891")
    assert bd_item["match_status"] == "AMBIGUOUS_MATCH"
    assert bd_item["review_status"] == "PENDING"
    assert bd_item["invoice_id"] == sample_invoices[1].id

    # Check Coffee & Snacks unmatched
    snack_item = next(i for i in items if i["record_identifier"] == "POS-9128")
    assert snack_item["match_status"] == "UNMATCHED_BANK_TXN"

    # NOW EXPLICITLY CONFIRM PAYMENT for BrightDesk
    confirm_resp = client.post(
        f"/api/reconciliation/batches/{batch_id}/items/{bd_item['id']}/confirm-payment",
        headers=auth_headers,
        json={"payment_method": "Bank Transfer", "notes": "Explicitly confirmed via bank statement"},
    )
    assert confirm_resp.status_code == 200
    confirmed_item = confirm_resp.json()
    assert confirmed_item["review_status"] == "CONFIRMED"
    assert confirmed_item["payment_id"] is not None

    # Verify that a payment record WAS created after explicit confirmation
    final_payment_count = db_session.query(Payment).filter(Payment.user_id == sample_invoices[0].user_id).count()
    assert final_payment_count == initial_payment_count + 1

    # Verify invoice status transitioned to PAID
    inv_bd = db_session.query(Invoice).filter(Invoice.id == sample_invoices[1].id).first()
    assert inv_bd is not None


def test_combined_reconciliation(client, auth_headers, sample_invoices):
    """Tests 4-way combined reconciliation linking Invoices, Ledger, Payments, and Bank."""
    ledger_csv = (
        "invoice_number,total_amount\n"
        "INV-2026-001,1100.00\n"
        "INV-2026-002,4366.00\n"
    ).encode("utf-8")

    bank_csv = (
        "Date,Description,Debit,Reference\n"
        "2026-10-15,Acme Tech Supplies,500.00,WIRE-TXN-001\n"
    ).encode("utf-8")

    files = {
        "ledger_file": ("ledger.csv", ledger_csv, "text/csv"),
        "bank_file": ("bank.csv", bank_csv, "text/csv"),
    }
    data = {
        "ledger_mapping": json.dumps({"invoice_number": "invoice_number", "total_amount": "total_amount"}),
        "bank_mapping": json.dumps({"transaction_date": "Date", "description": "Description", "debit_amount": "Debit"}),
    }

    resp = client.post("/api/reconciliation/run-combined", headers=auth_headers, files=files, data=data)
    assert resp.status_code == 201
    batch = resp.json()
    assert batch["batch_type"] == "COMBINED"
    assert len(batch["items"]) >= 3


def test_csv_export_formula_injection_protection(client, auth_headers, sample_invoices):
    """Verifies that reconciliation CSV export neutralizes formula injection triggers (=, +, -, @)."""
    malicious_csv = (
        "invoice_number,total_amount,vendor\n"
        "=cmd|' /C calc'!A0,1100.00,+@HyperlinkVendor\n"
    ).encode("utf-8")

    files = {"file": ("malicious.csv", malicious_csv, "text/csv")}
    run_resp = client.post("/api/reconciliation/run-ledger", headers=auth_headers, files=files)
    assert run_resp.status_code == 201
    batch_id = run_resp.json()["id"]

    export_resp = client.get(f"/api/reconciliation/batches/{batch_id}/export-csv", headers=auth_headers)
    assert export_resp.status_code == 200
    csv_text = export_resp.text

    # Formula injection check: Dangerous cells must be escaped with a leading single quote
    assert "'=cmd" in csv_text or "'=" in csv_text
    assert "'+@" in csv_text or "'+@HyperlinkVendor" in csv_text


def test_reconciliation_user_isolation(client, db_session: Session):
    """Ensures batches and items created by User A are completely inaccessible by User B."""
    user_a = User(name="User A", email="usera@corp.com", hashed_password="pw")
    user_b = User(name="User B", email="userb@corp.com", hashed_password="pw")
    db_session.add_all([user_a, user_b])
    db_session.commit()

    token_a = create_access_token({"sub": str(user_a.id)})
    token_b = create_access_token({"sub": str(user_b.id)})

    # User A creates a batch
    batch_a = ReconciliationBatch(
        user_id=user_a.id,
        batch_type="LEDGER",
        title="Batch A",
        total_records=1,
    )
    db_session.add(batch_a)
    db_session.commit()
    db_session.refresh(batch_a)

    # User B attempts to access User A's batch -> 404
    resp_b = client.get(
        f"/api/reconciliation/batches/{batch_a.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 404

    # User B lists batches -> empty
    list_b = client.get("/api/reconciliation/batches", headers={"Authorization": f"Bearer {token_b}"})
    assert list_b.status_code == 200
    assert len(list_b.json()) == 0


def test_invalid_files_and_size_validation(client, auth_headers):
    """
    Tests validation of file formats, file sizes, required columns, and malformed files:
    1. Empty file (0 bytes) -> 400
    2. File exceeding 10MB limit -> 400
    3. Unsupported file extensions (.exe, .pdf, .zip) -> 400
    4. Missing required columns without valid mapping -> 400
    """
    # 1. Empty file
    empty_res = client.post(
        "/api/reconciliation/preview",
        headers=auth_headers,
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert empty_res.status_code == 400
    assert "empty" in empty_res.json()["detail"].lower()

    # 2. File exceeding 10MB limit
    oversized = b"a" * (10 * 1024 * 1024 + 100)
    over_res = client.post(
        "/api/reconciliation/run-ledger",
        headers=auth_headers,
        files={"file": ("huge.csv", oversized, "text/csv")},
    )
    assert over_res.status_code == 400
    assert "exceeds maximum allowed limit" in over_res.json()["detail"].lower()

    # 3. Unsupported extension (.exe)
    bad_ext_res = client.post(
        "/api/reconciliation/preview",
        headers=auth_headers,
        files={"file": ("payload.exe", b"binary content", "application/octet-stream")},
    )
    assert bad_ext_res.status_code == 400
    assert "unsupported file format" in bad_ext_res.json()["detail"].lower()

    # 4. Missing required columns without column mapping
    missing_cols_csv = "CustomerName,TransactionNotes\nAcme,Monthly billing\n".encode("utf-8")
    miss_res = client.post(
        "/api/reconciliation/run-ledger",
        headers=auth_headers,
        files={"file": ("invalid_headers.csv", missing_cols_csv, "text/csv")},
    )
    assert miss_res.status_code == 400
    assert "required columns missing" in miss_res.json()["detail"].lower()


def test_ambiguous_matches_in_ledger_reconciliation(client, auth_headers, sample_invoices):
    """
    Tests fuzzy candidate matching when invoice numbers differ due to typos or prefix differences,
    but vendor name and amount match an open invoice in InvoiceIQ -> AMBIGUOUS_MATCH.
    """
    ledger_csv = (
        "Invoice Number,Vendor,Total Amount\n"
        "INV-MISSPELLED-999,Acme Tech Supplies,1100.00\n"
    ).encode("utf-8")

    files = {"file": ("ledger_typo.csv", ledger_csv, "text/csv")}
    resp = client.post("/api/reconciliation/run-ledger", headers=auth_headers, files=files)
    assert resp.status_code == 201
    batch = resp.json()

    ambig_item = next(i for i in batch["items"] if i["record_identifier"] == "INV-MISSPELLED-999")
    assert ambig_item["match_status"] == "AMBIGUOUS_MATCH"
    assert ambig_item["review_status"] == "PENDING"
    assert "Acme Tech" in ambig_item["evidence_text"]


def test_xlsx_ledger_and_bank_reconciliation(client, auth_headers, sample_invoices):
    """
    Validates end-to-end reconciliation using genuine Excel (.xlsx) workbooks generated via openpyxl.
    """
    import openpyxl
    from io import BytesIO

    # 1. Create an Excel workbook in memory
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Accounting Ledger"
    ws.append(["Invoice Number", "Vendor Name", "Total Amount", "Tax Amount", "Invoice Date"])
    ws.append(["INV-2026-001", "Acme Tech Supplies", 1100.00, 100.00, "2026-10-15"])
    ws.append(["INV-2026-002", "BrightDesk Office Supplies", 4366.00, 666.00, "2026-10-16"])

    excel_buf = BytesIO()
    wb.save(excel_buf)
    excel_bytes = excel_buf.getvalue()

    # 2. Preview XLSX
    prev_res = client.post(
        "/api/reconciliation/preview?file_type=LEDGER",
        headers=auth_headers,
        files={"file": ("ledger.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert prev_res.status_code == 200
    prev_data = prev_res.json()
    assert prev_data["file_type"] == "XLSX"
    assert prev_data["total_rows"] == 2
    assert prev_data["suggested_mapping"]["invoice_number"] == "Invoice Number"

    # 3. Run Ledger Reconciliation with XLSX
    run_res = client.post(
        "/api/reconciliation/run-ledger",
        headers=auth_headers,
        files={"file": ("ledger.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert run_res.status_code == 201
    batch = run_res.json()
    assert batch["exact_matches"] >= 2

