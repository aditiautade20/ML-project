import io
from datetime import date
from decimal import Decimal
import pytest


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


def get_auth_token(client, email="user@example.com", name="Test User"):
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


def test_upload_valid_pdf_invoice(client):
    token = get_auth_token(client, "uploader@example.com")
    pdf_bytes = make_pdf_bytes([
        "From: Cloudflare Inc",
        "Invoice Number: CF-8899",
        "Invoice Date: 2026-03-01",
        "Due Date: 2026-03-15",
        "Total: $200.00"
    ])

    response = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "file_token" in data
    assert data["file_name"] == "invoice.pdf"
    assert data["file_content_type"] == "application/pdf"
    assert data["candidate_fields"]["invoice_number"] == "CF-8899"
    assert "Cloudflare" in data["candidate_fields"]["vendor_name"]
    assert float(data["candidate_fields"]["total_amount"]) == 200.00


def test_upload_unsupported_and_empty_files(client):
    token = get_auth_token(client, "validator@example.com")

    # Unsupported format (.exe)
    res_exe = client.post(
        "/api/invoices/upload",
        files={"file": ("malicious.exe", io.BytesIO(b"binary data"), "application/x-msdownload")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_exe.status_code == 400
    assert "Unsupported file format" in res_exe.json()["detail"]

    # Empty file (0 bytes)
    res_empty = client.post(
        "/api/invoices/upload",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_empty.status_code == 400
    assert "empty" in res_empty.json()["detail"]


def test_review_and_save_workflow(client):
    token = get_auth_token(client, "reviewer@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: Upload invoice
    pdf_bytes = make_pdf_bytes(["Vendor: DigitalOcean", "Invoice Number: DO-1001", "Total: $50.00"])
    upload_res = client.post(
        "/api/invoices/upload",
        files={"file": ("digitalocean.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers,
    )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    file_token = upload_data["file_token"]

    # Step 2 & 3: User reviews candidate fields, corrects them, and confirms save
    save_payload = {
        "invoice_number": upload_data["candidate_fields"]["invoice_number"] or "DO-1001",
        "vendor_name": "DigitalOcean LLC",
        "invoice_date": "2026-04-01",
        "due_date": "2026-04-30",
        "subtotal": "45.00",
        "tax_amount": "5.00",
        "total_amount": "50.00",
        "currency": "USD",
        "file_token": file_token,
        "notes": "Monthly cloud infrastructure",
    }

    create_res = client.post("/api/invoices/", json=save_payload, headers=headers)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["invoice_number"] == "DO-1001"
    assert created_data["vendor_name"] == "DigitalOcean LLC"
    assert float(created_data["total_amount"]) == 50.00
    assert created_data["status"] == "CONFIRMED"
    assert created_data["has_file"] is True

    # Step 4: Verify it appears in the invoice list
    list_res = client.get("/api/invoices/", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 1
    assert list_data["items"][0]["invoice_number"] == "DO-1001"


def test_duplicate_invoice_number_rejection(client):
    token = get_auth_token(client, "dupecheck@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    invoice_data = {
        "invoice_number": "INV-DUPE-01",
        "vendor_name": "Stripe Payments",
        "invoice_date": "2026-05-01",
        "total_amount": 100.00,
    }

    # First save succeeds
    res1 = client.post("/api/invoices/", json=invoice_data, headers=headers)
    assert res1.status_code == 201

    # Second save with same number & vendor is rejected with 409 Conflict
    res2 = client.post("/api/invoices/", json=invoice_data, headers=headers)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_list_invoices_search_and_filter(client):
    token = get_auth_token(client, "filteruser@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create 3 invoices
    client.post("/api/invoices/", json={
        "invoice_number": "AWS-001", "vendor_name": "Amazon Web Services", "invoice_date": "2026-01-01", "total_amount": 500.00
    }, headers=headers)
    client.post("/api/invoices/", json={
        "invoice_number": "GCP-002", "vendor_name": "Google Cloud", "invoice_date": "2026-02-01", "total_amount": 250.00
    }, headers=headers)
    client.post("/api/invoices/", json={
        "invoice_number": "AWS-003", "vendor_name": "Amazon Web Services", "invoice_date": "2026-03-01", "total_amount": 750.00
    }, headers=headers)

    # Search for "GCP"
    search_res = client.get("/api/invoices/?search=GCP", headers=headers)
    assert search_res.status_code == 200
    assert search_res.json()["total"] == 1
    assert search_res.json()["items"][0]["invoice_number"] == "GCP-002"

    # Filter by vendor "Amazon Web Services"
    vendor_res = client.get("/api/invoices/?vendor=Amazon%20Web%20Services", headers=headers)
    assert vendor_res.status_code == 200
    assert vendor_res.json()["total"] == 2

    # Sort by total_amount ascending
    sort_res = client.get("/api/invoices/?sort_by=total_amount&sort_order=asc", headers=headers)
    assert sort_res.status_code == 200
    items = sort_res.json()["items"]
    assert float(items[0]["total_amount"]) == 250.00
    assert float(items[-1]["total_amount"]) == 750.00


def test_get_and_update_invoice(client):
    token = get_auth_token(client, "edituser@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/invoices/", json={
        "invoice_number": "EDIT-01",
        "vendor_name": "Old Vendor Name",
        "invoice_date": "2026-06-01",
        "total_amount": 120.00,
    }, headers=headers)
    inv_id = create_res.json()["id"]

    # Get by ID
    get_res = client.get(f"/api/invoices/{inv_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["vendor_name"] == "Old Vendor Name"

    # Update vendor and amount
    update_res = client.put(f"/api/invoices/{inv_id}", json={
        "vendor_name": "New Updated Vendor",
        "total_amount": 150.00,
    }, headers=headers)
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["vendor_name"] == "New Updated Vendor"
    assert float(updated_data["total_amount"]) == 150.00


def test_delete_invoice(client):
    token = get_auth_token(client, "deluser@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/invoices/", json={
        "invoice_number": "DEL-01",
        "vendor_name": "Delete Me Inc",
        "invoice_date": "2026-07-01",
        "total_amount": 75.00,
    }, headers=headers)
    inv_id = create_res.json()["id"]

    # Delete invoice
    del_res = client.delete(f"/api/invoices/{inv_id}", headers=headers)
    assert del_res.status_code == 204

    # Subsequent GET returns 404
    get_res = client.get(f"/api/invoices/{inv_id}", headers=headers)
    assert get_res.status_code == 404


def test_strict_user_isolation(client):
    token_a = get_auth_token(client, "user_a@example.com")
    token_b = get_auth_token(client, "user_b@example.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates an invoice
    create_res = client.post("/api/invoices/", json={
        "invoice_number": "PRIVATE-A-01",
        "vendor_name": "User A Private Vendor",
        "invoice_date": "2026-08-01",
        "total_amount": 999.00,
    }, headers=headers_a)
    invoice_a_id = create_res.json()["id"]

    # 1. User B lists invoices -> should NOT see User A's invoice
    list_b = client.get("/api/invoices/", headers=headers_b)
    assert list_b.status_code == 200
    assert list_b.json()["total"] == 0

    # 2. User B tries to GET User A's invoice directly -> 404
    get_b = client.get(f"/api/invoices/{invoice_a_id}", headers=headers_b)
    assert get_b.status_code == 404

    # 3. User B tries to UPDATE User A's invoice -> 404
    put_b = client.put(f"/api/invoices/{invoice_a_id}", json={"vendor_name": "Hacked"}, headers=headers_b)
    assert put_b.status_code == 404

    # 4. User B tries to DELETE User A's invoice -> 404
    del_b = client.delete(f"/api/invoices/{invoice_a_id}", headers=headers_b)
    assert del_b.status_code == 404

    # Confirm User A's invoice is still intact
    get_a = client.get(f"/api/invoices/{invoice_a_id}", headers=headers_a)
    assert get_a.status_code == 200
    assert get_a.json()["vendor_name"] == "User A Private Vendor"


def test_invalid_invoice_amounts_and_dates(client):
    token = get_auth_token(client, "invalidfields@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Zero amount (total_amount must be > 0)
    res_zero = client.post("/api/invoices/", json={
        "invoice_number": "ZERO-01",
        "vendor_name": "Vendor",
        "invoice_date": "2026-01-01",
        "total_amount": 0.00,
    }, headers=headers)
    assert res_zero.status_code == 422

    # Negative amount
    res_neg = client.post("/api/invoices/", json={
        "invoice_number": "NEG-01",
        "vendor_name": "Vendor",
        "invoice_date": "2026-01-01",
        "total_amount": -50.00,
    }, headers=headers)
    assert res_neg.status_code == 422
