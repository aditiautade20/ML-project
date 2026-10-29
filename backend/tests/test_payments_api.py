from datetime import date, timedelta
from decimal import Decimal
import pytest


def get_auth_token(client, email="payuser@example.com", name="Payment User"):
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


def create_test_invoice(client, headers, invoice_number="INV-PAY-01", total="500.00", due_date=None):
    """Helper to create an invoice for testing payments."""
    payload = {
        "invoice_number": invoice_number,
        "vendor_name": "Test Vendor Corp",
        "invoice_date": str(date.today()),
        "due_date": due_date,
        "total_amount": total,
    }
    res = client.post("/api/invoices/", json=payload, headers=headers)
    assert res.status_code == 201
    return res.json()


def test_record_full_payment(client):
    token = get_auth_token(client, "fullpay@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    invoice = create_test_invoice(client, headers, "INV-FULL-01", "500.00")

    # Record full payment
    pay_res = client.post(
        "/api/payments/",
        json={
            "invoice_id": invoice["id"],
            "amount": "500.00",
            "payment_date": str(date.today()),
            "payment_method": "Credit Card",
            "reference": "TXN-12345",
            "notes": "Full settlement",
        },
        headers=headers,
    )
    assert pay_res.status_code == 201
    pay_data = pay_res.json()
    assert float(pay_data["amount"]) == 500.00
    assert pay_data["payment_method"] == "Credit Card"
    assert pay_data["reference"] == "TXN-12345"

    # Verify invoice status is now PAID and balance is 0.00
    inv_res = client.get(f"/api/invoices/{invoice['id']}", headers=headers)
    inv_data = inv_res.json()
    assert float(inv_data["total_paid"]) == 500.00
    assert float(inv_data["balance_due"]) == 0.00
    assert inv_data["payment_status"] == "PAID"


def test_record_multiple_partial_payments(client):
    token = get_auth_token(client, "partialpay@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    invoice = create_test_invoice(client, headers, "INV-PART-01", "1000.00")

    # Payment 1: $400.00
    client.post("/api/payments/", json={
        "invoice_id": invoice["id"], "amount": "400.00", "payment_date": str(date.today()), "payment_method": "ACH"
    }, headers=headers)

    inv1 = client.get(f"/api/invoices/{invoice['id']}", headers=headers).json()
    assert float(inv1["total_paid"]) == 400.00
    assert float(inv1["balance_due"]) == 600.00
    assert inv1["payment_status"] == "PARTIAL"

    # Payment 2: $350.00
    client.post("/api/payments/", json={
        "invoice_id": invoice["id"], "amount": "350.00", "payment_date": str(date.today()), "payment_method": "Bank Transfer"
    }, headers=headers)

    inv2 = client.get(f"/api/invoices/{invoice['id']}", headers=headers).json()
    assert float(inv2["total_paid"]) == 750.00
    assert float(inv2["balance_due"]) == 250.00
    assert inv2["payment_status"] == "PARTIAL"

    # Payment 3: $250.00 (Final settlement)
    client.post("/api/payments/", json={
        "invoice_id": invoice["id"], "amount": "250.00", "payment_date": str(date.today()), "payment_method": "Bank Transfer"
    }, headers=headers)

    inv3 = client.get(f"/api/invoices/{invoice['id']}", headers=headers).json()
    assert float(inv3["total_paid"]) == 1000.00
    assert float(inv3["balance_due"]) == 0.00
    assert inv3["payment_status"] == "PAID"


def test_overpayment_rejected(client):
    token = get_auth_token(client, "overpay@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    invoice = create_test_invoice(client, headers, "INV-OVER-01", "100.00")

    # Attempt to pay $150 on $100 invoice
    res_over = client.post(
        "/api/payments/",
        json={
            "invoice_id": invoice["id"],
            "amount": "150.00",
            "payment_date": str(date.today()),
        },
        headers=headers,
    )
    assert res_over.status_code == 400
    assert "exceeds the remaining balance" in res_over.json()["detail"]

    # Record partial $60.00 (succeeds)
    client.post("/api/payments/", json={
        "invoice_id": invoice["id"], "amount": "60.00", "payment_date": str(date.today())
    }, headers=headers)

    # Attempt second payment of $50.00 (remaining balance is $40.00)
    res_over2 = client.post("/api/payments/", json={
        "invoice_id": invoice["id"], "amount": "50.00", "payment_date": str(date.today())
    }, headers=headers)
    assert res_over2.status_code == 400
    assert "exceeds the remaining balance" in res_over2.json()["detail"]


def test_payment_status_transitions_and_overdue(client):
    token = get_auth_token(client, "statustrans@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()
    past_due = str(today - timedelta(days=5))

    # Overdue invoice (past due date, unpaid)
    inv_overdue = create_test_invoice(client, headers, "INV-OD-01", "300.00", due_date=past_due)
    assert inv_overdue["payment_status"] == "OVERDUE"

    # Partial payment on overdue invoice -> still OVERDUE (unpaid balance past due date)
    client.post("/api/payments/", json={
        "invoice_id": inv_overdue["id"], "amount": "100.00", "payment_date": str(today)
    }, headers=headers)
    inv_od_partial = client.get(f"/api/invoices/{inv_overdue['id']}", headers=headers).json()
    assert inv_od_partial["payment_status"] == "OVERDUE"
    assert float(inv_od_partial["balance_due"]) == 200.00

    # Full payment on overdue invoice -> changes to PAID
    client.post("/api/payments/", json={
        "invoice_id": inv_overdue["id"], "amount": "200.00", "payment_date": str(today)
    }, headers=headers)
    inv_od_paid = client.get(f"/api/invoices/{inv_overdue['id']}", headers=headers).json()
    assert inv_od_paid["payment_status"] == "PAID"
    assert float(inv_od_paid["balance_due"]) == 0.00

    # Invoice with NO due date -> UNPAID, never marked OVERDUE
    inv_nodue = create_test_invoice(client, headers, "INV-NODUE-01", "200.00", due_date=None)
    assert inv_nodue["payment_status"] == "UNPAID"


def test_deadlines_summary_endpoint(client):
    token = get_auth_token(client, "deadlines@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()

    # 1. Overdue: 3 days ago ($150.00)
    create_test_invoice(client, headers, "DL-OD-1", "150.00", due_date=str(today - timedelta(days=3)))

    # 2. Due Today ($200.00)
    create_test_invoice(client, headers, "DL-TODAY-1", "200.00", due_date=str(today))

    # 3. Due within 7 days: 4 days from now ($300.00)
    create_test_invoice(client, headers, "DL-SOON-1", "300.00", due_date=str(today + timedelta(days=4)))

    # 4. Due later: 25 days from now ($400.00)
    create_test_invoice(client, headers, "DL-LATER-1", "400.00", due_date=str(today + timedelta(days=25)))

    # 5. No due date ($100.00, should be in due_later, never overdue)
    create_test_invoice(client, headers, "DL-NODATE-1", "100.00", due_date=None)

    # Fetch summary
    res = client.get("/api/invoices/deadlines/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["overdue_count"] == 1
    assert float(data["overdue_total"]) == 150.00
    assert data["due_today_count"] == 1
    assert float(data["due_today_total"]) == 200.00
    assert data["due_within_7_days_count"] == 1
    assert float(data["due_within_7_days_total"]) == 300.00
    assert float(data["total_outstanding_amount"]) == 1150.00


def test_edit_and_delete_payment(client):
    token = get_auth_token(client, "editpay@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    invoice = create_test_invoice(client, headers, "INV-EDIT-P", "500.00")

    # Record payment $200.00
    p_res = client.post("/api/payments/", json={
        "invoice_id": invoice["id"], "amount": "200.00", "payment_date": str(date.today()), "reference": "REF-OLD"
    }, headers=headers)
    payment_id = p_res.json()["id"]

    # Edit payment to $300.00 and update reference
    edit_res = client.put(f"/api/payments/{payment_id}", json={
        "amount": "300.00", "reference": "REF-UPDATED"
    }, headers=headers)
    assert edit_res.status_code == 200
    assert float(edit_res.json()["amount"]) == 300.00
    assert edit_res.json()["reference"] == "REF-UPDATED"

    # Attempting to edit to $600.00 (exceeds invoice total 500) -> 400
    over_res = client.put(f"/api/payments/{payment_id}", json={"amount": "600.00"}, headers=headers)
    assert over_res.status_code == 400

    # Delete payment
    del_res = client.delete(f"/api/payments/{payment_id}", headers=headers)
    assert del_res.status_code == 204

    # Balance returns to full $500.00
    inv = client.get(f"/api/invoices/{invoice['id']}", headers=headers).json()
    assert float(inv["total_paid"]) == 0.00
    assert float(inv["balance_due"]) == 500.00
    assert inv["payment_status"] == "UNPAID"


def test_payments_user_isolation(client):
    token_a = get_auth_token(client, "user_pay_a@example.com")
    token_b = get_auth_token(client, "user_pay_b@example.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates invoice and payment
    invoice_a = create_test_invoice(client, headers_a, "INV-ISOL-A", "400.00")
    pay_a = client.post("/api/payments/", json={
        "invoice_id": invoice_a["id"], "amount": "200.00", "payment_date": str(date.today())
    }, headers=headers_a).json()
    payment_a_id = pay_a["id"]

    # 1. User B cannot record payment on User A's invoice -> 404
    hack_pay = client.post("/api/payments/", json={
        "invoice_id": invoice_a["id"], "amount": "100.00", "payment_date": str(date.today())
    }, headers=headers_b)
    assert hack_pay.status_code == 404

    # 2. User B cannot GET User A's payment -> 404
    get_hack = client.get(f"/api/payments/{payment_a_id}", headers=headers_b)
    assert get_hack.status_code == 404

    # 3. User B cannot PUT User A's payment -> 404
    put_hack = client.put(f"/api/payments/{payment_a_id}", json={"amount": "50.00"}, headers=headers_b)
    assert put_hack.status_code == 404

    # 4. User B cannot DELETE User A's payment -> 404
    del_hack = client.delete(f"/api/payments/{payment_a_id}", headers=headers_b)
    assert del_hack.status_code == 404

    # 5. User B's payment list returns 0 records
    list_b = client.get("/api/payments/", headers=headers_b).json()
    assert list_b["total"] == 0


def test_invalid_payment_amounts(client):
    token = get_auth_token(client, "invalidpay@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    invoice = create_test_invoice(client, headers, "INV-INVALID-01", "200.00")

    # Negative amount -> 400 or 422
    res_neg = client.post(
        "/api/payments/",
        json={
            "invoice_id": invoice["id"],
            "amount": "-50.00",
            "payment_date": str(date.today()),
        },
        headers=headers,
    )
    assert res_neg.status_code in [400, 422]

    # Zero amount -> 400 or 422
    res_zero = client.post(
        "/api/payments/",
        json={
            "invoice_id": invoice["id"],
            "amount": "0.00",
            "payment_date": str(date.today()),
        },
        headers=headers,
    )
    assert res_zero.status_code in [400, 422]


def test_duplicate_payment_prevention(client):
    token = get_auth_token(client, "duppay@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    invoice = create_test_invoice(client, headers, "INV-DUP-01", "500.00")

    payload = {
        "invoice_id": invoice["id"],
        "amount": "100.00",
        "payment_date": str(date.today()),
        "payment_method": "Credit Card",
        "reference": "DUP-REF-123",
    }

    # First attempt -> succeeds (201)
    res1 = client.post("/api/payments/", json=payload, headers=headers)
    assert res1.status_code == 201

    # Second identical attempt -> 409 Conflict
    res2 = client.post("/api/payments/", json=payload, headers=headers)
    assert res2.status_code == 409
    assert "duplicate payment" in res2.json()["detail"].lower()


def test_date_boundary_and_due_soon_status(client):
    token = get_auth_token(client, "boundaries@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()

    # Invoice due today: MUST be DUE_SOON, NOT OVERDUE
    inv_today = create_test_invoice(client, headers, "INV-BOUND-TODAY", "100.00", due_date=str(today))
    assert inv_today["payment_status"] == "DUE_SOON"

    # Invoice due yesterday: MUST be OVERDUE
    yesterday = str(today - timedelta(days=1))
    inv_yesterday = create_test_invoice(client, headers, "INV-BOUND-YEST", "100.00", due_date=yesterday)
    assert inv_yesterday["payment_status"] == "OVERDUE"

    # Invoice due in 5 days: MUST be DUE_SOON
    in_5_days = str(today + timedelta(days=5))
    inv_5 = create_test_invoice(client, headers, "INV-BOUND-5D", "100.00", due_date=in_5_days)
    assert inv_5["payment_status"] == "DUE_SOON"

    # Invoice due in 15 days: MUST be UNPAID (not due soon)
    in_15_days = str(today + timedelta(days=15))
    inv_15 = create_test_invoice(client, headers, "INV-BOUND-15D", "100.00", due_date=in_15_days)
    assert inv_15["payment_status"] == "UNPAID"


def test_invoice_filters_status_vendor_dates(client):
    token = get_auth_token(client, "filters@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()

    # Create distinct invoices:
    # 1. Vendor Alpha, Due Soon
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "FILT-01",
            "vendor_name": "Alpha Supplies",
            "invoice_date": str(today),
            "due_date": str(today + timedelta(days=3)),
            "total_amount": "200.00",
        },
        headers=headers,
    )

    # 2. Vendor Beta, Overdue
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "FILT-02",
            "vendor_name": "Beta Corp",
            "invoice_date": str(today - timedelta(days=20)),
            "due_date": str(today - timedelta(days=5)),
            "total_amount": "400.00",
        },
        headers=headers,
    )

    # 3. Vendor Gamma, Paid
    res3 = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "FILT-03",
            "vendor_name": "Gamma Logistics",
            "invoice_date": str(today - timedelta(days=10)),
            "due_date": str(today + timedelta(days=10)),
            "total_amount": "300.00",
        },
        headers=headers,
    ).json()
    # Fully pay FILT-03
    client.post(
        "/api/payments/",
        json={
            "invoice_id": res3["id"],
            "amount": "300.00",
            "payment_date": str(today),
        },
        headers=headers,
    )

    # Test filter by payment_status=DUE_SOON
    res_due_soon = client.get("/api/invoices/?payment_status=DUE_SOON", headers=headers).json()
    assert res_due_soon["total"] == 1
    assert res_due_soon["items"][0]["invoice_number"] == "FILT-01"

    # Test filter by payment_status=OVERDUE
    res_overdue = client.get("/api/invoices/?payment_status=OVERDUE", headers=headers).json()
    assert res_overdue["total"] == 1
    assert res_overdue["items"][0]["invoice_number"] == "FILT-02"

    # Test filter by payment_status=PAID
    res_paid = client.get("/api/invoices/?payment_status=PAID", headers=headers).json()
    assert res_paid["total"] == 1
    assert res_paid["items"][0]["invoice_number"] == "FILT-03"

    # Test filter by vendor
    res_vendor = client.get("/api/invoices/?vendor=Beta Corp", headers=headers).json()
    assert res_vendor["total"] == 1
    assert res_vendor["items"][0]["invoice_number"] == "FILT-02"

    # Test filter by due_date range
    range_from = str(today + timedelta(days=1))
    range_to = str(today + timedelta(days=5))
    res_range = client.get(f"/api/invoices/?due_date_from={range_from}&due_date_to={range_to}", headers=headers).json()
    assert res_range["total"] == 1
    assert res_range["items"][0]["invoice_number"] == "FILT-01"


def test_dashboard_multi_currency_handling(client):
    token = get_auth_token(client, "multicurrency@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()

    # Invoice 1: USD 1000
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "MC-USD-01",
            "vendor_name": "US Vendor",
            "invoice_date": str(today),
            "due_date": str(today + timedelta(days=10)),
            "total_amount": "1000.00",
            "currency": "USD",
        },
        headers=headers,
    )

    # Invoice 2: EUR 500
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "MC-EUR-01",
            "vendor_name": "Euro Vendor",
            "invoice_date": str(today),
            "due_date": str(today + timedelta(days=10)),
            "total_amount": "500.00",
            "currency": "EUR",
        },
        headers=headers,
    )

    dash = client.get("/api/reports/dashboard", headers=headers).json()
    assert dash["total_invoices_count"] == 2
    assert dash["has_multiple_currencies"] is True
    assert "USD" in dash["by_currency"]
    assert "EUR" in dash["by_currency"]
    assert float(dash["by_currency"]["USD"]["total_invoiced_amount"]) == 1000.00
    assert float(dash["by_currency"]["EUR"]["total_invoiced_amount"]) == 500.00

