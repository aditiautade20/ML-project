# InvoiceIQ Showcase — Demo Samples & Verification Guide

This directory contains curated, fictional demo sample files designed for live recruiter demonstrations, portfolio showcases, and end-to-end feature verification.

None of these files contain real financial, personal, or proprietary data. They are designed to trigger exact matches, discrepancies, duplicates, and missing records in the **Invoice Extraction** and **Reconciliation Centre** modules.

---

## 1. Directory Inventory

| File Name | Format | Primary Purpose & Module | Key Scenarios Demonstrated |
|---|---|---|---|
| `sample_invoice.pdf` | Vector PDF | Invoice Upload & Automated Extraction | Text-stream PDF, tax calculation (Subtotal + GST = Total), multi-item table, vendor and due date extraction. |
| `accounting_ledger_sample.csv` | CSV | General Ledger Reconciliation | Exact match, amount mismatch, duplicate ledger rows, missing invoice record. |
| `accounting_ledger_sample.xlsx` | Excel (XLSX) | General Ledger Reconciliation | Excel parsing, intelligent header auto-mapping, penny tolerance testing. |
| `bank_statement_sample.csv` | CSV | Bank Statement Reconciliation | Debit/withdrawal parsing, settled match, candidate settlement proposal, unmatched bank debit, duplicate bank charge. |
| `bank_statement_sample.xlsx` | Excel (XLSX) | Bank Statement Reconciliation | Multi-column bank statement format, description reference extraction, 1-click payment confirmation. |

---

## 2. Sample File Details & Expected Behavior

### A. `sample_invoice.pdf` (Invoice Document)
- **Supplier:** BrightDesk Enterprise Solutions Ltd.
- **Invoice Number:** `INV-2026-BD88`
- **Invoice Date:** `2026-10-15`
- **Due Date:** `2026-11-15`
- **Subtotal:** `$850.00`
- **GST (10%):** `$85.00`
- **Grand Total:** `$935.00` (USD)
- **Line Items:** 
  - Ergonomic Dual-Monitor Arms (2x @ $175.00 = $350.00)
  - Standing Desk Motorized Frame (1x @ $500.00 = $500.00)
- **Expected Flow in Demo:**
  1. Upload in **Invoices** page (`/invoices`).
  2. The automated parser extracts `BrightDesk Enterprise Solutions Ltd.`, `INV-2026-BD88`, `$850.00`, `$85.00`, and `$935.00`.
  3. The **Review & Save Invoice** modal displays extracted values for human verification before saving to the database.

---

### B. `accounting_ledger_sample.csv` / `.xlsx` (General Ledger)
This dataset simulates an export from ERP/accounting software (e.g. QuickBooks, NetSuite, SAP) and reconciles against the seeded demo invoices:

| Row # | Invoice Ref | Vendor / Account | Ledger Amount | Seeded Invoice Total | Reconciled Status | Rationale |
|---|---|---|---|---|---|---|
| 1 | `INV-DEMO-001` | Apex Cloud Infrastructure | $450.00 | $450.00 | **Exact Match** | Amounts and references match exactly within tolerance. |
| 2 | `INV-DEMO-002` | Acme Office Supplies | $650.00 | $620.00 | **Amount Mismatch** | Ledger recorded $650.00 while the actual invoice was $620.00 (+$30.00 discrepancy). |
| 3 | `INV-DEMO-003` | Stellar Software Consulting | $850.00 | $850.00 | **Exact Match** | Multi-tranche payment matches ledger entry. |
| 4 | `INV-DEMO-004` | Global Telecom Services | $320.00 | $320.00 | **Exact Match** | Overdue invoice correctly reconciled against posted liability. |
| 5 | `INV-DEMO-005` | Precision Hardware Tools | $540.00 | $540.00 | **Duplicate Ledger Entry** | Row 5 and Row 6 both record `INV-DEMO-005` for $540.00. The engine flags the duplicate record. |
| 6 | `INV-DEMO-005` | Precision Hardware Tools | $540.00 | $540.00 | **Duplicate Ledger Entry** | Second instance of duplicate ledger entry. |
| 7 | `INV-DEMO-999` | Zenith Global Marketing | $1,200.00 | *None* | **Missing in Invoices (Ghost Liability)** | Entry exists on the ledger, but no corresponding invoice has been uploaded/registered in InvoiceIQ. |

---

### C. `bank_statement_sample.csv` / `.xlsx` (Bank Statement)
This dataset simulates an official bank statement export with debit/credit transactions:

| Date | Description / Reference | Withdrawal (Debit) | Matching Entity | Expected System Behavior |
|---|---|---|---|---|
| `2026-10-18` | `WIRE-00391 FastTrack Logistics Final` | $400.00 | Recorded Payment `WIRE-00391` | **Matched:** Reconciled against recorded payment for `INV-DEMO-006`. |
| `2026-10-20` | `ACH DEBIT - APEX CLOUD INV-DEMO-001` | $450.00 | Saved Invoice `INV-DEMO-001` (Unpaid) | **Proposed Settlement Candidate:** Invoice exists but payment was not yet recorded in InvoiceIQ. The UI presents a 1-click **"Confirm Payment"** button to safely record the payment. |
| `2026-10-21` | `POS-882910 CORNER CAFE & SNACKS` | $85.50 | *None* | **Unmatched Bank Debit:** Miscellaneous bank debit with no associated invoice or payment in the system. |
| `2026-10-22` | `CHQ-44912 Precision Hardware Part 1` | $175.00 | Bank Transaction Duplicate | **Duplicate Transaction:** Precision Hardware debited twice on the statement with identical references. |
| `2026-10-22` | `CHQ-44912 Precision Hardware Part 1` | $175.00 | Bank Transaction Duplicate | Duplicate flag raised for internal bank audit. |

---

## 3. How to Use These Samples During a Live Demo

1. **Reset Demo Data (Optional but Recommended):**
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\seed_demo.ps1
   ```
2. **Log In:**
   - Navigate to `http://127.0.0.1:5173/login`.
   - Click **"Fill Demo Credentials"** and sign in.
3. **Demonstrate Invoice Extraction:**
   - Go to **Invoices** (`/invoices`).
   - Click **"Upload Invoice"** and select `demo_samples/sample_invoice.pdf`.
   - Highlight the automatic parsing of vendor, total, and tax, followed by the human verification modal.
4. **Demonstrate Accounting Ledger Reconciliation:**
   - Go to **Reconciliation** (`/reconciliation`).
   - Click **"Accounting Ledger"** mode.
   - Upload `demo_samples/accounting_ledger_sample.csv` (or `.xlsx`).
   - Review the column mapping preview.
   - Click **"Run Reconciliation"**.
   - Review the categorized discrepancy tabs: **Matched (3)**, **Mismatches (1)**, **Duplicates (1)**, **Missing (1)**.
5. **Demonstrate Bank Statement Reconciliation & 1-Click Settlement:**
   - Switch to **"Bank Statement"** mode.
   - Upload `demo_samples/bank_statement_sample.csv`.
   - Point out `INV-DEMO-001` under proposed matches and click **"Confirm Payment"** to demonstrate human-in-the-loop settlement.
