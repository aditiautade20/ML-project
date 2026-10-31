# InvoiceIQ — Technical Architecture & System Design

## 1. System Overview & Architecture Diagram

InvoiceIQ is designed as a decoupled, multi-tier Single-Page Application (SPA) paired with a high-performance RESTful API backend.

```
                      ┌────────────────────────────────────────┐
                      │          React SPA (Vite)              │
                      │  Tailwind CSS • Lucide • React Router  │
                      └──────────────────┬─────────────────────┘
                                         │  HTTPS / JSON
                                         │  JWT Bearer Auth
                                         ▼
                      ┌────────────────────────────────────────┐
                      │         FastAPI API Gateway            │
                      │  CORS • Rate Limit • OAuth2 Bearer     │
                      └────┬─────────────────────────────┬─────┘
                           │                             │
              ┌────────────▼──────────┐     ┌────────────▼───────────┐
              │   Application Services│     │ Machine Learning Engine│
              │  • Auth & User Mgmt   │     │ • scikit-learn         │
              │  • OCR & Extraction   │     │ • Isolation Forest     │
              │  • Payment Ledger     │     │ • Statistical Baseline │
              │  • Report & CSV Gen   │     │ • Rationale Generator  │
              └────────────┬──────────┘     └────────────┬───────────┘
                           │                             │
                           └──────────────┬──────────────┘
                                          │ SQLAlchemy ORM
                                          ▼
                      ┌────────────────────────────────────────┐
                      │    Relational Database (SQLite/PG)     │
                      │ Users • Invoices • Payments • Anomalies │
                      └────────────────────────────────────────┘
```

---

## 2. Frontend Architecture (React 18 + Vite)

### Technology Stack
- **Framework:** React 18 with Functional Components and Hooks.
- **Build Tool:** Vite 5.x for near-instant hot module replacement (HMR) and optimized rollup production bundles.
- **Styling:** Tailwind CSS with utility-first responsive layout, dark-mode capability, and accessible contrast ratios.
- **Navigation:** React Router v6 with declarative nested routing, route-level authorization guards (`ProtectedRoute`), and redirect preservation (`location.state.from`).
- **Icons:** `lucide-react` for clean, consistent, professional SVG iconography.
- **HTTP Client:** Axios configured with base URL resolution and automated request/response interceptors.

### Key Architectural Patterns
1. **Centralized Authentication Context (`AuthContext`):**
   - Manages token persistence in `localStorage`.
   - Propagates user identity and authentication status throughout the component tree.
   - Handles automatic logout and redirection upon HTTP 401 Unauthorized responses.
2. **Defensive API Interceptors (`src/api/client.js`):**
   - Request interceptor injects `Authorization: Bearer <token>` into outgoing requests.
   - Response interceptor sanitizes error payloads and intercepts expired tokens.
3. **Resilient Data Presentation:**
   - Graceful empty state illustrations across all tables and cards.
   - Human-friendly currency formatting (`$#,##0.00`) and standard ISO date formatting.
   - In-line badge rendering reflecting payment statuses (`PAID`, `PARTIAL`, `OVERDUE`, `UNPAID`).

---

## 3. Backend Architecture (FastAPI + SQLAlchemy)

### Technology Stack
- **Framework:** FastAPI with Python 3.10+ type annotations and async support.
- **ASGI Server:** Uvicorn with auto-reload for development.
- **ORM:** SQLAlchemy 2.0 with strict foreign key constraints, relationship cascade deletions, and mapped models.
- **Validation:** Pydantic v2 schemas providing bidirectional request validation, schema conversion, and API documentation (OpenAPI / Swagger).
- **Database Engine:** SQLite (with WAL mode enabled) for local portability; architectured for drop-in migration to PostgreSQL.

### Layered Structure
- **Routers (`app/routers/`):** Thin HTTP entrypoints handling request parsing, parameter validation, and status code dispatching.
- **Services (`app/services/`):** Business logic encapsulation:
  - `auth_service.py`: Password hashing, salt management, JWT minting.
  - `extractor_service.py`: PDF/OCR document parsing and regex candidate extraction.
  - `payment_service.py`: Ledger math, partial payment balance checks, overpayment rejection.
  - `anomaly_service.py`: Feature vector construction, scikit-learn model fitting, anomaly scoring, natural language explanation generation.
  - `report_service.py`: Aggregation queries, monthly trend grouping, CSV formula sanitization, PDF generation.
- **Models (`app/models/`):** Declarative SQLAlchemy entities mapping database tables.
- **Utils (`app/utils/`):** Cross-cutting concerns including security dependencies, JWT token extraction, and file storage path sanitization.

---

## 4. Security & Hardening Architecture

| Threat / Vulnerability | Mitigation in InvoiceIQ | Implementation Reference |
| :--- | :--- | :--- |
| **Credential Compromise** | Passlib `bcrypt` hashing with individual per-user salts; minimum 8 characters; uppercase, lowercase, number, and special character validation. | `app/services/auth_service.py` |
| **Session Hijacking** | Stateless JWT tokens signed with HMAC-SHA256 and configurable expiration (default: 60 minutes). | `app/utils/security.py` |
| **Cross-Tenant Data Leakage** | Strict database-level scoping: Every database query enforces `user_id == current_user.id`. No endpoint ever accepts arbitrary `user_id` parameters from client payloads. | Verified in `test_health_and_isolation.py` & `test_security_audit.py` |
| **Arbitrary File Traversal** | Uploaded documents are saved under sanitized filenames (`uuid4().hex`) in isolated user-specific subdirectories. MIME types and extensions are strictly whitelisted (PDF, PNG, JPG, JPEG, TIFF). | `app/utils/storage.py` |
| **CSV Formula Injection (CSV Injection / DDE)** | All text fields exported to CSV are screened for leading trigger characters (`=`, `+`, `-`, `@`, `\t`, `\r`). Any detected formula cell is prefixed with a single quote (`'`). | `app/utils/csv_sanitizer.py` |
| **Financial Overpayment Race Condition** | Server-side validation calculates `balance_due = invoice_total - sum(payments)` using exact `Decimal` arithmetic. Overpayments are rejected with HTTP 400 Bad Request. | `app/services/payment_service.py` |
| **Information Disclosure in Production** | FastAPI `/docs` and `/redoc` endpoints can be disabled in production when `DEBUG=False`. Detailed stack traces are caught by custom exception handlers. | `app/main.py` |

---

## 5. Document Ingestion & Extraction Engine

The document extraction pipeline operates entirely offline without external third-party API dependencies:

1. **Document Validation:** Verifies file size (≤ 10MB) and checks file headers against permitted MIME signatures (`application/pdf`, `image/png`, `image/jpeg`, `image/tiff`).
2. **Text Extraction Pipeline:**
   - **Vector PDFs:** Parsed via `pdfplumber` for extraction of native text streams.
   - **Scanned PDFs & Images:** Pre-processed via Pillow and converted into high-contrast grayscale before OCR extraction via `pytesseract`.
3. **Regex Heuristic Pattern Matching:**
   - **Invoice Numbers:** Scans for patterns following keywords (`Invoice #`, `Inv No.`, `Bill #`) and alphanumeric alphanumeric tokens.
   - **Vendor Names:** Matches against sender blocks, email domain patterns, and header structures.
   - **Dates:** Matches multiple international date notations (`YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, `Month DD, YYYY`).
   - **Monetary Totals:** Isolates monetary symbols (`$`, `€`, `£`, `USD`, `INR`) and parses subtotal, tax/GST, and grand totals into exact `Decimal` objects.
4. **Human-in-the-Loop Verification:** Raw extractions are returned as candidate fields to the frontend. The user reviews, corrects, and confirms the fields before committing to the database.

---

## 6. Machine Learning Pipeline (Isolation Forest)

### Mathematical Foundation
InvoiceIQ utilizes **Isolation Forest**, an unsupervised tree-based ensemble algorithm that isolates anomalies by randomly selecting a feature and a split value. Anomalies have shorter path lengths in the isolation trees because they require fewer partitions to isolate from normal data points.

### Feature Engineering
For each invoice belonging to the user, an 8-dimensional feature vector is generated:
1. `total_amount`: Normalized total invoice amount.
2. `log_total`: $\ln(\text{total\_amount} + 1)$ to handle right-skewed financial distributions.
3. `tax_amount`: Absolute tax/GST amount.
4. `tax_ratio`: $\frac{\text{tax\_amount}}{\text{total\_amount}}$ (detects abnormal tax percentages).
5. `has_subtotal`: Binary indicator ($1$ if subtotal present, $0$ otherwise).
6. `subtotal_ratio`: $\frac{\text{subtotal}}{\text{total\_amount}}$.
7. `vendor_invoice_count`: Frequency of invoices from this specific vendor.
8. `vendor_amount_deviation`: Ratio of current invoice total to the vendor's historical median total:
   $$\text{deviation} = \frac{\text{total}}{\text{median}_{\text{vendor}}(\text{total})}$$

### Calibration & Cold Start Safety
- **Minimum Threshold:** The ML model requires at least 3 confirmed invoices before running inference. If the account has fewer than 3 invoices, the system returns status `INSUFFICIENT_DATA` with a clear explanation.
- **Contamination Parameter:** Set conservatively to $0.10$ (10% expected anomaly ceiling) to minimize false positives in standard business accounting.
- **Identical Value Fallback:** If all invoices in a baseline have identical amounts (standard deviation $= 0$), the model gracefully classifies records as normal without division-by-zero errors.

### Human-Readable Rationale Generation
Whenever an invoice is flagged as `POTENTIALLY_UNUSUAL`, the engine generates an explanatory diagnostic string:
- If vendor history exists: *"Total amount ($12,850.00) is 28.2x higher than historical median ($455.00) for vendor 'Apex Cloud Infrastructure'."*
- If overall account history exists: *"Total amount is 24.5x higher than your overall median invoice size ($525.00)."*

---

## 7. Database Schema & Data Integrity

The relational schema is governed by Alembic migrations:

```
  ┌────────────────────────┐
  │         users          │
  ├────────────────────────┤
  │ id (PK)                │
  │ email (UQ, indexed)    │
  │ hashed_password        │
  │ name                   │
  │ is_active              │
  │ created_at             │
  └───────────┬────────────┘
              │ 1:N
              ▼
  ┌────────────────────────┐         ┌────────────────────────┐
  │        invoices        │ 1:N     │        payments        │
  ├────────────────────────┼────────►├────────────────────────┤
  │ id (PK)                │         │ id (PK)                │
  │ user_id (FK, CASCADE)  │         │ invoice_id (FK, CASCADE│
  │ invoice_number         │         │ user_id (FK, CASCADE)  │
  │ vendor_name            │         │ amount (Decimal 10,2)  │
  │ invoice_date           │         │ payment_date           │
  │ due_date (Nullable)    │         │ payment_method         │
  │ subtotal (10,2)        │         │ reference (Nullable)   │
  │ tax_amount (10,2)      │         │ notes (Nullable)       │
  │ total_amount (10,2)    │         │ created_at             │
  │ currency (USD default) │         └────────────────────────┘
  │ status (CONFIRMED)     │
  │ notes                  │
  │ file_path              │         ┌────────────────────────┐
  │ created_at             │ 1:1     │    invoice_anomalies   │
  └───────────┬────────────┼────────►├────────────────────────┤
              │            │         │ id (PK)                │
              └────────────┘         │ invoice_id (FK, CASCADE│
                                     │ is_anomalous (Boolean) │
                                     │ anomaly_score (Float)  │
                                     │ status (Flagged/Normal)│
                                     │ explanation (Text)     │
                                     │ evaluated_at           │
                                     └────────────────────────┘
```

---

## 8. Automated Test Suite

The system includes **58 automated tests** covering 100% of core business features:
- `test_auth_api.py` & `test_auth_service.py`: User registration, unique constraints, bcrypt validation, JWT expiration and tampering rejection.
- `test_invoices_api.py` & `test_extractor.py`: PDF/OCR candidate parsing, invoice persistence, multi-user isolation, duplicate number rejection.
- `test_payments_api.py`: Partial payment recording, multi-tranche ledger, overpayment prevention, dynamic status resolution (`PAID`, `PARTIAL`, `OVERDUE`).
- `test_anomaly_detection.py`: scikit-learn feature vector extraction, Isolation Forest outlier flagging, explanation generation, insufficient-data handling.
- `test_reports_api.py`: Financial aggregation, CSV formula injection escaping, PDF summary creation.
- `test_security_audit.py`: Cross-tenant file isolation, unauthenticated access rejection, cascade deletion integrity.
- `test_demo_mode.py`: Demo seed repeatability, cleaner isolation, demo account authentication.
