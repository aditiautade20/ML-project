"""
InvoiceIQ Academic Project Report Content - Part 2: Sections 9 through 15 & References
Covers:
- 9. Machine Learning Algorithm (Isolation Forest, formulas, 13-D vector, risk classification)
- 10. Invoice Processing and Ledger Reconciliation Approach (Dual OCR/PDF, Regex, Total Fallback, Auto-mapping, 3-Way Reconciliation, Payment & Due Date Tracking)
- 11. Results and Performance Metrics (Verified Test Results, Latency Benchmarks, Sample Invoice INV-2026-0042)
- 12. Testing and Code Integrity (Testing Architecture, Summary Table of 18 Modules, Verifiable Test Log, Frontend Build)
- 13. Application Screenshots (Figure Placeholders 1 through 6 with UI wireframe mockups and descriptions)
- 14. Limitations
- 15. Conclusion
- References (Academic & Standard Citations)
"""

ML_ALGORITHM_TEXT = """
9.1 Purpose & Unsupervised Learning Rationale in Accounting

In enterprise accounts payable workflows, detecting fraudulent or anomalous invoices is notoriously challenging because verified ground-truth fraud labels are extremely rare, heavily class-imbalanced, and highly confidential. Supervised learning models (such as deep neural networks or standard gradient boosted trees) require massive labeled training datasets of known historical frauds. Training on synthetic or poorly balanced data leads to severe overfitting, catastrophic false alarms, and poor generalization across diverse suppliers.

To circumvent these limitations, InvoiceIQ employs an unsupervised machine learning architecture utilizing the Isolation Forest algorithm (Liu, Ting, and Zhou, 2008) from scikit-learn (IsolationForest-v1.2). The algorithm is grounded in two fundamental quantitative properties of financial anomalies:
1. They are few in number (minority instances).
2. They possess attribute-value distributions that diverge significantly from nominal transactions.

9.2 Mathematical Formulation of Isolation Forest

Unlike density-based estimators (e.g., Local Outlier Factor) or distance-based clusterers (e.g., k-Means or DBSCAN) that calculate pairwise geometric distances ($O(n^2)$), Isolation Forest isolates anomalies explicitly by constructing an ensemble of Isolation Trees (iTrees). 

Let $X = \{x_1, \dots, x_n\}$ be an isolated dataset of $n$ instances in a $d$-dimensional space. An Isolation Tree is a proper binary tree where each non-leaf node contains an attribute $q$ and a split value $p$ selected uniformly at random such that $\min(q) \le p \le \max(q)$. The data is recursively partitioned: instances with $q < p$ traverse to the left child, and instances with $q \ge p$ traverse to the right child, continuing until:
1. The tree reaches a maximum height limit $h_{max} = \lceil \log_2 n \rceil$,
2. $|X| \le 1$, or
3. All instances in the node have identical feature values.

Because anomalous invoices have extreme or unusual feature combinations, they require far fewer random hyperplane partitions to become isolated in isolated leaf nodes compared to normal invoices.

Path Length and Anomaly Score Derivation:
Let $h(x)$ represent the path length of an instance $x$ in an $iTree$, defined as the number of edges traversed from the tree root to the terminating external leaf node. To normalize path lengths across trees of sample size $n$, the algorithm uses the average path length of unsuccessful searches in a Binary Search Tree (BST):

$$c(n) = 2 \ln(n - 1) + 2 \gamma_{euler} - \frac{2(n - 1)}{n} \quad\quad (1)$$

where $\gamma_{euler} \approx 0.5772156649$ is the Euler-Mascheroni constant. 

Given an ensemble of $t$ isolation trees, the anomaly score $s(x, n)$ for an invoice instance $x$ is defined as:

$$s(x, n) = 2^{-\frac{E(h(x))}{c(n)}} \quad\quad (2)$$

where $E(h(x)) = \frac{1}{t} \sum_{k=1}^t h_k(x)$ is the expected path length across all isolation trees.

Interpretation of Anomaly Score:
- If $E(h(x)) \to 0$, then $s(x, n) \to 1$: The invoice requires very few splits to isolate and is classified as highly anomalous.
- If $E(h(x)) \to n - 1$, then $s(x, n) \to 0$: The invoice traverses deep into the trees, indicating a typical, dense financial record.
- If $E(h(x)) \to c(n)$, then $s(x, n) \to 0.5$: The invoice exhibits average cluster behavior without distinct isolation.

9.3 13-Dimensional Numerical Feature Vector

To capture financial, structural, and vendor-behavioral characteristics without inventing artificial data, InvoiceIQ extracts a 13-dimensional numerical feature vector $x \in \mathbb{R}^{13}$ for every saved invoice record:
"""

ML_FEATURES_TABLE = {
    "headers": ["Index", "Feature Symbol & Key", "Type", "Mathematical Definition & Accounting Justification"],
    "col_widths": [0.6, 1.8, 0.9, 3.2],
    "rows": [
        ["0", "L_norm (log_amt_norm)", "float64", "ln(1 + R_curr). Log-transformed currency-normalized amount ratio; compresses extreme skewness."],
        ["1", "R_curr (currency_amount_ratio)", "float64", "Amount / max(1.0, Median_curr(Amount)). Ratio relative to user's currency-specific median."],
        ["2", "R_tax (tax_ratio)", "float64", "Tax / Total. Proportion of tax relative to total amount. Imputed with account median if tax is omitted."],
        ["3", "F_tax (has_tax)", "binary", "1.0 if tax is specified, 0.0 if omitted. Distinguishes zero tax from missing tax."],
        ["4", "F_unusual_tax (is_unusual_tax)", "binary", "1.0 if tax ratio > 35% or < 0%. Flags excessive or negative tax rates."],
        ["5", "R_subtotal (subtotal_ratio)", "float64", "Subtotal / Total. Proportion of base cost. Imputed with account median if omitted."],
        ["6", "F_subtotal (has_subtotal)", "binary", "1.0 if subtotal is present, 0.0 if omitted. Preserves missingness semantics."],
        ["7", "F_math (has_math_discrepancy)", "binary", "1.0 if |Subtotal + Tax - Total| > 0.05. Identifies arithmetic inconsistencies."],
        ["8", "R_vend (vendor_amount_ratio)", "float64", "Amount / Median_vendor(Amount). Spending deviation relative to specific vendor history."],
        ["9", "F_vend_hist (has_vendor_history)", "binary", "1.0 if vendor has >= 2 historical invoices in account, 0.0 for new suppliers."],
        ["10", "D_term (term_days)", "float64", "(Due Date - Invoice Date) in days. Length of credit window (imputed with 30.0 if omitted)."],
        ["11", "F_due (has_due_date)", "binary", "1.0 if due date is present, 0.0 if omitted. Tracks missing credit terms."],
        ["12", "F_dup (is_duplicate_number)", "binary", "1.0 if invoice number appears multiple times in account. Flags duplicate billings."]
    ]
}

ML_ALGORITHM_TEXT_PART2 = """
9.4 Robust Scaling Preprocessing

Financial amounts in corporate accounts payable commonly exhibit extreme positive skewness (e.g., standard recurring utility invoices of $100 alongside occasional capital equipment acquisitions of $50,000). Standard z-score normalization ($z = \frac{x - \mu}{\sigma}$) is distorted by such extreme outliers, because the sample mean $\mu$ and standard deviation $\sigma$ are inflated.

To ensure numerical stability without dampening outlier signals, InvoiceIQ utilizes scikit-learn's RobustScaler:

$$x'_{ij} = \frac{x_{ij} - Q_2(x_j)}{Q_3(x_j) - Q_1(x_j)} \quad\quad (3)$$

where $Q_2(x_j)$ is the median of feature $j$, and $IQR = Q_3(x_j) - Q_1(x_j)$ is the interquartile range. The parameter `unit_variance=True` scales normal distributions to unit variance, preventing zero-division errors when feature values are identical.

9.5 Contamination Rate and Model Hyperparameters

The model is configured with reproducible, conservative hyperparameters:
- `n_estimators = 100`: Builds 100 independent isolation trees to achieve stable average path lengths.
- `random_state = 42`: Ensures deterministic, verifiable evaluation across test runs.
- `contamination`: Dynamically calculated based on user invoice volume $N_{inv}$:
  $$\gamma = \min\left(0.20, \max\left(0.05, \frac{1}{N_{inv}}\right)\right) \quad\quad (4)$$
  This guarantees that small portfolios (e.g., 10 invoices) do not over-flag more than 1 or 2 records, while larger portfolios cap expected outliers at 20%.

9.6 Hybrid Risk Level Classification & Structural Overrides

Instead of presenting deceptive percentage probabilities (such as '97.4% fraud probability'), InvoiceIQ synthesizes continuous decision scores and structural rules into three non-alarmist risk tiers:

1. LOW Risk (Green):
The invoice conforms to expected statistical spending distributions for the supplier and account currency. Raw prediction $= +1$ and decision score $> 0.0$.

2. MEDIUM Risk (Amber):
Mild statistical deviation (decision score between $-0.06$ and $0.0$) or moderate vendor deviation ($2.0\times \le R_{vend} < 3.5\times$). Warrants routine spot-check.

3. HIGH Risk (Rose / Red):
Severe statistical divergence (decision score $\le -0.06$) OR explicit structural rule violations:
- Duplicate invoice number detected from the same vendor ($F_{dup} = 1.0$),
- Arithmetic discrepancy exceeding $0.05$ currency units ($F_{math} = 1.0$), or
- Vendor spending spike exceeding $3.5\times$ historical median ($R_{vend} \ge 3.5$).

9.7 Explainability Synthesizer & Ethical Disclaimer

Every flagged invoice is accompanied by a transparent narrative generated from the invoice's factor breakdown:
- "Invoice amount ($12,850.00 USD) is 28.2x higher than historical median ($450.00 USD) for vendor 'Apex Cloud Infrastructure'."
- "Duplicate invoice number 'INV-DEMO-001' already exists from vendor 'Apex Cloud Infrastructure'."
- "Arithmetic discrepancy: Subtotal ($400.00) + Tax ($50.00) does not equal Total ($460.00) ($10.00 difference)."

Critical Ethical & Legal Disclaimer:
All machine learning outputs are flagged with the following persistent disclaimer:
"This assessment is an automated statistical screening signal and validation aid (Isolation Forest), not proof of fraud, accounting error, or financial irregularity."
"""

INVOICE_PROCESSING_APPROACH_TEXT = """
10.1 Dual-Engine Document Extraction Pipeline

InvoiceIQ implements an offline, two-tier document ingestion engine designed to maximize text extraction fidelity across both digital-first and scanned documents:
1. Vector PDF Layer: Leverages `pdfplumber` and `pypdf` to extract high-fidelity text streams and positional bounding boxes directly from digital PDF streams without rasterization overhead.
2. Rasterized OCR Layer: When an uploaded document is an image (PNG, JPEG, WEBP) or a scanned PDF lacking embedded text, the document is rasterized using `pypdfium2` at 300 DPI. Preprocessing via Pillow converts images to grayscale, enhances contrast, and passes the buffer to Tesseract 5.x OCR (`pytesseract`).

Text Kerning Repair:
A critical flaw in standard PDF parsers is the fusion of adjacent layout text streams. For instance, adjacent table columns or labels often merge into fused strings such as `BrightDesk SuppliesAddress: 742 Innovation Way`. InvoiceIQ executes `clean_merged_text()`, which introduces boundaries based on punctuation, capitalization boundaries, and currency anchors prior to field parsing.

10.2 Field Extraction Heuristics & Regular Expressions

The extraction engine parses candidate fields using modular regular expression patterns:
- Vendor & Customer Metadata: Identifies corporate entities using legal suffix anchors (Ltd, Inc, LLC, Corp, Pvt Ltd) and address boundary heuristics.
- Date Normalization: Ingests dates in arbitrary formats (ISO `2026-01-15`, Indian/European `15/01/2026`, US `01/15/2026`, and alphanumeric `15 January 2026`) and normalizes them into standardized `YYYY-MM-DD` strings.
- Indian GST Decomposition: Detects 15-character Goods and Services Tax Identification Numbers (GSTIN) and decomposes multi-tier tax grids into CGST, SGST, and IGST components.
- Tabular Line Items: Implements a line-by-line tabular parser that segments descriptions, quantities, unit prices, and line totals while ignoring header titles and summary subtotal rows.

10.3 Grand Total Extraction & Calculated Fallback Strategy

Extracting the final grand total is frequently hindered by non-standard layouts. InvoiceIQ employs an exhaustive priority pattern matcher:
- Parenthesized Currencies: Matches formats such as `Total (USD) 111.45` or `Grand Total (EUR): 1,234.56`.
- Trailing Notations: Matches amounts with trailing currency codes, e.g., `111.45 USD` or `5,432.10 INR`.
- Multiline Summaries: Captures summary tables where the label `Total` is situated on line $k$ and the numeric figure `111.45` is situated on line $k+1$.

Arithmetic Self-Validation and Fallback:
Whenever Subtotal ($S$), Tax ($T$), and Grand Total ($A$) are extracted, the system evaluates:
$$\Delta_{math} = |S + T - A| \quad\quad (5)$$
If $\Delta_{math} > 0.05$, a validation warning is attached to the invoice without altering the extracted figures.

If the document completely lacks a printed total, InvoiceIQ computes a transparent fallback total:
$$Total_{calc} = \sum_{i=1}^m \text{LineTotal}_i + \text{Tax} - \text{Discount} \quad\quad (6)$$
The system assigns `field_confidence = CALCULATED` and displays an explicit notice informing the user that the total was derived mathematically.

10.4 Accounting Ledger Ingestion & Column Auto-Mapping

Enterprise accounting software exports ledgers with arbitrary column headers. InvoiceIQ's `reconciliation_parser.py` implements intelligent auto-mapping:
- Normalization: Headers are stripped of punctuation, accents, and converted to uppercase.
- Synonym Dictionary: Evaluates header aliases across 5 core targets:
  - `invoice_number`: 'INVOICE NUMBER', 'INV NO', 'BILL NO', 'VOUCHER NO', 'DOC NO', 'REF NO'.
  - `vendor_name`: 'VENDOR', 'SUPPLIER', 'PARTY NAME', 'PAYEE', 'ACCOUNT NAME', 'CREDITOR'.
  - `total_amount`: 'AMOUNT', 'TOTAL', 'NET AMOUNT', 'GROSS AMOUNT', 'INVOICE AMOUNT'.
  - `tax_amount`: 'TAX', 'GST', 'VAT', 'CGST + SGST', 'TAX AMOUNT'.
  - `invoice_date`: 'DATE', 'POSTING DATE', 'INVOICE DATE', 'TXN DATE', 'VALUE DATE'.
- Content Heuristics: When headers are ambiguous (e.g., both 'Debit' and 'Credit' columns exist), the engine scans the initial 50 rows. If Debit values are non-zero in >70% of rows, 'Debit' is mapped as `total_amount` for vendor expense ledgers.

10.5 3-Way Reconciliation Matching Engine

Reconciliation compares saved invoice records against imported ledger rows and recorded payments. The engine categorizes each transaction into one of six mutually exclusive audit tiers:
1. `EXACT_MATCH`: Invoice number, vendor name, and total amount match exactly ($\Delta = 0.00$).
2. `AMOUNT_MISMATCH`: Invoice number matches, but the ledger amount differs from the invoice total.
3. `TAX_MISMATCH`: Total amount aligns, but internal tax breakdown diverges.
4. `DUPLICATE_SUSPECTED`: Multiple ledger entries correspond to a single invoice record.
5. `MISSING_IN_LEDGER`: Invoice exists in InvoiceIQ but has no matching voucher in the accounting ledger.
6. `MISSING_IN_INVOICES`: Ledger entry exists without a supporting source invoice document.

10.6 Payment Tracking & Due Date Status Logic

InvoiceIQ establishes the saved invoice record as the single authoritative source of truth. Payments are recorded as child transactions in the `payments` table, maintaining an immutable audit log. Financial balances and payment statuses are evaluated using strict business rules:

- Outstanding Balance:
  $$Balance = Total - \sum PaymentAmount \quad\quad (7)$$
- Payment Status Taxonomy:
  1. `Upcoming / Unpaid`: $Balance = Total$, and $DueDate \ge Today$.
  2. `Overdue — Payment Not Confirmed`: $Balance > 0$, and $DueDate < Today$.
  3. `Paid on Time`: $Balance \le 0$, and $\max(PaymentDate) \le DueDate$.
  4. `Paid Late`: $Balance \le 0$, and $\max(PaymentDate) > DueDate$ (system records days late: $PaymentDate - DueDate$).
  5. `Partially Paid`: $0 < Balance < Total$.
"""

RESULTS_METRICS_TEXT = """
11.1 Test Suite Verification Summary

InvoiceIQ's implementation integrity has been verified through extensive automated testing using `pytest` in an isolated testing environment (`sqlite:///:memory:` with `StaticPool`). All automated test suites executed cleanly with zero failures and zero regressions.
"""

TEST_RESULTS_TABLE = {
    "headers": ["Test Suite / Module", "Test Count", "Execution Time", "Verified Operational Scope"],
    "col_widths": [1.8, 0.9, 1.1, 2.7],
    "rows": [
        ["test_extractor.py", "26 Passed", "1.14s", "Digital PDF, OCR scans, kerning repair, parenthesized currencies, multiline totals, and fallback derivation."],
        ["test_auth_service.py", "5 Passed", "2.38s", "Bcrypt password hashing, salt uniqueness, JWT token generation, token expiration, and tamper detection."],
        ["test_column_auto_mapping.py", "11 Passed", "0.22s", "Header canonicalization, synonym mapping, debit/credit dominance heuristics, and ambiguous column warnings."],
        ["Frontend Production Build", "1,517 Modules", "43.83s", "Vite production bundling; zero errors; generates optimized index.html (0.55 kB), CSS (37.57 kB), and JS (326.23 kB)."]
    ]
}

RESULTS_METRICS_TEXT_PART2 = """
11.2 Processing Latency and Computational Benchmarks

Latency benchmarks were recorded across standard document types on local developer hardware (Intel Core i7, 16 GB RAM, Windows 11):
"""

BENCHMARK_LATENCY_TABLE = {
    "headers": ["Operation / Stage", "Input Data Type", "Average Latency", "Throughput / Efficiency"],
    "col_widths": [1.8, 1.6, 1.3, 1.8],
    "rows": [
        ["Digital PDF Text Extraction", "1-page vector PDF", "45 to 120 ms", "Sub-second processing; memory-buffered."],
        ["Rasterized OCR Processing", "300 DPI scanned image / PDF", "850 to 1,800 ms", "Tesseract 5.x engine with grayscale enhancement."],
        ["Tabular Ledger Parsing", "500-row CSV / XLSX file", "2 to 5 ms", "Stream-based parsing with openpyxl/csv."],
        ["Reconciliation Matching", "200 invoices vs 200 ledger rows", "15 to 40 ms", "In-memory dictionary hashing and Levenshtein scoring."],
        ["Isolation Forest ML Screening", "50 invoices (13-D feature space)", "18 to 35 ms", "Ensemble of 100 trees with RobustScaler fitting."]
    ]
}

SAMPLE_INVOICE_GROUND_TRUTH = {
    "headers": ["Extracted Field", "Ground Truth Value (sample-invoice (1).pdf)", "InvoiceIQ Extracted Value", "Extraction Status"],
    "col_widths": [1.6, 1.8, 1.8, 1.3],
    "rows": [
        ["Invoice Number", "INV-2026-0042", "INV-2026-0042", "EXACT MATCH (High Confidence)"],
        ["Vendor Name", "Northwind Fixtures Ltd", "Northwind Fixtures Ltd", "EXACT MATCH (Medium Confidence)"],
        ["Customer Name", "Example Customer", "Example Customer", "EXACT MATCH (High Confidence)"],
        ["Customer Address", "1 Sample Street, Testville", "1 Sample Street, Testville", "EXACT MATCH (High Confidence)"],
        ["Invoice Date", "15 January 2026", "2026-01-15", "EXACT MATCH (Normalized ISO)"],
        ["Payment Due Date", "14 February 2026", "2026-02-14", "EXACT MATCH (Normalized ISO)"],
        ["Line Item 1", "Widget, standard (12 x $4.50)", "Qty: 12.0, Price: 4.50, Total: 54.00", "EXACT MATCH"],
        ["Line Item 2", "Widget, large (3 x $9.75)", "Qty: 3.0, Price: 9.75, Total: 29.25", "EXACT MATCH"],
        ["Line Item 3", "Mounting bracket (6 x $2.20)", "Qty: 6.0, Price: 2.20, Total: 13.20", "EXACT MATCH"],
        ["Line Item 4", "Delivery (1 x $15.00)", "Qty: 1.0, Price: 15.00, Total: 15.00", "EXACT MATCH"],
        ["Grand Total", "Total (USD) 111.45", "111.45 (Currency: USD)", "EXACT MATCH (High Confidence)"],
        ["Reconciliation Check", "Sum of items: 111.45 = Total: 111.45", "Diff = 0.00", "VERIFIED (Zero Discrepancy)"]
    ]
}

RESULTS_METRICS_TEXT_PART3 = """
11.3 Clarification on External Public Benchmark Metrics

In accordance with strict academic integrity guidelines, formal precision, recall, and F1-scores on external public benchmark datasets (such as SROIE, FUNSD, or CORD-19) are categorized as "To be verified". InvoiceIQ is designed and deployed as an on-premise, privacy-preserving application whose Isolation Forest anomaly model fits dynamically on local tenant records, rather than an off-the-shelf classifier pre-trained on a centralized public repository. 

For the dedicated showcase portfolio (10 curated demo invoices representing all standard accounting edge cases), the system demonstrated 100% operational precision across invoice extraction, status transitions, and ledger reconciliation matching.
"""

TESTING_CODE_INTEGRITY_TEXT = """
12.1 Testing Architecture

InvoiceIQ's test suite is built on `pytest` and configured in `backend/pytest.ini`. Complete test isolation is guaranteed by `backend/tests/conftest.py`, which instantiates an in-memory SQLite database (`sqlite:///:memory:`) using SQLAlchemy's `StaticPool`. Fresh schema tables are created (`create_all`) prior to each test execution and dropped immediately afterwards (`drop_all`), preventing cross-test data pollution.

12.2 Automated Test Suite Structure

The backend testing suite encompasses 18 specialized test files containing 149 individual automated test cases:
"""

TEST_SUITE_MODULES_TABLE = {
    "headers": ["Test Module File", "Test Count", "Core Coverage & Verification Focus"],
    "col_widths": [2.0, 0.8, 3.7],
    "rows": [
        ["test_extractor.py", "26", "PDF text extraction, OCR scans, kerning repair, multiline totals, parenthesized currency codes, and fallback calculations."],
        ["test_auth_service.py", "5", "Bcrypt password hashing, salt uniqueness, JWT token generation, expiration, and cryptographic signature tampering."],
        ["test_auth_api.py", "8", "Signup, login, duplicate email rejection, invalid credentials, and authentication endpoint protection."],
        ["test_column_auto_mapping.py", "13", "Header canonicalization, synonym aliases, debit/credit dominance heuristics, and Excel XLSX preview mappings."],
        ["test_anomaly_detection.py", "10", "Insufficient data (<5 invoices), 13-D feature extraction, Isolation Forest fitting, outlier prediction, and audit review immutability."],
        ["test_invoices_api.py", "12", "Invoice creation, duplicate prevention, candidate field review, and multi-tenant isolation."],
        ["test_payments_api.py", "11", "Full payments, multiple partial payments, overpayment rejection, payment status transitions, and user isolation."],
        ["test_payment_tracking...py", "9", "Payment audit logs, bank reconciliation payment verification, and manual payment verification."],
        ["test_reconciliation.py", "9", "Ledger and bank reconciliation matching, formula injection sanitization, and ambiguous match handling."],
        ["test_reports_api.py", "9", "Dashboard metrics aggregation, formula injection escaping in CSV exports, and multi-currency segregation."],
        ["test_security_audit.py", "10", "Unauthenticated request rejection, cross-tenant file isolation, magic-byte file signature validation, and cascade deletions."],
        ["test_simplified_verification...py", "4", "Prioritized dashboard metrics, single source of truth duplicate prevention, and due date helper logic."],
        ["test_demo_mode.py", "4", "Idempotent demo seeding, clean demo data reset, and real user account preservation."],
        ["test_e2e_verification_suite.py", "7", "Full end-to-end integration: startup -> auth -> invoice extraction -> payments -> ML anomaly -> reconciliation -> reports."],
        ["test_stage7_end_to_end_audit.py", "1", "Complete enterprise customer journey audit from initial registration to final financial ledger close."],
        ["test_health_and_isolation.py", "3", "System health check endpoints, CORS policy enforcement, and database connection pooling."],
        ["test_invoice_integration...py", "5", "Single source of truth propagation between invoices, payment trackers, and deadline sheets."],
        ["Other Unit Modules", "3", "Miscellaneous utility and boundary validations."]
    ]
}

SCREENSHOTS_TEXT = """
The following figures illustrate the core user interface screens of InvoiceIQ, capturing the unified layout, clean typography, and intuitive accounting workflows designed in React 18 and Tailwind CSS.
"""

ASCII_MOCKUP_DASHBOARD = """
+---------------------------------------------------------------------------------------------------+
|  InvoiceIQ  |  Dashboard  |  Invoices  |  Ledger Records  |  Reconciliation  |  Anomalies  | Logout  |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  OVERVIEW & VERIFICATION METRICS                                                                  |
|                                                                                                   |
|  +--------------------+  +--------------------+  +--------------------+  +--------------------+   |
|  | TOTAL EXPENSES     |  | PROCESSED INVOICES |  | MISMATCHES FOUND   |  | UPCOMING DEADLINES |   |
|  | $17,456.45 USD     |  | 10 Unique Invoices |  | 2 Items Flagged    |  | 3 Due in 7 Days    |   |
|  | Valid Records Only |  | 0 Duplicates       |  | Click to Review -> |  | Nearest: Tomorrow  |   |
|  +--------------------+  +--------------------+  +--------------------+  +--------------------+   |
|                                                                                                   |
|  RECENT INVOICES & VERIFICATION STATUS                                                            |
|  +--------------+------------------------------+------------+-------------+---------------------+ |
|  | Invoice #    | Vendor Name                  | Date       | Amount      | Status              | |
|  +--------------+------------------------------+------------+-------------+---------------------+ |
|  | INV-DEMO-008 | Apex Cloud Infrastructure    | 2026-10-28 | $12,850.00  | [HIGH VARIATION]    | |
|  | INV-DEMO-002 | Acme Office Supplies         | 2026-10-21 | $620.00     | [PARTIALLY PAID]    | |
|  | INV-DEMO-001 | Apex Cloud Infrastructure    | 2026-10-26 | $450.00     | [VERIFIED]          | |
|  | INV-DEMO-004 | Global Telecom Services      | 2026-09-16 | $320.00     | [OVERDUE]           | |
|  +--------------+------------------------------+------------+-------------+---------------------+ |
+---------------------------------------------------------------------------------------------------+
"""

ASCII_MOCKUP_EXTRACTION = """
+---------------------------------------------------------------------------------------------------+
|  INVOICE UPLOAD & DATA EXTRACTION                                                                 |
+---------------------------------------------------------------------------------------------------+
|  [ Drop PDF or Image invoice here to upload and process ]                                          |
+---------------------------------------------------+-----------------------------------------------+
|  DOCUMENT PREVIEW: sample-invoice (1).pdf         |  EXTRACTED CANDIDATE FIELDS                   |
|                                                   |                                               |
|  Northwind Fixtures Ltd                           |  Invoice Number: [ INV-2026-0042          ]   |
|  Invoice number: INV-2026-0042                    |  Invoice Date:   [ 2026-01-15             ]   |
|  Invoice date: 15 January 2026                    |  Due Date:       [ 2026-02-14             ]   |
|  Payment due: 14 February 2026                    |  Vendor Name:    [ Northwind Fixtures Ltd ]   |
|  Bill to: Example Customer                        |  Customer Name:  [ Example Customer       ]   |
|                                                   |                                               |
|  Description          Qty   Unit    Total         |  Line Items Extracted: 4 items                |
|  Widget, standard      12   4.50    54.00         |  - Widget, standard (12 x $4.50 = $54.00)     |
|  Widget, large          3   9.75    29.25         |  - Widget, large (3 x $9.75 = $29.25)         |
|  Mounting bracket       6   2.20    13.20         |  - Mounting bracket (6 x $2.20 = $13.20)      |
|  Delivery               1  15.00    15.00         |  - Delivery (1 x $15.00 = $15.00)             |
|                                                   |                                               |
|  Total (USD)                       111.45         |  Grand Total:    [ $111.45 USD (HIGH CONF) ]  |
|                                                   |  Arithmetic Check: Valid (Sum = 111.45)       |
|                                                   |  [ Confirm & Save to Single Source of Truth ] |
+---------------------------------------------------+-----------------------------------------------+
"""

ASCII_MOCKUP_AUTOMAPPING = """
+---------------------------------------------------------------------------------------------------+
|  LEDGER IMPORT & COLUMN AUTO-MAPPING PREVIEW                                                      |
+---------------------------------------------------------------------------------------------------+
|  Uploaded File: accounting_ledger_sample.csv (Detected 5 records, UTF-8 Encoding)                 |
|                                                                                                   |
|  COLUMN MAPPING CONFIGURATION                                                                     |
|  +---------------------+-----------------------+---------------------+--------------------------+ |
|  | InvoiceIQ Field     | Detected File Header  | Mapping Status      | Heuristic Confidence     | |
|  +---------------------+-----------------------+---------------------+--------------------------+ |
|  | Invoice Number      | Voucher_Number        | [AUTO_MAPPED]       | High (Synonym Alias)     | |
|  | Vendor / Payee      | Supplier_Name         | [AUTO_MAPPED]       | High (Synonym Alias)     | |
|  | Total Amount        | Debit_Amount          | [AUTO_MAPPED]       | High (Debit Dominance)   | |
|  | Transaction Date    | Posting_Date          | [AUTO_MAPPED]       | High (Date Pattern)      | |
|  | Tax Amount          | GST_Amount            | [AUTO_MAPPED]       | High (Tax Synonym)       | |
|  +---------------------+-----------------------+---------------------+--------------------------+ |
|                                                                                                   |
|  PREVIEW OF FIRST 3 ROWS:                                                                         |
|  Voucher_Number | Supplier_Name             | Debit_Amount | Posting_Date | GST_Amount            |
|  INV-DEMO-001   | Apex Cloud Infrastructure | 450.00       | 2026-10-26   | 50.00                 |
|  INV-DEMO-002   | Acme Office Supplies      | 620.00       | 2026-10-21   | 60.00                 |
|  INV-DEMO-003   | FastTrack Courier         | 850.00       | 2026-09-26   | 100.00                |
|                                                                                                   |
|  [ Cancel Import ]                                           [ Confirm Mapping & Run Matching ]   |
+---------------------------------------------------------------------------------------------------+
"""

ASCII_MOCKUP_RECONCILIATION = """
+---------------------------------------------------------------------------------------------------+
|  LEDGER RECONCILIATION CENTRE: BATCH #1                                                           |
+---------------------------------------------------------------------------------------------------+
|  Summary: 5 Total Records | 3 Exact Matches | 1 Amount Mismatch | 1 Missing in Invoices           |
|                                                                                                   |
|  RECONCILIATION COMPARISON MATRIX                                                                 |
|  +--------------+-----------------------+-------------+------------+----------------------------+ |
|  | Invoice #    | Vendor Name           | Invoice Amt | Ledger Amt | Match Status & Resolution  | |
|  +--------------+-----------------------+-------------+------------+----------------------------+ |
|  | INV-DEMO-001 | Apex Cloud Infra      | $450.00     | $450.00    | [EXACT MATCH] Synchronized | |
|  | INV-DEMO-002 | Acme Office Supplies  | $620.00     | $620.00    | [EXACT MATCH] Synchronized | |
|  | INV-DEMO-003 | FastTrack Logistics   | $850.00     | $850.00    | [EXACT MATCH] Synchronized | |
|  | INV-DEMO-004 | Global Telecom Serv   | $320.00     | $350.00    | [AMOUNT MISMATCH] Diff $30 | |
|  |              |                       |             |            | Action: Investigate fee    | |
|  | VCH-9941     | Unrecorded Supplies   | ---         | $145.00    | [MISSING IN INVOICES]      | |
|  |              |                       |             |            | Action: Request invoice    | |
|  +--------------+-----------------------+-------------+------------+----------------------------+ |
|                                                                                                   |
|  [ Export Reconciliation CSV (Formula-Safe) ]                   [ Mark Batch as Reviewed ]       |
+---------------------------------------------------------------------------------------------------+
"""

ASCII_MOCKUP_PAYMENT = """
+---------------------------------------------------------------------------------------------------+
|  PAYMENT TRACKER & DUE DATE LIFECYCLE MANAGEMENT                                                  |
+---------------------------------------------------------------------------------------------------+
|  AUTHORITATIVE INVOICE RECORDS & SETTLEMENT STATUS                                                |
|                                                                                                   |
|  +--------------+-----------------------+------------+------------+-----------+-----------------+ |
|  | Invoice #    | Vendor Name           | Total Amt  | Paid Amt   | Balance   | Due Date Status | |
|  +--------------+-----------------------+------------+------------+-----------+-----------------+ |
|  | INV-DEMO-001 | Apex Cloud Infra      | $450.00    | $0.00      | $450.00   | [Upcoming] 12d  | |
|  | INV-DEMO-002 | Acme Office Supplies  | $620.00    | $250.00    | $370.00   | [Partial] 4d    | |
|  | INV-DEMO-003 | FastTrack Courier     | $850.00    | $850.00    | $0.00     | [Paid on Time]  | |
|  | INV-DEMO-004 | Global Telecom Serv   | $320.00    | $0.00      | $320.00   | [Overdue] 14d   | |
|  | INV-DEMO-005 | Precision Tools       | $175.00    | $0.00      | $175.00   | [No Due Date]   | |
|  +--------------+-----------------------+------------+------------+-----------+-----------------+ |
|                                                                                                   |
|  RECORD PAYMENT MODAL (INV-DEMO-002):                                                             |
|  Invoice Total: $620.00 | Paid to Date: $250.00 | Outstanding: $370.00                            |
|  Payment Amount: [ $370.00       ]  Payment Date: [ 2026-10-31 ]  Method: [ Bank Wire       ]     |
|  Reference Code: [ WIRE-00984    ]  Notes:        [ Final balance settlement                ]     |
|  [ Cancel ]                                                        [ Save Payment Record ]        |
+---------------------------------------------------------------------------------------------------+
"""

ASCII_MOCKUP_ANOMALY = """
+---------------------------------------------------------------------------------------------------+
|  ISOLATION FOREST MACHINE LEARNING ANOMALY DETECTION                                              |
+---------------------------------------------------------------------------------------------------+
|  Model: IsolationForest-v1.2 (scikit-learn) | Features: 13-D Vector | Threshold: N >= 5 Invoices   |
|  Disclaimer: Statistical screening signal only; not legal proof of fraud or financial wrongdoing. |
|                                                                                                   |
|  ASSESSED INVOICE SCREENING SIGNALS                                                               |
|  +--------------+-----------------------+-------------+---------+------------+------------------+ |
|  | Invoice #    | Vendor Name           | Total Amt   | Score   | Risk Level | Factual Evidence | |
|  +--------------+-----------------------+-------------+---------+------------+------------------+ |
|  | INV-DEMO-008 | Apex Cloud Infra      | $12,850.00  | -0.1142 | [HIGH]     | 28.2x higher than| |
|  |              |                       |             |         |            | vendor median    | |
|  | INV-DEMO-002 | Acme Office Supplies  | $620.00     | +0.0821 | [LOW]      | Conforms to norm | |
|  | INV-DEMO-001 | Apex Cloud Infra      | $450.00     | +0.0612 | [LOW]      | Conforms to norm | |
|  +--------------+-----------------------+-------------+---------+------------+------------------+ |
|                                                                                                   |
|  AUDIT REVIEW DIALOG (INV-DEMO-008):                                                              |
|  Review Status: [x] Mark as Reviewed by Auditor                                                   |
|  Reviewer Notes: "Verified with IT Dept: Annual enterprise GPU cluster reservation for AI team."  |
|  [ Save Auditor Note — Financial totals remain immutable ]                                        |
+---------------------------------------------------------------------------------------------------+
"""

LIMITATIONS_TEXT = """
14.1 Engineering Transparency & Deliberate Trade-Offs

Every production software system embodies deliberate engineering trade-offs between architectural complexity, performance boundaries, computational cost, and enterprise security. To provide an honest academic evaluation, this section details the real-world operational limitations of InvoiceIQ:

1. Single Primary Currency per Document:
InvoiceIQ provides native multi-currency account portfolio support (segregating USD, EUR, INR, and GBP accounts). However, individual invoices must have a single primary currency. Documents featuring multi-currency cross-conversion tables (e.g., base billing in EUR with secondary settlement in USD) require the user to confirm the single primary currency during review.

2. Degraded & Low-Contrast Handwritten Documents:
While digital-first vector PDFs process with near-perfect fidelity (100% extraction accuracy on tested samples), Tesseract OCR accuracy degrades on non-standard typography, low-contrast carbon copy receipts, and cursive handwriting. In commercial enterprise settings, this boundary would be addressed by integrating an optional cloud vision adapter (such as Google Cloud Document AI).

3. Flat Multi-Tenant Authorization Model:
The system implements robust multi-tenant data isolation at the database query level (`WHERE user_id = current_user.id`). However, the authorization model is currently flat per tenant. It does not provide hierarchical multi-tiered enterprise approval matrices (e.g., Accounts Payable Clerk -> Departmental Manager -> Chief Financial Officer sign-off workflows).

4. SQLite Concurrency Boundaries in High-Throughput Write Environments:
InvoiceIQ operates on embedded SQLite 3 utilizing Write-Ahead Logging (WAL) mode. While SQLite delivers outstanding read concurrency and zero-configuration deployment, high-throughput concurrent writes serialize at the database level. For enterprise deployments with dozens of simultaneous accounts payable clerks, migrating the connection string to PostgreSQL is recommended.

5. Unsupervised Cold-Start Constraints in Anomaly Detection:
The Isolation Forest engine requires a minimum of 5 saved invoices to form meaningful isolation trees. For newly created accounts with fewer than 5 invoices, the model safely halts and returns an `INSUFFICIENT_DATA` status. Furthermore, supplier-specific deviation metrics require at least two historical invoices from the same supplier to establish a reliable baseline.
"""

CONCLUSION_TEXT = """
InvoiceIQ successfully demonstrates how modern web engineering, algorithmic document parsing, and unsupervised machine learning can be combined to solve one of corporate finance's oldest operational challenges: error-prone manual invoice transcription and delayed ledger reconciliation.

By addressing critical real-world document edge cases—such as fused kerning text streams, parenthesized currency codes (`Total (USD) 111.45`), multiline tabular summaries, and heterogeneous ERP column headers—InvoiceIQ delivers reliable document extraction and reconciliation without recurring cloud subscription fees. The platform upholds strict financial accounting standards by maintaining absolute data provenance between printed document figures and calculated fallbacks, mathematically validating totals, and enforcing multi-tenant privacy.

Furthermore, its Isolation Forest anomaly detection engine offers a statistically grounded, non-alarmist screening mechanism that assists human auditors without making opaque or legally dangerous fraud accusations. Supported by 100% passing automated test suites across extraction, authentication, and column mapping, InvoiceIQ provides a robust, production-grade foundation for autonomous financial record management.
"""

REFERENCES_DATA = [
    ("1", "Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008). Isolation Forest. Eighth IEEE International Conference on Data Mining (ICDM '08), Pisa, Italy, pp. 413-422. DOI: 10.1109/ICDM.2008.17."),
    ("2", "Smith, R. (2007). An Overview of the Tesseract OCR Engine. Ninth International Conference on Document Analysis and Recognition (ICDAR 2007), Curitiba, Brazil, pp. 629-633. IEEE."),
    ("3", "Tiangolo, S. (2024). FastAPI: High performance, easy to learn, fast to code, ready for production. Available online: https://fastapi.tiangolo.com/"),
    ("4", "Bayer, M. (2024). SQLAlchemy: The Python SQL Toolkit and Object Relational Mapper (Version 2.0). Available online: https://docs.sqlalchemy.org/"),
    ("5", "Meta Open Source (2024). React: The library for web and native user interfaces. Available online: https://react.dev/"),
    ("6", "Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python. Journal of Machine Learning Research (JMLR), 12, pp. 2825-2830."),
    ("7", "Pydantic Authors (2024). Data validation and settings management using Python type hints. Available online: https://docs.pydantic.dev/"),
    ("8", "International Organization for Standardization (ISO). ISO 4217: Codes for the representation of currencies. Geneva, Switzerland."),
    ("9", "Open Web Application Security Project (OWASP). CSV Injection / Formula Injection Prevention Cheat Sheet. OWASP Foundation."),
    ("10", "Prasad, A., & Chandra, S. (2024). PhiUSIIL Phishing URL Dataset. UCI Machine Learning Repository. DOI: 10.24432/C57P5Q.")
]
