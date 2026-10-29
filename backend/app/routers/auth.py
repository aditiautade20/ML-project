from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserSignupRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
)
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
)
from app.utils.security import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def signup(user_in: UserSignupRequest, db: Session = Depends(get_db)):
    """Registers a new user account with secure password hashing.
    Rejects duplicate emails with HTTP 409 Conflict.
    """
    normalized_email = user_in.email.strip().lower()

    # Check for duplicate email
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # Securely hash password using bcrypt
    hashed_pwd = hash_password(user_in.password)

    new_user = User(
        name=user_in.name.strip(),
        email=normalized_email,
        hashed_password=hashed_pwd,
        is_active=True,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while creating the account.",
        )

    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive access token",
)
def login(credentials: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticates user credentials and returns a secure JWT access token.
    Uses unified generic error message to prevent user enumeration.
    """
    normalized_email = credentials.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    # Generic authentication failure message prevents enumeration
    auth_failed_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user:
        raise auth_failed_exception

    if not verify_password(credentials.password, user.hashed_password):
        raise auth_failed_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is currently inactive.",
        )

    # Create short-lived JWT access token
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the profile of the currently authenticated user.
    Requires a valid, non-expired Bearer JWT token.
    """
    return current_user
