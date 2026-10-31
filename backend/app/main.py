from datetime import datetime, timezone
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import init_db
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


@app.on_event("startup")
def on_startup():
    init_db()


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
cors_origins = settings.cors_origins
allow_all = "*" in cors_origins or not cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else cors_origins,
    allow_origin_regex=None if allow_all else r"https://.*\.onrender\.com",
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


# Static Frontend Serving (enables full-stack single-service deployment on Render)
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa_frontend(request: Request, full_path: str):
        # Do not intercept API, health, or interactive documentation routes
        if full_path.startswith("api/") or full_path == "api" or full_path in ("docs", "redoc", "openapi.json"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        target_file = FRONTEND_DIST / full_path
        if target_file.is_file():
            return FileResponse(str(target_file))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
else:
    @app.get("/", include_in_schema=False)
    def root_status():
        return {
            "service": "InvoiceIQ API",
            "status": "operational",
            "docs": "/docs" if settings.DEBUG else "disabled in production",
            "health": "/api/health",
        }
