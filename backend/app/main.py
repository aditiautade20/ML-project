from datetime import datetime, timezone
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.invoices import router as invoices_router
from app.routers.payments import router as payments_router
from app.routers.anomalies import router as anomalies_router
from app.routers.reports import router as reports_router
from app.routers.reconciliation import router as reconciliation_router

logger = logging.getLogger("invoiceiq.api")
settings = get_settings()

app = FastAPI(
    title="InvoiceIQ API",
    description="Professional Financial and Invoice Management System API",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Catches all unexpected exceptions and returns a clean 500 response,
    preventing any leak of tracebacks, passwords, or system internals.
    Preserves Starlette/FastAPI HTTPExceptions and RequestValidationError.
    """
    if isinstance(exc, (StarletteHTTPException, RequestValidationError)):
        raise exc
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. Please try again or contact support."},
    )


# Restrict CORS to configured origins (prevents arbitrary origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(invoices_router)
app.include_router(payments_router)
app.include_router(anomalies_router)
app.include_router(reports_router)
app.include_router(reconciliation_router)


@app.get("/api/health", tags=["Health"], summary="Service Health Check")
def health_check():
    """Returns the operational status, current timestamp, and environment of the API."""
    return {
        "status": "healthy",
        "service": "InvoiceIQ Backend",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
