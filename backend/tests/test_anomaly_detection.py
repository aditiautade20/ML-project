import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.models.invoice import Invoice
from app.services.anomaly_service import (
    extract_invoice_features,
    assess_user_invoices,
    MIN_INVOICES_FOR_ANOMALY_MODEL,
)


def get_auth_token(client, email="anomuser@example.com", name="Anomaly User"):
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


def test_insufficient_data_returns_clear_message(client):
    """
    When a user has fewer than 5 invoices, the assessment must return
    an INSUFFICIENT_DATA status explaining that more data is required,
    without fitting on noise.
    """
    token = get_auth_token(client, "insuff@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Add only 2 invoices
    for i in range(1, 3):
        create_res = client.post(
            "/api/invoices/",
            json={
                "invoice_number": f"INV-INSUFF-{i}",
                "vendor_name": "Acme Supplies",
                "invoice_date": str(date.today()),
                "total_amount": 150.00,
                "currency": "USD",
            },
            headers=headers,
        )
        assert create_res.status_code == 201

    # Run assessment
    assess_res = client.post("/api/anomalies/assess", headers=headers)
    assert assess_res.status_code == 200
    data = assess_res.json()

    assert data["status"] == "INSUFFICIENT_DATA"
    assert data["total_invoices"] == 2
    assert data["min_required"] == MIN_INVOICES_FOR_ANOMALY_MODEL
    assert "At least 5 saved invoices are required" in data["message"]
    assert len(data["items"]) == 0

    # GET /api/anomalies/ should also reflect insufficient data
    get_res = client.get("/api/anomalies/", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "INSUFFICIENT_DATA"


def test_feature_extraction_safe_with_missing_fields(db_session):
    """
    Verifies that feature extraction safely handles null subtotal, null tax,
    and null due_date without inserting zero or crashing.
    """
    invoices = [
        Invoice(
            id=1,
            user_id=1,
            invoice_number="INV-001",
            vendor_name="Vendor A",
            invoice_date=date(2026, 1, 1),
            due_date=None,  # missing due date
            subtotal=None,  # missing subtotal
            tax_amount=None,  # missing tax
            total_amount=Decimal("100.00"),
            currency="USD",
        ),
        Invoice(
            id=2,
            user_id=1,
            invoice_number="INV-002",
            vendor_name="Vendor A",
            invoice_date=date(2026, 1, 5),
            due_date=date(2026, 1, 25),
            subtotal=Decimal("180.00"),
            tax_amount=Decimal("20.00"),
            total_amount=Decimal("200.00"),
            currency="USD",
        ),
    ]

    X, factor_dicts, context_meta = extract_invoice_features(invoices)

    assert X.shape == (2, 13)
    # Check no NaN values anywhere in matrix
    import numpy as np
    assert not np.isnan(X).any()

    # Invoice 1 missing flags
    assert factor_dicts[0]["has_tax"] is False
    assert factor_dicts[0]["has_due_date"] is False
    assert factor_dicts[0]["has_subtotal"] is False

    # Invoice 2 present flags
    assert factor_dicts[1]["has_tax"] is True
    assert factor_dicts[1]["has_due_date"] is True
    assert factor_dicts[1]["has_subtotal"] is True


def test_model_fitting_and_outlier_prediction(client):
    """
    Fits Isolation Forest with 6 normal invoices ($100-$300) and 1 distinct
    outlier ($12,500). Verifies that the outlier is flagged as POTENTIALLY_UNUSUAL
    with an explanatory note.
    """
    token = get_auth_token(client, "outlier@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create 6 regular invoices for "Standard Vendor"
    for i in range(1, 7):
        client.post(
            "/api/invoices/",
            json={
                "invoice_number": f"INV-NORM-{i:03d}",
                "vendor_name": "Standard Vendor",
                "invoice_date": str(date.today() - timedelta(days=i * 5)),
                "due_date": str(date.today() + timedelta(days=30)),
                "subtotal": 180.00 + (i * 10),
                "tax_amount": 20.00,
                "total_amount": 200.00 + (i * 10),
                "currency": "USD",
            },
            headers=headers,
        )

    # Create 1 massive outlier invoice ($12,500)
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-OUTLIER-999",
            "vendor_name": "Standard Vendor",
            "invoice_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=30)),
            "subtotal": 11500.00,
            "tax_amount": 1000.00,
            "total_amount": 12500.00,
            "currency": "USD",
        },
        headers=headers,
    )

    # Trigger ML Assessment
    assess_res = client.post("/api/anomalies/assess", headers=headers)
    assert assess_res.status_code == 200
    data = assess_res.json()

    assert data["status"] == "COMPLETED"
    assert data["total_invoices"] == 7
    assert data["assessed_count"] == 7
    assert data["anomalous_count"] >= 1

    # Find the outlier item
    outlier_item = next((it for it in data["items"] if it["invoice_number"] == "INV-OUTLIER-999"), None)
    assert outlier_item is not None
    assert outlier_item["is_anomaly"] is True
    assert outlier_item["status"] == "POTENTIALLY_UNUSUAL"
    assert "higher" in outlier_item["explanation"].lower() or "median" in outlier_item["explanation"].lower()


def test_anomaly_persistence_and_filtering(client):
    """
    Tests that assessment records are stored in the database, retrievable via GET,
    and filterable by status and search terms.
    """
    token = get_auth_token(client, "persist@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Add 5 normal invoices
    for i in range(1, 6):
        client.post(
            "/api/invoices/",
            json={
                "invoice_number": f"INV-FILTER-{i}",
                "vendor_name": f"Regular Vendor {i}",
                "invoice_date": str(date.today()),
                "total_amount": 150.00,
                "currency": "USD",
            },
            headers=headers,
        )

    # Assess
    client.post("/api/anomalies/assess", headers=headers)

    # Fetch list via GET /api/anomalies/
    list_res = client.get("/api/anomalies/", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["status"] == "COMPLETED"
    assert len(list_data["items"]) == 5

    # Filter with search term
    search_res = client.get("/api/anomalies/?search=INV-FILTER-1", headers=headers)
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data["items"]) == 1
    assert search_data["items"][0]["invoice_number"] == "INV-FILTER-1"

    # Get single invoice anomaly
    inv_id = search_data["items"][0]["invoice_id"]
    single_res = client.get(f"/api/anomalies/invoice/{inv_id}", headers=headers)
    assert single_res.status_code == 200
    assert single_res.json()["invoice_id"] == inv_id


def test_anomaly_user_isolation(client):
    """
    Confirms that User A's invoices and anomaly evaluations are strictly isolated
    from User B.
    """
    user_a_token = get_auth_token(client, "user_a_anom@example.com", "User A")
    user_a_headers = {"Authorization": f"Bearer {user_a_token}"}

    user_b_token = get_auth_token(client, "user_b_anom@example.com", "User B")
    user_b_headers = {"Authorization": f"Bearer {user_b_token}"}

    # User A creates 6 invoices and assesses
    for i in range(1, 7):
        client.post(
            "/api/invoices/",
            json={
                "invoice_number": f"INV-USER-A-{i}",
                "vendor_name": "Vendor Alpha",
                "invoice_date": str(date.today()),
                "total_amount": 100.00 * i,
                "currency": "USD",
            },
            headers=user_a_headers,
        )
    a_assess = client.post("/api/anomalies/assess", headers=user_a_headers)
    assert a_assess.status_code == 200
    assert a_assess.json()["status"] == "COMPLETED"

    # User B has 0 invoices. Checking User B's assessment should show 0 invoices and INSUFFICIENT_DATA
    b_get = client.get("/api/anomalies/", headers=user_b_headers)
    assert b_get.status_code == 200
    assert b_get.json()["total_invoices"] == 0
    assert b_get.json()["status"] == "INSUFFICIENT_DATA"
    assert len(b_get.json()["items"]) == 0


def test_ml_handles_identical_amounts_without_crashing(client):
    """
    Even when all invoices have identical amounts and features (zero variance),
    RobustScaler and IsolationForest must complete gracefully without divide-by-zero
    or internal crashes.
    """
    token = get_auth_token(client, "identical@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(1, 6):
        client.post(
            "/api/invoices/",
            json={
                "invoice_number": f"INV-IDENTICAL-{i}",
                "vendor_name": "Flat Rate Vendor",
                "invoice_date": str(date.today()),
                "total_amount": 100.00,
                "currency": "USD",
            },
            headers=headers,
        )

    res = client.post("/api/anomalies/assess", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "COMPLETED"
    assert res.json()["total_invoices"] == 5


def test_duplicate_invoice_number_anomaly_flagging(client):
    """
    Invoices sharing a duplicate invoice number must be detected and flagged
    with HIGH risk and clear explanation citing the duplicate.
    """
    token = get_auth_token(client, "dup_anom@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()

    # 4 standard invoices
    for i in range(1, 5):
        client.post(
            "/api/invoices/",
            json={
                "invoice_number": f"INV-DUP-TEST-{i}",
                "vendor_name": "Supplier X",
                "invoice_date": str(today - timedelta(days=i)),
                "total_amount": 200.00,
                "currency": "USD",
            },
            headers=headers,
        )

    # 2 invoices with the SAME invoice number 'INV-REPEAT-999' from different vendors
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-REPEAT-999",
            "vendor_name": "Supplier X",
            "invoice_date": str(today - timedelta(days=10)),
            "total_amount": 200.00,
            "currency": "USD",
        },
        headers=headers,
    )
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-REPEAT-999",
            "vendor_name": "Supplier Y",
            "invoice_date": str(today),
            "total_amount": 200.00,
            "currency": "USD",
        },
        headers=headers,
    )

    res = client.post("/api/anomalies/assess", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"

    dup_items = [it for it in data["items"] if it["invoice_number"] == "INV-REPEAT-999"]
    assert len(dup_items) == 2
    for it in dup_items:
        assert it["is_anomaly"] is True
        assert it["risk_level"] == "HIGH"
        assert "duplicate" in it["explanation"].lower()


def test_multi_currency_anomaly_handling(client):
    """
    Ensures different currency scales (e.g. INR vs USD) do not cause false anomaly
    flags. Invoices in INR should be evaluated relative to INR distributions, not USD.
    """
    token = get_auth_token(client, "multicurranom@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()

    # 4 USD invoices ($200.00 each)
    for i in range(1, 5):
        client.post(
            "/api/invoices/",
            json={
                "invoice_number": f"INV-USD-{i}",
                "vendor_name": "US Vendor",
                "invoice_date": str(today - timedelta(days=i)),
                "total_amount": 200.00,
                "currency": "USD",
            },
            headers=headers,
        )

    # 4 INR invoices (₹15,000 INR each) - typical INR rate
    for i in range(1, 5):
        client.post(
            "/api/invoices/",
            json={
                "invoice_number": f"INV-INR-{i}",
                "vendor_name": "India Tech Corp",
                "invoice_date": str(today - timedelta(days=i * 2)),
                "total_amount": 15000.00,
                "currency": "INR",
            },
            headers=headers,
        )

    # 1 Extreme INR Outlier (₹1,500,000 INR, 100x higher than typical INR invoice)
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-INR-OUTLIER",
            "vendor_name": "India Tech Corp",
            "invoice_date": str(today),
            "total_amount": 1500000.00,
            "currency": "INR",
        },
        headers=headers,
    )

    res = client.post("/api/anomalies/assess", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"

    # Standard INR invoices (₹15,000) should NOT be flagged as anomalies
    norm_inr = [it for it in data["items"] if it["invoice_number"].startswith("INV-INR-") and it["invoice_number"] != "INV-INR-OUTLIER"]
    assert len(norm_inr) == 4
    for it in norm_inr:
        assert it["is_anomaly"] is False

    # The actual outlier (₹1,500,000) MUST be flagged
    outlier_inr = next((it for it in data["items"] if it["invoice_number"] == "INV-INR-OUTLIER"), None)
    assert outlier_inr is not None
    assert outlier_inr["is_anomaly"] is True
    assert "higher" in outlier_inr["explanation"].lower() or "median" in outlier_inr["explanation"].lower()


def test_anomaly_audit_review_workflow(client):
    """
    Confirms the manual audit review process:
    - User marks an anomaly as reviewed with notes.
    - Anomaly status updates to reviewed with timestamp.
    - CRITICAL: Underneath invoice totals and payment status remain 100% unaltered.
    - Subsequent assessments preserve the user's audit review.
    """
    token = get_auth_token(client, "reviewflow@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()

    # Create 5 normal invoices and 1 outlier
    for i in range(1, 6):
        client.post(
            "/api/invoices/",
            json={
                "invoice_number": f"INV-REV-NORM-{i}",
                "vendor_name": "Hardware Depot",
                "invoice_date": str(today - timedelta(days=i)),
                "total_amount": 100.00,
                "currency": "USD",
            },
            headers=headers,
        )

    outlier_res = client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-REV-OUTLIER",
            "vendor_name": "Hardware Depot",
            "invoice_date": str(today),
            "total_amount": 9500.00,
            "currency": "USD",
        },
        headers=headers,
    ).json()

    # Assess
    assess_res = client.post("/api/anomalies/assess", headers=headers).json()
    assert assess_res["status"] == "COMPLETED"

    outlier_item = next(it for it in assess_res["items"] if it["invoice_number"] == "INV-REV-OUTLIER")
    assert outlier_item["is_anomaly"] is True
    assert outlier_item["is_reviewed"] is False

    # 1. Review the anomaly with notes
    rev_res = client.patch(
        f"/api/anomalies/{outlier_item['id']}/review",
        json={"review_notes": "Approved annual server infrastructure upgrade."},
        headers=headers,
    )
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["is_reviewed"] is True
    assert rev_data["review_notes"] == "Approved annual server infrastructure upgrade."
    assert rev_data["reviewed_at"] is not None

    # 2. Verify underlying invoice was NOT altered
    inv_check = client.get(f"/api/invoices/{outlier_res['id']}", headers=headers).json()
    assert float(inv_check["total_amount"]) == 9500.00
    assert inv_check["payment_status"] == "UNPAID"
    assert float(inv_check["total_paid"]) == 0.00

    # 3. GET /api/anomalies/?status=REVIEWED returns the reviewed invoice
    rev_list = client.get("/api/anomalies/?status=REVIEWED", headers=headers).json()
    assert rev_list["reviewed_count"] == 1
    assert any(it["invoice_number"] == "INV-REV-OUTLIER" for it in rev_list["items"])

    # 4. Re-running assess preserves the reviewed status
    reassess_res = client.post("/api/anomalies/assess", headers=headers).json()
    re_item = next(it for it in reassess_res["items"] if it["invoice_number"] == "INV-REV-OUTLIER")
    assert re_item["is_reviewed"] is True
    assert re_item["review_notes"] == "Approved annual server infrastructure upgrade."


def test_dashboard_agrees_with_anomaly_assessments(client):
    """
    Confirms that the dashboard's anomalous_invoices_count exactly matches
    the count of anomalous invoices assessed in the database.
    """
    token = get_auth_token(client, "dashagree@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()

    # 5 normal invoices
    for i in range(1, 6):
        client.post(
            "/api/invoices/",
            json={
                "invoice_number": f"INV-DASH-NORM-{i}",
                "vendor_name": "Office Store",
                "invoice_date": str(today - timedelta(days=i)),
                "total_amount": 100.00,
                "currency": "USD",
            },
            headers=headers,
        )

    # 1 outlier
    client.post(
        "/api/invoices/",
        json={
            "invoice_number": "INV-DASH-OUTLIER",
            "vendor_name": "Office Store",
            "invoice_date": str(today),
            "total_amount": 8000.00,
            "currency": "USD",
        },
        headers=headers,
    )

    # Run assessment
    assess_res = client.post("/api/anomalies/assess", headers=headers).json()
    expected_count = assess_res["anomalous_count"]

    # Check dashboard
    dash_res = client.get("/api/reports/dashboard", headers=headers).json()
    assert dash_res["anomalous_invoices_count"] == expected_count

