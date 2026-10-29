from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.models.reconciliation import ReconciliationBatch, ReconciliationItem
from app.models.user import User
from app.services.report_service import sanitize_for_csv


def get_auth_token(client, email="reportuser@example.com", name="Report User"):
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


def test_sanitize_for_csv_formula_injection_protection():
    """
    Direct unit test for CSV injection prevention.
    Values starting with =, +, -, @, \\t, or \\r must be prefixed with a single quote.
    """
    assert sanitize_for_csv("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert sanitize_for_csv("+12345") == "'+12345"
    assert sanitize_for_csv("-9876") == "'-9876"
    assert sanitize_for_csv("@cmd|'/C calc'!A0") == "'@cmd|'/C calc'!A0"
    assert sanitize_for_csv("\tTabbed") == "'\tTabbed"
    assert sanitize_for_csv("\rCarriage") == "'\rCarriage"
    assert sanitize_for_csv("  =SUM(A1)") == "'  =SUM(A1)"
    assert sanitize_for_csv("Normal Text") == "Normal Text"
    assert sanitize_for_csv("100.50") == "100.50"
    assert sanitize_for_csv(None) == ""


def test_dashboard_calculations_and_trends(client):
    """
    Tests that dashboard calculations accurately aggregate saved invoices,
    payments, outstanding balances, overdue amounts, upcoming deadlines,
    and status distribution counts strictly from database records.
    """
    token = get_auth_token(client, "dash@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()

    # Invoice 1: $100 (fully paid -> status PAID)
    inv1 = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-DASH-01",
            "vendor_name": "Vendor 1",
            "invoice_date": str(today),
            "due_date": str(today + timedelta(days=15)),
            "total_amount": 100.00,
            "currency": "USD",
        },
        headers=headers,
    ).json()

    client.post(
        "/api/payments/",
        json={
            "invoice_id": inv1["id"],
            "amount": 100.00,
            "payment_date": str(today),
            "payment_method": "Bank Transfer",
        },
        headers=headers,
    )

    # Invoice 2: $200 (partially paid $50 -> balance $150, status PARTIAL)
    inv2 = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-DASH-02",
            "vendor_name": "Vendor 2",
            "invoice_date": str(today),
            "due_date": str(today + timedelta(days=3)),  # within 7 days
            "total_amount": 200.00,
            "currency": "USD",
        },
        headers=headers,
    ).json()

    client.post(
        "/api/payments/",
        json={
            "invoice_id": inv2["id"],
            "amount": 50.00,
            "payment_date": str(today),
            "payment_method": "Credit Card",
        },
        headers=headers,
    )

    # Invoice 3: $300 (overdue by 5 days, 0 paid -> balance $300, status OVERDUE)
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-DASH-03",
            "vendor_name": "Vendor 2",
            "invoice_date": str(today - timedelta(days=20)),
            "due_date": str(today - timedelta(days=5)),
            "total_amount": 300.00,
            "currency": "USD",
        },
        headers=headers,
    )

    # Invoice 4: $400 (unpaid, due in 4 days -> status DUE_SOON)
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-DASH-04",
            "vendor_name": "Vendor 3",
            "invoice_date": str(today),
            "due_date": str(today + timedelta(days=4)),
            "total_amount": 400.00,
            "currency": "USD",
        },
        headers=headers,
    )

    # Fetch Dashboard
    res = client.get("/api/reports/dashboard", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total_invoices_count"] == 4
    assert float(data["total_invoiced_amount"]) == 1000.00
    assert float(data["total_paid_amount"]) == 150.00
    assert float(data["total_outstanding_balance"]) == 850.00
    assert data["overdue_count"] == 1
    assert float(data["overdue_amount"]) == 300.00
    assert data["due_within_7_days_count"] == 2  # inv2 ($150 bal) and inv4 ($400 bal)
    assert float(data["due_within_7_days_amount"]) == 550.00

    # Verify status distribution counts
    status_counts = data["status_counts"]
    assert status_counts["PAID"] == 1
    assert status_counts["PARTIAL"] == 1
    assert status_counts["OVERDUE"] == 1
    assert status_counts["DUE_SOON"] == 1
    assert status_counts["UNPAID"] == 0

    # Verify monthly trends list exists and has 6 buckets
    assert len(data["monthly_trends"]) == 6
    # Verify recent activity
    assert len(data["recent_invoices"]) == 4
    assert len(data["recent_payments"]) == 2


def test_reports_analytics_filters_and_tables(client):
    """
    Tests period and vendor filtering, and verifies that detailed invoices,
    payments, and vendor breakdown lists are returned accurately.
    """
    token = get_auth_token(client, "filter_rep@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()

    # Invoice A: Alpha Corp $250
    inv_a = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-VEND-A",
            "vendor_name": "Alpha Corp",
            "invoice_date": str(today),
            "due_date": str(today + timedelta(days=10)),
            "total_amount": 250.00,
            "currency": "USD",
        },
        headers=headers,
    ).json()

    # Invoice B: Beta LLC $400
    inv_b = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-VEND-B",
            "vendor_name": "Beta LLC",
            "invoice_date": str(today),
            "due_date": str(today + timedelta(days=5)),
            "total_amount": 400.00,
            "currency": "USD",
        },
        headers=headers,
    ).json()

    # Payment for Invoice A: $100
    client.post(
        "/api/payments/",
        json={
            "invoice_id": inv_a["id"],
            "amount": 100.00,
            "payment_date": str(today),
            "payment_method": "ACH",
            "reference": "REF-ALPHA-01",
        },
        headers=headers,
    )

    # 1. Filter specifically by vendor Alpha Corp
    res = client.get("/api/reports/analytics?vendor=Alpha+Corp", headers=headers)
    assert res.status_code == 200
    data = res.json()

    summary = data["summary"]
    assert summary["total_invoices_count"] == 1
    assert float(summary["total_invoiced_amount"]) == 250.00
    assert float(summary["total_paid_amount"]) == 100.00
    assert float(summary["total_outstanding_balance"]) == 150.00

    vendors = data["vendor_breakdown"]
    assert len(vendors) == 1
    assert vendors[0]["vendor_name"] == "Alpha Corp"

    # Invoices list check
    invoices = data["invoices"]
    assert len(invoices) == 1
    assert invoices[0]["invoice_number"] == "INV-VEND-A"
    assert float(invoices[0]["total_paid"]) == 100.00
    assert float(invoices[0]["balance_due"]) == 150.00
    assert invoices[0]["payment_status"] == "PARTIAL"

    # Payments list check
    payments = data["payments"]
    assert len(payments) == 1
    assert payments[0]["invoice_number"] == "INV-VEND-A"
    assert payments[0]["reference"] == "REF-ALPHA-01"


def test_invalid_date_range_validation(client):
    """
    Validates that if start_date > end_date, endpoints return 400 Bad Request.
    """
    token = get_auth_token(client, "daterange@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Analytics endpoint
    res = client.get(
        f"/api/reports/analytics?start_date={tomorrow}&end_date={today}",
        headers=headers,
    )
    assert res.status_code == 400
    assert "Start date cannot be after end date" in res.json()["detail"]

    # Invoices export endpoint
    res_inv = client.get(
        f"/api/reports/export/invoices?start_date={tomorrow}&end_date={today}",
        headers=headers,
    )
    assert res_inv.status_code == 400

    # Payments export endpoint
    res_pay = client.get(
        f"/api/reports/export/payments?start_date={tomorrow}&end_date={today}",
        headers=headers,
    )
    assert res_pay.status_code == 400

    # Outstanding export endpoint
    res_out = client.get(
        f"/api/reports/export/outstanding?start_date={tomorrow}&end_date={today}",
        headers=headers,
    )
    assert res_out.status_code == 400

    # Reconciliation export endpoint
    res_rec = client.get(
        f"/api/reports/export/reconciliation?start_date={tomorrow}&end_date={today}",
        headers=headers,
    )
    assert res_rec.status_code == 400

    # PDF export endpoint
    res_pdf = client.get(
        f"/api/reports/export/pdf?start_date={tomorrow}&end_date={today}",
        headers=headers,
    )
    assert res_pdf.status_code == 400


def test_empty_dataset_handling(client):
    """
    Ensures empty accounts with no invoices or payments return zero metrics
    and clean structures without throwing exceptions.
    """
    token = get_auth_token(client, "empty@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    dash = client.get("/api/reports/dashboard", headers=headers)
    assert dash.status_code == 200
    dash_data = dash.json()
    assert dash_data["total_invoices_count"] == 0
    assert float(dash_data["total_invoiced_amount"]) == 0.00
    assert float(dash_data["total_paid_amount"]) == 0.00
    assert float(dash_data["total_outstanding_balance"]) == 0.00
    assert dash_data["status_counts"]["PAID"] == 0
    assert dash_data["status_counts"]["UNPAID"] == 0

    analytics = client.get("/api/reports/analytics", headers=headers)
    assert analytics.status_code == 200
    an_data = analytics.json()
    assert an_data["summary"]["total_invoices_count"] == 0
    assert len(an_data["invoices"]) == 0
    assert len(an_data["payments"]) == 0
    assert an_data["reconciliation_summary"]["total_records"] == 0


def test_csv_export_with_formula_injection_escaping(client):
    """
    Verifies that CSV export outputs valid CSV files with proper headers,
    supports vendor filtering, and safely escapes spreadsheet formulas in user input.
    """
    token = get_auth_token(client, "csvexport@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Invoice with potential formula injection in number and vendor
    inv = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "=1+2",
            "vendor_name": "@EvilVendor",
            "invoice_date": str(date.today()),
            "total_amount": 100.00,
            "notes": "-DDE('cmd';'/c calc';'A0')",
            "currency": "USD",
        },
        headers=headers,
    ).json()

    # Record payment with formula injection in reference
    client.post(
        "/api/payments/",
        json={
            "invoice_id": inv["id"],
            "amount": 40.00,
            "payment_date": str(date.today()),
            "payment_method": "Wire",
            "reference": "+REF=cmd|'calc'!A0",
        },
        headers=headers,
    )

    # 1. Test Invoices CSV export
    inv_csv_res = client.get("/api/reports/export/invoices", headers=headers)
    assert inv_csv_res.status_code == 200
    assert "text/csv" in inv_csv_res.headers["content-type"]
    csv_text = inv_csv_res.text

    assert "Invoice Number" in csv_text
    assert "Supplier / Vendor" in csv_text
    assert "Balance Due" in csv_text
    assert "'=1+2" in csv_text
    assert "'@EvilVendor" in csv_text
    assert "'-DDE('cmd';'/c calc';'A0')" in csv_text

    # 2. Test Payments CSV export
    pay_csv_res = client.get("/api/reports/export/payments", headers=headers)
    assert pay_csv_res.status_code == 200
    assert "text/csv" in pay_csv_res.headers["content-type"]
    pay_text = pay_csv_res.text
    assert "'+REF=cmd|'calc'!A0" in pay_text

    # 3. Test Outstanding CSV export
    out_csv_res = client.get("/api/reports/export/outstanding", headers=headers)
    assert out_csv_res.status_code == 200
    assert "text/csv" in out_csv_res.headers["content-type"]
    assert "'=1+2" in out_csv_res.text

    # 4. Test Vendor filter on Invoices CSV
    vendor_csv_res = client.get("/api/reports/export/invoices?vendor=%40EvilVendor", headers=headers)
    assert vendor_csv_res.status_code == 200
    assert "'@EvilVendor" in vendor_csv_res.text


def test_reconciliation_report_and_export(client, db_session):
    """
    Tests reconciliation summary aggregation and CSV export of reconciliation results
    (matched records, mismatches, missing entries, duplicates).
    """
    token = get_auth_token(client, "reconcile_rep@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Retrieve user ID
    user = db_session.query(User).filter(User.email == "reconcile_rep@example.com").first()
    assert user is not None

    # Create a Reconciliation Batch with items
    batch = ReconciliationBatch(
        user_id=user.id,
        batch_type="COMBINED",
        title="May 2026 Monthly Audit",
        status="COMPLETED",
        total_records=3,
        exact_matches=1,
        mismatches=1,
        unmatched_records=1,
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    # Item 1: Exact Match
    item1 = ReconciliationItem(
        batch_id=batch.id,
        user_id=user.id,
        item_type="COMBINED",
        match_status="MATCHED",
        record_identifier="INV-REC-101",
        vendor_or_counterparty="Dell Technologies",
        transaction_date="2026-05-10",
        expected_value="1500.00",
        actual_value="1500.00",
        discrepancy_amount=Decimal("0.00"),
        currency="USD",
        review_status="CONFIRMED",
    )
    # Item 2: Discrepancy with dangerous formula
    item2 = ReconciliationItem(
        batch_id=batch.id,
        user_id=user.id,
        item_type="COMBINED",
        match_status="AMOUNT_MISMATCH",
        record_identifier="=CMD(1)",
        vendor_or_counterparty="OfficeMart Inc",
        transaction_date="2026-05-12",
        expected_value="500.00",
        actual_value="480.00",
        discrepancy_amount=Decimal("20.00"),
        currency="USD",
        review_status="PENDING",
        evidence_text="Bank debited $480.00 instead of $500.00",
    )
    db_session.add_all([item1, item2])
    db_session.commit()

    # Test Analytics endpoint returns reconciliation summary
    an_res = client.get("/api/reports/analytics", headers=headers)
    assert an_res.status_code == 200
    data = an_res.json()

    rec_summary = data["reconciliation_summary"]
    assert rec_summary["total_batches"] == 1
    assert rec_summary["total_records"] == 2
    assert rec_summary["matched_count"] == 1
    assert rec_summary["mismatch_count"] == 1

    rec_items = data["reconciliation_items"]
    assert len(rec_items) == 2
    assert rec_items[0]["record_identifier"] in ("INV-REC-101", "=CMD(1)")

    # Test Reconciliation CSV export
    csv_res = client.get("/api/reports/export/reconciliation", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    csv_text = csv_res.text

    assert "Batch Title" in csv_text
    assert "Record ID" in csv_text
    assert "Discrepancy Amount" in csv_text
    assert "May 2026 Monthly Audit" in csv_text
    assert "Dell Technologies" in csv_text
    # Verify formula injection in record identifier is safely escaped
    assert "'=CMD(1)" in csv_text


def test_pdf_export_generation(client):
    """
    Tests PDF generation endpoint /api/reports/export/pdf with vendor filter
    and status distribution inclusion.
    """
    token = get_auth_token(client, "pdfexport@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-PDF-01",
            "vendor_name": "PDF Partner Inc",
            "invoice_date": str(date.today()),
            "total_amount": 750.00,
            "currency": "USD",
        },
        headers=headers,
    )

    pdf_res = client.get("/api/reports/export/pdf?vendor=PDF+Partner+Inc", headers=headers)
    assert pdf_res.status_code == 200
    assert "application/pdf" in pdf_res.headers["content-type"]
    assert "attachment;" in pdf_res.headers["content-disposition"]

    pdf_bytes = pdf_res.content
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000


def test_multi_currency_segregation(client):
    """
    Ensures that accounts with multiple currencies (e.g. USD and EUR) segment
    financial totals and do not falsely combine distinct currency symbols.
    """
    token = get_auth_token(client, "multicurrency@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()

    # Invoice 1: USD 100
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-USD-01",
            "vendor_name": "US Vendor",
            "invoice_date": str(today),
            "total_amount": 100.00,
            "currency": "USD",
        },
        headers=headers,
    )

    # Invoice 2: EUR 200
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-EUR-01",
            "vendor_name": "EU Vendor",
            "invoice_date": str(today),
            "total_amount": 200.00,
            "currency": "EUR",
        },
        headers=headers,
    )

    dash = client.get("/api/reports/dashboard", headers=headers).json()
    assert dash["has_multiple_currencies"] is True
    assert "USD" in dash["by_currency"]
    assert "EUR" in dash["by_currency"]
    assert float(dash["by_currency"]["USD"]["total_invoiced_amount"]) == 100.00
    assert float(dash["by_currency"]["EUR"]["total_invoiced_amount"]) == 200.00


def test_reports_user_isolation(client):
    """
    Confirms strict multi-tenant isolation: User A's data is never visible
    or aggregated into User B's dashboard, analytics, or export reports.
    """
    token_a = get_auth_token(client, "user_a_rep@example.com", "User Alpha")
    token_b = get_auth_token(client, "user_b_rep@example.com", "User Beta")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates $5,000 invoice
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-SECRET-A",
            "vendor_name": "Confidential Vendor",
            "invoice_date": str(date.today()),
            "total_amount": 5000.00,
            "currency": "USD",
        },
        headers=headers_a,
    )

    # User B checks dashboard
    b_dash = client.get("/api/reports/dashboard", headers=headers_b).json()
    assert b_dash["total_invoices_count"] == 0
    assert float(b_dash["total_invoiced_amount"]) == 0.00

    # User B checks analytics
    b_an = client.get("/api/reports/analytics", headers=headers_b).json()
    assert b_an["summary"]["total_invoices_count"] == 0
    assert len(b_an["invoices"]) == 0

    # User B exports CSV
    b_csv = client.get("/api/reports/export/invoices", headers=headers_b).text
    assert "INV-SECRET-A" not in b_csv
    assert "Confidential Vendor" not in b_csv
