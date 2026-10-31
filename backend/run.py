import os
import sys
from pathlib import Path

# Add backend directory to sys.path so modules are easily resolved
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import uvicorn
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    port = int(os.environ.get("PORT", settings.PORT))
    host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else settings.HOST)
    print(f"Starting InvoiceIQ Backend on http://{host}:{port}")
    print(f"Swagger API Docs: http://{host}:{port}/docs")
    print(f"Database: {settings.resolved_database_url}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=settings.DEBUG and not bool(os.environ.get("PORT")),
    )
