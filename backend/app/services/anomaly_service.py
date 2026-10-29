import json
import logging
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.anomaly import InvoiceAnomaly

logger = logging.getLogger(__name__)

# Strict Minimum Requirement: Need at least 5 invoices to form meaningful Isolation Trees
MIN_INVOICES_FOR_ANOMALY_MODEL = 5
MODEL_VERSION = "IsolationForest-v1.2"
DISCLAIMER_TEXT = (
    "This assessment is an automated statistical screening signal and validation aid (Isolation Forest), "
    "not proof of fraud, accounting error, or financial irregularity."
)


def extract_invoice_features(
    invoices: List[Invoice],
) -> Tuple[np.ndarray, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Extracts genuine numeric features exclusively from available database fields.
    Does NOT invent missing data fields or arbitrarily treat missing values as zero.
    
    Guarantees:
    - Currency Normalization: Computes baselines per currency so mixed-currency accounts
      (e.g., USD vs INR) do not cause false anomaly flags.
    - Vendor Baseline: Compares current invoice total to historical median for the same vendor.
    - Structural Rules: Evaluates duplicate invoice numbers, arithmetic consistency, and due date bounds.
    
    Returns:
        - X (np.ndarray): 2D numeric feature matrix
        - factor_dicts (List[Dict]): Per-invoice factor breakdowns
        - context_meta (Dict): Overall user-level and vendor-level distributions
    """
    n = len(invoices)

    # 1. Compute Currency-Segmented Baselines
    currency_groups: Dict[str, List[float]] = {}
    for inv in invoices:
        c_code = (inv.currency or "USD").upper()
        currency_groups.setdefault(c_code, []).append(float(inv.total_amount))

    currency_medians: Dict[str, float] = {}
    for c_code, c_amts in currency_groups.items():
        currency_medians[c_code] = float(np.median(c_amts)) if c_amts else 1.0

    # Overall user median fallback
    all_amounts = [float(inv.total_amount) for inv in invoices]
    user_median_amount = float(np.median(all_amounts)) if all_amounts else 1.0

    # 2. Compute Vendor-Level Baselines (within specific currency)
    vendor_groups: Dict[Tuple[str, str], List[float]] = {}
    for inv in invoices:
        v_key = inv.vendor_name.strip().lower()
        c_code = (inv.currency or "USD").upper()
        vendor_groups.setdefault((v_key, c_code), []).append(float(inv.total_amount))

    vendor_stats: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for (v_key, c_code), v_amounts in vendor_groups.items():
        vendor_stats[(v_key, c_code)] = {
            "count": len(v_amounts),
            "median": float(np.median(v_amounts)),
            "mean": float(np.mean(v_amounts)),
        }

    # 3. Detect Duplicate Invoice Numbers within user's invoices
    inv_num_counts = Counter(inv.invoice_number.strip().upper() for inv in invoices)
    vendor_inv_num_counts = Counter(
        (inv.vendor_name.strip().lower(), inv.invoice_number.strip().upper()) for inv in invoices
    )

    # 4. Safe imputation baselines for optional fields
    valid_tax_ratios = []
    valid_subtotal_ratios = []
    valid_terms = []

    for inv in invoices:
        tot = float(inv.total_amount)
        if tot > 0:
            if inv.tax_amount is not None:
                valid_tax_ratios.append(float(inv.tax_amount) / tot)
            if inv.subtotal is not None:
                valid_subtotal_ratios.append(float(inv.subtotal) / tot)
        if inv.due_date is not None and inv.invoice_date is not None:
            diff = (inv.due_date - inv.invoice_date).days
            valid_terms.append(diff)

    default_tax_ratio = float(np.median(valid_tax_ratios)) if valid_tax_ratios else 0.0
    default_subtotal_ratio = float(np.median(valid_subtotal_ratios)) if valid_subtotal_ratios else 1.0
    default_term = float(np.median(valid_terms)) if valid_terms else 30.0

    feature_rows = []
    factor_dicts = []

    for inv in invoices:
        amt = float(inv.total_amount)
        curr = (inv.currency or "USD").upper()
        c_median = currency_medians.get(curr, user_median_amount)

        # Currency-normalized amount ratio and log
        currency_amount_ratio = amt / max(1.0, c_median)
        log_amt_norm = float(np.log1p(max(0.0, currency_amount_ratio)))

        # Tax Ratio & Missingness
        has_tax = 1.0 if inv.tax_amount is not None else 0.0
        if inv.tax_amount is not None and amt > 0:
            tax_ratio = float(inv.tax_amount) / amt
        else:
            tax_ratio = default_tax_ratio
        is_unusual_tax = 1.0 if (has_tax and (tax_ratio > 0.35 or tax_ratio < 0.0)) else 0.0

        # Subtotal Ratio & Math Discrepancy
        has_subtotal = 1.0 if inv.subtotal is not None else 0.0
        if inv.subtotal is not None and amt > 0:
            subtotal_ratio = float(inv.subtotal) / amt
        else:
            subtotal_ratio = default_subtotal_ratio

        # Arithmetic consistency check: Subtotal + Tax == Total
        has_math_discrepancy = 0.0
        math_diff = 0.0
        if inv.subtotal is not None and inv.tax_amount is not None and amt > 0:
            calc_sum = float(inv.subtotal) + float(inv.tax_amount)
            math_diff = abs(calc_sum - amt)
            if math_diff > 0.05:
                has_math_discrepancy = 1.0

        # Payment Term Days & Date Sequence
        has_due_date = 1.0 if inv.due_date is not None else 0.0
        if inv.due_date is not None and inv.invoice_date is not None:
            term_days = float((inv.due_date - inv.invoice_date).days)
        else:
            term_days = default_term
        is_negative_term = 1.0 if (has_due_date and term_days < 0) else 0.0

        # Vendor Historical Comparison
        v_key = inv.vendor_name.strip().lower()
        v_stat = vendor_stats.get((v_key, curr), {"count": 1, "median": amt})
        has_vendor_history = 1.0 if v_stat["count"] >= 2 else 0.0
        if has_vendor_history and v_stat["median"] > 0:
            vendor_amount_ratio = amt / v_stat["median"]
        else:
            vendor_amount_ratio = 1.0

        # Duplicate Invoice Number Tracking
        norm_inv_num = inv.invoice_number.strip().upper()
        dup_count = inv_num_counts[norm_inv_num]
        is_duplicate_number = 1.0 if dup_count > 1 else 0.0
        same_vendor_dup_count = vendor_inv_num_counts[(v_key, norm_inv_num)]
        is_same_vendor_dup = 1.0 if same_vendor_dup_count > 1 else 0.0

        # Build Rule Warnings List
        rule_warnings = []
        if is_same_vendor_dup:
            rule_warnings.append(
                f"Duplicate invoice number '{inv.invoice_number}' detected from vendor '{inv.vendor_name}'."
            )
        elif is_duplicate_number:
            rule_warnings.append(
                f"Invoice number '{inv.invoice_number}' is repeated across {dup_count} records."
            )

        if has_math_discrepancy:
            rule_warnings.append(
                f"Arithmetic discrepancy: Subtotal ({float(inv.subtotal):,.2f}) + Tax ({float(inv.tax_amount):,.2f}) does not equal Total ({amt:,.2f}) (difference: {math_diff:,.2f})."
            )

        if is_unusual_tax:
            rule_warnings.append(
                f"Tax ratio ({tax_ratio * 100:.1f}%) is unusually high (>35% of total amount)."
            )

        if is_negative_term:
            rule_warnings.append(
                f"Due date precedes invoice date by {abs(int(term_days))} day(s)."
            )

        if has_vendor_history and vendor_amount_ratio >= 2.5:
            rule_warnings.append(
                f"Amount is {vendor_amount_ratio:.1f}x higher than vendor '{inv.vendor_name}' median ({v_stat['median']:,.2f} {curr})."
            )

        # 13-Dimensional Numerical Feature Vector
        row = [
            log_amt_norm,
            currency_amount_ratio,
            tax_ratio,
            has_tax,
            is_unusual_tax,
            subtotal_ratio,
            has_subtotal,
            has_math_discrepancy,
            vendor_amount_ratio,
            has_vendor_history,
            term_days,
            has_due_date,
            is_duplicate_number,
        ]
        feature_rows.append(row)

        factor_dicts.append({
            "total_amount": amt,
            "currency": curr,
            "currency_median_amount": c_median,
            "currency_amount_ratio": currency_amount_ratio,
            "vendor_name": inv.vendor_name,
            "vendor_invoice_count": v_stat["count"],
            "vendor_median_amount": v_stat["median"],
            "vendor_amount_ratio": vendor_amount_ratio,
            "has_vendor_history": bool(has_vendor_history),
            "invoice_number": inv.invoice_number,
            "is_duplicate_number": bool(is_duplicate_number),
            "duplicate_count": dup_count,
            "is_same_vendor_dup": bool(is_same_vendor_dup),
            "tax_amount": float(inv.tax_amount) if inv.tax_amount is not None else None,
            "tax_ratio": tax_ratio if inv.tax_amount is not None else None,
            "has_tax": bool(has_tax),
            "is_unusual_tax": bool(is_unusual_tax),
            "subtotal": float(inv.subtotal) if inv.subtotal is not None else None,
            "has_subtotal": bool(has_subtotal),
            "has_math_discrepancy": bool(has_math_discrepancy),
            "math_difference": math_diff if has_math_discrepancy else 0.0,
            "term_days": int(term_days) if inv.due_date is not None else None,
            "has_due_date": bool(has_due_date),
            "is_negative_term": bool(is_negative_term),
            "rule_warnings": rule_warnings,
        })

    context_meta = {
        "currency_medians": currency_medians,
        "sample_count": n,
    }

    return np.array(feature_rows, dtype=np.float64), factor_dicts, context_meta


def calculate_risk_level(
    is_anomaly: bool,
    decision_score: float,
    factors: Dict[str, Any],
) -> str:
    """
    Computes a statistically grounded, non-alarmist risk classification
    (LOW, MEDIUM, HIGH) without fabricated percentage claims.
    """
    if not is_anomaly:
        return "LOW"

    # Extreme outlier or severe structural anomalies -> HIGH
    if (
        decision_score <= -0.06
        or factors["is_duplicate_number"]
        or factors.get("has_math_discrepancy", False)
        or (factors["has_vendor_history"] and factors["vendor_amount_ratio"] >= 3.5)
    ):
        return "HIGH"

    # Moderate statistical deviation -> MEDIUM
    return "MEDIUM"


def generate_explanation(
    is_anomaly: bool,
    factors: Dict[str, Any],
) -> str:
    """
    Generates a factual, transparent human-understandable explanation citing
    specific numbers, vendor medians, and observed discrepancies.
    """
    curr = factors.get("currency", "USD")
    amt = factors["total_amount"]

    if not is_anomaly:
        if factors["has_vendor_history"]:
            return (
                f"Invoice amount ({amt:,.2f} {curr}) and financial ratios are within normal expected parameters "
                f"for vendor '{factors['vendor_name']}' (median: {factors['vendor_median_amount']:,.2f} {curr})."
            )
        return (
            f"Invoice amount ({amt:,.2f} {curr}) and financial ratios conform to normal expected distributions "
            f"for your overall {curr} account history."
        )

    observations = []

    # Priority 1: Duplicate Invoice Number
    if factors.get("is_same_vendor_dup"):
        observations.append(
            f"Duplicate invoice number '{factors['invoice_number']}' already exists from vendor '{factors['vendor_name']}'."
        )
    elif factors.get("is_duplicate_number"):
        observations.append(
            f"Duplicate invoice number '{factors['invoice_number']}' matches {factors['duplicate_count']} existing invoices in your records."
        )

    # Priority 2: Vendor Deviation
    if factors["has_vendor_history"]:
        v_ratio = factors["vendor_amount_ratio"]
        v_median = factors["vendor_median_amount"]
        if v_ratio >= 2.0:
            observations.append(
                f"Total amount ({amt:,.2f} {curr}) is {v_ratio:.1f}x higher than the historical median "
                f"({v_median:,.2f} {curr}) for vendor '{factors['vendor_name']}'."
            )
        elif v_ratio <= 0.25 and v_median > 0:
            observations.append(
                f"Total amount ({amt:,.2f} {curr}) is significantly lower ({v_ratio:.1f}x) "
                f"than usual for vendor '{factors['vendor_name']}' ({v_median:,.2f} {curr} median)."
            )
    else:
        # First invoice for vendor
        c_ratio = factors["currency_amount_ratio"]
        c_median = factors["currency_median_amount"]
        if c_ratio >= 3.0:
            observations.append(
                f"Total amount ({amt:,.2f} {curr}) is {c_ratio:.1f}x higher than your overall median {curr} invoice size ({c_median:,.2f} {curr})."
            )

    # Priority 3: Arithmetic discrepancy
    if factors.get("has_math_discrepancy"):
        observations.append(
            f"Subtotal ({factors['subtotal']:,.2f}) + Tax ({factors['tax_amount']:,.2f}) does not equal Total ({amt:,.2f}) "
            f"({factors['math_difference']:,.2f} difference)."
        )

    # Priority 4: Tax irregularity
    if factors.get("is_unusual_tax") and factors["tax_ratio"] is not None:
        t_pct = factors["tax_ratio"] * 100.0
        observations.append(
            f"Tax proportion ({t_pct:.1f}% of total) is unusually high (>35%)."
        )

    # Priority 5: Payment term irregularity
    if factors.get("is_negative_term"):
        observations.append(
            f"Due date precedes invoice date by {abs(factors['term_days'])} day(s)."
        )
    elif factors["has_due_date"] and factors["term_days"] is not None and factors["term_days"] > 120:
        observations.append(
            f"Payment term ({factors['term_days']} days) is unusually extended."
        )

    if observations:
        return " ".join(observations)

    # Fallback multi-dimensional tree isolation explanation
    return (
        f"Statistical multivariate isolation detected: Combined invoice values "
        f"(amount {amt:,.2f} {curr}, financial ratios, and timing) form an isolated pattern."
    )


def assess_user_invoices(
    user_id: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Fits Isolation Forest on all invoices for the authenticated user and updates
    persistent InvoiceAnomaly records.
    
    Strict guarantees:
    - User data isolation: Trains and predicts ONLY on current user's invoices.
    - Insufficient data handling: If invoices < 5, returns clear status without training.
    - Safe error handling: Catches ML exceptions so the API and app never crash.
    - Review Preservation: Preserves user review state, timestamps, and notes on re-assessment.
    """
    # 1. Fetch user's invoices
    invoices = (
        db.query(Invoice)
        .filter(Invoice.user_id == user_id)
        .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
        .all()
    )

    total_invoices = len(invoices)

    if total_invoices < MIN_INVOICES_FOR_ANOMALY_MODEL:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": (
                f"Insufficient data: At least {MIN_INVOICES_FOR_ANOMALY_MODEL} saved invoices "
                f"are required to fit the anomaly detection model (currently have {total_invoices}). "
                f"Please add {MIN_INVOICES_FOR_ANOMALY_MODEL - total_invoices} more invoice(s) to enable machine learning analysis."
            ),
            "total_invoices": total_invoices,
            "assessed_count": 0,
            "anomalous_count": 0,
            "normal_count": 0,
            "reviewed_count": 0,
            "unreviewed_anomalous_count": 0,
            "min_required": MIN_INVOICES_FOR_ANOMALY_MODEL,
            "disclaimer": DISCLAIMER_TEXT,
            "items": [],
        }

    try:
        # 2. Extract features safely
        X, factor_dicts, context_meta = extract_invoice_features(invoices)

        # 3. Robust scaling to prevent extreme outliers from skewing tree splits
        scaler = RobustScaler(unit_variance=True)
        X_scaled = scaler.fit_transform(X)

        # 4. Fit Isolation Forest
        contamination_rate = min(0.20, max(0.05, 1.0 / total_invoices))
        model = IsolationForest(
            n_estimators=100,
            contamination=contamination_rate,
            random_state=42,
        )
        model.fit(X_scaled)

        # 5. Predict labels (-1: anomaly, 1: normal) and continuous decision scores
        raw_preds = model.predict(X_scaled)
        decision_scores = model.decision_function(X_scaled)

        now = datetime.now(timezone.utc)
        assessed_items = []
        anomalous_count = 0
        normal_count = 0
        reviewed_count = 0

        # 6. Upsert results into database while preserving audit review state
        for idx, inv in enumerate(invoices):
            factors = factor_dicts[idx]
            # Flag if tree isolated (-1) OR if structural red flags exist (duplicate number, severe math discrepancy)
            is_anomaly = bool(
                raw_preds[idx] == -1
                or factors.get("is_duplicate_number", False)
                or factors.get("has_math_discrepancy", False)
            )
            score = float(decision_scores[idx])

            if is_anomaly:
                status_str = "POTENTIALLY_UNUSUAL"
                anomalous_count += 1
            else:
                status_str = "NO_UNUSUAL_PATTERN"
                normal_count += 1

            risk_lvl = calculate_risk_level(is_anomaly, score, factors)
            explanation = generate_explanation(is_anomaly, factors)

            # Check if record already exists for this invoice
            anomaly_record = (
                db.query(InvoiceAnomaly)
                .filter(InvoiceAnomaly.invoice_id == inv.id, InvoiceAnomaly.user_id == user_id)
                .first()
            )

            is_reviewed = False
            reviewed_at = None
            review_notes = None

            if anomaly_record:
                # IMPORTANT: preserve review status and notes if user previously reviewed this invoice!
                is_reviewed = anomaly_record.is_reviewed
                reviewed_at = anomaly_record.reviewed_at
                review_notes = anomaly_record.review_notes

                anomaly_record.is_anomaly = is_anomaly
                anomaly_record.anomaly_score = score
                anomaly_record.status = status_str
                anomaly_record.risk_level = risk_lvl
                anomaly_record.explanation = explanation
                anomaly_record.factors_json = json.dumps(factors)
                anomaly_record.model_version = MODEL_VERSION
                anomaly_record.assessed_at = now
            else:
                anomaly_record = InvoiceAnomaly(
                    invoice_id=inv.id,
                    user_id=user_id,
                    is_anomaly=is_anomaly,
                    anomaly_score=score,
                    status=status_str,
                    risk_level=risk_lvl,
                    explanation=explanation,
                    factors_json=json.dumps(factors),
                    model_version=MODEL_VERSION,
                    assessed_at=now,
                    is_reviewed=False,
                )
                db.add(anomaly_record)

            db.flush()

            if is_reviewed:
                reviewed_count += 1

            assessed_items.append({
                "id": anomaly_record.id,
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "vendor_name": inv.vendor_name,
                "invoice_date": inv.invoice_date,
                "total_amount": inv.total_amount,
                "currency": inv.currency or "USD",
                "is_anomaly": is_anomaly,
                "anomaly_score": score,
                "status": status_str,
                "risk_level": risk_lvl,
                "is_reviewed": is_reviewed,
                "reviewed_at": reviewed_at,
                "review_notes": review_notes,
                "rule_warnings": factors.get("rule_warnings", []),
                "explanation": explanation,
                "model_version": MODEL_VERSION,
                "assessed_at": now,
            })

        db.commit()

        unreviewed_anomalous_count = sum(
            1 for it in assessed_items if it["is_anomaly"] and not it["is_reviewed"]
        )

        return {
            "status": "COMPLETED",
            "message": (
                f"Successfully assessed {total_invoices} invoices using Isolation Forest. "
                f"Identified {anomalous_count} potentially unusual pattern(s)."
            ),
            "total_invoices": total_invoices,
            "assessed_count": len(assessed_items),
            "anomalous_count": anomalous_count,
            "normal_count": normal_count,
            "reviewed_count": reviewed_count,
            "unreviewed_anomalous_count": unreviewed_anomalous_count,
            "min_required": MIN_INVOICES_FOR_ANOMALY_MODEL,
            "disclaimer": DISCLAIMER_TEXT,
            "items": assessed_items,
        }

    except Exception as e:
        logger.error(f"Error during anomaly assessment for user {user_id}: {str(e)}", exc_info=True)
        db.rollback()
        return {
            "status": "ERROR",
            "message": f"Machine learning anomaly assessment encountered an error: {str(e)}",
            "total_invoices": total_invoices,
            "assessed_count": 0,
            "anomalous_count": 0,
            "normal_count": 0,
            "reviewed_count": 0,
            "unreviewed_anomalous_count": 0,
            "min_required": MIN_INVOICES_FOR_ANOMALY_MODEL,
            "disclaimer": DISCLAIMER_TEXT,
            "items": [],
        }
