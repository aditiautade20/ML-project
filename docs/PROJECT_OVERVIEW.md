# InvoiceIQ — Project Overview & Executive Summary

## 1. Executive Summary

**InvoiceIQ** is an enterprise-grade financial management and invoice processing web application designed for small-to-medium businesses (SMBs), independent finance consultants, and corporate accounts payable teams. It automates invoice lifecycle management from document ingestion and automated parsing to multi-stage payment tracking, deadline monitoring, machine learning-driven anomaly screening, 4-way financial reconciliation, and executive cash-flow analytics.

Unlike basic spreadsheet trackers or rigid legacy ERPs, InvoiceIQ bridges the gap between lightweight usability and rigorous financial engineering:
- **Zero Silent Overpayments:** Strict server-side decimal math enforces financial integrity.
- **Explainable Machine Learning:** An automated Scikit-Learn Isolation Forest engine screens incoming invoices against historical vendor and account spending patterns, accompanied by human-readable explanations.
- **Invoice Verification & 4-Way Financial Reconciliation:** Cross-verifies Invoices ⟷ General Ledger (GL) entries ⟷ Recorded Payments ⟷ Cleared Bank Statement debits with directionality-aware parsing, penny-tolerance matching, and 1-click payment confirmation.
- **Multi-Tenant Isolation:** Complete per-user data segregation across authentication, document uploads, payments, analytics, reconciliation batches, and ML screening.
- **Privacy-First Ingestion:** Document parsing utilizes local `pdfplumber` and `pypdf` engines, keeping sensitive vendor financial data strictly on-premise or within the private cloud perimeter.

---

## 2. Problem Statement

Small businesses and accounting departments face significant operational friction and financial leakage:
1. **Manual Data Entry Bottlenecks:** Manual transcription of invoice numbers, line totals, and tax breakdowns introduces typing errors and slows accounts payable cycles.
2. **Hidden Anomaly & Fraud Risks:** Erroneous duplicate billings, inflated unit pricing, or rogue invoices often go undetected in high-volume environments without automated statistical screening.
3. **Fragmented Payment Tracking:** Disconnected ledgers lead to missed due dates, avoidable late fees, and inaccurate outstanding balance calculations.
4. **Month-End Reconciliation Nightmares:** Manually cross-referencing internal invoices against external general ledgers and bank statement exports takes days and frequently suffers from rounding and timing mismatches.
5. **Lack of Instant Visibility:** Business owners lack a consolidated dashboard showing cash outflows, impending deadlines, and historical vendor spending patterns.

---

## 3. The InvoiceIQ Solution

InvoiceIQ provides an integrated, end-to-end workflow:

| Stage | Capability | User Benefit |
| :--- | :--- | :--- |
| **Ingestion** | Multi-format upload (PDF, PNG, JPG, WebP) with dual-layer binary signature validation. | Eliminates manual transcription; pre-fills candidate values for human review. |
| **Verification** | Review & confirmation interface before database commit. | Ensures human-in-the-loop validation of extracted financial figures; never invents missing fields. |
| **Payments** | Ledger tracking partial, full, and multi-tranche payments. | Real-time balance calculations with strict overpayment guards. |
| **Deadlines** | Automated categorization (Overdue, Due Today, Due ≤ 7 Days, Due Later, No Due Date). | Prevents late fees and prioritizes urgent obligations without erroneously marking invoices with no due date overdue. |
| **ML Intelligence** | Unsupervised Isolation Forest anomaly screening (13-feature matrix + RobustScaler). | Flags statistical spending outliers with human-readable rationale; requires ≥ 5 records to prevent false positives. |
| **Reconciliation** | 4-Way Reconciliation Centre (Accounting Ledger, Bank Statement, Combined). | Pinpoints exact matches, amount mismatches, duplicate entries, ghost liabilities, and unrecorded payments with 1-click settlement. |
| **Analytics & Export** | Interactive dashboard, monthly trend charts, CSV & PDF reports. | Actionable financial insights and audit-ready data exports protected against CSV spreadsheet formula injection. |

---

## 4. Target User Personas

1. **SMB Operations & Business Owners:** Require quick oversight of total outstanding liabilities, upcoming cash outflows, and monthly spending trends without navigating complex ERP systems.
2. **Accounts Payable Clerks & Bookkeepers:** Need automated invoice ingestion, OCR assistance, rigorous partial payment tracking that prevents accidental double payments, and automated bank reconciliation.
3. **Financial Auditors & Controllers:** Require tamper-resistant audit trails, CSV formula injection protection, secure tenant data isolation, SHA-256 fingerprinting of external ledgers, and PDF summary generation.

---

## 5. Core Feature Matrix

### Document Ingestion & Extraction
- Support for digital and scanned PDFs, PNGs, JPEGs, and WebPs.
- Extraction engine powered by `pdfplumber` and `pypdf` with binary magic byte signature verification (`%PDF-`, `\x89PNG`, `\xFF\xD8\xFF`, `RIFF...WEBP`).
- Multi-field regex heuristic extractors for invoice numbers, vendor names, issue dates, due dates, subtotal, tax/GST, and grand totals.
- Pre-upload validation: strict MIME verification, extension whitelisting, and a 10MB payload ceiling.

### Financial Ledger & Payment Tracking
- Exact two-decimal place `Decimal` arithmetic preventing floating-point rounding errors.
- Support for multi-tranche partial payments against any confirmed invoice.
- Strict rejection of overpayments exceeding the invoice's remaining balance with HTTP 400.
- Dynamic status resolution: `PAID`, `PARTIALLY_PAID`, `OVERDUE`, and `UNPAID`.
- Invoices without explicit due dates are gracefully tracked without being erroneously marked overdue.

### AI / Machine Learning Anomaly Detection
- Unsupervised anomaly detection powered by `scikit-learn` Isolation Forest (100 isolation trees).
- 13-dimensional feature matrix: log-transformed amounts, tax ratio, subtotal ratio, round number flags, vendor spending deviation multiples, historical account median comparison, and payment term days.
- Features scaled with `RobustScaler` (median & interquartile range) to prevent extreme outliers from skewing tree splits.
- Cold-start safety: requires a minimum statistical baseline (≥ 5 invoices) before fitting models; informs users clearly during the baseline calibration phase.
- Natural language explanations generated alongside statistical anomaly flags (e.g., *"Total amount ($12,850.00) is 28.2x higher than historical median ($455.00) for vendor 'Apex Cloud Infrastructure'"*).
- Manual review workflow: users can review flags and mark them as `REVIEWED` or `CONFIRMED_ISSUE`.

### Invoice Verification & Financial Reconciliation Centre
- **Accounting Ledger Reconciliation:** Compares external General Ledger (CSV/XLSX) entries against recorded invoices. Identifies exact matches, amount mismatches, duplicate ledger rows, and missing invoices (ghost liabilities).
- **Bank Statement Reconciliation:** Directionality-aware parser handles debit/credit columns, negative withdrawals, and UTR/reference strings. Matches cleared debits against recorded payments and flags candidate settlements for unpaid invoices.
- **1-Click Confirmed Payment:** Bank statement matching NEVER silently mutates balances; users review candidate payments and confirm them with a single click.
- **Combined 4-Way Reconciliation:** Simultaneously evaluates Invoices ⟷ General Ledger ⟷ Payments ⟷ Bank Statements.
- **Configurable Penny Tolerance:** Customizable matching tolerance (default ±$0.05) to accommodate banking and FX rounding.
- **Full Audit Trail:** Persists batch uploads with SHA-256 file fingerprints and review statuses.

### Analytics, Reporting & Secure Export
- Executive KPI summary: Invoiced, Paid, Balance Due, Overdue Invoices, Imminent Deadlines (7 days), and Flagged Outliers.
- Monthly cash flow trends charting total invoiced vs. total paid over time.
- Vendor breakdown distribution and high-value liability tracking.
- RFC 4180-compliant CSV export with formula injection sanitization (`=`, `+`, `-`, `@`, `\t`, `\r` escaping).
- Formatted PDF financial summary generation with complete corporate headers and status indicators.

---

## 6. Project Directory Layout

```
InvoiceIQ_New/
├── backend/
│   ├── alembic/                # Database migrations (Alembic)
│   ├── app/
│   │   ├── models/             # SQLAlchemy ORM models (User, Invoice, Payment, Anomaly, ReconciliationBatch, ReconciliationItem)
│   │   ├── routers/            # FastAPI API endpoints (Auth, Invoices, Payments, Anomalies, Reports, Reconciliation)
│   │   ├── schemas/            # Pydantic validation schemas
│   │   ├── services/           # Business logic (Extractor, Payments, ML Isolation Forest, Reports, Reconciliation)
│   │   ├── utils/              # Security, JWT, CSV formula sanitization, storage
│   │   ├── demo_seed.py        # Dedicated demo account generator & cleaner
│   │   └── main.py             # FastAPI application entrypoint & middleware
│   └── tests/                  # 116 automated unit, integration, and security tests across 16 test suites
├── demo_samples/               # Curated sample files for live presentations
│   ├── sample_invoice.pdf      # Vector tax invoice document
│   ├── accounting_ledger_sample.csv / .xlsx
│   ├── bank_statement_sample.csv / .xlsx
│   └── README.md               # Detailed sample guide and verification steps
├── frontend/
│   ├── src/
│   │   ├── api/                # Fetch API client modules
│   │   ├── components/         # Reusable UI components (Navbar, Sidebar, Modals, Cards)
│   │   ├── context/            # AuthContext & session state management
│   │   └── pages/              # Dashboard, Invoices, Payments, Deadlines, Reconciliation, Anomalies, Reports, Login
│   └── package.json            # React 18, Vite, Tailwind CSS, Lucide
└── docs/                       # Engineering artifacts & presentation materials
```

---

## 7. Known Limitations & Roadmap

- **OCR for Complex Scanned Images:** Extraction uses native PDF parsing (`pdfplumber` / `pypdf`). For low-resolution or scanned photos without a digital text layer, the review modal allows manual verification and entry.
- **Single-Node Filesystem:** Attachments are currently stored in `backend/data/uploads`. Cloud object storage adapters (AWS S3, GCP Cloud Storage) are planned for high-scale multi-region deployment.
- **Machine Learning Sample Size:** The Isolation Forest model requires ≥ 5 invoices from a user before fitting anomaly trees to prevent false positives on statistical noise.
