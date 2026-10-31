# InvoiceIQ — Known Limitations & Future Architecture Roadmap

## 1. Engineering Transparency & Scope

Every mature software project involves deliberate trade-offs between implementation complexity, dependencies, security boundaries, and runtime requirements. This document provides an honest, transparent evaluation of current architectural limitations in InvoiceIQ, why those trade-offs were made, and how they would be addressed in high-scale enterprise environments.

---

## 2. Document Extraction & OCR Boundaries

### Current Architecture
InvoiceIQ uses an offline, privacy-first extraction pipeline combining `pdfplumber` (for vector text extraction) and `pytesseract` (Tesseract 5.x OCR for scanned images/PDFs), followed by deterministic regex heuristic pattern matching.

### Known Limitations
1. **Handwritten Invoices & Receipts:**
   - Tesseract performs best on high-contrast, printed typography. Handwritten notes, receipt slips, or degraded thermal receipts yield lower character confidence scores.
2. **Multi-Column or Non-Standard Tabular Layouts:**
   - Complex nested tables without standard column lines or invoices with scattered text blocks across multiple columns may result in misaligned line-item extraction.
3. **Multi-Lingual Non-Latin Invoices:**
   - The default configuration targets English-language invoicing formats and international date standards. While UTF-8 is supported throughout, OCR accuracy decreases for scripts without installed Tesseract language packs (e.g., CJK, Arabic).

### Production Roadmap & Upgrades
- **Cloud Document AI Integration:** In a cloud deployment, this pipeline can be augmented with a pluggable adapter for **Google Cloud Document AI** or **AWS Textract** for enterprise-grade table recognition and handwriting parsing.
- **Multimodal LLM Verification:** An optional secondary validation stage using lightweight vision models (e.g., Gemini Flash) for fuzzy layout interpretation.

---

## 3. Machine Learning Anomaly Detection Boundaries

### Current Architecture
InvoiceIQ implements an unsupervised **Isolation Forest** model (`scikit-learn`) utilizing multi-dimensional feature vectors (normalized total, tax ratio, log-transformed amounts, vendor deviation factor, account median comparison).

### Known Limitations
1. **Cold-Start Sample Size:**
   - Unsupervised statistical models require sufficient historical data points to establish a baseline distribution. Accounts with fewer than 3 invoices are marked `INSUFFICIENT_DATA`.
   - Optimal statistical anomaly sensitivity typically begins once an account reaches 10–20 invoices.
2. **Sparse Vendor History:**
   - If an account purchases from 10 different vendors only once, the vendor-specific deviation cannot establish a vendor-level median. The engine gracefully falls back to account-wide statistical medians, but cannot detect vendor-specific drift.
3. **Statistical Outlier vs. Malicious Intent:**
   - Isolation Forest detects *statistical abnormalities* (e.g., a $12,850 GPU cluster invoice when the vendor typical bill is $440). It cannot determine whether an expenditure was authorized by management or fraudulent. Human-in-the-loop review remains essential.

### Production Roadmap & Upgrades
- **Active Learning Feedback Loop:** Allow users to mark flagged anomalies as "Approved / Expected" or "Confirmed Error", using feedback to calibrate the isolation boundary or train a semi-supervised classifier.
- **Industry Benchmark Priors:** Incorporate anonymized industry-standard spending distributions to mitigate cold-start limitations for new accounts.

---

## 4. Database Concurrency & Storage Scalability

### Current Architecture
InvoiceIQ operates on **SQLite 3** with WAL (Write-Ahead Logging) mode and connection pools configured in SQLAlchemy 2.0. Uploaded files are stored in user-isolated local disk directories (`backend/data/uploads/{user_id}/`).

### Known Limitations
1. **SQLite Write Concurrency:**
   - While SQLite supports high read concurrency in WAL mode, write operations serialize via database-level locks. For concurrent enterprise deployments with dozens of simultaneous accounts payable clerks writing payments, SQLite may experience lock contention.
2. **Local Filesystem Storage:**
   - Local disk storage means invoice files are tied to the specific server host. In containerized (Docker / Kubernetes) deployments, server restarts or multi-pod autoscaling requires shared volume mounts.

### Production Roadmap & Upgrades
- **PostgreSQL Migration:** The entire database tier is built on standard SQLAlchemy ORM models and Alembic migrations. Migrating to PostgreSQL or Amazon RDS requires simply updating `DATABASE_URL` in `.env` without altering application code.
- **Object Storage Adapter (S3 / GCS):** Refactor the storage utility (`app/utils/storage.py`) to stream uploads to AWS S3, Google Cloud Storage, or Azure Blob Storage with pre-signed URLs.

---

## 5. Notification & Background Task Boundaries

### Current Architecture
Deadlines, overdue alerts, and anomaly indicators are calculated dynamically on-demand when users access the dashboard or deadline views.

### Known Limitations
1. **No External Push Notifications:**
   - The application does not currently dispatch external email (e.g., SendGrid/SES) or SMS reminders for upcoming payment deadlines.
2. **Synchronous Extraction:**
   - Document uploads are processed synchronously within the HTTP request cycle. While standard 1-page invoices process in 1–2 seconds, multi-page PDFs (10+ pages) may lead to prolonged HTTP response times.

### Production Roadmap & Upgrades
- **Asynchronous Task Queue (Celery / Redis / BackgroundTasks):** Offload document OCR and extraction to background Celery workers, notifying the user via WebSockets or polling when processing completes.
- **Automated Email Reminders:** Scheduled cron tasks dispatching daily/weekly payment reminder digests to accounts payable managers.

---

## 6. Summary Matrix

| Domain | Current Local Implementation | Enterprise Target State | Effort to Upgrade |
| :--- | :--- | :--- | :--- |
| **Database** | SQLite with WAL mode | PostgreSQL (AWS RDS / Cloud SQL) | Very Low (Config change) |
| **File Storage** | Local user-isolated directories | AWS S3 / Cloud Storage buckets | Low (Pluggable storage provider) |
| **OCR / Parsing** | `pdfplumber` + Tesseract 5.x | Google Cloud Document AI / Textract | Medium (Service adapter) |
| **Background Jobs** | In-process synchronous | Celery + Redis workers | Medium (Worker queue setup) |
| **Alerting** | In-app dashboard indicators | Email (SendGrid) + Webhooks | Low (SMTP / API integration) |
| **ML Engine** | Isolation Forest + Rationale | Isolation Forest + Active Feedback | Medium (Labeling UI & weights) |
