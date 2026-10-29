import io
from datetime import date, timedelta
from decimal import Decimal
import pytest

from tests.test_invoices_api import get_auth_token, make_pdf_bytes


def test_saved_invoice_is_single_source_of_truth_across_app(client):
    """Verify that a saved invoice is immediately accessible in Invoices,
    Deadlines Summary, and Payment tracking without requiring duplicate entry."""
    token = get_auth_token(client, email="singlesource@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a valid invoice
    due_date = (date.today() + timedelta(days=14)).isoformat()
    invoice_payload = {
        "invoice_number": "INV-SS-001",
        "vendor_name": "Unified Tech Ltd",
        "invoice_date": date.today().isoformat(),
        "due_date": due_date,
        "currency": "USD",
        "subtotal": 1000.00,
        "tax_amount": 100.00,
        "total_amount": 1100.00,
    }
    create_res = client.post("/api/invoices/", json=invoice_payload, headers=headers)
    assert create_res.status_code == 201
    created_inv = create_res.json()
    invoice_id = created_inv["id"]
    assert created_inv["total_amount"] == "1100.00"
    assert created_inv["amount_paid"] == "0.00"
    assert created_inv["balance_due"] == "1100.00"
    assert created_inv["payment_status"] == "UNPAID"
    assert created_inv["status"] == "CONFIRMED"

    # 2. Check Invoices list
    list_res = client.get("/api/invoices/", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) == 1
    assert items[0]["invoice_number"] == "INV-SS-001"
    assert items[0]["balance_due"] == "1100.00"

    # 3. Check Deadlines Summary (populated directly from saved invoices)
    deadlines_res = client.get("/api/invoices/deadlines/summary", headers=headers)
    assert deadlines_res.status_code == 200
    deadlines_data = deadlines_res.json()
    # It has a future due date > 7 days, so it should be in due_later
    all_deadline_invoices = (
        deadlines_data["overdue"]
        + deadlines_data["due_today"]
        + deadlines_data["due_within_7_days"]
        + deadlines_data["due_later"]
    )
    found = next((i for i in all_deadline_invoices if i["id"] == invoice_id), None)
    assert found is not None
    assert found["invoice_number"] == "INV-SS-001"
    assert found["balance_due"] == "1100.00"

    # 4. Check Payment Summary for this invoice
    summary_res = client.get(f"/api/payments/invoice/{invoice_id}/summary", headers=headers)
    assert summary_res.status_code == 200
    summary_data = summary_res.json()
    assert summary_data["invoice_total"] == "1100.00"
    assert summary_data["amount_paid"] == "0.00"
    assert summary_data["balance_due"] == "1100.00"
    assert summary_data["payment_status"] == "UNPAID"
    assert len(summary_data["payments"]) == 0


def test_payment_recording_updates_balances_and_settlement_across_views(client):
    """Test recording partial payment and remaining payment:
    updates balance, payment status, transaction logs, and deadlines."""
    token = get_auth_token(client, email="payflow@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create an invoice
    due_date = (date.today() + timedelta(days=3)).isoformat()
    create_res = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-PAY-555",
            "vendor_name": "Apex Hosting",
            "invoice_date": date.today().isoformat(),
            "due_date": due_date,
            "subtotal": 500.00,
            "tax_amount": 50.00,
            "total_amount": 550.00,
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    invoice_id = create_res.json()["id"]

    # 2. Record partial payment of 250.00
    pay1_res = client.post(
        "/api/payments/",
        json={
            "invoice_id": invoice_id,
            "amount": 250.00,
            "payment_date": date.today().isoformat(),
            "payment_method": "Credit Card",
            "reference": "TXN-001",
        },
        headers=headers,
    )
    assert pay1_res.status_code == 201
    pay1_data = pay1_res.json()
    assert pay1_data["amount"] == "250.00"

    # Verify invoice status is PARTIAL and balance is 300.00
    inv_res = client.get(f"/api/invoices/{invoice_id}", headers=headers)
    assert inv_res.status_code == 200
    inv_data = inv_res.json()
    assert inv_data["amount_paid"] == "250.00"
    assert inv_data["balance_due"] == "300.00"
    assert inv_data["payment_status"] == "PARTIAL"

    # Deadlines summary should show updated balance 300.00
    dl_res = client.get("/api/invoices/deadlines/summary", headers=headers)
    assert dl_res.status_code == 200
    in_7_days = dl_res.json()["due_within_7_days"]
    target = next((x for x in in_7_days if x["id"] == invoice_id), None)
    assert target is not None
    assert target["balance_due"] == "300.00"
    assert target["payment_status"] == "PARTIAL"

    # 3. Record remaining payment of 300.00
    pay2_res = client.post(
        "/api/payments/",
        json={
            "invoice_id": invoice_id,
            "amount": 300.00,
            "payment_date": date.today().isoformat(),
            "payment_method": "Bank Transfer",
            "reference": "TXN-002",
        },
        headers=headers,
    )
    assert pay2_res.status_code == 201

    # Verify invoice is now PAID and balance is 0.00
    inv_res2 = client.get(f"/api/invoices/{invoice_id}", headers=headers)
    inv_data2 = inv_res2.json()
    assert inv_data2["amount_paid"] == "550.00"
    assert inv_data2["balance_due"] == "0.00"
    assert inv_data2["payment_status"] == "PAID"

    # Deadlines summary should now place it in settled list
    dl_res2 = client.get("/api/invoices/deadlines/summary", headers=headers)
    settled = dl_res2.json()["settled"]
    settled_item = next((x for x in settled if x["id"] == invoice_id), None)
    assert settled_item is not None
    assert settled_item["payment_status"] == "PAID"
    assert settled_item["balance_due"] == "0.00"


def test_invoice_total_and_due_date_update_propagates(client):
    """Editing invoice total or due date propagates to balances, status, and deadlines."""
    token = get_auth_token(client, email="editor@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-EDIT-100",
            "vendor_name": "Global Logistics",
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=2)).isoformat(),
            "subtotal": 400.00,
            "tax_amount": 0.00,
            "total_amount": 400.00,
        },
        headers=headers,
    )
    invoice_id = create_res.json()["id"]

    # Record partial payment of 100.00
    client.post(
        "/api/payments/",
        json={
            "invoice_id": invoice_id,
            "amount": 100.00,
            "payment_date": date.today().isoformat(),
            "payment_method": "ACH",
        },
        headers=headers,
    )

    # Now edit invoice total from 400 to 600, and extend due date to 30 days
    new_due_date = (date.today() + timedelta(days=30)).isoformat()
    update_res = client.put(
        f"/api/invoices/{invoice_id}",
        json={
            "subtotal": 600.00,
            "tax_amount": 0.00,
            "total_amount": 600.00,
            "due_date": new_due_date,
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    updated_inv = update_res.json()
    assert updated_inv["total_amount"] == "600.00"
    assert updated_inv["amount_paid"] == "100.00"
    assert updated_inv["balance_due"] == "500.00"
    assert updated_inv["due_date"] == new_due_date

    # Deadlines summary should show it in due_later with balance 500.00
    dl_res = client.get("/api/invoices/deadlines/summary", headers=headers)
    due_later = dl_res.json()["due_later"]
    target = next((x for x in due_later if x["id"] == invoice_id), None)
    assert target is not None
    assert target["balance_due"] == "500.00"
    assert target["due_date"] == new_due_date


def test_cannot_reduce_invoice_total_below_paid_amount(client):
    """User cannot edit invoice total to be less than the already recorded payments."""
    token = get_auth_token(client, email="safeamount@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-FLOOR-01",
            "vendor_name": "Floor Test Inc",
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=5)).isoformat(),
            "subtotal": 500.00,
            "tax_amount": 0.00,
            "total_amount": 500.00,
        },
        headers=headers,
    )
    invoice_id = create_res.json()["id"]

    # Record 350.00 payment
    client.post(
        "/api/payments/",
        json={
            "invoice_id": invoice_id,
            "amount": 350.00,
            "payment_date": date.today().isoformat(),
            "payment_method": "Check",
        },
        headers=headers,
    )

    # Attempt to reduce invoice total to 200.00 (< 350.00)
    bad_edit = client.put(
        f"/api/invoices/{invoice_id}",
        json={
            "total_amount": 200.00,
            "subtotal": 200.00,
        },
        headers=headers,
    )
    assert bad_edit.status_code == 400
    assert "already been paid" in bad_edit.json()["detail"].lower()


def test_duplicate_invoice_prevention_case_and_whitespace(client):
    """Prevent duplicate invoices with case-insensitive and trimmed checking."""
    token = get_auth_token(client, email="dupcheck@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create first invoice
    res1 = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-2026-X99",
            "vendor_name": "Starlight Industries",
            "invoice_date": "2026-03-01",
            "due_date": "2026-03-15",
            "subtotal": 100.00,
            "tax_amount": 10.00,
            "total_amount": 110.00,
        },
        headers=headers,
    )
    assert res1.status_code == 201

    # 2. Attempt exact match
    res2 = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-2026-X99",
            "vendor_name": "Starlight Industries",
            "invoice_date": "2026-03-01",
            "total_amount": 110.00,
        },
        headers=headers,
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]

    # 3. Attempt lowercase with spaces
    res3 = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "  inv-2026-x99  ",
            "vendor_name": " starlight industries ",
            "invoice_date": "2026-03-01",
            "total_amount": 110.00,
        },
        headers=headers,
    )
    assert res3.status_code == 409
    assert "already exists" in res3.json()["detail"]


def test_review_status_flagging_and_payment_eligibility(client):
    """Invoices with arithmetic or date discrepancies are marked NEEDS_REVIEW,
    remain eligible for payment, and resolve to CONFIRMED when fixed."""
    token = get_auth_token(client, email="reviewstatus@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Discrepancy: subtotal (100) + tax (20) = 120, but total is 150
    res = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-DISC-01",
            "vendor_name": "Discrepancy Vendor",
            "invoice_date": "2026-03-01",
            "due_date": "2026-03-15",
            "subtotal": 100.00,
            "tax_amount": 20.00,
            "total_amount": 150.00,
        },
        headers=headers,
    )
    assert res.status_code == 201
    inv_data = res.json()
    assert inv_data["status"] == "NEEDS_REVIEW"

    invoice_id = inv_data["id"]

    # 2. Payment is still allowed against this invoice (payment eligible)
    pay_res = client.post(
        "/api/payments/",
        json={
            "invoice_id": invoice_id,
            "amount": 50.00,
            "payment_date": date.today().isoformat(),
            "payment_method": "Wire Transfer",
        },
        headers=headers,
    )
    assert pay_res.status_code == 201

    # Check updated balance
    inv_check = client.get(f"/api/invoices/{invoice_id}", headers=headers).json()
    assert inv_check["amount_paid"] == "50.00"
    assert inv_check["balance_due"] == "100.00"
    assert inv_check["status"] == "NEEDS_REVIEW"

    # 3. User edits invoice to correct arithmetic (subtotal 130 + tax 20 = 150)
    fix_res = client.put(
        f"/api/invoices/{invoice_id}",
        json={
            "subtotal": 130.00,
            "tax_amount": 20.00,
            "total_amount": 150.00,
        },
        headers=headers,
    )
    assert fix_res.status_code == 200
    assert fix_res.json()["status"] == "CONFIRMED"


def test_strict_multi_user_isolation(client):
    """Ensure invoices, payments, and deadlines are strictly isolated by tenant/user."""
    token_a = get_auth_token(client, email="tenant_a@example.com")
    token_b = get_auth_token(client, email="tenant_b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates an invoice
    res_a = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-ISOLATION-A",
            "vendor_name": "Tenant A Supplier",
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=7)).isoformat(),
            "subtotal": 1000.00,
            "tax_amount": 0.00,
            "total_amount": 1000.00,
        },
        headers=headers_a,
    )
    invoice_a_id = res_a.json()["id"]

    # User B checks invoices list: should be empty
    list_b = client.get("/api/invoices/", headers=headers_b)
    assert list_b.status_code == 200
    assert len(list_b.json()["items"]) == 0

    # User B checks deadlines summary: should not have invoice A
    dl_b = client.get("/api/invoices/deadlines/summary", headers=headers_b)
    assert dl_b.status_code == 200
    all_b = dl_b.json()["overdue"] + dl_b.json()["due_within_7_days"] + dl_b.json()["due_later"]
    assert len(all_b) == 0

    # User B attempts to get User A's invoice directly: 404
    get_b = client.get(f"/api/invoices/{invoice_a_id}", headers=headers_b)
    assert get_b.status_code == 404

    # User B attempts to record payment on User A's invoice: 404
    pay_b = client.post(
        "/api/payments/",
        json={
            "invoice_id": invoice_a_id,
            "amount": 100.00,
            "payment_date": date.today().isoformat(),
            "payment_method": "Cash",
        },
        headers=headers_b,
    )
    assert pay_b.status_code == 404

    # User B attempts to edit User A's invoice: 404
    edit_b = client.put(
        f"/api/invoices/{invoice_a_id}",
        json={"total_amount": 500.00},
        headers=headers_b,
    )
    assert edit_b.status_code == 404
