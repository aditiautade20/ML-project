from datetime import timedelta
from app.services.auth_service import create_access_token


def test_successful_signup(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Jane Doe",
            "email": "jane.doe@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Jane Doe"
    assert data["email"] == "jane.doe@example.com"
    assert "id" in data
    assert data["is_active"] is True
    assert "created_at" in data

    # Security check: Password hash must NEVER be returned in response
    assert "password" not in data
    assert "hashed_password" not in data


def test_duplicate_email_signup_rejected(client):
    # First registration
    client.post(
        "/api/auth/signup",
        json={
            "name": "Jane Doe",
            "email": "duplicate@example.com",
            "password": "Password123!",
        },
    )

    # Second registration with identical email (different case/whitespace)
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Another Name",
            "email": "  DUPLICATE@example.com ",
            "password": "DifferentPassword123!",
        },
    )
    assert response.status_code == 409
    data = response.json()
    assert "already exists" in data["detail"]


def test_invalid_signup_data(client):
    # Short password (< 8 chars)
    res1 = client.post(
        "/api/auth/signup",
        json={
            "name": "Jane Doe",
            "email": "valid@example.com",
            "password": "short",
        },
    )
    assert res1.status_code == 422

    # Invalid email format
    res2 = client.post(
        "/api/auth/signup",
        json={
            "name": "Jane Doe",
            "email": "not-an-email",
            "password": "Password123!",
        },
    )
    assert res2.status_code == 422

    # Blank / whitespace name
    res3 = client.post(
        "/api/auth/signup",
        json={
            "name": "   ",
            "email": "valid2@example.com",
            "password": "Password123!",
        },
    )
    assert res3.status_code == 422


def test_successful_login(client):
    # Register user
    client.post(
        "/api/auth/signup",
        json={
            "name": "John Smith",
            "email": "john.smith@example.com",
            "password": "StrongPassword987!",
        },
    )

    # Login
    response = client.post(
        "/api/auth/login",
        json={
            "email": "JOHN.SMITH@example.com",
            "password": "StrongPassword987!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "john.smith@example.com"
    assert data["user"]["name"] == "John Smith"

    # Security check: Password hash must NOT be in user object
    assert "password" not in data["user"]
    assert "hashed_password" not in data["user"]


def test_incorrect_login_credentials(client):
    # Register user
    client.post(
        "/api/auth/signup",
        json={
            "name": "Alice Wonderland",
            "email": "alice@example.com",
            "password": "CorrectPassword123!",
        },
    )

    # Wrong password
    res_wrong_pw = client.post(
        "/api/auth/login",
        json={
            "email": "alice@example.com",
            "password": "WrongPassword!",
        },
    )
    assert res_wrong_pw.status_code == 401
    assert res_wrong_pw.json()["detail"] == "Invalid email or password."

    # Non-existent email should give identical error message (no email enumeration)
    res_nonexistent = client.post(
        "/api/auth/login",
        json={
            "email": "nobody@example.com",
            "password": "AnyPassword123!",
        },
    )
    assert res_nonexistent.status_code == 401
    assert res_nonexistent.json()["detail"] == "Invalid email or password."


def test_get_current_user_authenticated(client):
    # Register
    signup_res = client.post(
        "/api/auth/signup",
        json={
            "name": "Bob Builder",
            "email": "bob@example.com",
            "password": "CanWeFixIt123!",
        },
    )
    user_id = signup_res.json()["id"]

    # Login
    login_res = client.post(
        "/api/auth/login",
        json={
            "email": "bob@example.com",
            "password": "CanWeFixIt123!",
        },
    )
    token = login_res.json()["access_token"]

    # Access /api/auth/me with Bearer token
    me_res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["id"] == user_id
    assert me_data["name"] == "Bob Builder"
    assert me_data["email"] == "bob@example.com"
    assert me_data["is_active"] is True
    assert "password" not in me_data
    assert "hashed_password" not in me_data


def test_get_current_user_unauthenticated(client):
    # Without Authorization header
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_get_current_user_invalid_token(client):
    # With garbage token
    res = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt.token"},
    )
    assert res.status_code == 401


def test_get_current_user_expired_token(client):
    # Create an expired token for an existing user id
    signup_res = client.post(
        "/api/auth/signup",
        json={
            "name": "Time Traveler",
            "email": "timetravel@example.com",
            "password": "BackToTheFuture1!",
        },
    )
    user_id = signup_res.json()["id"]
    expired_token = create_access_token(
        {"sub": str(user_id), "email": "timetravel@example.com"},
        expires_delta=timedelta(seconds=-30),
    )

    res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert "Could not validate credentials" in res.json()["detail"]
