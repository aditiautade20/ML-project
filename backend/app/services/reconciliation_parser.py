import csv
import hashlib
import io
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import openpyxl

logger = logging.getLogger(__name__)

# Standard known header variations for intelligent column mapping
LEDGER_HEADER_SYNONYMS = {
    "invoice_number": [
        "invoice_number", "invoice_no", "invoice_num", "invoice_id", "inv_id",
        "inv_no", "inv_num", "inv_number", "inv_#", "bill_no", "bill_number",
        "bill_#", "invoice", "doc_no", "doc_number", "document_number",
        "document_no", "reference", "ref", "ref_no", "reference_no", "reference_number"
    ],
    "total_amount": [
        "total_amount", "total", "invoice_amount", "gross_amount", "grand_total",
        "amount", "transaction_amount", "net_amount", "invoice_total", "total_val",
        "balance", "net_payable", "debit_amount", "credit_amount", "debit", "credit"
    ],
    "tax_amount": [
        "tax_amount", "tax", "gst", "gst_amount", "vat", "vat_amount",
        "sales_tax", "cgst", "sgst", "igst", "cgst_sgst", "taxes"
    ],
    "vendor_name": [
        "vendor_name", "vendor", "payee", "payee_name", "supplier", "supplier_name",
        "company", "party_name", "party", "seller", "contractor", "counterparty", "account_name"
    ],
    "invoice_date": [
        "posting_date", "transaction_date", "invoice_date", "date", "inv_date",
        "bill_date", "trans_date", "txn_date", "entry_date", "doc_date", "document_date"
    ],
    "subtotal": [
        "subtotal", "sub_total", "taxable_amount", "taxable_value", "base_amount"
    ],
    "currency": [
        "currency", "curr", "ccy"
    ],
}

BANK_HEADER_SYNONYMS = {
    "transaction_date": [
        "transaction_date", "trans_date", "txn_date", "date", "posting_date",
        "value_date", "booking_date"
    ],
    "description": [
        "description", "narration", "details", "particulars", "counterparty",
        "payee", "party", "transaction_description", "memo", "remarks", "narrative"
    ],
    "debit_amount": [
        "debit_amount", "debit", "withdrawal", "withdrawals", "paid_out", "dr",
        "amount_debited", "debits", "payments", "payment"
    ],
    "credit_amount": [
        "credit_amount", "credit", "deposit", "deposits", "paid_in", "cr",
        "amount_credited", "credits", "receipts"
    ],
    "amount": [
        "amount", "transaction_amount", "txn_amount", "net_amount"
    ],
    "reference_id": [
        "reference_id", "reference", "ref_no", "referenceno", "ref", "txn_id",
        "transaction_id", "cheque_no", "chq_no", "check_no", "utr", "trace_id", "id"
    ],
    "currency": [
        "currency", "curr", "ccy"
    ],
}


def compute_file_hash(content: bytes) -> str:
    """Computes SHA-256 hash of file content to detect duplicate uploads."""
    return hashlib.sha256(content).hexdigest()


def canonicalize_header(header: str) -> str:
    """
    Normalizes a header for strict canonical matching by:
    - Lowercasing
    - Stripping currency designators in parentheses like (USD), ($), (EUR), (INR), (GBP), (CAD), (AUD)
    - Stripping currency symbols ($, €, £, ₹, ¥)
    - Stripping all non-alphanumeric characters (spaces, underscores, hyphens, periods, hashes, etc.)
    """
    if not header:
        return ""
    s = str(header).strip().lower()
    s = re.sub(r"\((?:usd|eur|inr|cad|gbp|aud|\$|€|£|₹|¥)\)", "", s)
    s = re.sub(r"[\$€£₹¥]", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def normalize_header_name(header: str) -> str:
    """
    Cleans a header string: lowercases, replaces non-alphanumeric with spaces,
    and collapses whitespace/underscores into single underscores.
    Handles hyphens, dots, and symbols cleanly (e.g., 'Total-Amount' -> 'total_amount').
    """
    if not header:
        return ""
    clean = re.sub(r"[^\w\s]", " ", str(header).strip().lower())
    clean = re.sub(r"[_\s]+", "_", clean)
    return clean.strip("_")


# Conflicting qualifiers that prevent broad substring matching
CONFLICTING_QUALIFIERS = {
    "total_amount": ["tax", "gst", "vat", "discount", "subtotal", "shipping", "fee", "rate", "percentage"],
    "tax_amount": ["total", "grand", "gross", "subtotal", "invoice", "balance"],
    "invoice_number": ["tax", "amount", "date", "vendor", "payee", "balance", "rate"],
    "invoice_date": ["amount", "number", "tax", "vendor", "payee"],
    "vendor_name": ["number", "amount", "date", "tax"],
}


def detect_column_mappings(
    headers: List[str],
    mapping_type: str = "LEDGER",
    rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Automatically detects column mappings with intelligent variation handling,
    data-driven debit/credit column arbitration, and ambiguity detection.

    Returns:
        {
            "suggested_mapping": Dict[target_field, detected_header],
            "mapping_statuses": Dict[target_field, "AUTO_MAPPED" | "NEEDS_CONFIRMATION" | "UNMAPPED"],
            "mapping_warnings": Dict[target_field, str],
            "ambiguous_columns": Dict[target_field, List[str]],
        }
    """
    synonyms = LEDGER_HEADER_SYNONYMS if mapping_type.upper() == "LEDGER" else BANK_HEADER_SYNONYMS
    suggested: Dict[str, str] = {}
    statuses: Dict[str, str] = {}
    warnings: Dict[str, str] = {}
    ambiguous: Dict[str, List[str]] = {}
    used_headers: set = set()

    clean_headers = [h for h in headers if h and str(h).strip()]

    # 1. Special Handling for Accounting Ledgers with Debit and Credit Columns
    if mapping_type.upper() == "LEDGER":
        debit_candidates = [
            h for h in clean_headers
            if canonicalize_header(h) in {"debit", "debitamount", "dr", "amountdebited", "debits"}
        ]
        credit_candidates = [
            h for h in clean_headers
            if canonicalize_header(h) in {"credit", "creditamount", "cr", "amountcredited", "credits"}
        ]
        explicit_total_candidates = [
            h for h in clean_headers
            if canonicalize_header(h) in {
                "totalamount", "invoiceamount", "grossamount", "grandtotal",
                "total", "netpayable", "totalval", "totalvalue"
            }
        ]

        # If there is NO explicit total column, but BOTH debit and credit exist:
        if not explicit_total_candidates and debit_candidates and credit_candidates:
            deb_col = debit_candidates[0]
            cre_col = credit_candidates[0]

            d_count, d_sum = 0, Decimal("0.00")
            c_count, c_sum = 0, Decimal("0.00")

            if rows:
                for r in rows[:100]:
                    d_val = parse_numeric_decimal(r.get(deb_col))
                    if d_val and d_val > 0:
                        d_count += 1
                        d_sum += d_val
                    c_val = parse_numeric_decimal(r.get(cre_col))
                    if c_val and c_val > 0:
                        c_count += 1
                        c_sum += c_val

            # Determine dominant column based on row data
            if c_count > 0 and d_count == 0:
                # Credit clearly dominant
                suggested["total_amount"] = cre_col
                statuses["total_amount"] = "AUTO_MAPPED"
                used_headers.add(cre_col)
            elif d_count > 0 and c_count == 0:
                # Debit clearly dominant
                suggested["total_amount"] = deb_col
                statuses["total_amount"] = "AUTO_MAPPED"
                used_headers.add(deb_col)
            elif c_count >= 2 * d_count and c_count > 0:
                suggested["total_amount"] = cre_col
                statuses["total_amount"] = "NEEDS_CONFIRMATION"
                warnings["total_amount"] = (
                    f"Both '{deb_col}' and '{cre_col}' columns exist. '{cre_col}' was selected "
                    f"because it contains the transaction amounts ({c_count} non-zero entries). "
                    f"Please confirm."
                )
                ambiguous["total_amount"] = [cre_col, deb_col]
                used_headers.add(cre_col)
            elif d_count >= 2 * c_count and d_count > 0:
                suggested["total_amount"] = deb_col
                statuses["total_amount"] = "NEEDS_CONFIRMATION"
                warnings["total_amount"] = (
                    f"Both '{deb_col}' and '{cre_col}' columns exist. '{deb_col}' was selected "
                    f"because it contains the transaction amounts ({d_count} non-zero entries). "
                    f"Please confirm."
                )
                ambiguous["total_amount"] = [deb_col, cre_col]
                used_headers.add(deb_col)
            else:
                # Mixed or empty rows
                chosen = deb_col if d_count >= c_count else cre_col
                other = cre_col if chosen == deb_col else deb_col
                suggested["total_amount"] = chosen
                statuses["total_amount"] = "NEEDS_CONFIRMATION"
                warnings["total_amount"] = (
                    f"Both '{deb_col}' and '{cre_col}' contain transaction amounts. '{chosen}' was "
                    f"pre-selected. Please confirm which column represents your invoice amounts."
                )
                ambiguous["total_amount"] = [chosen, other]
                used_headers.add(chosen)

            # Store auxiliary debit and credit columns
            suggested["debit_column"] = deb_col
            suggested["credit_column"] = cre_col

    # 2. Pass 1: Exact Matches (Canonical and Normalized) across all Target Keys
    for target_key, aliases in synonyms.items():
        if target_key in suggested and suggested[target_key]:
            continue

        alias_canons = [canonicalize_header(a) for a in aliases]
        alias_norms = [normalize_header_name(a) for a in aliases]

        exact_matches = []
        for h in clean_headers:
            if h in used_headers:
                continue
            h_canon = canonicalize_header(h)
            h_norm = normalize_header_name(h)

            for idx, a_canon in enumerate(alias_canons):
                if h_canon == a_canon or h_norm == alias_norms[idx]:
                    exact_matches.append((idx, h))
                    break

        if exact_matches:
            # Sort by alias priority (lowest index in aliases list is highest priority)
            exact_matches.sort(key=lambda x: x[0])
            best_idx, selected = exact_matches[0]
            suggested[target_key] = selected
            used_headers.add(selected)

            # Check if there were multiple exact matches (ambiguity)
            all_exact_headers = list(dict.fromkeys(h for _, h in exact_matches))
            if len(all_exact_headers) > 1:
                statuses[target_key] = "NEEDS_CONFIRMATION"
                warnings[target_key] = (
                    f"Multiple matching columns found ({', '.join(all_exact_headers)}). "
                    f"Pre-selected '{selected}'. Please confirm."
                )
                ambiguous[target_key] = all_exact_headers
            else:
                statuses[target_key] = "AUTO_MAPPED"

    # 3. Pass 2: Fallback Substring Matching for remaining unmapped target keys
    for target_key, aliases in synonyms.items():
        if target_key in suggested and suggested[target_key]:
            continue

        alias_canons = [canonicalize_header(a) for a in aliases]
        alias_norms = [normalize_header_name(a) for a in aliases]
        conflicts = CONFLICTING_QUALIFIERS.get(target_key, [])

        sub_matches = []
        for h in clean_headers:
            if h in used_headers:
                continue
            h_canon = canonicalize_header(h)
            h_norm = normalize_header_name(h)

            # Skip header if it contains conflicting qualifiers for this field
            if any(cq in h_canon for cq in conflicts):
                continue

            for idx, a_norm in enumerate(alias_norms):
                if len(a_norm) >= 4 and (a_norm in h_norm or alias_canons[idx] in h_canon):
                    sub_matches.append((idx, h))
                    break

        if sub_matches:
            sub_matches.sort(key=lambda x: x[0])
            best_idx, selected = sub_matches[0]
            suggested[target_key] = selected
            used_headers.add(selected)

            all_sub_headers = list(dict.fromkeys(h for _, h in sub_matches))
            if len(all_sub_headers) > 1:
                statuses[target_key] = "NEEDS_CONFIRMATION"
                warnings[target_key] = (
                    f"Multiple matching columns found ({', '.join(all_sub_headers)}). "
                    f"Pre-selected '{selected}'. Please confirm."
                )
                ambiguous[target_key] = all_sub_headers
            else:
                statuses[target_key] = "AUTO_MAPPED"
        else:
            suggested[target_key] = ""
            statuses[target_key] = "UNMAPPED"
            if target_key in ("invoice_number", "total_amount", "transaction_date", "description"):
                warnings[target_key] = (
                    f"Required column '{target_key}' could not be automatically detected. "
                    f"Please select manually from the dropdown."
                )

    return {
        "suggested_mapping": suggested,
        "mapping_statuses": statuses,
        "mapping_warnings": warnings,
        "ambiguous_columns": ambiguous,
    }


def auto_map_columns(
    headers: List[str],
    mapping_type: str = "LEDGER",
    rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, str]:
    """
    Backward-compatible wrapper for detect_column_mappings.
    Returns: Dict[target_field, detected_file_header]
    """
    result = detect_column_mappings(headers, mapping_type, rows=rows)
    return result["suggested_mapping"]


def parse_numeric_decimal(val: Any) -> Optional[Decimal]:
    """Extracts a clean positive Decimal from strings with commas, currencies, etc."""
    if val is None or val == "":
        return None
    s = str(val).strip()
    # Check for negative in parentheses e.g. (120.00) or -120.00
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1]
    elif s.startswith("-"):
        is_negative = True
        s = s[1:]

    # Remove currency symbols and non-digits except dot
    cleaned = re.sub(r"[^\d.]", "", s)
    if not cleaned:
        return None
    try:
        dec = Decimal(cleaned).quantize(Decimal("0.01"))
        return -dec if is_negative else dec
    except (InvalidOperation, TypeError):
        return None


def parse_csv_file(content: bytes) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
    """
    Parses a CSV file from bytes, handling multiple encodings and delimiters.
    Returns:
        (headers, list_of_row_dicts, errors_or_warnings)
    """
    errors: List[str] = []
    text = ""
    # Try encodings: utf-8-sig (handles BOM), utf-8, latin1
    for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if not text.strip():
        errors.append("CSV file is empty or contains unreadable encoding.")
        return [], [], errors

    # Detect delimiter
    sample = text[:4096]
    delimiter = ","
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=",\t;|")
        delimiter = dialect.delimiter
    except Exception:
        # Fallback delimiter inference
        for d in [",", "\t", ";"]:
            if d in sample.splitlines()[0]:
                delimiter = d
                break

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        raw_rows = list(reader)
    except Exception as e:
        errors.append(f"Failed to parse CSV rows: {str(e)}")
        return [], [], errors

    if not raw_rows:
        errors.append("No rows found in CSV file.")
        return [], [], errors

    # Header row
    headers = [h.strip() for h in raw_rows[0] if h is not None]
    if not headers or all(not h for h in headers):
        errors.append("No valid header row detected in CSV file.")
        return [], [], errors

    row_dicts = []
    for line_idx, row in enumerate(raw_rows[1:], start=2):
        if not row or all(not str(cell).strip() for cell in row):
            continue  # skip completely blank rows
        # Map values to headers
        row_map = {}
        for h_idx, h in enumerate(headers):
            cell_val = row[h_idx].strip() if h_idx < len(row) else ""
            row_map[h] = cell_val
        row_dicts.append(row_map)

    return headers, row_dicts, errors


def parse_xlsx_file(content: bytes) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
    """
    Parses an Excel XLSX workbook from bytes using openpyxl.
    Returns:
        (headers, list_of_row_dicts, errors_or_warnings)
    """
    errors: List[str] = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        sheet = wb.active
        if not sheet:
            errors.append("No active worksheet found in Excel file.")
            return [], [], errors
    except Exception as e:
        errors.append(f"Could not open Excel file: {str(e)}. Please ensure file is a valid .xlsx format.")
        return [], [], errors

    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        errors.append("The Excel sheet is completely empty.")
        return [], [], errors

    # First non-empty row as header
    header_idx = 0
    while header_idx < len(rows) and all(cell is None or str(cell).strip() == "" for cell in rows[header_idx]):
        header_idx += 1

    if header_idx >= len(rows):
        errors.append("No non-empty header row found in Excel file.")
        return [], [], errors

    headers = [str(cell).strip() if cell is not None else f"Column_{i+1}" for i, cell in enumerate(rows[header_idx])]

    row_dicts = []
    for line_idx, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        row_map = {}
        for h_idx, h in enumerate(headers):
            val = row[h_idx] if h_idx < len(row) else ""
            row_map[h] = str(val).strip() if val is not None else ""
        row_dicts.append(row_map)

    return headers, row_dicts, errors


def parse_tabular_file(
    content: bytes, filename: str
) -> Tuple[List[str], List[Dict[str, Any]], str, List[str]]:
    """
    Unified entry point for CSV and XLSX files.
    Returns:
        (headers, rows, sha256_hash, errors)
    """
    file_hash = compute_file_hash(content)
    ext = Path(filename).suffix.lower()

    if ext in [".xlsx", ".xlsm"]:
        headers, rows, errors = parse_xlsx_file(content)
    elif ext in [".csv", ".tsv", ".txt"]:
        headers, rows, errors = parse_csv_file(content)
    else:
        errors = [f"Unsupported file format '{ext}'. Supported formats: CSV (.csv) and Excel (.xlsx)."]
        headers, rows = [], []

    return headers, rows, file_hash, errors
