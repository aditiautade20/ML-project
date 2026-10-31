"""
InvoiceIQ Academic Project Report Content - Part 1: Sections 1 through 8
Covers:
- Academic Cover Page & Acknowledgement
- Table of Contents Structure
- 1. Abstract
- 2. Introduction
- 3. Problem Statement
- 4. Objectives
- 5. Existing vs. Proposed System (with Comparison Matrix Table)
- 6. Technologies Used (with Architecture Tier Tables)
- 7. System Architecture (with Layer Table, Architecture Diagram, Workflow Diagram)
- 8. Dataset Description (Demo Data vs Actual ML Instance Training, Provenance Table)
"""

COVER_PAGE_DATA = {
    "report_type": "PROJECT REPORT",
    "project_title": "InvoiceIQ",
    "project_subtitle": "AI-Powered Invoice Processing and Ledger Reconciliation System",
    "done_by_label": "Done By",
    "student_name": "[Student Name]",
    "student_roll": "[Roll Number / Registration Number]",
    "guidance_label": "Under the Guidance Of",
    "guide_name": "[Guide Name]",
    "guide_designation": "[Designation, Department]",
    "institution_name": "[College / University Name]",
    "academic_year": "Academic Year [2026 – 2027]",
}

ACKNOWLEDGEMENT_TEXT = """
I would like to express my sincere gratitude to everyone who supported me in the successful completion of this project, "InvoiceIQ: AI-Powered Invoice Processing and Ledger Reconciliation System".

First and foremost, I thank my project guide, [Guide Name], for the valuable guidance, constant encouragement, and constructive feedback given throughout this work. Their technical insights and rigorous support helped me understand the intricacies of financial data extraction, accounting reconciliation, and machine learning anomaly detection, shaping the project in the right direction.

I am also thankful to the Head of the Department, [HOD Name], and to all the faculty members of the Department of [Department Name], [College / University Name], for providing the necessary facilities, computing infrastructure, and a supportive academic environment to carry out this project.

I extend my sincere thanks to the open-source software communities behind FastAPI, React, SQLAlchemy, PyPDF, pdfplumber, Tesseract OCR, and scikit-learn, whose robust tools, libraries, and comprehensive documentation made this research and engineering implementation possible.

Finally, I express my deepest appreciation to my family and peers for their continuous patience, motivation, and moral support throughout the course of this engineering endeavor.

[Student Name]
[Roll Number / Registration Number]
Department of [Department Name]
[College / University Name]
"""

TOC_ITEMS = [
    ("1. Abstract", "3"),
    ("2. Introduction", "4"),
    ("3. Problem Statement", "5"),
    ("4. Objectives", "6"),
    ("5. Existing vs. Proposed System", "7"),
    ("6. Technologies Used", "9"),
    ("7. System Architecture", "11"),
    ("8. Dataset Description", "14"),
    ("9. Machine Learning Algorithm", "17"),
    ("10. Invoice Processing and Ledger Reconciliation Approach", "20"),
    ("11. Results and Performance Metrics", "24"),
    ("12. Testing and Code Integrity", "26"),
    ("13. Application Screenshots", "28"),
    ("14. Limitations", "31"),
    ("15. Conclusion", "32"),
    ("References", "33"),
]

ABSTRACT_TEXT = """
In contemporary enterprise corporate operations, manual accounts payable (AP) and financial ledger reconciliation represent critical operational bottlenecks. Organizations receive invoices in heterogeneous formats—ranging from digital-first vector PDFs to degraded scanned images—which require labor-intensive manual data entry into accounting systems. This reliance on human entry causes data transcription errors, arithmetic discrepancies, unmapped ledger headers, duplicate invoice payments, and delayed financial closing cycles.

InvoiceIQ is an intelligent, offline-capable, and privacy-preserving invoice processing and ledger reconciliation platform engineered to automate financial accounting pipelines end-to-end. The system integrates a dual-tier text extraction pipeline combining digital PDF stream parsing (via pdfplumber and pypdf) with Optical Character Recognition (via Tesseract OCR), paired with robust layout-aware regular expression heuristics that recover distorted text streams and multiline totals. 

To guarantee financial data integrity, InvoiceIQ enforces strict mathematical self-validation (Subtotal + Taxes - Discounts = Total) and implements an intelligent calculated fallback total when document-printed figures are omitted, maintaining transparent audit provenance without silently altering financial records. The platform further introduces an automated accounting ledger ingestion module capable of dynamic column mapping across disparate ERP exports (e.g., Tally, SAP, QuickBooks) using synonym dictionaries and debit-credit dominance heuristics. Reconciliations are executed via an automated 3-way matching engine that classifies transaction records into exact matches, amount discrepancies, tax mismatches, and suspected duplicates with actionable resolution recommendations.

For proactive financial governance, InvoiceIQ incorporates an unsupervised anomaly screening engine powered by scikit-learn's Isolation Forest. Operating under strict tenant data isolation, the model evaluates a 13-dimensional numerical feature space—capturing currency-normalized amounts, vendor historical medians, tax ratios, arithmetic discrepancies, and duplicate frequencies—yielding non-alarmist, statistically grounded risk ratings (LOW, MEDIUM, HIGH) accompanied by transparent human-readable explanations.

Evaluated on comprehensive test suites and realistic industry sample documents, InvoiceIQ achieved a 100% automated test pass rate across 26 document extraction test cases and 11 column auto-mapping scenarios. With sub-second document processing latency (45–120 ms for vector PDFs) and complete data privacy ensured through local execution, InvoiceIQ demonstrates a scalable, production-grade foundation for autonomous financial record management.
"""

INTRODUCTION_TEXT = """
Accounts Payable (AP) and General Ledger reconciliation form the indispensable operational backbone of corporate financial accounting. Every procurement transaction—from hardware acquisition and cloud infrastructure leasing to regional logistics—generates an invoice that must be recorded, verified, approved, scheduled for payment, and reconciled against corporate ledgers and bank statements.

Historically, this accounting lifecycle relied heavily on physical paper invoices stamped and transcribed manually into enterprise resource planning (ERP) journals. In contemporary enterprises, although invoices have shifted to electronic formats (PDF, TIFF, JPEG), the underlying data remains largely unstructured. Invoices arrive without universal layout standards: suppliers place invoice numbers, line item grids, tax breakdowns, and banking instructions in arbitrary locations.

Consequently, accounting personnel spend between 10 to 20 minutes manually transcribing figures from each document into ERP software. This manual workflow introduces significant operational vulnerabilities:
1. Keystroke errors and transposed digits frequently corrupt ledger balances.
2. Invoices with unusual formatting (such as parenthesized currency codes like 'Total (USD) 111.45' or multiline total labels) lead to missed grand totals.
3. Complex multi-jurisdictional tax regimes (such as the Indian Goods and Services Tax comprising CGST, SGST, and IGST) are prone to misallocation.
4. Month-end ledger reconciliation requires exhausting manual cross-referencing between general ledgers and invoices to detect unrecorded disbursements or duplicate bookings.

InvoiceIQ is designed to address these fundamental accounting challenges by combining algorithmic document parsing, deterministic financial validation rules, intelligent ERP ledger auto-mapping, and unsupervised machine learning. Built from first principles on a modern open-source software stack (React 18, FastAPI, SQLite, and scikit-learn), the platform operates entirely on-premise without external cloud API dependencies, ensuring complete enterprise data confidentiality, zero per-page subscription fees, and verifiable mathematical audit trails.
"""

PROBLEM_STATEMENT_TEXT = """
Modern financial departments face multiple interconnected technical challenges when handling invoice data extraction and accounting reconciliation:

1. Heterogeneous Document Layouts & Stream Kerning Failures:
Invoices lack standardized structural templates. Digital-first PDFs often contain overlapping text streams where adjacent labels and values fuse together (e.g., 'BrightDesk SuppliesAddress: 742 Innovation Way'), causing standard extractors to produce corrupted character strings.

2. The "Missing Grand Total" Extraction Failure:
Many invoice generators format grand totals using non-standard conventions, such as parenthesized currency codes ('Total (USD) 111.45'), trailing currency symbols ('111.45 USD'), or multiline summary tables where the label 'Total' appears on one line and the numeric value appears on the following line. Conventional single-line regular expressions fail to extract these totals, returning null values.

3. The Silent Overwrite Hazard in Naive Systems:
When extraction fails, naive automated systems often compute an estimated sum from extracted line items and overwrite the document's total amount silently. This masks real arithmetic discrepancies, billing errors, and fraudulent supplier overcharges, depriving auditors of the ground-truth printed figure.

4. Disparate ERP Export Schemas & Header Inconsistencies:
Accounting ledgers exported from diverse accounting packages (such as SAP, Oracle NetSuite, Tally, and QuickBooks) utilize inconsistent column names (e.g., 'Voucher No', 'Ref_ID', 'Doc_Num', 'Debit', 'Credit', 'Net_Amt'). Systems without flexible column auto-mapping require repetitive manual column mapping on every file upload.

5. Ambiguous Debit and Credit Conventions:
Ledger exports represent financial disbursements using conflicting conventions: some ERPs report expense disbursements as positive debit figures, while others record them as negative credit amounts. Treating these columns uniformly without heuristic analysis results in false mismatch flags.

6. Double Payments and Duplicate Invoice Bookings:
When duplicate invoices are submitted across departments or re-booked in accounting journals, manual auditors struggle to detect duplicate invoice numbers, resulting in accidental cash leakage and inflated expense metrics.

7. Payment Timing and Due Date Conflation:
Conventional accounting software frequently marks invoices as 'Overdue' simply because the due date has passed, failing to verify whether payment was settled on time, paid late, or partially settled.

8. Black-Box Anomaly Flagging and Unfounded Fraud Accusations:
Commercial AI accounting tools often flag invoices using opaque neural network confidence scores (e.g., '98.4% fraud probability') without explaining why an invoice was flagged. This generates alert fatigue and exposes organizations to legal liability from ungrounded fraud claims.
"""

OBJECTIVES_TEXT = """
The primary objectives of the InvoiceIQ system are:

1. Resilient Multi-Format Document Ingestion & Extraction:
Develop an offline, multi-tier document ingestion engine supporting vector PDFs, scanned image PDFs, and standard raster graphics (PNG, JPEG, WEBP). Implement layered text extraction fallbacks (pdfplumber -> pypdf -> pypdfium2 -> Tesseract OCR) capable of repairing fused text kerning and extracting metadata, parties, tax breakdowns (CGST/SGST/IGST), and tabular line items.

2. Robust Grand Total Extraction & Provenance-Preserving Fallback:
Detect diverse grand total formatting conventions (parenthesized codes, trailing symbols, multiline tabular grids). Maintain strict separation between document-printed totals and calculated fallback totals, ensuring transparent audit warnings whenever calculations are utilized.

3. Intelligent Ledger Column Auto-Mapping:
Ingest CSV and Excel (.xlsx) accounting ledgers and automatically map column headers using an extensive synonym dictionary and content-heuristic analysis (debit-dominant vs credit-dominant columns).

4. Comprehensive 3-Way Ledger Reconciliation:
Compare invoice records against accounting ledgers and payment disbursements to categorize transactions into Exact Matches, Amount Discrepancies, Tax Mismatches, Suspected Duplicates, and Missing Records with human-readable resolution guidance.

5. Single Source of Truth for Payment Tracking & Due Date Management:
Establish the saved invoice record as the single authoritative source of truth across the application. Track partial payments, full settlements, remaining balances, and payment timing status (Upcoming/Unpaid, Overdue — Payment Not Confirmed, Paid on Time, Paid Late with days late, Partially Paid).

6. Explainable Machine Learning Anomaly Detection:
Fit an unsupervised scikit-learn Isolation Forest model dynamically on user-isolated invoice data. Extract a 13-dimensional numerical feature vector capturing amount distributions, vendor historical baselines, tax proportions, arithmetic discrepancies, and duplicate frequencies. Provide non-alarmist risk classifications (LOW, MEDIUM, HIGH) accompanied by transparent explanations citing specific financial figures.

7. Multi-Tenant Enterprise Security & Production Web Interface:
Enforce cryptographic password hashing (Bcrypt), stateless JWT authorization, database-level tenant isolation (WHERE user_id = current_user.id), OWASP formula injection protection in CSV exports, and a modern, responsive React 18 user interface.
"""

EXISTING_VS_PROPOSED_DATA = {
    "headers": ["Dimension", "Traditional Manual Accounting", "Commercial Semi-Automated Tools", "Proposed InvoiceIQ System"],
    "col_widths": [1.2, 1.7, 1.8, 1.8],
    "rows": [
        [
            "Document Ingestion & OCR",
            "Manual keystroke transcription from physical or digital documents (10–20 min/doc).",
            "Cloud-dependent OCR APIs (AWS Textract, Google Document AI); incurs recurring per-page fees.",
            "100% offline dual pipeline (pdfplumber + Tesseract OCR); zero recurring API fees and complete data privacy."
        ],
        [
            "Grand Total Extraction",
            "Human visual inspection; subject to digit inversion and typographical errors.",
            "Single-line regex matching; frequently drops parenthesized codes or multiline totals.",
            "Heuristic pattern engine handling currency codes, parenthesized formats, and multiline grids with arithmetic self-checks."
        ],
        [
            "Calculated Fallback & Provenance",
            "Manual re-calculation using desktop calculators; error-prone and untracked.",
            "Often silently overwrites missing totals with estimated line item sums without audit warnings.",
            "Derives calculated fallback from line items while strictly preserving the distinction between printed and calculated values."
        ],
        [
            "Ledger Integration",
            "Manual side-by-side visual cross-checking across spreadsheets.",
            "Rigid column templates requiring tedious manual header re-naming before import.",
            "Automated header auto-mapping using synonym dictionaries and debit/credit dominance content heuristics."
        ],
        [
            "Reconciliation Mechanism",
            "End-of-month manual tick-marking; takes days or weeks to reconcile ledger batches.",
            "Binary matched/unmatched status flags; lacks detailed discrepancy breakdowns.",
            "Automated multi-tier 3-way matching (Exact Match, Amount Mismatch, Tax Mismatch, Duplicate, Missing) with resolution advice."
        ],
        [
            "Payment & Due Date Tracking",
            "Fragmented across separate spreadsheets; invoices must be re-entered in payment sheets.",
            "Infers payment status strictly from calendar due dates; marks settled invoices as overdue.",
            "Saved invoice record serves as single source of truth; evaluates recorded transactions to distinguish Paid on Time vs Paid Late."
        ],
        [
            "Anomaly / Error Detection",
            "Post-disbursement spot checks; fails to detect systemic fraud or duplicate invoices.",
            "Black-box neural network probability scores ('98% fraud') creating false alarms.",
            "Unsupervised Isolation Forest on 13-D feature space; non-alarmist risk ratings with human-readable financial explanations."
        ],
        [
            "Data Privacy & Security",
            "Paper files vulnerable to physical loss; spreadsheets shared without access control.",
            "Financial invoices uploaded to third-party cloud servers, risking corporate data exposure.",
            "Complete local execution; Bcrypt password hashing, HMAC-SHA256 JWT, and strict SQL multi-tenant isolation."
        ],
        [
            "Processing Latency",
            "10 to 20 minutes per invoice document.",
            "3 to 15 seconds per document (network latency + cloud queuing).",
            "45 to 120 milliseconds for vector PDFs; sub-second ledger reconciliation."
        ]
    ]
}

TECHNOLOGY_STACK_DATA = {
    "headers": ["Architecture Tier", "Component / Tool", "Version / Library", "Role & Engineering Purpose"],
    "col_widths": [1.4, 1.5, 1.6, 2.0],
    "rows": [
        ["Frontend UI", "React", "18.3.1", "Component-based declarative user interface and state management."],
        ["Frontend Build", "Vite", "5.4.21", "Next-generation frontend tooling, bundling, and hot module replacement."],
        ["Frontend Styling", "Tailwind CSS", "3.4.1", "Utility-first CSS framework for clean, minimal financial dashboard design."],
        ["Frontend Icons", "Lucide React", "0.344.0", "Clean, accessible iconography for financial metrics and status badges."],
        ["Frontend HTTP", "Axios", "1.6.8", "Promise-based HTTP client with Bearer token interceptors."],
        ["Backend API", "FastAPI", "0.115.11", "High-performance asynchronous Python web framework for RESTful endpoints."],
        ["ASGI Server", "Uvicorn", "0.34.0", "Lightning-fast ASGI web server implementation for Python."],
        ["Data Validation", "Pydantic", "2.10.6", "Robust schema definition, data validation, and serialization with type hints."],
        ["Persistence / ORM", "SQLAlchemy", "2.0.38", "Enterprise-grade Object Relational Mapper for relational database modeling."],
        ["Database Engine", "SQLite 3", "In-Process (WAL)", "Embedded relational database with Write-Ahead Logging and foreign key enforcement."],
        ["Document Parsing", "pdfplumber", "0.11.5", "Precise visual layout inspection and vector character stream extraction."],
        ["PDF Streaming", "pypdf", "5.3.1", "Low-level digital PDF document structure parsing and fallback text stream recovery."],
        ["PDF Rendering", "pypdfium2", "4.30.1", "Fast PDF rasterization engine for converting pages to images for OCR."],
        ["Optical Recognition", "pytesseract", "0.3.13", "Python wrapper for Tesseract 5.x OCR for scanned images and paper bills."],
        ["Image Processing", "Pillow (PIL)", "11.1.0", "Image preprocessing, contrast enhancement, and grayscaling for OCR."],
        ["Tabular Processing", "pandas", "2.2.3", "High-performance tabular data frame manipulation and Excel sheet parsing."],
        ["Spreadsheet Engine", "openpyxl", "3.1.5", "Reading and parsing Microsoft Excel (.xlsx) accounting ledger workbooks."],
        ["Machine Learning", "scikit-learn", "1.6.1", "Unsupervised Isolation Forest anomaly detection and RobustScaler normalization."],
        ["Numerical Computing", "NumPy", "2.2.3", "Multi-dimensional numeric array operations and vectorized math calculations."],
        ["Scientific Routines", "SciPy", "1.15.2", "Statistical distribution calculations and interquartile range evaluations."],
        ["Authentication", "python-jose", "3.3.0", "Cryptographic JSON Web Token (JWT) signing and HMAC-SHA256 verification."],
        ["Password Security", "passlib / bcrypt", "4.1.2", "Adaptive-cost cryptographic password hashing with unique salt generation."],
        ["Automated Testing", "pytest", "8.4.2", "Automated test suite framework with in-memory database test isolation."]
    ]
}

SYSTEM_ARCHITECTURE_LAYERS = {
    "headers": ["Architecture Tier", "Primary Modules", "Core Responsibilities & Data Transformations"],
    "col_widths": [1.4, 1.8, 3.3],
    "rows": [
        [
            "1. Presentation Tier (Client)",
            "Dashboard, Invoices, Ledger Reconciliation, Payment Deadlines, Reports, ML Screening",
            "Single Page Application built with React 18. Renders interactive summary cards, file upload dropzones, candidate field review forms, reconciliation comparison matrices, payment progress bars, and anomaly risk badges."
        ],
        [
            "2. Application & API Tier",
            "FastAPI Routers, Dependency Injection, Auth Middleware, Error Handlers",
            "Exposes 18 secure RESTful endpoints. Enforces JWT token validation, user authentication, multi-tenant database filtering (WHERE user_id = current_user.id), request schema validation via Pydantic v2, and OWASP formula injection escaping."
        ],
        [
            "3. Processing & Analytics Engine",
            "Extractor Service, Parser Service, Reconciliation Engine, ML Anomaly Service",
            "Executes multi-tier PDF/OCR text extraction, regex heuristics, arithmetic validation (Subtotal + Tax = Total), ledger column auto-mapping, 3-way reconciliation matching, and scikit-learn Isolation Forest anomaly estimation."
        ],
        [
            "4. Persistence & Storage Tier",
            "SQLite Database, SQLAlchemy ORM Models, Local Storage Vault",
            "Maintains 7 relational database tables (users, invoices, invoice_items, ledger_records, reconciliation_results, payments, audit_logs) with foreign key cascades. Stores uploaded files in secure user-isolated directories."
        ]
    ]
}

ASCII_ARCHITECTURE_DIAGRAM = """
+---------------------------------------------------------------------------------------+
|                               INVOICEIQ SYSTEM ARCHITECTURE                           |
+---------------------------------------------------------------------------------------+
|  PRESENTATION TIER (React 18 + Vite + Tailwind CSS SPA)                              |
|  - Dashboard (Overview & Verification Metrics)  - Invoice Upload & Review Form        |
|  - Ledger Records & Reconciliation Centre      - Payment Tracker & Due Date Deadlines|
|  - Isolation Forest ML Anomaly Screening UI     - Financial Analytics & Reports Export|
+-------------------------------------------+-------------------------------------------+
                                            | RESTful JSON API / JWT Bearer
                                            v
+---------------------------------------------------------------------------------------+
|  APPLICATION & API TIER (FastAPI + Uvicorn + Starlette + Pydantic v2)                 |
|  - /api/auth          - /api/invoices         - /api/reconciliation                   |
|  - /api/payments      - /api/anomalies        - /api/reports                          |
|  [Security: Bcrypt Hashing | JWT HMAC-SHA256 | Multi-Tenant SQL Isolation | CORS]     |
+-------------------------------------------+-------------------------------------------+
                                            | Service Layer Calls
                                            v
+---------------------------------------------------------------------------------------+
|  PROCESSING & ANALYTICS ENGINE TIER                                                  |
|  +------------------------+  +------------------------+  +--------------------------+ |
|  | Document Extraction    |  | Ledger Column Mapping  |  | 3-Way Reconciliation     | |
|  | - pdfplumber / pypdf   |  | - Synonym Dictionary   |  | - Exact & Discrepancies  | |
|  | - Tesseract 5.x OCR    |  | - Debit/Credit Dominant|  | - Tax & Duplicate Checks | |
|  | - Kerning Repair Regex |  | - Excel/CSV Ingestion  |  | - Resolution Guidance    | |
|  +------------------------+  +------------------------+  +--------------------------+ |
|  +----------------------------------------------------------------------------------+ |
|  | Machine Learning Anomaly Detection Engine (scikit-learn IsolationForest-v1.2)   | |
|  | - 13-D Numerical Feature Vector  - RobustScaler (Median/IQR) - Dynamic Contam.   | |
|  | - Non-Alarmist Risk Tiers (LOW, MEDIUM, HIGH)  - Explainable Evidence Generator   | |
|  +----------------------------------------------------------------------------------+ |
+-------------------------------------------+-------------------------------------------+
                                            | SQLAlchemy 2.0 ORM / Connection Pool
                                            v
+---------------------------------------------------------------------------------------+
|  DATA & PERSISTENCE TIER (In-Process SQLite 3 with WAL Mode + Local File Vault)      |
|  - users        - invoices       - invoice_items        - ledger_records              |
|  - payments     - audit_logs     - reconciliation_results (batches & items)           |
|  - Encrypted User File Storage: data/uploads/{user_id}/inv_<uuid4>.<ext>              |
+---------------------------------------------------------------------------------------+
"""

ASCII_WORKFLOW_DIAGRAM = """
+---------------------------------------------------------------------------------------+
|                          END-TO-END INVOICEIQ PROCESSING WORKFLOW                     |
+---------------------------------------------------------------------------------------+
   [Step 1: Document Ingestion]
   User uploads PDF, PNG, or JPEG invoice file via drag-and-drop web UI.
              │
              ▼
   [Step 2: Dual Extraction Pipeline]
   Inspect text layer: Vector PDF? --> Extract text via pdfplumber / pypdf.
                       Scanned doc? --> Rasterize with pypdfium2 & run Tesseract OCR.
              │
              ▼
   [Step 3: Fused Stream Repair & Heuristic Parsing]
   clean_merged_text() resolves character kerning. Regular expressions extract:
   Invoice No, Dates, Vendor/Customer Details, GSTIN, Taxes, Subtotal, Line Items.
              │
              ▼
   [Step 4: Grand Total Resolution & Arithmetic Check]
   Printed Total Detected? ────> Check Subtotal + Tax = Total. Flag if discrepant.
              │ (No)
              ▼
   Calculate Fallback Total: Sum(Line Items) + Tax - Discounts.
   Assign CALCULATED confidence & issue user verification notice.
              │
              ▼
   [Step 5: User Verification & Single Source of Truth Save]
   User reviews candidate fields in UI form. Upon save, record is committed to
   'invoices' table as authoritative single source of truth.
              │
              ├───────────────────────────────────┐
              ▼                                   ▼
   [Step 6: Payment Lifecycle Tracking]     [Step 7: Ledger Ingestion & Auto-Mapping]
   Record full or partial disbursements.    User uploads accounting ledger CSV/XLSX.
   Compute remaining balance.               Synonym dict maps: Voucher->invoice_number,
   Set status: Paid on Time / Paid Late     Debit->total_amount, Payee->vendor_name.
   / Overdue / Partially Paid.                            │
              │                                           ▼
              │                             [Step 8: 3-Way Reconciliation]
              │                             Compare Invoices vs Ledger vs Payments.
              │                             Tiers: EXACT_MATCH, AMOUNT_MISMATCH,
              │                             TAX_MISMATCH, DUPLICATE, MISSING.
              │                                           │
              └───────────────────┬───────────────────────┘
                                  ▼
   [Step 9: Isolation Forest Anomaly Screening]
   User triggers ML assessment (requires N >= 5 invoices).
   Extract 13-D feature vector -> RobustScaler -> IsolationForest(n=100).
   Assign Risk Level (LOW, MEDIUM, HIGH) & generate human-readable explanation.
                                  │
                                  ▼
   [Step 10: Executive Reporting & Audit Export]
   Real-time dashboard updates total expenses, processed counts, and mismatches.
   Export sanitized CSV reports (with OWASP formula injection protection).
"""

DATASET_DEMO_TABLE = {
    "headers": ["Invoice Number", "Vendor Name", "Invoice Date", "Due Date", "Total Amount", "Payment State", "Showcase Scenario / Purpose"],
    "col_widths": [1.1, 1.4, 0.9, 0.9, 0.9, 0.9, 1.4],
    "rows": [
        ["INV-DEMO-001", "Apex Cloud Infrastructure", "Today - 5d", "Today + 12d", "$450.00", "Unpaid", "Normal upcoming invoice due in 12 days."],
        ["INV-DEMO-002", "Acme Office Supplies", "Today - 10d", "Today + 4d", "$620.00", "Partially Paid", "Deposit paid ($250.00); balance ($370.00) due soon."],
        ["INV-DEMO-003", "FastTrack Courier", "Today - 35d", "Today - 10d", "$850.00", "Paid on Time", "Fully settled before due date; NOT overdue."],
        ["INV-DEMO-004", "Global Telecom Services", "Today - 45d", "Today - 14d", "$320.00", "Overdue", "Due date passed 14 days ago; no payment recorded."],
        ["INV-DEMO-005", "Precision Hardware Tools", "Today - 8d", "None", "$175.00", "Unpaid", "No due date specified; must not be marked overdue."],
        ["INV-DEMO-006", "Apex Cloud Infrastructure", "Today - 65d", "Today - 35d", "$420.00", "Paid on Time", "Historical baseline 1 for vendor spending median."],
        ["INV-DEMO-007", "Apex Cloud Infrastructure", "Today - 95d", "Today - 65d", "$460.00", "Paid on Time", "Historical baseline 2 for vendor spending median."],
        ["INV-DEMO-008", "Apex Cloud Infrastructure", "Today - 3d", "Today + 25d", "$12,850.00", "Unpaid", "Extreme statistical outlier (GPU cluster; 28x median)."],
        ["INV-DEMO-009", "Acme Office Supplies", "Today - 40d", "Today - 10d", "$590.00", "Paid on Time", "Historical baseline 2 for office supply median."],
        ["INV-DEMO-010", "FastTrack Courier", "Today - 14d", "Today + 1d", "$780.00", "Unpaid", "Urgent deadline due tomorrow (within 7 days)."]
    ]
}

DATA_PROVENANCE_TABLE = {
    "headers": ["Field / Dimension", "Stated (Printed) Total", "Calculated Fallback Total", "User-Corrected Total"],
    "col_widths": [1.4, 1.7, 1.7, 1.7],
    "rows": [
        [
            "Primary Source",
            "Extracted directly from document text stream via printed grand total regular expressions.",
            "Algorithmically derived: Sum(Line Item Amounts) + Tax Amount - Discounts.",
            "Manually entered or adjusted by the human reviewer in the verification form."
        ],
        [
            "Confidence Level",
            "HIGH (exact keyword match) or MEDIUM (positional proximity).",
            "CALCULATED (derived mathematically when printed total is missing).",
            "MANUAL / AUDITED (explicitly confirmed by authorized user)."
        ],
        [
            "Arithmetic Verification",
            "Cross-checked against Subtotal + Tax. Mismatches generate warning flags.",
            "Guaranteed mathematically consistent with extracted line items and taxes.",
            "Subject to human judgment; system validates non-negative bounds."
        ],
        [
            "Audit Trail Display",
            "Displayed as the primary official total with confidence badge.",
            "Accompanied by an explicit UI callout: 'Total derived from line items'.",
            "Stored with audit timestamp and reviewer ID in audit_logs table."
        ]
    ]
}
