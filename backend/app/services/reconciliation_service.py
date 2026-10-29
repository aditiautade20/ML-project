from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Set

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.reconciliation import ReconciliationBatch, ReconciliationItem
from app.services.payment_service import calculate_invoice_financials
from app.services.reconciliation_parser import (
    parse_numeric_decimal,
    parse_tabular_file,
    auto_map_columns,
)
from app.services.extractor import parse_date_flexible

logger = logging.getLogger(__name__)


def clean_alphanumeric(val: Any) -> str:
    """Removes non-alphanumeric characters and lowercases string for robust key matching."""
    if not val:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(val).strip().lower())


def clean_vendor_name(vendor: Any) -> str:
    """Normalizes vendor name by removing corporate entity suffixes and punctuation."""
    if not vendor:
        return ""
    v = str(vendor).strip().lower()
    v = re.sub(r"[^\w\s]", " ", v)
    suffixes = [
        r"\binc\b", r"\bincorporated\b", r"\bltd\b", r"\blimited\b", r"\bcorp\b",
        r"\bcorporation\b", r"\bllc\b", r"\bpvt\b", r"\bco\b", r"\bcompany\b",
        r"\bservices\b", r"\bsolutions\b", r"\btechnologies\b", r"\bsupplies\b"
    ]
    for suf in suffixes:
        v = re.sub(suf, "", v)
    return re.sub(r"\s+", " ", v).strip()


def vendor_names_or_tokens_match(name1: Optional[str], name2: Optional[str]) -> bool:
    """Checks if two vendor names or counterparty descriptions match by substring or significant token overlap."""
    if not name1 or not name2:
        return False
    c1 = clean_vendor_name(name1)
    c2 = clean_vendor_name(name2)
    if not c1 or not c2:
        return False
    if c1 in c2 or c2 in c1:
        return True
    t1 = {t for t in c1.split() if len(t) >= 4}
    t2 = {t for t in c2.split() if len(t) >= 4}
    return bool(t1.intersection(t2))


def run_ledger_reconciliation(
    user_id: int,
    file_content: bytes,
    filename: str,
    column_mapping: Optional[Dict[str, str]] = None,
    amount_tolerance: Decimal = Decimal("0.05"),
    db: Session = None,
) -> ReconciliationBatch:
    """
    Compares authenticated user's invoices against an uploaded accounting ledger (CSV/XLSX).
    Identifies exact matches, amount mismatches, tax mismatches, missing ledger records,
    missing invoices, and duplicate entries.
    """
    headers, rows, file_hash, parse_errors = parse_tabular_file(file_content, filename)
    if parse_errors:
        raise ValueError(f"File parsing error: {'; '.join(parse_errors)}")

    # Auto-map columns if not explicitly supplied
    mapping = column_mapping or auto_map_columns(headers, "LEDGER", rows=rows)
    inv_col = mapping.get("invoice_number")
    tot_col = mapping.get("total_amount")
    debit_col = mapping.get("debit_column") or mapping.get("debit_amount") or mapping.get("debit")
    credit_col = mapping.get("credit_column") or mapping.get("credit_amount") or mapping.get("credit")
    ven_col = mapping.get("vendor_name")
    dat_col = mapping.get("invoice_date")
    sub_col = mapping.get("subtotal")
    tax_col = mapping.get("tax_amount")
    cur_col = mapping.get("currency")

    # If tot_col is missing but debit_col or credit_col was provided in custom mapping:
    if not tot_col and (debit_col or credit_col):
        tot_col = debit_col or credit_col

    if not inv_col or not tot_col:
        raise ValueError(
            f"Required columns missing: Could not map 'invoice_number' and 'total_amount'. "
            f"Detected headers: {', '.join(headers)}. Please specify custom column mapping."
        )

    # 1. Fetch user's saved invoices
    invoices = db.query(Invoice).filter(Invoice.user_id == user_id).all()
    inv_by_clean_num: Dict[str, Invoice] = {clean_alphanumeric(inv.invoice_number): inv for inv in invoices}
    matched_invoice_ids: Set[int] = set()

    # Create Batch Record
    batch = ReconciliationBatch(
        user_id=user_id,
        batch_type="LEDGER",
        title=f"Ledger Reconciliation — {filename}",
        status="COMPLETED",
        ledger_filename=filename,
        ledger_hash=file_hash,
        amount_tolerance=amount_tolerance,
        total_records=0,
        exact_matches=0,
        mismatches=0,
        unmatched_records=0,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    items: List[ReconciliationItem] = []
    seen_ledger_keys: Set[str] = set()

    # 2. Iterate through Ledger Rows
    for idx, row in enumerate(rows, start=1):
        raw_inv_num = str(row.get(inv_col, "")).strip()
        raw_total = row.get(tot_col, "")
        raw_vendor = str(row.get(ven_col, "")).strip() if ven_col else ""
        raw_date = str(row.get(dat_col, "")).strip() if dat_col else ""
        raw_subtotal = row.get(sub_col, "") if sub_col else None
        raw_tax = row.get(tax_col, "") if tax_col else None
        raw_currency = str(row.get(cur_col, "USD")).strip().upper() if cur_col else "USD"

        parsed_amount = parse_numeric_decimal(raw_total)
        # Adapt for separate debit and credit columns if primary total is empty or zero
        if (parsed_amount is None or parsed_amount == Decimal("0.00")):
            if debit_col and debit_col != tot_col:
                d_val = parse_numeric_decimal(row.get(debit_col, ""))
                if d_val is not None and d_val != Decimal("0.00"):
                    parsed_amount = abs(d_val)
            if (parsed_amount is None or parsed_amount == Decimal("0.00")) and credit_col and credit_col != tot_col:
                c_val = parse_numeric_decimal(row.get(credit_col, ""))
                if c_val is not None and c_val != Decimal("0.00"):
                    parsed_amount = abs(c_val)
        elif parsed_amount is not None:
            parsed_amount = abs(parsed_amount)
        parsed_sub = parse_numeric_decimal(raw_subtotal) if raw_subtotal else None
        parsed_tax = parse_numeric_decimal(raw_tax) if raw_tax else None

        clean_num = clean_alphanumeric(raw_inv_num)
        record_id = raw_inv_num if raw_inv_num else f"Row #{idx}"

        if not clean_num:
            # Row without invoice number
            item = ReconciliationItem(
                batch_id=batch.id,
                user_id=user_id,
                item_type="LEDGER",
                match_status="MISSING_IN_INVOICES",
                record_identifier=record_id,
                vendor_or_counterparty=raw_vendor,
                transaction_date=raw_date,
                expected_value="N/A",
                actual_value=f"{raw_currency} {parsed_amount:.2f}" if parsed_amount else "N/A",
                discrepancy_amount=parsed_amount,
                currency=raw_currency,
                evidence_text="Ledger entry lacks an invoice number and cannot be matched.",
                action_recommendation="Verify invoice reference in your accounting system.",
                review_status="PENDING",
                raw_record_json=json.dumps(row),
            )
            items.append(item)
            batch.unmatched_records += 1
            continue

        # Check for suspected duplicate ledger entry
        is_dup = clean_num in seen_ledger_keys
        seen_ledger_keys.add(clean_num)

        invoice = inv_by_clean_num.get(clean_num)

        if invoice:
            matched_invoice_ids.add(invoice.id)
            exp_total = Decimal(str(invoice.total_amount))
            act_total = parsed_amount if parsed_amount is not None else Decimal("0.00")
            diff = act_total - exp_total
            abs_diff = abs(diff)

            if is_dup:
                status = "DUPLICATE_SUSPECTED"
                evidence = f"Duplicate ledger entry: Invoice #{raw_inv_num} appears multiple times in uploaded ledger."
                recom = "Verify whether this represents a duplicate booking or duplicate payment."
                batch.mismatches += 1
            elif abs_diff <= amount_tolerance:
                # Check subtotal and tax amounts if provided in ledger
                tax_mismatch = False
                if parsed_tax is not None and invoice.tax_amount is not None:
                    if abs(parsed_tax - Decimal(str(invoice.tax_amount))) > amount_tolerance:
                        tax_mismatch = True

                if tax_mismatch:
                    status = "TAX_MISMATCH"
                    evidence = (
                        f"Invoice total matches ({raw_currency} {act_total:.2f}), but ledger tax ({parsed_tax}) "
                        f"differs from invoice tax ({invoice.tax_amount})."
                    )
                    recom = "Review tax distribution between CGST/SGST/IGST or net tax classification."
                    batch.mismatches += 1
                else:
                    status = "EXACT_MATCH"
                    evidence = (
                        f"Exact match on Invoice #{invoice.invoice_number}. "
                        f"Ledger amount ({raw_currency} {act_total:.2f}) matches invoice total within tolerance."
                    )
                    recom = "No action required. Records are reconciled."
                    batch.exact_matches += 1
            else:
                status = "AMOUNT_MISMATCH"
                evidence = (
                    f"Invoice #{invoice.invoice_number} found, but ledger amount ({raw_currency} {act_total:.2f}) "
                    f"differs from saved invoice total ({invoice.currency} {exp_total:.2f}) by {diff:+.2f}."
                )
                recom = "Investigate price discrepancy, credit memo, or rounding difference."
                batch.mismatches += 1

            item = ReconciliationItem(
                batch_id=batch.id,
                user_id=user_id,
                invoice_id=invoice.id,
                item_type="LEDGER",
                match_status=status,
                record_identifier=invoice.invoice_number,
                vendor_or_counterparty=raw_vendor or invoice.vendor_name,
                transaction_date=raw_date or str(invoice.invoice_date),
                expected_value=f"{invoice.currency} {exp_total:.2f}",
                actual_value=f"{raw_currency} {act_total:.2f}",
                discrepancy_amount=diff,
                currency=raw_currency,
                evidence_text=evidence,
                action_recommendation=recom,
                review_status="CONFIRMED" if status == "EXACT_MATCH" else "PENDING",
                raw_record_json=json.dumps(row),
            )
            items.append(item)

        else:
            # Ledger entry not in InvoiceIQ
            # Check for ambiguous fuzzy candidate match (same vendor and exact amount)
            fuzzy_candidate = None
            if parsed_amount is not None and raw_vendor:
                clean_v = clean_vendor_name(raw_vendor)
                for inv in invoices:
                    if inv.id not in matched_invoice_ids:
                        if abs(Decimal(str(inv.total_amount)) - parsed_amount) <= amount_tolerance:
                            if clean_v in clean_vendor_name(inv.vendor_name) or clean_vendor_name(inv.vendor_name) in clean_v:
                                fuzzy_candidate = inv
                                break

            if fuzzy_candidate:
                status = "AMBIGUOUS_MATCH"
                evidence = (
                    f"Ledger invoice #{raw_inv_num} not in system, but open invoice #{fuzzy_candidate.invoice_number} "
                    f"from '{fuzzy_candidate.vendor_name}' has the exact amount ({parsed_amount:.2f})."
                )
                recom = "Confirm if ledger entry refers to invoice #{fuzzy_candidate.invoice_number} under a typo/prefix."
                inv_link_id = fuzzy_candidate.id
                batch.mismatches += 1
            else:
                status = "MISSING_IN_INVOICES"
                evidence = f"Ledger entry #{raw_inv_num} for '{raw_vendor}' ({parsed_amount:.2f}) does not exist in InvoiceIQ."
                recom = "Upload the missing vendor invoice to InvoiceIQ or remove erroneous ledger entry."
                inv_link_id = None
                batch.unmatched_records += 1

            item = ReconciliationItem(
                batch_id=batch.id,
                user_id=user_id,
                invoice_id=inv_link_id,
                item_type="LEDGER",
                match_status=status,
                record_identifier=raw_inv_num,
                vendor_or_counterparty=raw_vendor,
                transaction_date=raw_date,
                expected_value="Not in InvoiceIQ",
                actual_value=f"{raw_currency} {parsed_amount:.2f}" if parsed_amount else "N/A",
                discrepancy_amount=parsed_amount,
                currency=raw_currency,
                evidence_text=evidence,
                action_recommendation=recom,
                review_status="PENDING",
                raw_record_json=json.dumps(row),
            )
            items.append(item)

    # 3. Identify Invoices Missing from Ledger
    for inv in invoices:
        if inv.id not in matched_invoice_ids:
            exp_val = Decimal(str(inv.total_amount))
            item = ReconciliationItem(
                batch_id=batch.id,
                user_id=user_id,
                invoice_id=inv.id,
                item_type="LEDGER",
                match_status="MISSING_IN_LEDGER",
                record_identifier=inv.invoice_number,
                vendor_or_counterparty=inv.vendor_name,
                transaction_date=str(inv.invoice_date),
                expected_value=f"{inv.currency} {exp_val:.2f}",
                actual_value="Missing from Ledger",
                discrepancy_amount=-exp_val,
                currency=inv.currency,
                evidence_text=f"Confirmed Invoice #{inv.invoice_number} ({inv.currency} {exp_val:.2f}) was not found in uploaded ledger.",
                action_recommendation="Post this invoice to your accounting general ledger to reflect liability.",
                review_status="PENDING",
                raw_record_json=None,
            )
            items.append(item)
            batch.unmatched_records += 1

    batch.total_records = len(items)
    batch.summary_json = json.dumps({
        "total_items": len(items),
        "exact_matches": batch.exact_matches,
        "mismatches": batch.mismatches,
        "unmatched": batch.unmatched_records,
        "ledger_rows_count": len(rows),
        "invoices_count": len(invoices),
    })

    db.add_all(items)
    db.commit()
    db.refresh(batch)
    return batch


def run_bank_reconciliation(
    user_id: int,
    file_content: bytes,
    filename: str,
    column_mapping: Optional[Dict[str, str]] = None,
    amount_tolerance: Decimal = Decimal("0.05"),
    db: Session = None,
) -> ReconciliationBatch:
    """
    Parses bank transactions and matches outgoing debits against recorded InvoiceIQ payments
    and open accounts payable liabilities.
    Enforces critical safety rule: Bank statement import NEVER automatically modifies
    payments or balances; proposed matches are returned for explicit confirmation.
    """
    headers, rows, file_hash, parse_errors = parse_tabular_file(file_content, filename)
    if parse_errors:
        raise ValueError(f"File parsing error: {'; '.join(parse_errors)}")

    mapping = column_mapping or auto_map_columns(headers, "BANK", rows=rows)
    dat_col = mapping.get("transaction_date")
    des_col = mapping.get("description")
    deb_col = mapping.get("debit_amount")
    cre_col = mapping.get("credit_amount")
    amt_col = mapping.get("amount")
    ref_col = mapping.get("reference_id")
    cur_col = mapping.get("currency")

    if not dat_col or not (deb_col or amt_col):
        raise ValueError(
            f"Required columns missing: Could not map 'transaction_date' and debit/amount. "
            f"Detected headers: {', '.join(headers)}. Please specify custom column mapping."
        )

    # 1. Fetch user's payments and invoices
    payments = (
        db.query(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .filter(Payment.user_id == user_id)
        .options(joinedload(Payment.invoice))
        .all()
    )
    invoices = db.query(Invoice).filter(Invoice.user_id == user_id).all()

    matched_payment_ids: Set[int] = set()

    batch = ReconciliationBatch(
        user_id=user_id,
        batch_type="BANK",
        title=f"Bank Statement Reconciliation — {filename}",
        status="COMPLETED",
        bank_filename=filename,
        bank_hash=file_hash,
        amount_tolerance=amount_tolerance,
        total_records=0,
        exact_matches=0,
        mismatches=0,
        unmatched_records=0,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    items: List[ReconciliationItem] = []

    # 2. Process Bank Transactions
    for idx, row in enumerate(rows, start=1):
        raw_date_str = str(row.get(dat_col, "")).strip()
        raw_desc = str(row.get(des_col, "")).strip() if des_col else ""
        raw_ref = str(row.get(ref_col, "")).strip() if ref_col else ""
        raw_cur = str(row.get(cur_col, "USD")).strip().upper() if cur_col else "USD"

        # Determine transaction debit amount
        debit_val = None
        if deb_col and row.get(deb_col):
            debit_val = parse_numeric_decimal(row.get(deb_col))
        elif amt_col and row.get(amt_col):
            parsed_raw = parse_numeric_decimal(row.get(amt_col))
            # If negative or credit is 0/empty, treat as debit
            if parsed_raw is not None and parsed_raw < 0:
                debit_val = abs(parsed_raw)
            elif cre_col and not row.get(cre_col):
                debit_val = parsed_raw

        # If transaction is an incoming deposit (Credit) and not a debit:
        if debit_val is None or debit_val <= Decimal("0.00"):
            # Skip or record as non-AP credit
            continue

        record_id = raw_ref if raw_ref else f"BankTxn-{idx:04d}"

        # Strategy A: Check match against existing recorded Payments
        payment_match = None
        for p in payments:
            if p.id not in matched_payment_ids:
                # Check reference match
                if raw_ref and p.reference and clean_alphanumeric(raw_ref) == clean_alphanumeric(p.reference):
                    payment_match = p
                    break
                # Check amount match within tolerance
                if abs(Decimal(str(p.amount)) - debit_val) <= amount_tolerance:
                    # Check description similarity or invoice match
                    if p.invoice and (
                        vendor_names_or_tokens_match(p.invoice.vendor_name, raw_desc)
                        or (p.invoice.invoice_number and clean_alphanumeric(p.invoice.invoice_number) in clean_alphanumeric(raw_desc))
                    ):
                        payment_match = p
                        break

        if payment_match:
            matched_payment_ids.add(payment_match.id)
            inv = payment_match.invoice
            exp_amt = Decimal(str(payment_match.amount))
            diff = debit_val - exp_amt

            item = ReconciliationItem(
                batch_id=batch.id,
                user_id=user_id,
                invoice_id=inv.id if inv else None,
                payment_id=payment_match.id,
                item_type="BANK",
                match_status="EXACT_MATCH",
                record_identifier=record_id,
                vendor_or_counterparty=inv.vendor_name if inv else raw_desc,
                transaction_date=raw_date_str,
                expected_value=f"{raw_cur} {exp_amt:.2f}",
                actual_value=f"{raw_cur} {debit_val:.2f}",
                discrepancy_amount=diff,
                currency=raw_cur,
                evidence_text=(
                    f"Cleared payment confirmed: Bank debit matches recorded payment of {raw_cur} {exp_amt:.2f} "
                    f"against Invoice #{inv.invoice_number if inv else 'N/A'} (Ref: {payment_match.reference or 'None'})."
                ),
                action_recommendation="No action required. Payment cleared in bank.",
                review_status="CONFIRMED",
                raw_record_json=json.dumps(row),
            )
            items.append(item)
            batch.exact_matches += 1
            continue

        # Strategy B: Check unrecorded payment match against open invoices
        open_inv_match = None
        for inv in invoices:
            total_paid, bal_due, p_status = calculate_invoice_financials(inv)
            if bal_due > Decimal("0.00"):
                if abs(bal_due - debit_val) <= amount_tolerance or abs(Decimal(str(inv.total_amount)) - debit_val) <= amount_tolerance:
                    if (
                        vendor_names_or_tokens_match(inv.vendor_name, raw_desc)
                        or (inv.invoice_number and clean_alphanumeric(inv.invoice_number) in clean_alphanumeric(raw_desc))
                        or (raw_ref and clean_alphanumeric(inv.invoice_number) in clean_alphanumeric(raw_ref))
                    ):
                        open_inv_match = inv
                        break

        if open_inv_match:
            # Found matching open invoice: Candidate for payment creation!
            total_paid, bal_due, p_status = calculate_invoice_financials(open_inv_match)
            item = ReconciliationItem(
                batch_id=batch.id,
                user_id=user_id,
                invoice_id=open_inv_match.id,
                item_type="BANK",
                match_status="AMBIGUOUS_MATCH",
                record_identifier=record_id,
                vendor_or_counterparty=open_inv_match.vendor_name,
                transaction_date=raw_date_str,
                expected_value=f"{open_inv_match.currency} {bal_due:.2f} due",
                actual_value=f"{raw_cur} {debit_val:.2f}",
                discrepancy_amount=debit_val - bal_due,
                currency=raw_cur,
                evidence_text=(
                    f"Potential unrecorded bank settlement: Bank debit {raw_cur} {debit_val:.2f} matches "
                    f"open balance on Invoice #{open_inv_match.invoice_number} ({open_inv_match.vendor_name})."
                ),
                action_recommendation="Review and click 'Confirm & Record Payment' to record this payment in InvoiceIQ.",
                review_status="PENDING",
                raw_record_json=json.dumps(row),
            )
            items.append(item)
            batch.mismatches += 1
            continue

        # Strategy C: Unmatched bank transaction
        item = ReconciliationItem(
            batch_id=batch.id,
            user_id=user_id,
            item_type="BANK",
            match_status="UNMATCHED_BANK_TXN",
            record_identifier=record_id,
            vendor_or_counterparty=raw_desc,
            transaction_date=raw_date_str,
            expected_value="Unmatched",
            actual_value=f"{raw_cur} {debit_val:.2f}",
            discrepancy_amount=debit_val,
            currency=raw_cur,
            evidence_text=f"Bank debit of {raw_cur} {debit_val:.2f} ('{raw_desc}') does not correspond to any invoice or payment.",
            action_recommendation="Verify if this represents non-invoice operating expense, bank fee, or unrecorded bill.",
            review_status="PENDING",
            raw_record_json=json.dumps(row),
        )
        items.append(item)
        batch.unmatched_records += 1

    # 3. Identify recorded payments not found on the bank statement
    for p in payments:
        if p.id not in matched_payment_ids:
            inv = p.invoice
            exp_amt = Decimal(str(p.amount))
            item = ReconciliationItem(
                batch_id=batch.id,
                user_id=user_id,
                invoice_id=inv.id if inv else None,
                payment_id=p.id,
                item_type="BANK",
                match_status="UNMATCHED_PAYMENT",
                record_identifier=p.reference or f"Pay-{p.id}",
                vendor_or_counterparty=inv.vendor_name if inv else "Unknown",
                transaction_date=str(p.payment_date),
                expected_value=f"{inv.currency if inv else 'USD'} {exp_amt:.2f}",
                actual_value="Not on Bank Statement",
                discrepancy_amount=-exp_amt,
                currency=inv.currency if inv else "USD",
                evidence_text=(
                    f"Payment #{p.id} of {exp_amt:.2f} recorded on {p.payment_date} against Invoice "
                    f"#{inv.invoice_number if inv else 'N/A'} was not cleared on this bank statement."
                ),
                action_recommendation="Check if payment is in transit, pending clearance, or check date range.",
                review_status="PENDING",
                raw_record_json=None,
            )
            items.append(item)
            batch.unmatched_records += 1

    batch.total_records = len(items)
    batch.summary_json = json.dumps({
        "total_items": len(items),
        "exact_matches": batch.exact_matches,
        "mismatches": batch.mismatches,
        "unmatched": batch.unmatched_records,
        "bank_rows_count": len(rows),
        "payments_count": len(payments),
    })

    db.add_all(items)
    db.commit()
    db.refresh(batch)
    return batch


def run_combined_reconciliation(
    user_id: int,
    ledger_content: bytes,
    ledger_filename: str,
    bank_content: bytes,
    bank_filename: str,
    ledger_mapping: Optional[Dict[str, str]] = None,
    bank_mapping: Optional[Dict[str, str]] = None,
    amount_tolerance: Decimal = Decimal("0.05"),
    db: Session = None,
) -> ReconciliationBatch:
    """
    Performs 4-way cross-verification across Invoices, Ledger, Payments, and Bank Transactions.
    """
    # Parse both files
    l_headers, l_rows, l_hash, l_errs = parse_tabular_file(ledger_content, ledger_filename)
    b_headers, b_rows, b_hash, b_errs = parse_tabular_file(bank_content, bank_filename)

    if l_errs:
        raise ValueError(f"Ledger file error: {'; '.join(l_errs)}")
    if b_errs:
        raise ValueError(f"Bank statement error: {'; '.join(b_errs)}")

    l_map = ledger_mapping or auto_map_columns(l_headers, "LEDGER", rows=l_rows)
    b_map = bank_mapping or auto_map_columns(b_headers, "BANK", rows=b_rows)

    batch = ReconciliationBatch(
        user_id=user_id,
        batch_type="COMBINED",
        title=f"Combined Reconciliation — {ledger_filename} & {bank_filename}",
        status="COMPLETED",
        ledger_filename=ledger_filename,
        ledger_hash=l_hash,
        bank_filename=bank_filename,
        bank_hash=b_hash,
        amount_tolerance=amount_tolerance,
        total_records=0,
        exact_matches=0,
        mismatches=0,
        unmatched_records=0,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    # Invoices & Payments for user
    invoices = db.query(Invoice).filter(Invoice.user_id == user_id).all()
    payments = db.query(Payment).filter(Payment.user_id == user_id).all()

    # Index ledger by clean invoice number
    l_inv_col = l_map.get("invoice_number", "invoice_number")
    l_tot_col = l_map.get("total_amount", "total_amount")
    ledger_by_inv_num: Dict[str, Dict[str, Any]] = {}
    for r in l_rows:
        num = clean_alphanumeric(r.get(l_inv_col, ""))
        if num:
            ledger_by_inv_num[num] = r

    # Index bank payments
    b_deb_col = b_map.get("debit_amount") or b_map.get("amount", "amount")
    b_des_col = b_map.get("description", "description")
    b_ref_col = b_map.get("reference_id", "reference_id")
    bank_debits: List[Tuple[Decimal, str, str, Dict[str, Any]]] = []
    for r in b_rows:
        amt = parse_numeric_decimal(r.get(b_deb_col))
        if amt and amt > 0:
            bank_debits.append((amt, str(r.get(b_des_col, "")), str(r.get(b_ref_col, "")), r))

    items: List[ReconciliationItem] = []
    matched_ledger_keys: Set[str] = set()
    matched_bank_indices: Set[int] = set()

    for inv in invoices:
        clean_num = clean_alphanumeric(inv.invoice_number)
        ledger_row = ledger_by_inv_num.get(clean_num)
        inv_payments = [p for p in payments if p.invoice_id == inv.id]
        inv_tot = Decimal(str(inv.total_amount))

        # Check ledger status
        has_ledger = ledger_row is not None
        ledger_match = False
        ledger_amt = Decimal("0.00")
        if has_ledger:
            matched_ledger_keys.add(clean_num)
            parsed_l_amt = parse_numeric_decimal(ledger_row.get(l_tot_col))
            if parsed_l_amt:
                ledger_amt = parsed_l_amt
                ledger_match = abs(ledger_amt - inv_tot) <= amount_tolerance

        # Check payment status
        total_paid, bal_due, p_status = calculate_invoice_financials(inv)

        # Check bank statement clearance
        bank_cleared = False
        bank_cleared_amt = Decimal("0.00")
        for b_idx, (b_amt, b_desc, b_ref, b_raw) in enumerate(bank_debits):
            desc_or_ref_match = (
                vendor_names_or_tokens_match(inv.vendor_name, b_desc)
                or (b_ref and clean_alphanumeric(inv.invoice_number) in clean_alphanumeric(b_ref))
                or (clean_alphanumeric(inv.invoice_number) in clean_alphanumeric(b_desc))
            )
            if desc_or_ref_match:
                if abs(b_amt - total_paid) <= amount_tolerance or abs(b_amt - inv_tot) <= amount_tolerance:
                    bank_cleared = True
                    bank_cleared_amt = b_amt
                    matched_bank_indices.add(b_idx)
                    break

        # Synthesize Combined Status
        if ledger_match and p_status == "PAID" and bank_cleared:
            status = "EXACT_MATCH"
            evidence = "Complete 4-Way Reconciliation: Invoice, Ledger entry, Payment record, and Bank debit all match."
            recom = "Fully reconciled and audited. No action required."
            batch.exact_matches += 1
        elif ledger_match and p_status != "PAID" and not bank_cleared:
            status = "EXACT_MATCH"
            evidence = f"Ledger verified unpaid liability: Invoice and Ledger match ({inv_tot:.2f}). No payment or bank debit (Due: {inv.due_date or 'N/A'})."
            recom = "Legitimate pending obligation. Settle prior to due date."
            batch.exact_matches += 1
        elif not has_ledger:
            status = "MISSING_IN_LEDGER"
            evidence = f"Invoice #{inv.invoice_number} is saved in InvoiceIQ but missing from accounting ledger."
            recom = "Post invoice to general ledger."
            batch.unmatched_records += 1
        elif not ledger_match:
            status = "AMOUNT_MISMATCH"
            evidence = f"Invoice total ({inv_tot:.2f}) does not match Ledger amount ({ledger_amt:.2f})."
            recom = "Investigate price discrepancy or tax adjustments."
            batch.mismatches += 1
        else:
            status = "AMBIGUOUS_MATCH"
            evidence = f"Partial reconciliation: Ledger matches, but payment status ({p_status}) and bank clearance differ."
            recom = "Review bank statement to ensure payment clearance."
            batch.mismatches += 1

        item = ReconciliationItem(
            batch_id=batch.id,
            user_id=user_id,
            invoice_id=inv.id,
            item_type="COMBINED",
            match_status=status,
            record_identifier=inv.invoice_number,
            vendor_or_counterparty=inv.vendor_name,
            transaction_date=str(inv.invoice_date),
            expected_value=f"Invoice: {inv.currency} {inv_tot:.2f}",
            actual_value=f"Ledger: {ledger_amt:.2f} | Bank: {bank_cleared_amt:.2f}",
            discrepancy_amount=ledger_amt - inv_tot if has_ledger else -inv_tot,
            currency=inv.currency,
            evidence_text=evidence,
            action_recommendation=recom,
            review_status="CONFIRMED" if status == "EXACT_MATCH" else "PENDING",
            raw_record_json=json.dumps(ledger_row) if ledger_row else None,
        )
        items.append(item)

    # 2. Check for Ledger entries that had no corresponding invoice in InvoiceIQ
    for clean_num, l_row in ledger_by_inv_num.items():
        if clean_num not in matched_ledger_keys:
            raw_inv = str(l_row.get(l_inv_col, "")).strip() or "Ledger-Entry"
            parsed_amt = parse_numeric_decimal(l_row.get(l_tot_col)) or Decimal("0.00")
            item = ReconciliationItem(
                batch_id=batch.id,
                user_id=user_id,
                item_type="COMBINED",
                match_status="MISSING_IN_INVOICES",
                record_identifier=raw_inv,
                vendor_or_counterparty=str(l_row.get(l_map.get("vendor_name", "vendor_name"), "N/A")),
                transaction_date=str(l_row.get(l_map.get("invoice_date", "invoice_date"), "")),
                expected_value="Invoice: None",
                actual_value=f"Ledger: {parsed_amt:.2f}",
                discrepancy_amount=parsed_amt,
                currency="USD",
                evidence_text=f"Ledger entry #{raw_inv} exists in accounting records but is missing from InvoiceIQ.",
                action_recommendation="Verify whether an invoice was omitted or recorded under a different reference.",
                review_status="PENDING",
                raw_record_json=json.dumps(l_row),
            )
            items.append(item)
            batch.unmatched_records += 1

    # 3. Check for Bank debits that had no corresponding invoice / payment
    for b_idx, (b_amt, b_desc, b_ref, b_raw) in enumerate(bank_debits):
        if b_idx not in matched_bank_indices:
            rec_id = b_ref if b_ref else f"BankTxn-{b_idx+1:04d}"
            item = ReconciliationItem(
                batch_id=batch.id,
                user_id=user_id,
                item_type="COMBINED",
                match_status="UNMATCHED_BANK_TXN",
                record_identifier=rec_id,
                vendor_or_counterparty=b_desc,
                transaction_date=str(b_raw.get(b_map.get("transaction_date", "transaction_date"), "")),
                expected_value="Invoice / Payment: None",
                actual_value=f"Bank Debit: {b_amt:.2f}",
                discrepancy_amount=b_amt,
                currency="USD",
                evidence_text=f"Bank statement debit of {b_amt:.2f} ('{b_desc}') does not correspond to any invoice or recorded payment.",
                action_recommendation="Investigate bank transaction for unrecorded expense or non-AP withdrawal.",
                review_status="PENDING",
                raw_record_json=json.dumps(b_raw),
            )
            items.append(item)
            batch.unmatched_records += 1

    batch.total_records = len(items)
    batch.summary_json = json.dumps({
        "total_items": len(items),
        "exact_matches": batch.exact_matches,
        "mismatches": batch.mismatches,
        "unmatched": batch.unmatched_records,
    })

    db.add_all(items)
    db.commit()
    db.refresh(batch)
    return batch
