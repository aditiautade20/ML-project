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
    print(f"Starting InvoiceIQ Backend on http://{settings.HOST}:{settings.PORT}")
    print(f"Swagger API Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"Database: {settings.resolved_database_url}")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
