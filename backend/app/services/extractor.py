from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import logging
import os
from pathlib import Path
import re
import shutil
from typing import Optional, Tuple, List, Dict, Any
import pdfplumber

from app.schemas.invoice import InvoiceCandidateFields

logger = logging.getLogger(__name__)

MONTH_NAMES_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

MONTH_REGEX_STR = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
)

CURRENCY_PREFIX_REGEX = r"(?:INR|USD|EUR|GBP|CAD|AUD|Rs\.?|[$€£₹\u20b9]|n)?"
AMOUNT_NUM_REGEX = r"(?:\d{1,3}(?:,\d{2,3})*(?:\.\d{2})|\d+(?:\.\d{2}))"

DATE_CAPTURE_PATTERN = (
    rf"(?:\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH_REGEX_STR}\s+\d{{2,4}}|"
    rf"{MONTH_REGEX_STR}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{2,4}}|"
    rf"\d{{4}}[-/.]\d{{1,2}}[-/.]\d{{1,2}}|"
    rf"\d{{1,2}}[-/.]\d{{1,2}}[-/.]\d{{2,4}}|"
    rf"\d{{1,2}}[-/]{MONTH_REGEX_STR}[-/]\d{{2,4}})"
)


def clean_merged_text(text: str) -> str:
    """
    Separates fused keywords and labels that occur when PDF kerning or layout streams
    lack whitespace between text runs (e.g. 'BrightDesk Office SuppliesAddress:').
    """
    if not text:
        return ""
    # Split keywords that are fused directly onto preceding word characters
    pattern = (
        r"([a-z0-9])"
        r"((?:Address|GSTIN|CIN|PAN|Bill\s*To|Customer|Invoice|Date|Due\s*Date|Total|Subtotal|Tax|CGST|SGST|IGST|Phone|Tel|Email)\b)"
    )
    cleaned = re.sub(pattern, r"\1 \2", text, flags=re.IGNORECASE)
    return cleaned


def parse_date_string(date_str: str) -> Optional[date]:
    """Backward-compatible wrapper for date parsing."""
    return parse_date_flexible(date_str, default_to_dmy=True)


def parse_date_flexible(text: str, default_to_dmy: bool = True) -> Optional[date]:
    """
    Parses candidate date strings across common international and domestic formats:
    - 25 October 2026, 25th Oct 2026, 25-Oct-2026
    - October 25, 2026, Oct 25 2026
    - 2026-10-25, 2026/10/25
    - 25/10/2026, 25-10-2026
    - 25/10/26 (2-digit year)
    """
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[,/.-]+", " ", cleaned)
    parts = cleaned.split()

    if len(parts) == 3:
        p0, p1, p2 = parts[0], parts[1], parts[2]

        # Case A: Year first -> 2026 10 25 or 2026 Oct 25
        if len(p0) == 4 and p0.isdigit():
            year = int(p0)
            if p1.lower() in MONTH_NAMES_MAP:
                month = MONTH_NAMES_MAP[p1.lower()]
                day = int(p2)
                return _safe_date(year, month, day)
            elif p1.isdigit() and p2.isdigit():
                month = int(p1)
                day = int(p2)
                return _safe_date(year, month, day)

        # Case B: Year last -> Day Month Year OR Month Day Year
        if p2.isdigit():
            year = int(p2)
            if year < 100:
                year += 2000

            # Day Month Year (e.g. 25 October 2026)
            if p1.lower() in MONTH_NAMES_MAP and p0.isdigit():
                day = int(p0)
                month = MONTH_NAMES_MAP[p1.lower()]
                return _safe_date(year, month, day)

            # Month Day Year (e.g. October 25 2026)
            if p0.lower() in MONTH_NAMES_MAP and p1.isdigit():
                month = MONTH_NAMES_MAP[p0.lower()]
                day = int(p1)
                return _safe_date(year, month, day)

            # Purely Numeric (e.g. 25 10 2026 or 10 25 2026)
            if p0.isdigit() and p1.isdigit():
                v0, v1 = int(p0), int(p1)
                if v0 > 12:  # Unambiguously Day first
                    return _safe_date(year, v1, v0)
                elif v1 > 12:  # Month first
                    return _safe_date(year, v0, v1)
                else:
                    return _safe_date(year, v1, v0) if default_to_dmy else _safe_date(year, v0, v1)

    return None


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def parse_amount_string(amount_str: str) -> Optional[Decimal]:
    """Converts a raw amount string (e.g. '$1,234.50' or 'INR 3,700.00') into a clean Decimal."""
    if not amount_str:
        return None
    m = re.search(r"(\d{1,3}(?:,\d{2,3})*\.\d{2}|\d+\.\d{2})", amount_str.strip())
    if not m:
        m = re.search(r"(\d{1,3}(?:,\d{2,3})+|\d+)", amount_str.strip())
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        val = Decimal(raw).quantize(Decimal("0.01"))
        return val if val >= 0 else None
    except (InvalidOperation, TypeError):
        return None


def extract_text_from_pdf(file_path: Path) -> Tuple[str, bool]:
    """
    Extracts raw text from all pages of a PDF using pdfplumber,
    with pypdfium2 text fallback if needed.
    Returns:
        (full_text, is_scanned)
    """
    text_content = []
    total_chars = 0
    total_images = 0

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                layout_text = page.extract_text(layout=True) or ""
                selected_text = page_text if len(page_text.strip()) >= len(layout_text.strip()) else layout_text
                if selected_text:
                    text_content.append(selected_text)
                    total_chars += len(selected_text.strip())
                if hasattr(page, "images"):
                    total_images += len(page.images)
    except Exception as e:
        logger.warning(f"pdfplumber extraction warning for {file_path}: {e}")

    # Fallback to pypdfium2 if pdfplumber extracted nothing or very little
    if total_chars < 20:
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(file_path)
            ium_texts = []
            for page in pdf:
                textpage = page.get_textpage()
                p_text = textpage.get_text_range()
                if p_text and p_text.strip():
                    ium_texts.append(p_text.strip())
            if ium_texts:
                combined_ium = "\n".join(ium_texts)
                if len(combined_ium.strip()) > total_chars:
                    text_content = ium_texts
                    total_chars = len(combined_ium.strip())
        except Exception:
            pass

    full_text = "\n".join(text_content)
    is_scanned = total_chars < 20 and (total_images > 0 or not full_text.strip())
    return full_text, is_scanned


def run_ocr_if_available(file_path: Path) -> Tuple[str, bool, str]:
    """
    Attempts to perform OCR if pytesseract and tesseract executable are installed.
    Honestly informs caller if OCR engine or executable is not available.
    Returns:
        (extracted_text, ocr_succeeded, status_message)
    """
    try:
        import pytesseract
        from PIL import Image

        # Check PATH and standard Windows Tesseract installation directories
        tesseract_bin = shutil.which("tesseract")
        if not tesseract_bin:
            candidates_bin = [
                os.environ.get("TESSERACT_CMD"),
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Programs\Tesseract-OCR\tesseract.exe"),
            ]
            for candidate in candidates_bin:
                if candidate and os.path.exists(candidate):
                    tesseract_bin = candidate
                    break

        if not tesseract_bin:
            return "", False, "OCR engine (Tesseract executable) is not installed or configured in system PATH."

        pytesseract.pytesseract.tesseract_cmd = tesseract_bin

        # If it's a PDF, render pages with pypdfium2
        if file_path.suffix.lower() == ".pdf":
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(file_path)
                ocr_texts = []
                for i in range(len(pdf)):
                    page = pdf[i]
                    bitmap = page.render(scale=2.0)
                    pil_image = bitmap.to_pil()
                    text = pytesseract.image_to_string(pil_image)
                    if text.strip():
                        ocr_texts.append(text)
                combined = "\n".join(ocr_texts)
                return combined, bool(combined.strip()), "OCR processed successfully."
            except Exception as pdf_err:
                return "", False, f"PDF rendering for OCR failed: {str(pdf_err)}"
        else:
            # Direct image file
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
            return text, bool(text.strip()), "OCR processed successfully."

    except ImportError:
        return "", False, "pytesseract library is not installed in the Python environment."
    except Exception as e:
        return "", False, f"OCR processing encountered an error: {str(e)}"


def extract_candidate_fields(raw_text: str) -> Tuple[InvoiceCandidateFields, List[str]]:
    """
    Heuristically extracts invoice metadata from document text.
    Handles same-line and adjacent-line labels, Indian GST layouts, multiple currencies,
    customer/bill-to names, explicit payment statuses, and performs cross-field
    mathematical reconciliation.
    Never invents missing dates or amounts.
    """
    notes: List[str] = []
    validation_warnings: List[str] = []
    candidates = InvoiceCandidateFields()
    field_confidence: Dict[str, str] = {}

    if not raw_text or not raw_text.strip():
        notes.append("No readable text detected in the document. Please manually enter invoice fields.")
        candidates.field_confidence = field_confidence
        return candidates, notes

    # Clean unmerged keywords caused by tight kerning in PDF streams
    clean_text = clean_merged_text(raw_text)
    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

    # 1. Currency Detection
    if re.search(r"(?:₹|\bINR\b|\bRs\.?\b|\bRupees\b|GSTIN:\s*\d{2})", clean_text, re.I):
        candidates.currency = "INR"
    elif "€" in clean_text or re.search(r"\bEUR\b", clean_text):
        candidates.currency = "EUR"
    elif "£" in clean_text or re.search(r"\bGBP\b", clean_text):
        candidates.currency = "GBP"
    elif re.search(r"\bCAD\b", clean_text):
        candidates.currency = "CAD"
    elif re.search(r"\bAUD\b", clean_text):
        candidates.currency = "AUD"
    else:
        candidates.currency = "USD"

    default_dmy = candidates.currency in {"INR", "GBP", "EUR", "AUD"}

    # 2. Invoice Number Extraction
    inv_num_patterns = [
        r"(?im)^\s*(?:invoice|tax\s+invoice|bill|inv|receipt)\s*(?:#|number|no\.?|num)?\s*[:#]\s*([A-Za-z0-9\-_/#]{2,40})",
        r"(?im)\b(?:invoice|tax\s+invoice|bill|inv|receipt)\s*(?:#|number|no\.?|num)?\s*[:#]\s*([A-Za-z0-9\-_/#]{2,40})",
        r"(?im)\b(?:invoice|tax\s+invoice|bill|inv)\s*(?:#|number|no\.?|num)\s+([A-Za-z0-9\-_/#]{2,40})",
    ]
    for pat in inv_num_patterns:
        m = re.search(pat, clean_text)
        if m:
            val = m.group(1).strip()
            if val.lower() not in {"date", "number", "due", "total", "amount", "tax"}:
                candidates.invoice_number = val
                field_confidence["invoice_number"] = "HIGH"
                break

    # Adjacent line fallback for invoice number
    if not candidates.invoice_number:
        for i, line in enumerate(lines[:-1]):
            if re.match(r"(?i)^(?:invoice|inv|bill)\s*(?:number|no\.?|#)?\s*[:#]?$", line):
                next_line = lines[i+1].strip()
                m_next = re.match(r"^([A-Za-z0-9\-_/#]{2,40})", next_line)
                if m_next and m_next.group(1).lower() not in {"date", "due", "total"}:
                    candidates.invoice_number = m_next.group(1)
                    field_confidence["invoice_number"] = "MEDIUM"
                    break

    if not candidates.invoice_number:
        notes.append("Invoice number could not be reliably detected.")
        validation_warnings.append("Invoice number was not detected automatically. Please enter it manually.")

    # 3. Vendor / Supplier Extraction
    # Strategy A: Explicit Label Matching
    vendor_pattern = r"(?im)^\s*(?:vendor|supplier|from|billed\s+by|seller|company)[^\S\r\n]*[:#]\s*([^\r\n]+)"
    v_match = re.search(vendor_pattern, clean_text)
    if v_match:
        candidate_v = v_match.group(1).strip()
        clean_v = re.split(
            r"(?i)(?:\b|(?<=[a-z]))(?:address|gstin|cin|pan|phone|tel|email|bill\s+to|customer|invoice\s*(?:no|number)?|date)\b",
            candidate_v
        )[0].strip().rstrip(":, -")
        if len(clean_v) >= 2:
            candidates.vendor_name = clean_v
            field_confidence["vendor_name"] = "HIGH"

    # Strategy B: Adjacent line if label is on its own line
    if not candidates.vendor_name:
        for i, line in enumerate(lines[:-1]):
            if re.match(r"(?i)^(?:vendor|supplier|seller|billed\s+by)\s*[:#]?$", line):
                next_line = lines[i+1].strip()
                clean_v = re.split(
                    r"(?i)(?:\b|(?<=[a-z]))(?:address|gstin|bill\s+to|date)\b",
                    next_line
                )[0].strip().rstrip(":, -")
                if len(clean_v) >= 2 and not clean_v.lower().startswith("bill to"):
                    candidates.vendor_name = clean_v
                    field_confidence["vendor_name"] = "HIGH"
                    break

    # Strategy C: Top Header Fallback
    if not candidates.vendor_name:
        ignore_headers = {
            "sample invoice", "invoice", "tax invoice", "bill of supply", "receipt",
            "statement", "estimate", "commercial invoice", "fictional document for software testing",
            "original for recipient", "duplicate for transporter", "invoiceiq demo invoice"
        }
        for line in lines[:8]:
            l_clean = line.strip().lower()
            if l_clean in ignore_headers:
                continue
            if re.match(r"(?i)^(?:address|gstin|cin|pan|bill\s+to|customer|invoice\s+number|date|phone|email)", line):
                continue
            if re.search(r"\b(?:road|street|nagar|pune|mumbai|delhi|bangalore|maharashtra|\d{6})\b", l_clean):
                continue
            if len(line) >= 3 and not re.search(r"^\d+", line) and not re.search(r"^\W+$", line):
                candidates.vendor_name = line.strip()
                field_confidence["vendor_name"] = "MEDIUM"
                break

    if not candidates.vendor_name:
        notes.append("Vendor name could not be reliably detected.")
        validation_warnings.append("Supplier / Vendor name was not detected automatically. Please enter it manually.")

    # 4. Customer / Bill-To Name Extraction
    customer_pattern = r"(?im)^\s*(?:bill(?:ed)?\s+to|invoice\s+to|customer(?:\s+name)?|client(?:\s+name)?|buyer|sold\s+to|recipient)[^\S\r\n]*[:#]\s*([^\r\n]+)"
    c_match = re.search(customer_pattern, clean_text)
    if c_match:
        candidate_c = c_match.group(1).strip()
        clean_c = re.split(
            r"(?i)(?:\b|(?<=[a-z]))(?:address|gstin|cin|pan|phone|tel|email|invoice\s*(?:no|number)?|date)\b",
            candidate_c
        )[0].strip().rstrip(":, -")
        if len(clean_c) >= 2 and clean_c.lower() not in {"name", "details", "customer", "address"}:
            candidates.customer_name = clean_c
            field_confidence["customer_name"] = "HIGH"

    if not candidates.customer_name:
        for i, line in enumerate(lines[:-1]):
            if re.match(r"(?i)^(?:bill(?:ed)?\s+to|invoice\s+to|customer|client|sold\s+to|buyer)\s*[:#]?$", line):
                next_line = lines[i+1].strip()
                clean_c = re.split(
                    r"(?i)(?:\b|(?<=[a-z]))(?:address|gstin|cin|pan|phone|tel|email|invoice\s*(?:no|number)?|date)\b",
                    next_line
                )[0].strip().rstrip(":, -")
                if len(clean_c) >= 2 and not clean_c.lower().startswith("address"):
                    candidates.customer_name = clean_c
                    field_confidence["customer_name"] = "HIGH"
                    break

    # 5. Payment Status Extraction (when explicitly stated on invoice)
    status_match = re.search(
        r"(?im)^\s*(?:payment\s+status|invoice\s+status|\bstatus)[^\S\r\n]*[:#]\s*([A-Za-z\s()]+)",
        clean_text
    )
    if status_match:
        raw_status = status_match.group(1).strip()
        raw_status = re.split(r"[\(\[\n]", raw_status)[0].strip()
        s_lower = raw_status.lower()
        if "partially" in s_lower or "partial" in s_lower:
            candidates.payment_status = "Partially Paid"
            field_confidence["payment_status"] = "HIGH"
        elif "unpaid" in s_lower or "due" in s_lower:
            candidates.payment_status = "Unpaid"
            field_confidence["payment_status"] = "HIGH"
        elif "paid" in s_lower:
            candidates.payment_status = "Paid"
            field_confidence["payment_status"] = "HIGH"
        elif "overdue" in s_lower:
            candidates.payment_status = "Overdue"
            field_confidence["payment_status"] = "HIGH"
        elif "pending" in s_lower:
            candidates.payment_status = "Pending"
            field_confidence["payment_status"] = "HIGH"
        elif len(raw_status) >= 3:
            candidates.payment_status = raw_status.title()
            field_confidence["payment_status"] = "HIGH"
    elif re.search(r"\b(?:PAID\s+IN\s+FULL|PAYMENT\s+RECEIVED)\b", clean_text, re.I):
        candidates.payment_status = "Paid"
        field_confidence["payment_status"] = "HIGH"

    # 6. Dates Extraction
    # Invoice Date
    inv_date_pattern = rf"(?im)\b(?:invoice\s*date|date\s*of\s*issue|issue\s*date|bill\s*date|\bdate\b)\s*[:#]?\s*({DATE_CAPTURE_PATTERN})"
    inv_date_m = re.search(inv_date_pattern, clean_text)
    if inv_date_m:
        parsed_d = parse_date_flexible(inv_date_m.group(1), default_to_dmy=default_dmy)
        if parsed_d:
            candidates.invoice_date = parsed_d
            field_confidence["invoice_date"] = "HIGH"

    if not candidates.invoice_date:
        validation_warnings.append("Invoice date was not detected automatically. Please specify the invoice date.")

    # Due Date
    due_date_pattern = rf"(?im)\b(?:due\s*date|payment\s*due|pay\s*by|due\s*by|payment\s*due\s*date)\s*[:#]?\s*({DATE_CAPTURE_PATTERN})"
    due_date_m = re.search(due_date_pattern, clean_text)
    if due_date_m:
        parsed_d = parse_date_flexible(due_date_m.group(1), default_to_dmy=default_dmy)
        if parsed_d:
            candidates.due_date = parsed_d
            field_confidence["due_date"] = "HIGH"
    else:
        notes.append("Due date not specified on document.")

    # Validate Date Sequence
    if candidates.invoice_date and candidates.due_date:
        if candidates.due_date < candidates.invoice_date:
            field_confidence["due_date"] = "MEDIUM"
            validation_warnings.append(
                f"Date Sequence Warning: Due date ({candidates.due_date}) is earlier than invoice date ({candidates.invoice_date}). Please verify."
            )

    # 7. Amounts Extraction (Subtotal, Taxes, Total)
    # A. Subtotal
    subtotal_m = re.search(
        rf"(?im)^\s*(?:subtotal|sub-total|sub\s+total|taxable\s+(?:amount|value)|subtotal\s*[/|]\s*taxable\s+value|net\s+amount|base\s+amount)[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )
    if subtotal_m:
        candidates.subtotal = parse_amount_string(subtotal_m.group(1))
        if candidates.subtotal is not None:
            field_confidence["subtotal"] = "HIGH"

    # B. Taxes (CGST, SGST, IGST, Generic Tax)
    cgst_m = re.search(
        rf"(?im)^\s*cgst(?:\s*[@(]\s*\d+%\s*\)?)?[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )
    sgst_m = re.search(
        rf"(?im)^\s*(?:sgst|utgst)(?:\s*[@(]\s*\d+%\s*\)?)?[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )
    igst_m = re.search(
        rf"(?im)^\s*igst(?:\s*[@(]\s*\d+%\s*\)?)?[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )
    gen_tax_m = re.search(
        rf"(?im)^\s*(?:total\s+tax|tax|gst|vat|sales\s+tax)[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )

    if cgst_m:
        candidates.cgst = parse_amount_string(cgst_m.group(1))
        if candidates.cgst is not None:
            field_confidence["cgst"] = "HIGH"
    if sgst_m:
        candidates.sgst = parse_amount_string(sgst_m.group(1))
        if candidates.sgst is not None:
            field_confidence["sgst"] = "HIGH"
    if igst_m:
        candidates.igst = parse_amount_string(igst_m.group(1))
        if candidates.igst is not None:
            field_confidence["igst"] = "HIGH"

    # Reconcile tax_amount
    if candidates.cgst is not None and candidates.sgst is not None:
        candidates.tax_amount = (candidates.cgst + candidates.sgst).quantize(Decimal("0.01"))
        field_confidence["tax_amount"] = "HIGH"
        notes.append(
            f"Extracted Indian GST: CGST {candidates.currency} {candidates.cgst}, "
            f"SGST {candidates.currency} {candidates.sgst} (Combined: {candidates.currency} {candidates.tax_amount})."
        )
    elif candidates.igst is not None:
        candidates.tax_amount = candidates.igst
        field_confidence["tax_amount"] = "HIGH"
        notes.append(f"Extracted IGST: {candidates.currency} {candidates.tax_amount}.")
    elif gen_tax_m:
        candidates.tax_amount = parse_amount_string(gen_tax_m.group(1))
        if candidates.tax_amount is not None:
            field_confidence["tax_amount"] = "HIGH"

    # C. Total Amount
    # Match explicitly labelled totals
    total_m = re.search(
        rf"(?im)^\s*(?:total\s+due|grand\s+total|invoice\s+total|total\s+amount|amount\s+(?:payable|due)|net\s+payable|balance\s+due|\btotal\b)[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )
    if total_m:
        candidates.total_amount = parse_amount_string(total_m.group(1))
        if candidates.total_amount is not None:
            field_confidence["total_amount"] = "HIGH"
    else:
        # Fallback: search backwards from bottom lines
        for line in reversed(lines):
            m_rev = re.search(
                rf"(?i)\b(?:total\s+due|grand\s+total|invoice\s+total|total\s+amount|amount\s+payable|\btotal\b)[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
                line
            )
            if m_rev:
                candidates.total_amount = parse_amount_string(m_rev.group(1))
                if candidates.total_amount is not None:
                    field_confidence["total_amount"] = "MEDIUM"
                break

    if not candidates.total_amount:
        notes.append("Total amount could not be reliably detected.")
        validation_warnings.append("Total amount was not detected automatically. Please enter the invoice total.")

    # 8. Mathematical Verification & Arithmetic Consistency
    if candidates.subtotal is not None and candidates.tax_amount is not None and candidates.total_amount is not None:
        expected_total = (candidates.subtotal + candidates.tax_amount).quantize(Decimal("0.01"))
        diff = abs(expected_total - candidates.total_amount)
        if diff <= Decimal("0.05"):
            notes.append(
                f"Financial reconciliation verified: Subtotal ({candidates.subtotal}) + "
                f"Tax ({candidates.tax_amount}) = Total ({candidates.total_amount})."
            )
            field_confidence["total_amount"] = "HIGH"
        else:
            field_confidence["total_amount"] = "MEDIUM"
            field_confidence["subtotal"] = "MEDIUM"
            msg = (
                f"Arithmetic Discrepancy: Extracted Subtotal ({candidates.currency} {candidates.subtotal}) + "
                f"Tax ({candidates.currency} {candidates.tax_amount}) = {candidates.currency} {expected_total}, "
                f"differing from stated Total ({candidates.currency} {candidates.total_amount}). "
                "The original extracted figures have been preserved for your review."
            )
            notes.append(msg)
            validation_warnings.append(msg)

    if candidates.subtotal is not None and candidates.total_amount is not None:
        if candidates.subtotal > candidates.total_amount:
            validation_warnings.append(
                f"Warning: Extracted Subtotal ({candidates.currency} {candidates.subtotal}) is greater than Grand Total ({candidates.currency} {candidates.total_amount}). Please review."
            )

    candidates.field_confidence = field_confidence
    return candidates, notes


def process_invoice_file(file_path: Path, content_type: str) -> Tuple[InvoiceCandidateFields, List[str]]:
    """Primary extraction entry point for uploaded invoice files."""
    notes: List[str] = []

    if content_type == "application/pdf" or file_path.suffix.lower() == ".pdf":
        try:
            raw_text, is_scanned = extract_text_from_pdf(file_path)

            if is_scanned:
                logger.info("Scanned PDF detected without selectable digital text. Attempting OCR...")
                ocr_text, ocr_ok, ocr_msg = run_ocr_if_available(file_path)
                if ocr_ok and ocr_text.strip():
                    raw_text = ocr_text
                    notes.append("Document text recovered via Optical Character Recognition (OCR).")
                else:
                    notes.append(
                        f"Scanned document detected: This document does not contain selectable text. {ocr_msg} "
                        "Please manually review and enter the invoice details in the review form."
                    )
                    empty_cand = InvoiceCandidateFields()
                    return empty_cand, notes

            candidates, extraction_notes = extract_candidate_fields(raw_text)
            notes.extend(extraction_notes)
            return candidates, notes

        except Exception as e:
            logger.error(f"PDF extraction error for {file_path}: {e}", exc_info=True)
            notes.append(f"PDF text extraction failed: {str(e)}. Please manually review and enter details.")
            return InvoiceCandidateFields(), notes

    elif content_type in ["image/png", "image/jpeg", "image/jpg", "image/webp"] or file_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
        logger.info("Image invoice uploaded. Attempting OCR...")
        ocr_text, ocr_ok, ocr_msg = run_ocr_if_available(file_path)
        if ocr_ok and ocr_text.strip():
            notes.append("Image text recovered via Optical Character Recognition (OCR).")
            candidates, extraction_notes = extract_candidate_fields(ocr_text)
            notes.extend(extraction_notes)
            return candidates, notes
        else:
            notes.append(
                f"Image file uploaded. {ocr_msg} "
                "Please review and enter the invoice details manually in the review form."
            )
            return InvoiceCandidateFields(), notes

    else:
        notes.append("Unsupported file type for automated parsing.")
        return InvoiceCandidateFields(), notes
