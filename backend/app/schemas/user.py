from datetime import datetime
from typing import Optional
import re
from pydantic import BaseModel, Field, field_validator


class UserSignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of the user")
    email: str = Field(..., max_length=255, description="Valid email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password with minimum 8 characters")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Name must be at least 2 characters after trimming whitespace.")
        return trimmed

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        trimmed = v.strip().lower()
        # RFC-compliant basic email validation
        email_regex = r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+(\.[a-zA-Z0-9\-]+)+$"
        if not re.match(email_regex, trimmed):
            raise ValueError("Invalid email format.")
        return trimmed

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="User's registered email")
    password: str = Field(..., description="User's password")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
