# InvoiceIQ — Machine Learning Anomaly Detection Architecture & Technical Documentation

**Version:** IsolationForest-v1.2  
**Implementation Files:**  
- Engine: [`backend/app/services/anomaly_service.py`](file:///C:/Users/aditi/Downloads/InvoiceIQ_New/backend/app/services/anomaly_service.py)  
- API Router: [`backend/app/routers/anomalies.py`](file:///C:/Users/aditi/Downloads/InvoiceIQ_New/backend/app/routers/anomalies.py)  
- Data Model: [`backend/app/models/anomaly.py`](file:///C:/Users/aditi/Downloads/InvoiceIQ_New/backend/app/models/anomaly.py)  
- Schemas: [`backend/app/schemas/anomaly.py`](file:///C:/Users/aditi/Downloads/InvoiceIQ_New/backend/app/schemas/anomaly.py)  
- Frontend Interface: [`frontend/src/pages/AnomalyDetection.jsx`](file:///C:/Users/aditi/Downloads/InvoiceIQ_New/frontend/src/pages/AnomalyDetection.jsx)  
- Automated Test Suite: [`backend/tests/test_anomaly_detection.py`](file:///C:/Users/aditi/Downloads/InvoiceIQ_New/backend/tests/test_anomaly_detection.py)

---

## 1. Executive Summary & Philosophy

InvoiceIQ's Machine Learning Anomaly Detection feature provides automated statistical outlier screening across persistent invoice records. It is designed from first principles as an **auditor assistance and screening tool**, rather than an automated decision maker.

### Core Non-Negotiable Tenets:
1. **Never Label Invoices as "Fraud":** Statistical outliers occur naturally (e.g., annual hardware renewals, large quarterly vendor payments, bulk inventory purchases). Anomaly scores represent statistical deviation, never criminal guilt or proven irregularity.
2. **No Arbitrary Percentage Claims:** Avoids pseudo-scientific confidence numbers (such as "98.7% chance of fraud"). Instead, it presents an ordinal risk level (`LOW`, `MEDIUM`, `HIGH`) alongside factual, verifiable evidence (vendor medians, spending ratios, and duplicate flags).
3. **Non-Destructive Audit Reviews:** When an auditor confirms or reviews an anomaly, the review is logged with an audit timestamp and reviewer notes. **It never modifies invoice totals, taxes, or payment balances.**
4. **Strict Multi-Tenant Isolation:** The model is trained and predicted strictly on the authenticated customer's own invoices. Records from different users are never aggregated or leaked.

---

## 2. Algorithm Architecture & Preprocessing

The screening pipeline relies on **Isolation Forest** paired with **RobustScaler** from `scikit-learn`:

```
User Invoices (PostgreSQL / SQLite)
               │
               ▼
   [Feature Extraction Engine]
    - Currency Normalization
    - Vendor Baseline Aggregation
    - Duplicate Tracking
    - Math & Term Sanity Checks
               │
               ▼
      [13-D Numeric Matrix X]
               │
               ▼
       [RobustScaler(unit_variance=True)]
       - Scales by Median & IQR (Resistant to Outliers)
               │
               ▼
   [IsolationForest(n_estimators=100)]
   - Dynamic contamination rate: min(0.20, max(0.05, 1.0 / N))
   - Random state: 42 (Reproducible results)
               │
        ┌──────┴──────┐
        ▼             ▼
   raw_preds     decision_scores
   (-1 or +1)    (Continuous Score)
        │             │
        └──────┬──────┘
               ▼
 [Risk Level & Explanation Synthesizer]
               │
               ▼
   Persisted into `invoice_anomalies` Table
```

### Why Isolation Forest?
Unlike distance-based models (such as k-Means or DBSCAN) or density models (LOF), Isolation Forests explicitly isolate anomalies by randomly selecting a feature and randomly selecting a split value between the maximum and minimum values. Anomalies require significantly fewer splits to isolate than normal points, making the algorithm computationally efficient ($O(n \log n)$) and robust on skewed financial spending data.

### Why RobustScaler?
Standard scaling ($z = \frac{x - \mu}{\sigma}$) is notoriously sensitive to extreme financial outliers because a single massive invoice inflates the mean $\mu$ and standard deviation $\sigma$. `RobustScaler` scales features using the median and Interquartile Range ($IQR = Q_3 - Q_1$), guaranteeing that extreme amounts do not distort standard normalization.

---

## 3. Feature Engineering (13 Dimensions)

Every feature in the numeric matrix $X$ is grounded in actual database fields without inventing artificial data or treating null values as zero:

| Index | Feature Key | Data Type | Description & Mathematical Definition |
|---|---|---|---|
| `0` | `log_amt_norm` | `float64` | Natural logarithm of currency-normalized amount: $\ln(1 + \frac{\text{amt}}{\text{median}(\text{currency})})$. |
| `1` | `currency_amount_ratio` | `float64` | Ratio of invoice total to account median within the same currency code. |
| `2` | `tax_ratio` | `float64` | $\frac{\text{tax\_amount}}{\text{total\_amount}}$. Safely imputed with account median if tax is omitted. |
| `3` | `has_tax` | `float64` | Binary indicator ($1.0$ if tax is specified, $0.0$ if omitted). Prevents zero-bias. |
| `4` | `is_unusual_tax` | `float64` | Binary indicator ($1.0$ if tax ratio $> 35\%$ or negative). |
| `5` | `subtotal_ratio` | `float64` | $\frac{\text{subtotal}}{\text{total\_amount}}$. Safely imputed with account median if omitted. |
| `6` | `has_subtotal` | `float64` | Binary indicator ($1.0$ if subtotal is specified, $0.0$ if omitted). |
| `7` | `has_math_discrepancy` | `float64` | Binary indicator ($1.0$ if $|\text{subtotal} + \text{tax} - \text{total}| > 0.05$). |
| `8` | `vendor_amount_ratio` | `float64` | $\frac{\text{total\_amount}}{\text{median}_{\text{vendor}}(\text{amount})}$. Set to $1.0$ if vendor has $< 2$ invoices. |
| `9` | `has_vendor_history` | `float64` | Binary indicator ($1.0$ if vendor has $\ge 2$ invoices in account history). |
| `10` | `term_days` | `float64` | Billing payment window in days: $(\text{due\_date} - \text{invoice\_date})$. |
| `11` | `has_due_date` | `float64` | Binary indicator ($1.0$ if due date is present, $0.0$ if omitted). |
| `12` | `is_duplicate_number` | `float64` | Binary indicator ($1.0$ if invoice number appears multiple times in account records). |

---

## 4. Currency Normalization & Cross-Currency Safety

A major limitation of naive anomaly detectors is mixing different currencies. For instance, an invoice of ₹50,000 INR would appear as a massive 250x outlier if compared against an average US Dollar invoice of \$200 USD.

InvoiceIQ solves this via **Currency-Segmented Baseline Normalization**:
1. Invoices are grouped by currency (`USD`, `EUR`, `INR`, `GBP`, etc.).
2. Currency-specific medians are computed: $\text{median}_{\text{curr}}$.
3. Invoices are scaled relative to their own currency baseline before matrix transformation:
   $$\text{currency\_amount\_ratio} = \frac{\text{amt}}{\max(1.0, \text{median}_{\text{curr}})}$$
4. Vendor statistics are evaluated strictly against historical invoices from that vendor in the *same* currency.

---

## 5. Insufficient Data Handling

Machine learning models fitted on tiny sample sizes produce arbitrary splits, noise memorization, and high false-positive rates.

- **Minimum Required Threshold:** $\ge 5$ saved invoices.
- **Under-threshold Behavior:** If $N < 5$, the model terminates immediately and returns HTTP 200 with status `INSUFFICIENT_DATA`:
  > *"Insufficient data: At least 5 saved invoices are required to fit the anomaly detection model (currently have 3). Please add 2 more invoice(s) to enable machine learning analysis."*
- **Vendor-Level Insufficient Data:** If a vendor has only 1 recorded invoice, `has_vendor_history` is set to $0.0$, and the invoice is evaluated against overall account distributions rather than generating an invalid vendor-specific deviation.

---

## 6. Risk Categorization & Explainability

Instead of deceptive probability numbers, invoices are assigned to one of three transparent risk categories:

| Risk Category | Conditions | UI Styling | Meaning |
|---|---|---|---|
| **`LOW`** | Model prediction $= 1$ (Normal), no structural warnings. | Green badge (`Low Risk`) | Financial figures and ratios align with historical patterns. |
| **`MEDIUM`** | Decision score between $-0.06$ and $0.0$, or mild vendor ratio jump ($2.0\times - 3.5\times$). | Amber badge (`Moderate`) | Mild statistical deviation; worth a standard spot check. |
| **`HIGH`** | Decision score $\le -0.06$, duplicate invoice numbers, arithmetic discrepancies, or vendor jump $\ge 3.5\times$. | Rose/Red badge (`High Variation`) | Severe statistical or structural divergence requiring auditor review. |

### Explanation Generation:
Each flagged invoice receives an observation report citing actual figures:
- *"Total amount ($12,500.00 USD) is 6.2x higher than historical median ($2,000.00 USD) for vendor 'Office Depot'."*
- *"Duplicate invoice number 'INV-1002' matches 2 existing invoices in your records."*
- *"Arithmetic discrepancy: Subtotal ($100.00) + Tax ($20.00) does not equal Total ($150.00) ($30.00 difference)."*
- *"Tax proportion (38.5% of total) is unusually high (>35%)."*

---

## 7. Non-Destructive Auditor Review Workflow

Auditors can review flagged invoices directly from the Anomaly Detection UI.

### API Endpoints:
- `PATCH /api/anomalies/{anomaly_id}/review`: Marks an anomaly assessment as reviewed.
- `PATCH /api/anomalies/invoice/{invoice_id}/review`: Equivalent alias matching by invoice ID.
- `DELETE /api/anomalies/{anomaly_id}/review`: Resets review status.

### Guarantees:
- **Audit Preservation:** Stores `is_reviewed = True`, `reviewed_at = UTC timestamp`, and optional `review_notes`.
- **Financial Immutability:** Reviewing an anomaly **never alters** `total_amount`, `subtotal`, `tax_amount`, or `payment_status` of the invoice.
- **Re-assessment Idempotency:** When the user re-runs or refreshes the Isolation Forest assessment, existing review flags and notes are preserved.

---

## 8. Multi-Tenant User Isolation

Strict data isolation is enforced at the database and query levels:
- Invoices are selected with `WHERE invoices.user_id = :current_user_id`.
- Vendor baselines, duplicate counters, and Isolation Forest training data are instantiated purely inside the scope of the current user's session.
- Anomaly review operations verify that `invoice_anomalies.user_id == current_user.id`, rejecting any cross-user attempts with HTTP 404.

---

## 9. Limitations & Practical Considerations

1. **Unsupervised Outlier Nature:** Isolation Forest identifies *statistical outliers*, not accounting legality. Legitimate one-off large purchases (e.g. annual server renewals) will be flagged by design.
2. **Cold Start per Vendor:** When ordering from a new vendor for the first time, vendor-specific baselines cannot exist until at least two invoices have been processed.
3. **Threshold Sensitivity:** Accounts with very small variance (e.g., utility subscriptions of identical \$50 amounts) have very narrow isolation trees. The model uses `RobustScaler(unit_variance=True)` to prevent zero-division errors under identical inputs.
