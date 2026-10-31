# InvoiceIQ — 5–7 Minute Professional Demonstration Script

This script provides a structured, repeatable walkthrough for presenting InvoiceIQ to recruiters, engineering managers, stakeholders, or technical interviewers.

---

## 1. Demo Setup & Quick Start

### Step 1: Launch Application
Run the startup script from the root directory in PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File .\start_invoiceiq.ps1
```
- **Backend API:** `http://127.0.0.1:8000`
- **Frontend UI:** `http://127.0.0.1:5173`
- **Swagger Docs:** `http://127.0.0.1:8000/docs`

### Step 2: Populate Showcase Demo Data
Ensure the isolated showcase account is populated with pristine demo records:
```powershell
powershell -ExecutionPolicy Bypass -File .\seed_demo.ps1
```

### Demo Account Credentials
- **Email:** `demo@invoiceiq.local`
- **Password:** `DemoUser123!`
- *(Or simply click the **"Fill Demo Credentials"** button on the Login page)*

---

## 2. Step-by-Step Presentation Walkthrough

### Act 1: The Executive Dashboard (Time: 0:00 – 0:45)
**Objective:** Showcase high-level business intelligence, real-time KPI aggregation, and cash-flow visibility.

1. **Sign In:** Navigate to `http://127.0.0.1:5173/login`. Click **"Fill Demo Credentials"**, then click **Sign In**.
2. **Key Metric Cards:** Direct the audience's attention to the top KPI grid:
   - **Total Invoiced:** Total spending across all invoices.
   - **Total Paid:** Actual settled cash outflow with percentage progress bar.
   - **Outstanding Balance:** Total outstanding accounts payable liabilities.
   - **Overdue Invoices:** Invoices past due with unpaid balances.
   - **Due in 7 Days:** Immediate upcoming liquidity requirements.
   - **Potential Anomalies:** ML anomaly indicator flagging unusual statistical transactions.
3. **Monthly Financial Trends:**
   - Point out the 6-month continuous cash flow bar chart comparing Invoiced commitments vs Settled payments.

*Presenter Talking Point:*
> *"InvoiceIQ provides instant financial transparency for leadership. Right from the moment you log in, business owners know their cash liabilities, impending deadlines, and spending anomalies without manual spreadsheet calculations."*

---

### Act 2: Invoice Upload & Automated Extraction (Time: 0:45 – 1:30)
**Objective:** Demonstrate document parsing, candidate value extraction, and human-in-the-loop review.

1. **Navigate to "Invoices":**
   - Click **Invoices** in the sidebar.
   - Point out the filterable table displaying invoices by status (`PAID`, `PARTIAL`, `OVERDUE`, `UNPAID`).
2. **Upload Sample Invoice:**
   - Click **Upload Invoice**.
   - Select or drag-and-drop `demo_samples/sample_invoice.pdf` (BrightDesk Enterprise Solutions Ltd.).
3. **Human-in-the-Loop Review Modal:**
   - Show how the backend extracted:
     - **Supplier:** BrightDesk Enterprise Solutions Ltd.
     - **Invoice #:** `INV-2026-BD88`
     - **Subtotal:** `$850.00`
     - **Tax (GST):** `$85.00`
     - **Total Amount:** `$935.00`
     - **Due Date:** Automatically extracted 30-day term.
   - Explain that fields are never fabricated if missing; financial controllers verify values before committing to the database.
   - Click **Save Invoice**.

*Presenter Talking Point:*
> *"Data entry errors are eliminated through automated extraction using pdfplumber and regex heuristics, but financial control remains in human hands before records hit the general ledger."*

---

### Act 3: Partial Payment Tracking & Overpayment Guard (Time: 1:30 – 2:15)
**Objective:** Demonstrate strict decimal arithmetic, partial payment tranches, and overpayment prevention.

1. **Navigate to "Payment Tracker":**
   - Click **Payment Tracker** in the sidebar.
   - Point out invoice `INV-DEMO-002` (Acme Office Supplies).
   - Show the financial breakdown: Original Total: `$620.00`, Total Paid: `$250.00`, Remaining Balance: `$370.00`.
2. **Demonstrate Overpayment Guard (Security & Financial Integrity):**
   - Click **Record Payment** on `INV-DEMO-002`.
   - Enter an amount of `$500.00` (which exceeds the $370.00 remaining balance).
   - Click **Submit Payment**.
   - Show the immediate validation rejection: *"Payment amount cannot exceed remaining balance of $370.00."*
3. **Record a Valid Partial Payment:**
   - Enter `$170.00`, select **Bank Transfer**, enter reference `TXN-DEMO-552`, and submit.
   - Point out that the ledger updates instantly: Balance Due decreases to `$200.00`, and status remains `PARTIALLY_PAID`.

*Presenter Talking Point:*
> *"Financial ledgers cannot permit floating-point rounding discrepancies or accidental overpayments. InvoiceIQ enforces exact two-decimal arithmetic at both the schema and service layers."*

---

### Act 4: Payment Deadlines & Smart Categorization (Time: 2:15 – 2:45)
**Objective:** Show working capital prioritization and calendar rules.

1. **Navigate to "Payment Deadlines":**
   - Click **Payment Deadlines** in the sidebar.
2. **Explain the 4 Smart Buckets:**
   - **Overdue:** Highlight `INV-DEMO-004` (Global Telecom Services) — past due date with unpaid balance.
   - **Due in Next 7 Days:** Highlight near-term obligations prioritizing cash liquidity.
   - **Due Later:** Long-term commitments.
   - **No Due Date:** Highlight `INV-DEMO-005` (Precision Hardware Tools) — handled gracefully without erroneous overdue flags.
   - Mention that fully paid invoices are cleanly separated and never flagged as overdue regardless of original due date.

*Presenter Talking Point:*
> *"In accounts payable, missing a due date incurs penalties, while paying too early hurts liquidity. InvoiceIQ automatically buckets liabilities into actionable priority queues."*

---

### Act 5: Machine Learning Anomaly Detection (Time: 2:45 – 3:30)
**Objective:** Demonstrate explainable, unsupervised machine learning for fraud and anomaly screening.

1. **Navigate to "Anomaly Detection":**
   - Click **Anomaly Detection** in the sidebar.
2. **Review the ML Screening Dashboard:**
   - Point out the evaluation status: **10 Invoices Evaluated**, **1 Potential Outlier Identified**.
3. **Inspect the Flagged Outlier (`INV-DEMO-008`):**
   - Vendor: **Apex Cloud Infrastructure**
   - Invoice Total: **$12,850.00**
   - Status Badge: Red **POTENTIALLY UNUSUAL**
4. **Highlight the Natural Language Explanation:**
   - Read the generated rationale:
     > *"Total amount ($12,850.00) is 28.2x higher than the historical median ($455.00) for vendor 'Apex Cloud Infrastructure'. Total amount is 24.5x higher than your overall median invoice size ($525.00)."*
5. **Explain the ML Architecture:**
   - Explain that it uses an **Isolation Forest** (100 trees) with a **RobustScaler** across 13 engineered features.
   - Emphasize cold-start safety: requires ≥ 5 baseline invoices to prevent false positives on statistical noise.
   - Show the user action: mark as **Reviewed / Normal** or **Confirmed Issue**.

*Presenter Talking Point:*
> *"Most ML features are black boxes. InvoiceIQ couples unsupervised Isolation Forest scoring with deterministic diagnostic explainability, giving accountants clear reasons why an invoice was flagged for secondary review."*

---

### Act 6: Reconciliation Centre — 4-Way Financial Verification (Time: 3:30 – 5:00)
**Objective:** Demonstrate automated reconciliation against external General Ledgers and Bank Statements with exact matches, mismatches, duplicates, and 1-click settlement.

1. **Navigate to "Reconciliation":**
   - Click **Reconciliation** in the sidebar.
2. **Demonstrate Accounting Ledger Reconciliation:**
   - Select **Accounting Ledger** mode.
   - Upload `demo_samples/accounting_ledger_sample.csv` (or `.xlsx`).
   - Show the **Column Mapping & Data Preview** screen: intelligent auto-mapping of Date, Reference, Vendor, and Amount columns.
   - Click **Run Reconciliation**.
   - Walk through the categorized result tabs:
     - **Exact Match:** `INV-DEMO-001` (Apex Cloud, $450.00) matched within tolerance.
     - **Amount Mismatch:** `INV-DEMO-002` (Acme Office Supplies) — Ledger shows $650.00 while the actual invoice was $620.00 (+$30.00 discrepancy flagged).
     - **Duplicate Ledger Row:** `INV-DEMO-005` (Precision Hardware Tools) entered twice in the ledger.
     - **Missing in Invoices (Ghost Liability):** `INV-DEMO-999` ($1,200.00) exists on ledger but no invoice exists in the system.
3. **Demonstrate Bank Statement Reconciliation & 1-Click Settlement:**
   - Select **Bank Statement** mode.
   - Upload `demo_samples/bank_statement_sample.csv`.
   - Show the directionality-aware parsing of cleared withdrawals/debits.
   - Walk through the results:
     - **Matched:** `WIRE-00391` ($400.00) reconciled against recorded payment.
     - **Unmatched Debit:** `POS-882910` ($85.50 Corner Cafe & Snacks).
     - **Duplicate Bank Charge:** `CHQ-44912` debited twice on the statement.
     - **Proposed Settlement Candidate:** `INV-DEMO-001` (Apex Cloud, $450.00).
   - Point out the 1-click **"Confirm Payment"** button:
     - Explain that bank uploads NEVER alter invoice balances silently.
     - Click **Confirm Payment** to record the cleared settlement safely.

*Presenter Talking Point:*
> *"Month-end reconciliation usually takes days of manual cross-referencing. InvoiceIQ automates 2-way and 4-way matching with penny tolerance, while maintaining strict financial auditability by requiring human confirmation before mutating payment records."*

---

### Act 7: Reports, Analytics & Secure Export (Time: 5:00 – 5:45)
**Objective:** Showcase business intelligence, audit trails, and spreadsheet security protections.

1. **Navigate to "Reports":**
   - Click **Reports** in the sidebar.
2. **Interactive Filters:**
   - Demonstrate quick range presets (This Month, Last Month, This Year, All Time) and custom date ranges.
   - Review the vendor performance breakdown table.
3. **Export CSV with DDE Formula Protection:**
   - Click **Export Invoices (CSV)**.
   - *Technical highlight:* Mention that all exported CSVs feature automated spreadsheet formula injection escaping (`=`, `@`, `+`, `-`, `\t`, `\r` sanitization) to protect financial analysts from CSV macro exploits.
4. **Export Executive PDF Summary:**
   - Click **Download PDF Summary**.
   - Show the formatted ReportLab PDF with corporate headers, executive summary metrics, and status breakdowns.

---

### Act 8: Safe Cleanup & Teardown (Time: 5:45 – 6:00)
**Objective:** Show that demo data is completely isolated and cleanly removable.

1. **Run Cleaner:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\seed_demo.ps1 -Clean
   ```
2. **Verification:**
   - Demo user and all associated invoices, payments, and reconciliation batches are cleanly removed via foreign key cascades.
   - Real user data in the database remains 100% untouched.

---

## 3. Summary of Key Talking Points

| Feature | Key Architecture Point to Mention |
|---|---|
| **Security** | 100% tenant isolation (`user_id == current_user.id`), bcrypt 12 rounds, JWT HS256, magic byte file validation. |
| **Financial Integrity** | Exact two-decimal `Decimal` arithmetic, overpayment prevention, no phantom balance updates. |
| **Document AI** | Native text extraction (`pdfplumber`/`pypdf`), regex heuristics, human-in-the-loop verification. |
| **Machine Learning** | Unsupervised Isolation Forest (100 trees), RobustScaler, 13 features, natural language explanations, cold-start safety (≥5 records). |
| **Reconciliation** | 4-way cross-verification, intelligent header auto-mapping, ±$0.05 penny tolerance, 1-click confirmed payments. |
| **Spreadsheet Safety** | Automatic DDE formula injection escaping on all CSV exports. |
