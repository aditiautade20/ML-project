"""
Tests for Intelligent Automatic Column Mapping in InvoiceIQ.
Covers:
1. All recognized column name synonyms and variations:
   - Invoice Number: invoice_number, invoice_no, invoice_id, reference, ref, document_number
   - Total Amount: total, total_amount, amount, invoice_amount, debit, transaction_amount, net_amount
   - Tax/GST Amount: tax, tax_amount, gst, gst_amount, vat
   - Vendor/Payee: vendor, vendor_name, payee, supplier, supplier_name
   - Posting Date: date, posting_date, transaction_date, invoice_date
2. Case-insensitivity, spaces, underscores, hyphens, and currency symbols
3. Data-driven Debit vs. Credit arbitration:
   - Debit dominant -> auto-mapped to Debit
   - Credit dominant -> auto-mapped to Credit (never blindly chooses debit)
   - Mixed debit/credit -> flags NEEDS_CONFIRMATION with warning and supports row parsing
4. Ambiguous multiple column matches with warnings and candidate lists
5. Missing required columns handling without crashing
6. API endpoint verification for preview responses and XLSX files
"""

from datetime import date
from decimal import Decimal
import io
import json
import pytest
from starlette.testclient import TestClient
import openpyxl

from app.services.reconciliation_parser import (
    canonicalize_header,
    normalize_header_name,
    detect_column_mappings,
    auto_map_columns,
)
from app.services.reconciliation_service import run_ledger_reconciliation
from app.models.invoice import Invoice
from app.models.user import User
from app.services.auth_service import create_access_token


def test_canonicalize_and_normalize_header_variations():
    """Verifies that punctuation, hyphens, spaces, and currency symbols normalize properly."""
    variations = [
        ("Total Amount", "totalamount", "total_amount"),
        ("total_amount", "totalamount", "total_amount"),
        ("Total-Amount", "totalamount", "total_amount"),
        ("TOTAL AMOUNT", "totalamount", "total_amount"),
        ("Total Amount ($)", "totalamount", "total_amount"),
        ("Total Amount (USD)", "totalamount", "total_amount_usd"),
        ("Invoice-No.", "invoiceno", "invoice_no"),
        ("Invoice #", "invoice", "invoice"),
        ("Posting Date", "postingdate", "posting_date"),
        ("Tax / GST Amount", "taxgstamount", "tax_gst_amount"),
    ]
    for orig, expected_canon, expected_norm in variations:
        assert canonicalize_header(orig) == expected_canon, f"Failed canon for {orig}"
        assert normalize_header_name(orig) == expected_norm, f"Failed norm for {orig}"


def test_all_recognized_aliases_for_invoice_number():
    """Tests all required variations of invoice number."""
    inv_aliases = [
        "invoice_number", "invoice_no", "invoice_id", "reference", "ref",
        "document_number", "Invoice-Number", "INVOICE_NO", "Invoice ID", "Doc Number", "Ref #"
    ]
    for alias in inv_aliases:
        headers = [alias, "Vendor Name", "Total Amount", "Date"]
        res = detect_column_mappings(headers, "LEDGER")
        assert res["suggested_mapping"]["invoice_number"] == alias, f"Failed to map invoice number alias: {alias}"
        assert res["mapping_statuses"]["invoice_number"] in ("AUTO_MAPPED", "NEEDS_CONFIRMATION")


def test_all_recognized_aliases_for_total_amount():
    """Tests all required variations of total amount."""
    amount_aliases = [
        "total", "total_amount", "amount", "invoice_amount", "debit",
        "transaction_amount", "net_amount", "Total-Amount", "TOTAL AMOUNT",
        "Invoice Amount", "Gross Amount", "Net-Amount", "Transaction Amount"
    ]
    for alias in amount_aliases:
        headers = ["Invoice Number", "Vendor Name", alias, "Date"]
        res = detect_column_mappings(headers, "LEDGER")
        assert res["suggested_mapping"]["total_amount"] == alias, f"Failed to map total amount alias: {alias}"
        assert res["mapping_statuses"]["total_amount"] in ("AUTO_MAPPED", "NEEDS_CONFIRMATION")


def test_all_recognized_aliases_for_tax_amount():
    """Tests all required variations of tax/GST amount."""
    tax_aliases = ["tax", "tax_amount", "gst", "gst_amount", "vat", "Tax-Amount", "GST Amount", "VAT"]
    for alias in tax_aliases:
        headers = ["Invoice Number", "Total Amount", alias, "Date"]
        res = detect_column_mappings(headers, "LEDGER")
        assert res["suggested_mapping"]["tax_amount"] == alias, f"Failed to map tax alias: {alias}"
        assert res["mapping_statuses"]["tax_amount"] == "AUTO_MAPPED"


def test_all_recognized_aliases_for_vendor_name():
    """Tests all required variations of vendor/payee."""
    vendor_aliases = ["vendor", "vendor_name", "payee", "supplier", "supplier_name", "Vendor-Name", "Supplier Name"]
    for alias in vendor_aliases:
        headers = ["Invoice Number", "Total Amount", alias, "Date"]
        res = detect_column_mappings(headers, "LEDGER")
        assert res["suggested_mapping"]["vendor_name"] == alias, f"Failed to map vendor alias: {alias}"
        assert res["mapping_statuses"]["vendor_name"] == "AUTO_MAPPED"


def test_all_recognized_aliases_for_posting_date():
    """Tests all required variations of posting date."""
    date_aliases = ["date", "posting_date", "transaction_date", "invoice_date", "Posting-Date", "Transaction Date"]
    for alias in date_aliases:
        headers = ["Invoice Number", "Total Amount", "Vendor", alias]
        res = detect_column_mappings(headers, "LEDGER")
        assert res["suggested_mapping"]["invoice_date"] == alias, f"Failed to map date alias: {alias}"
        assert res["mapping_statuses"]["invoice_date"] == "AUTO_MAPPED"


def test_debit_dominant_accounting_ledger():
    """When Debit column has amounts and Credit is empty/zero, Debit is chosen with AUTO_MAPPED."""
    headers = ["Invoice Number", "Vendor", "Debit", "Credit", "Date"]
    rows = [
        {"Invoice Number": "INV-001", "Vendor": "Acme", "Debit": "500.00", "Credit": "", "Date": "2026-10-01"},
        {"Invoice Number": "INV-002", "Vendor": "Beta", "Debit": "350.00", "Credit": "0.00", "Date": "2026-10-02"},
        {"Invoice Number": "INV-003", "Vendor": "Gamma", "Debit": "200.00", "Credit": "", "Date": "2026-10-03"},
    ]
    res = detect_column_mappings(headers, "LEDGER", rows=rows)
    assert res["suggested_mapping"]["total_amount"] == "Debit"
    assert res["mapping_statuses"]["total_amount"] == "AUTO_MAPPED"
    assert res["suggested_mapping"]["debit_column"] == "Debit"
    assert res["suggested_mapping"]["credit_column"] == "Credit"


def test_credit_dominant_accounting_ledger():
    """When Credit column has amounts and Debit is empty/zero, Credit is chosen (never blindly chooses debit)."""
    headers = ["Invoice Number", "Vendor", "Debit", "Credit", "Date"]
    rows = [
        {"Invoice Number": "INV-001", "Vendor": "Acme", "Debit": "", "Credit": "500.00", "Date": "2026-10-01"},
        {"Invoice Number": "INV-002", "Vendor": "Beta", "Debit": "0.00", "Credit": "350.00", "Date": "2026-10-02"},
        {"Invoice Number": "INV-003", "Vendor": "Gamma", "Debit": "", "Credit": "200.00", "Date": "2026-10-03"},
    ]
    res = detect_column_mappings(headers, "LEDGER", rows=rows)
    assert res["suggested_mapping"]["total_amount"] == "Credit"
    assert res["mapping_statuses"]["total_amount"] == "AUTO_MAPPED"
    assert res["suggested_mapping"]["debit_column"] == "Debit"
    assert res["suggested_mapping"]["credit_column"] == "Credit"


def test_mixed_debit_credit_accounting_ledger_ambiguity(db_session):
    """When both Debit and Credit columns have transaction amounts, status is NEEDS_CONFIRMATION with warning."""
    headers = ["Invoice Number", "Vendor", "Debit", "Credit", "Date"]
    rows = [
        {"Invoice Number": "INV-001", "Vendor": "Acme", "Debit": "500.00", "Credit": "", "Date": "2026-10-01"},
        {"Invoice Number": "INV-002", "Vendor": "Beta", "Debit": "", "Credit": "350.00", "Date": "2026-10-02"},
    ]
    res = detect_column_mappings(headers, "LEDGER", rows=rows)
    assert res["mapping_statuses"]["total_amount"] == "NEEDS_CONFIRMATION"
    assert "total_amount" in res["mapping_warnings"]
    assert "Debit" in res["ambiguous_columns"]["total_amount"]
    assert "Credit" in res["ambiguous_columns"]["total_amount"]

    # Verify reconciliation service extracts amounts from both columns when mapped
    user = User(name="DC User", email="dc.user@test.local", hashed_password="pw", is_active=True)
    db_session.add(user)
    db_session.commit()

    inv1 = Invoice(
        user_id=user.id, invoice_number="INV-001", vendor_name="Acme",
        invoice_date=date(2026, 10, 1), due_date=date(2026, 10, 1),
        total_amount=Decimal("500.00"), currency="USD", status="CONFIRMED"
    )
    inv2 = Invoice(
        user_id=user.id, invoice_number="INV-002", vendor_name="Beta",
        invoice_date=date(2026, 10, 2), due_date=date(2026, 10, 2),
        total_amount=Decimal("350.00"), currency="USD", status="CONFIRMED"
    )
    db_session.add_all([inv1, inv2])
    db_session.commit()

    csv_data = (
        "Invoice Number,Vendor,Debit,Credit,Date\n"
        "INV-001,Acme,500.00,,2026-10-01\n"
        "INV-002,Beta,,350.00,2026-10-02\n"
    ).encode("utf-8")

    batch = run_ledger_reconciliation(
        user_id=user.id,
        file_content=csv_data,
        filename="mixed_dc.csv",
        column_mapping=res["suggested_mapping"],
        db=db_session
    )
    assert batch.exact_matches == 2


def test_ambiguous_columns_warning():
    """When multiple columns match a field (e.g. Gross Amount vs Net Amount), warns user."""
    headers = ["Invoice Number", "Vendor", "Gross Amount", "Net Amount", "Date"]
    res = detect_column_mappings(headers, "LEDGER")
    # Gross Amount has higher priority for total_amount than Net Amount
    assert res["suggested_mapping"]["total_amount"] == "Gross Amount"
    assert res["mapping_statuses"]["total_amount"] == "NEEDS_CONFIRMATION"
    assert "Multiple matching columns" in res["mapping_warnings"]["total_amount"]
    assert "Net Amount" in res["ambiguous_columns"]["total_amount"]


def test_missing_required_columns_handling():
    """When required columns are missing, sets status to UNMAPPED with warning without crashing."""
    headers = ["Vendor Name", "Tax Amount", "Date"]  # Missing invoice number and total amount
    res = detect_column_mappings(headers, "LEDGER")
    assert res["mapping_statuses"]["invoice_number"] == "UNMAPPED"
    assert res["mapping_statuses"]["total_amount"] == "UNMAPPED"
    assert "invoice_number" in res["mapping_warnings"]
    assert "total_amount" in res["mapping_warnings"]


def test_preview_api_endpoint_returns_metadata(client: TestClient, db_session):
    """Verifies that the /api/reconciliation/preview endpoint returns mapping statuses and warnings."""
    user = User(name="Preview User", email="preview.user@test.local", hashed_password="pw", is_active=True)
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    csv_content = (
        "Invoice-ID,Supplier-Name,Debit,Credit,Posting-Date\n"
        "INV-991,Apex Corp,450.00,,2026-10-05\n"
        "INV-992,Beta LLC,120.00,,2026-10-06\n"
    ).encode("utf-8")

    files = {"file": ("ledger_preview.csv", csv_content, "text/csv")}
    resp = client.post("/api/reconciliation/preview", headers=headers, files=files, data={"file_type": "LEDGER"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["suggested_mapping"]["invoice_number"] == "Invoice-ID"
    assert data["suggested_mapping"]["vendor_name"] == "Supplier-Name"
    assert data["suggested_mapping"]["total_amount"] == "Debit"
    assert data["suggested_mapping"]["invoice_date"] == "Posting-Date"
    assert "mapping_statuses" in data
    assert data["mapping_statuses"]["invoice_number"] == "AUTO_MAPPED"
    assert data["mapping_statuses"]["total_amount"] == "AUTO_MAPPED"


def test_excel_xlsx_auto_mapping_via_api(client: TestClient, db_session):
    """Verifies that an uploaded Excel (.xlsx) file with custom column names auto-maps properly."""
    user = User(name="XLSX User", email="xlsx.user@test.local", hashed_password="pw", is_active=True)
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Document_Number", "Payee", "Transaction_Amount", "Tax_Amount", "Date"])
    ws.append(["DOC-501", "BrightDesk Supplies", 850.00, 85.00, "2026-10-10"])

    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    files = {"file": ("ledger.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = client.post("/api/reconciliation/preview", headers=headers, files=files, data={"file_type": "LEDGER"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["suggested_mapping"]["invoice_number"] == "Document_Number"
    assert data["suggested_mapping"]["vendor_name"] == "Payee"
    assert data["suggested_mapping"]["total_amount"] == "Transaction_Amount"
    assert data["suggested_mapping"]["tax_amount"] == "Tax_Amount"
    assert data["suggested_mapping"]["invoice_date"] == "Date"
    assert data["mapping_statuses"]["total_amount"] == "AUTO_MAPPED"
