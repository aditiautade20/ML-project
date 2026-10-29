from app.models.user import User


def test_health_check_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "InvoiceIQ Backend"
    assert "environment" in data
    assert "timestamp" in data


def test_test_database_isolation(client, db_session):
    # Verify that data created during tests stays isolated in the test session
    client.post(
        "/api/auth/signup",
        json={
            "name": "Isolated User",
            "email": "isolated@example.com",
            "password": "Password123!",
        },
    )

    # Check via direct session query on test DB
    user_in_test_db = db_session.query(User).filter(User.email == "isolated@example.com").first()
    assert user_in_test_db is not None
    assert user_in_test_db.name == "Isolated User"
