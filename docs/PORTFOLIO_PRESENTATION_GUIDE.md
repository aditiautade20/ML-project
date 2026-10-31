# InvoiceIQ — Portfolio Presentation & Screenshot Capture Guide

This guide outlines how to capture high-impact screenshots and present InvoiceIQ effectively in portfolios, case studies, GitHub repositories, and live interviews.

---

## 1. Environment Preparation for Screen Capture

To ensure screenshots look clean, crisp, and professional:
1. **Screen Resolution:** Recommended browser window size is **1440 × 900** or **1920 × 1080** at 100% zoom (do not use browser zoom scaling).
2. **Browser Theme:** Use a clean browser profile without visible extension icons or cluttered bookmarks bars.
3. **Pristine Demo Data:** Before capturing, reset the demo data to ensure all 10 curated test fixtures are populated:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\seed_demo.ps1
   ```
4. **Login:** Navigate to `http://localhost:5173/login`, click **"Fill Demo Credentials"**, and log in.

---

## 2. Screenshot Inventory & Composition

Capture the following 6 key views:

### Screenshot 1: Executive Analytics Dashboard
- **URL:** `http://localhost:5173/dashboard`
- **What to Frame:** The full dashboard including:
  - Top 5 KPI metric cards (*Total Invoiced, Total Paid, Remaining Balance, Overdue, Anomalies*).
  - The monthly financial trend bar chart.
  - The recent invoice and payment activity tables.
- **Caption for Portfolio:** *"Executive Analytics Dashboard featuring real-time financial KPI cards, monthly cash outflow trends, and urgent action indicators."*

### Screenshot 2: Invoice Management & Filtering
- **URL:** `http://localhost:5173/invoices`
- **What to Frame:** The invoice table showing multiple invoice states:
  - Search bar with a filter applied (or all 10 demo invoices).
  - Visible status badges: Green `PAID`, Amber `PARTIAL`, Red `OVERDUE`, Slate `UNPAID`.
  - Financial columns displaying exact Total, Amount Paid, and Balance Due.
- **Caption for Portfolio:** *"Centralized Invoice Ledger with dynamic status resolution, search, and two-decimal accounting accuracy."*

### Screenshot 3: Payment Tracker & Overpayment Guard
- **URL:** `http://localhost:5173/payments`
- **What to Frame:** The payment management screen for `INV-DEMO-002`:
  - The historical payment ledger showing initial partial payment of `$250.00`.
  - The balance calculation showing `$370.00` remaining.
  - The payment entry modal/form showing method selection and reference ID.
- **Caption for Portfolio:** *"Multi-Tranche Payment Tracker with strict server-side overpayment prevention and transaction reference logging."*

### Screenshot 4: Payment Deadlines & Smart Priority Queues
- **URL:** `http://localhost:5173/deadlines`
- **What to Frame:** The deadline categorization layout:
  - The Red **Overdue** queue highlighting past-due unpaid invoices.
  - The Amber **Due in ≤ 7 Days** queue highlighting imminent obligations.
  - The Slate **No Due Date** queue showing graceful handling of invoices without strict payment terms.
- **Caption for Portfolio:** *"Smart Payment Deadline Tracker prioritizing urgent accounts payable obligations to eliminate late fees."*

### Screenshot 5: Machine Learning Anomaly Detection & Explainability
- **URL:** `http://localhost:5173/anomalies`
- **What to Frame:** The ML screening interface:
  - The summary banner (*10 Invoices Evaluated • 1 Potential Outlier Identified*).
  - The highlighted anomaly card for `INV-DEMO-008` (Apex Cloud Infrastructure - `$12,850.00`).
  - The natural language explanation block explaining the 28.2x deviation against vendor history.
- **Caption for Portfolio:** *"Explainable ML Anomaly Detection powered by scikit-learn Isolation Forest with human-readable diagnostic explanations."*

### Screenshot 6: Financial Reports & Secure Export
- **URL:** `http://localhost:5173/reports`
- **What to Frame:** The reporting view:
  - Date range filters and top vendor distribution breakdown.
  - Export action buttons (*Export CSV* with formula injection protection and *Download PDF Summary*).
- **Caption for Portfolio:** *"Financial Reporting and Audit-Ready Export Suite with automated CSV formula injection escaping and executive PDF generation."*

---

## 3. Portfolio Case Study Talking Points

When describing InvoiceIQ on your portfolio website or resume:

- **Key Highlights:**
  - *"Engineered an enterprise financial management web platform from scratch using FastAPI, React 18, Vite, and Tailwind CSS."*
  - *"Designed an explainable machine learning anomaly detection pipeline using scikit-learn Isolation Forest to screen invoices for statistical spending outliers, providing natural language explanations for human review."*
  - *"Built an offline document ingestion pipeline combining pdfplumber and Tesseract OCR with heuristic regex parsing and human-in-the-loop validation."*
  - *"Implemented a strict two-decimal payment ledger with automated partial payment tracking, overpayment guards, dynamic overdue resolution, and RFC 4180 CSV export protected against formula injection (CSV/DDE)."*
  - *"Achieved 100% test pass rate across 58 automated integration and security tests, verifying multi-user data isolation, password hashing (bcrypt), and JWT session management."*

---

## 4. Teardown / Reset Instructions

When finished recording or capturing screenshots, reset or clean up demo data at any time:
```powershell
powershell -ExecutionPolicy Bypass -File .\seed_demo.ps1 -Clean
```
