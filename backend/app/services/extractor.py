from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import logging
import os
from pathlib import Path
import re
import shutil
from typing import Optional, Tuple, List, Dict, Any
import pdfplumber

from app.schemas.invoice import InvoiceCandidateFields, LineItemCandidate

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

CURRENCY_PREFIX_REGEX = (
    r"(?:"
    r"\((?:INR|USD|EUR|GBP|CAD|AUD|[A-Za-z]{3})\)|"
    r"INR|USD|EUR|GBP|CAD|AUD|[A-Za-z]{3}|"
    r"Rs\.?|C\$|A\$|[$€£₹\u20b9■n]"
    r")?"
)
CURRENCY_SUFFIX_REGEX = (
    r"(?:"
    r"\s*(?:\((?:INR|USD|EUR|GBP|CAD|AUD|[A-Za-z]{3})\)|INR|USD|EUR|GBP|CAD|AUD|[A-Za-z]{3}|Rs\.?|[$€£₹\u20b9■n])"
    r")?"
)
AMOUNT_NUM_REGEX = r"(?:\d{1,3}(?:,\d{2,3})*(?:\.\d{2})|\d+(?:\.\d{2}))"

TOTAL_LABEL_REGEX = (
    r"(?:"
    r"total\s+amount\s+due|total\s+amount\s+payable|total\s+payable|"
    r"grand\s+total|invoice\s+total|total\s+invoice\s+amount|total\s+amount|"
    r"total\s+due|amount\s+due|balance\s+due|amount\s+payable|net\s+payable|"
    r"net\s+amount|final\s+total|"
    r"(?<!sub\s)(?<!sub-)(?<!tax\s)\btotal\b"
    r")"
)

DATE_CAPTURE_PATTERN = (
    rf"(?:\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH_REGEX_STR}\s+\d{{2,4}}|"
    rf"{MONTH_REGEX_STR}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{2,4}}|"
    rf"\d{{4}}[-/.]\d{{1,2}}[-/.]\d{{1,2}}|"
    rf"\d{{1,2}}[-/.]\d{{1,2}}[-/.]\d{{2,4}}|"
    rf"\d{{1,2}}[-/]{MONTH_REGEX_STR}[-/]\d{{2,4}})"
)

GST_STATE_CODES: Dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}
STATE_NAME_TO_CODE = {v.lower(): k for k, v in GST_STATE_CODES.items()}


def clean_merged_text(text: str) -> str:
    """
    Separates fused keywords and labels that occur when PDF kerning or layout streams
    lack whitespace between text runs (e.g. 'BrightDesk Office SuppliesAddress:').
    Preserves 'Subtotal' without breaking into 'Sub total'.
    Normalizes bullet/glyph symbols used for rupee currencies.
    """
    if not text:
        return ""

    # Replace currency bullets and mismapped glyphs
    t = text.replace("\u25a0", "INR ").replace("■", "INR ")
    t = re.sub(r"(?<=\s)n(?=\d{1,3}(?:,\d{2,3})*\.\d{2})", "INR ", t)

    # Split keywords fused onto preceding word characters, but DO NOT split 'Subtotal'
    pattern = (
        r"([a-z0-9])"
        r"((?:Address|GSTIN|CIN|PAN|Bill\s*To|Customer|Invoice|Date|Due\s*Date|(?<!sub)Total|Subtotal|Tax|CGST|SGST|IGST|Phone|Tel|Email)\b)"
    )
    cleaned = re.sub(pattern, r"\1 \2", t, flags=re.IGNORECASE)
    # Re-unify any accidental Sub Total
    cleaned = re.sub(r"\bSub\s+Total\b", "Subtotal", cleaned, flags=re.IGNORECASE)
    return cleaned


def parse_date_string(date_str: str) -> Optional[date]:
    """Backward-compatible wrapper for date parsing."""
    return parse_date_flexible(date_str, default_to_dmy=True)


def parse_date_flexible(text: str, default_to_dmy: bool = True) -> Optional[date]:
    """
    Parses candidate date strings across common international and domestic formats:
    - 25 October 2026, 25th Oct 2026, 25-Oct-2026, 28 Oct 2026
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

            # Day Month Year (e.g. 25 October 2026 or 28 Oct 2026)
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
    """Converts a raw amount string (e.g. '$1,234.50' or 'INR 3,700.00' or '■23,600.00') into a clean Decimal."""
    if not amount_str:
        return None
    cleaned = re.sub(r"[^\d.,]", "", amount_str.strip())
    m = re.search(r"(\d{1,3}(?:,\d{2,3})*\.\d{2}|\d+\.\d{2})", cleaned)
    if not m:
        m = re.search(r"(\d{1,3}(?:,\d{2,3})+|\d+)", cleaned)
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
    Extracts raw text from all pages of a PDF.
    Uses pypdf as primary flow/reading-order extractor to prevent multi-column
    flattening regressions, with pypdfium2 and pdfplumber support.
    Returns:
        (full_text, is_scanned)
    """
    text_content = []
    total_chars = 0

    # Strategy 1: pypdf (best for preserving natural document stream and column order)
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        for page in reader.pages:
            p_text = page.extract_text() or ""
            if p_text.strip():
                text_content.append(p_text.strip())
                total_chars += len(p_text.strip())
    except Exception as e:
        logger.warning(f"pypdf extraction notice for {file_path}: {e}")

    # Strategy 2: pypdfium2 fallback
    if total_chars < 20:
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(file_path)
            ium_texts = []
            for page in doc:
                textpage = page.get_textpage()
                t = textpage.get_text_range()
                if t and t.strip():
                    ium_texts.append(t.strip())
            if ium_texts:
                combined_ium = "\n".join(ium_texts)
                if len(combined_ium.strip()) > total_chars:
                    text_content = ium_texts
                    total_chars = len(combined_ium.strip())
        except Exception as e:
            logger.warning(f"pypdfium2 extraction notice: {e}")

    # Strategy 3: pdfplumber fallback (standard text without layout distortion)
    if total_chars < 20:
        try:
            with pdfplumber.open(file_path) as pdf:
                plumber_texts = []
                for page in pdf.pages:
                    pt = page.extract_text() or ""
                    if pt.strip():
                        plumber_texts.append(pt.strip())
                if plumber_texts:
                    combined_pt = "\n".join(plumber_texts)
                    if len(combined_pt.strip()) > total_chars:
                        text_content = plumber_texts
                        total_chars = len(combined_pt.strip())
        except Exception as e:
            logger.warning(f"pdfplumber extraction notice: {e}")

    full_text = "\n".join(text_content)
    is_scanned = total_chars < 20
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
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
            return text, bool(text.strip()), "OCR processed successfully."

    except ImportError:
        return "", False, "OCR library (pytesseract) is not installed in the Python environment."
    except Exception as e:
        return "", False, f"OCR processing encountered an error: {str(e)}"


def _extract_line_items(lines: List[str]) -> List[LineItemCandidate]:
    """
    Extracts line items from tabular sections of the invoice.
    Supports single-line items, 4-line items (Desc, Qty, Price, Total),
    and 6-line items (#, Desc, HSN, Qty, Price, Total).
    """
    start_idx = -1
    end_idx = -1
    for idx, l in enumerate(lines):
        ll = l.lower()
        if re.search(r"\b(?:items\s*(?:/\s*services)?|description|item\s+description)\b", ll) and start_idx == -1:
            start_idx = idx
        if re.search(r"^\s*(?:subtotal|sub-total|sub\s+total|cgst|sgst|igst|tax\b|total\s+amount|grand\s+total|total\s+due|invoice\s+total|amount\s+due|balance\s+due|net\s+payable|\btotal\s*[:(]|\btotal\s+[\d$€£₹A-Za-z])", ll) and start_idx != -1 and end_idx == -1:
            end_idx = idx

    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return []

    table_lines = lines[start_idx:end_idx]
    header_keywords = {"items", "services", "description", "qty", "quantity", "unit", "price", "rate", "taxable", "amount", "total", "#", "hsn", "sac", "hsn/sac"}
    data_lines = [l for l in table_lines if not all(w in header_keywords for w in re.findall(r"\w+", l.lower()))]

    items: List[LineItemCandidate] = []
    i = 0
    while i < len(data_lines):
        l = data_lines[i]

        # Single-line with HSN and optional item # (e.g. '1 Industrial Drills Model X 84672100 2 150.00 300.00' or 'Laptop accessories 8473 (test) 2 ■5,000.00 ■10,000.00')
        m_single_hsn = re.search(
            r"^(?:(\d+)\s+)?([A-Za-z].*?)\s+(?:(\d{4,8}(?:\s*\([^\)]*\))?)\s+)?(\d+(?:\.\d+)?)\s+(?:INR|USD|Rs\.?|[$€£₹■n])?\s*(\d{1,3}(?:,\d{2,3})*\.\d{2})\s+(?:INR|USD|Rs\.?|[$€£₹■n])?\s*(\d{1,3}(?:,\d{2,3})*\.\d{2})$",
            l
        )
        if m_single_hsn:
            num = m_single_hsn.group(1)
            desc = m_single_hsn.group(2).strip()
            hsn = m_single_hsn.group(3)
            qty = Decimal(m_single_hsn.group(4))
            price = Decimal(m_single_hsn.group(5).replace(",", ""))
            tot = Decimal(m_single_hsn.group(6).replace(",", ""))
            items.append(LineItemCandidate(item_number=num, description=desc, hsn_sac=hsn, quantity=qty, unit_price=price, line_total=tot))
            i += 1
            continue

        # Single-line format without HSN (e.g. 'A4 copier paper 10 250.00 2,500.00')
        m_single = re.search(
            r"^(?:(\d+)\s+)?([A-Za-z].*?)\s+(\d+(?:\.\d+)?)\s+(?:INR|USD|Rs\.?|[$€£₹■n])?\s*(\d{1,3}(?:,\d{2,3})*\.\d{2})\s+(?:INR|USD|Rs\.?|[$€£₹■n])?\s*(\d{1,3}(?:,\d{2,3})*\.\d{2})$",
            l
        )
        if m_single:
            num = m_single.group(1)
            desc = m_single.group(2).strip()
            qty = Decimal(m_single.group(3))
            price = Decimal(m_single.group(4).replace(",", ""))
            tot = Decimal(m_single.group(5).replace(",", ""))
            items.append(LineItemCandidate(item_number=num, description=desc, quantity=qty, unit_price=price, line_total=tot))
            i += 1
            continue

        # 6-line block pattern: item #, description, hsn, qty, unit price, total
        if l.isdigit() and i + 5 < len(data_lines):
            item_no = l
            desc = data_lines[i+1]
            hsn = data_lines[i+2]
            qty_str = data_lines[i+3]
            price_str = data_lines[i+4]
            total_str = data_lines[i+5]
            if qty_str.isdigit() or re.match(r"^\d+\.\d+$", qty_str):
                price_m = re.search(r"(\d{1,3}(?:,\d{2,3})*\.\d{2})", price_str)
                total_m = re.search(r"(\d{1,3}(?:,\d{2,3})*\.\d{2})", total_str)
                if price_m and total_m:
                    items.append(LineItemCandidate(
                        item_number=item_no,
                        description=desc,
                        hsn_sac=hsn,
                        quantity=Decimal(qty_str),
                        unit_price=Decimal(price_m.group(1).replace(",", "")),
                        line_total=Decimal(total_m.group(1).replace(",", ""))
                    ))
                    i += 6
                    continue

        # 4-line block pattern: description, qty, unit price, total
        if i + 3 < len(data_lines):
            desc = l
            qty_str = data_lines[i+1]
            price_str = data_lines[i+2]
            total_str = data_lines[i+3]
            if re.match(r"^\d+(?:\.\d+)?$", qty_str):
                price_m = re.search(r"(\d{1,3}(?:,\d{2,3})*\.\d{2})", price_str)
                total_m = re.search(r"(\d{1,3}(?:,\d{2,3})*\.\d{2})", total_str)
                if price_m and total_m:
                    items.append(LineItemCandidate(
                        description=desc,
                        quantity=Decimal(qty_str),
                        unit_price=Decimal(price_m.group(1).replace(",", "")),
                        line_total=Decimal(total_m.group(1).replace(",", ""))
                    ))
                    i += 4
                    continue

        i += 1

    return items


def extract_candidate_fields(raw_text: str) -> Tuple[InvoiceCandidateFields, List[str]]:
    """
    Extracts invoice metadata, vendor details, customer details, tax breakdown,
    line items, and financial values from document text.
    Preserves original text for review and audit transparency.
    Never invents absent fields.
    """
    notes: List[str] = []
    validation_warnings: List[str] = []
    candidates = InvoiceCandidateFields()
    field_confidence: Dict[str, str] = {}

    if not raw_text or not raw_text.strip():
        notes.append("No readable text detected in the document. Please manually enter invoice fields.")
        candidates.field_confidence = field_confidence
        return candidates, notes

    # Preserve raw text
    candidates.raw_text = raw_text

    # Pre-clean fused text without breaking 'Subtotal'
    clean_text = clean_merged_text(raw_text)
    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

    # 1. Currency Detection (Explicit currency takes precedence)
    curr_m = re.search(r"(?im)\b(?:currency|curr)\s*[:#]\s*([A-Za-z]{3}|[$€£₹])", clean_text)
    if curr_m:
        raw_c = curr_m.group(1).upper()
        if raw_c in {"USD", "EUR", "GBP", "INR", "CAD", "AUD"}:
            candidates.currency = raw_c
        elif raw_c == "$":
            candidates.currency = "USD"
        elif raw_c == "€":
            candidates.currency = "EUR"
        elif raw_c == "£":
            candidates.currency = "GBP"
        elif raw_c in {"₹", "RS"}:
            candidates.currency = "INR"
    elif re.search(r"(?:₹|\bINR\b|\bRs\.?\b|\bRupees\b|GSTIN:\s*\d{2}|Place\s+of\s+Supply|CGST|SGST|IGST)", clean_text, re.I):
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

    # 2. Invoice Type Extraction
    type_m = re.search(r"\b(TAX\s+INVOICE|COMMERCIAL\s+INVOICE|BILL\s+OF\s+SUPPLY|PROFORMA\s+INVOICE|CREDIT\s+NOTE|DEBIT\s+NOTE)\b", clean_text, re.I)
    if type_m:
        candidates.invoice_type = type_m.group(1).title()
        field_confidence["invoice_type"] = "HIGH"
    elif re.search(r"(?:tax|gst|cgst|sgst)", clean_text, re.I):
        candidates.invoice_type = "Tax Invoice"
        field_confidence["invoice_type"] = "MEDIUM"
    else:
        candidates.invoice_type = "Standard Invoice"
        field_confidence["invoice_type"] = "MEDIUM"

    # 3. Multi-Header Grid Block Detection (e.g. Invoice Number, Date, Due Date, Terms)
    for i in range(len(lines) - 7):
        b_hdr = lines[i:i+4]
        b_val = lines[i+4:i+8]
        # Only treat as a grid block if the header lines are short labels without colons/amounts
        if all(len(h) < 40 and not re.search(r"\d", h) for h in b_hdr):
            hdr_str = " ".join(b_hdr).lower()
            if "invoice number" in hdr_str and "invoice date" in hdr_str:
                for h, v in zip(b_hdr, b_val):
                    hl = h.lower()
                    if "number" in hl and not candidates.invoice_number:
                        candidates.invoice_number = v.strip()
                        field_confidence["invoice_number"] = "HIGH"
                    elif "due" in hl and not candidates.due_date:
                        candidates.due_date = parse_date_flexible(v, default_to_dmy=default_dmy)
                        if candidates.due_date:
                            field_confidence["due_date"] = "HIGH"
                    elif "date" in hl and not candidates.invoice_date:
                        candidates.invoice_date = parse_date_flexible(v, default_to_dmy=default_dmy)
                        if candidates.invoice_date:
                            field_confidence["invoice_date"] = "HIGH"
                    elif "terms" in hl and not candidates.payment_terms:
                        candidates.payment_terms = v.strip()
                        field_confidence["payment_terms"] = "HIGH"

            if "po number" in hdr_str and ("currency" in hdr_str or "supply" in hdr_str or "status" in hdr_str):
                for h, v in zip(b_hdr, b_val):
                    hl = h.lower()
                    if "po" in hl and not candidates.po_number:
                        candidates.po_number = v.strip()
                        field_confidence["po_number"] = "HIGH"
                    elif "supply" in hl and not candidates.place_of_supply:
                        candidates.place_of_supply = v.strip()
                        field_confidence["place_of_supply"] = "HIGH"
                    elif "status" in hl and not candidates.payment_status:
                        s_clean = re.sub(r"[\(\[\n].*$", "", v).strip()
                        if s_clean.lower() in {"unpaid", "paid", "partially paid", "overdue", "pending"}:
                            candidates.payment_status = s_clean.title()
                        else:
                            candidates.payment_status = s_clean
                        field_confidence["payment_status"] = "HIGH"

    # 4. Same-line and Adjacent-line Label Matching for Invoice Identifiers
    # Invoice Number
    if not candidates.invoice_number:
        inv_num_patterns = [
            r"(?im)^\s*(?:invoice|tax\s+invoice|bill|inv|receipt)\s*(?:#|number|no\.?|num)\s*[:#]\s*([A-Za-z0-9\-_/#]{2,40})",
            r"(?im)\b(?:invoice|tax\s+invoice|bill|inv|receipt)\s*(?:#|number|no\.?|num)\s*[:#]\s*([A-Za-z0-9\-_/#]{2,40})",
            r"(?im)^\s*(?:invoice|inv)\s*(?:#|no\.?|number)?\s*[:#]\s*([A-Za-z0-9\-_/#]{2,40})",
        ]
        for pat in inv_num_patterns:
            m = re.search(pat, clean_text)
            if m:
                val = m.group(1).strip()
                if val.lower() not in {"date", "number", "due", "total", "amount", "tax", "terms", "invoice"}:
                    candidates.invoice_number = val
                    field_confidence["invoice_number"] = "HIGH"
                    break

    # Adjacent line fallback for invoice number
    if not candidates.invoice_number:
        for i, line in enumerate(lines[:-1]):
            if re.match(r"(?i)^(?:invoice|inv|bill)\s*(?:number|no\.?|#)?\s*[:#]?$", line):
                next_line = lines[i+1].strip()
                m_next = re.match(r"^([A-Za-z0-9\-_/#]{2,40})", next_line)
                if m_next and m_next.group(1).lower() not in {"date", "due", "total", "amount", "tax", "terms", "invoice"}:
                    candidates.invoice_number = m_next.group(1)
                    field_confidence["invoice_number"] = "MEDIUM"
                    break

    if not candidates.invoice_number:
        notes.append("Invoice number could not be reliably detected.")
        validation_warnings.append("Invoice number was not detected automatically. Please enter it manually.")

    # Dates (Invoice Date & Due Date)
    if not candidates.invoice_date:
        inv_date_pattern = rf"(?im)\b(?:invoice\s*date|date\s*of\s*issue|issue\s*date|bill\s*date|\bdate\b)\s*[:#]?\s*({DATE_CAPTURE_PATTERN})"
        inv_date_m = re.search(inv_date_pattern, clean_text)
        if inv_date_m:
            parsed_d = parse_date_flexible(inv_date_m.group(1), default_to_dmy=default_dmy)
            if parsed_d:
                candidates.invoice_date = parsed_d
                field_confidence["invoice_date"] = "HIGH"

    if not candidates.invoice_date:
        validation_warnings.append("Invoice date was not detected automatically. Please specify the invoice date.")

    if not candidates.due_date:
        due_date_pattern = rf"(?im)\b(?:due\s*date|payment\s*due(?:\s*date)?|pay\s*by|due\s*by)\s*[:#]?\s*({DATE_CAPTURE_PATTERN})"
        due_date_m = re.search(due_date_pattern, clean_text)
        if due_date_m:
            parsed_d = parse_date_flexible(due_date_m.group(1), default_to_dmy=default_dmy)
            if parsed_d:
                candidates.due_date = parsed_d
                field_confidence["due_date"] = "HIGH"
        else:
            notes.append("Due date not specified on document.")

    # Payment Terms
    if not candidates.payment_terms:
        terms_m = re.search(r"(?im)^\s*(?:payment\s+terms|terms)\s*[:#]?\s*([^\r\n]+)", clean_text)
        if terms_m:
            candidates.payment_terms = terms_m.group(1).strip()
            field_confidence["payment_terms"] = "HIGH"
        else:
            m_net = re.search(r"\b(net\s+\d+(?:\s+days)?|due\s+on\s+receipt|immediate|advance|cod)\b", clean_text, re.I)
            if m_net:
                candidates.payment_terms = m_net.group(1).title()
                field_confidence["payment_terms"] = "MEDIUM"

    # PO Number & Reference Number
    if not candidates.po_number:
        po_m = re.search(r"(?im)\b(?:po\s+(?:number|no\.?|#|ref(?:erence)?)|purchase\s+order(?:\s+(?:no|number|#))?)\s*[:#]?\s*([A-Za-z0-9\-_/#]{2,40})", clean_text)
        if po_m:
            candidates.po_number = po_m.group(1).strip()
            field_confidence["po_number"] = "HIGH"

    ref_m = re.search(r"(?im)\b(?:reference\s*(?:no\.?|#|number)?|ref\s*(?:no\.?|#)?)\s*[:#]?\s*([A-Za-z0-9\-_/#]{2,40})", clean_text)
    if ref_m:
        candidates.reference_number = ref_m.group(1).strip()
        field_confidence["reference_number"] = "HIGH"

    # Place of Supply
    if not candidates.place_of_supply:
        pos_m = re.search(r"(?im)\b(?:place\s+of\s+supply|pos)\s*[:#]?\s*([A-Za-z\s]+)", clean_text)
        if pos_m:
            candidates.place_of_supply = pos_m.group(1).strip().splitlines()[0]
            field_confidence["place_of_supply"] = "HIGH"

    # Payment Status
    if not candidates.payment_status:
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

    # 5. Vendor & Customer Extraction
    seller_idx = -1
    bill_to_idx = -1
    for idx, l in enumerate(lines):
        ll = l.strip().lower()
        if ll in {"seller", "vendor", "supplier"} or re.match(r"^(?:seller|vendor|supplier):?$", ll):
            if seller_idx == -1:
                seller_idx = idx
        if ll in {"bill to", "buyer", "customer"} or re.match(r"^(?:bill to|buyer|customer):?$", ll):
            if bill_to_idx == -1:
                bill_to_idx = idx

    # Case A: Sequential SELLER block and BILL TO block (from pypdf flow output)
    if seller_idx != -1 and bill_to_idx == seller_idx + 1:
        sub_lines = lines[bill_to_idx + 1:]
        gstin_indices = [i for i, sl in enumerate(sub_lines) if "gstin" in sl.lower()]
        if len(gstin_indices) >= 2:
            g1, g2 = gstin_indices[0], gstin_indices[1]
            seller_block = sub_lines[:g1+1]
            buyer_block = sub_lines[g1+1:g2+1]

            candidates.vendor_name = seller_block[0].strip()
            field_confidence["vendor_name"] = "HIGH"
            v_addr_parts = [line.strip() for line in seller_block[1:g1] if "@" not in line and not line.lower().startswith("gstin")]
            if v_addr_parts:
                candidates.vendor_address = ", ".join(v_addr_parts)
                field_confidence["vendor_address"] = "HIGH"

            m_g1 = re.search(r"GSTIN:\s*([0-9A-Za-z]{15})", seller_block[g1], re.I)
            if m_g1:
                candidates.vendor_gstin = m_g1.group(1).upper()
                candidates.vendor_state_code = candidates.vendor_gstin[:2]
                candidates.vendor_state = GST_STATE_CODES.get(candidates.vendor_state_code)
                field_confidence["vendor_gstin"] = "HIGH"
                field_confidence["vendor_state"] = "HIGH"
                field_confidence["vendor_state_code"] = "HIGH"

            candidates.customer_name = buyer_block[0].strip()
            field_confidence["customer_name"] = "HIGH"
            c_addr_parts = [line.strip() for line in buyer_block[1:g2-g1] if "@" not in line and not line.lower().startswith("gstin")]
            if c_addr_parts:
                candidates.customer_billing_address = ", ".join(c_addr_parts)
                field_confidence["customer_billing_address"] = "HIGH"

            m_g2 = re.search(r"GSTIN:\s*([0-9A-Za-z]{15})", buyer_block[-1], re.I)
            if m_g2:
                candidates.customer_gstin = m_g2.group(1).upper()
                candidates.customer_state_code = candidates.customer_gstin[:2]
                candidates.customer_state = GST_STATE_CODES.get(candidates.customer_state_code)
                field_confidence["customer_gstin"] = "HIGH"
                field_confidence["customer_state"] = "HIGH"
                field_confidence["customer_state_code"] = "HIGH"

    # Case B: Standard Labeled Matching
    if not candidates.vendor_name:
        vendor_pattern = r"(?im)^\s*(?:supplier\s*(?:/\s*vendor)?|vendor\s*(?:/\s*supplier)?|vendor|supplier|from|billed\s+by|seller|company)[^\S\r\n]*[:#][^\S\r\n]+([^\r\n]+)"
        v_match = re.search(vendor_pattern, clean_text)
        if v_match:
            candidate_v = v_match.group(1).strip()
            clean_v = re.split(
                r"(?i)(?:\b|(?<=[a-z]))(?:address|gstin|cin|pan|phone|tel|email|bill\s+to|customer|invoice\s*(?:no|number)?|date)\b",
                candidate_v
            )[0].strip().rstrip(":, -")
            clean_v = re.sub(r"\s*\((?:fictional|sample|test|demo|testing)[^)]*\)", "", clean_v, flags=re.IGNORECASE).strip()
            if len(clean_v) >= 2:
                candidates.vendor_name = clean_v
                field_confidence["vendor_name"] = "HIGH"

    # Adjacent line fallback for vendor name
    if not candidates.vendor_name:
        for i, line in enumerate(lines[:-1]):
            if re.match(r"(?i)^(?:supplier\s*(?:/\s*vendor)?|vendor\s*(?:/\s*supplier)?|vendor|supplier|seller|billed\s+by)\s*[:#]?$", line):
                for offset in range(1, 4):
                    if i + offset >= len(lines):
                        break
                    cand_line = lines[i + offset].strip()
                    if re.match(r"(?i)^(?:invoice|inv|bill|date|due|po|terms|status|gstin|phone|email)\b", cand_line):
                        continue
                    clean_v = re.split(
                        r"(?i)(?:\b|(?<=[a-z]))(?:address|gstin|bill\s+to|date)\b",
                        cand_line
                    )[0].strip().rstrip(":, -")
                    if len(clean_v) >= 2 and not clean_v.lower().startswith("bill to"):
                        candidates.vendor_name = clean_v
                        field_confidence["vendor_name"] = "HIGH"
                        # Next line might be street address
                        if i + offset + 1 < len(lines) and not candidates.vendor_address:
                            addr_cand = lines[i + offset + 1].strip()
                            if re.search(r"\d", addr_cand) and not re.match(r"(?i)^(?:invoice|date|due|gstin)", addr_cand):
                                candidates.vendor_address = addr_cand
                                field_confidence["vendor_address"] = "HIGH"
                        break
                if candidates.vendor_name:
                    break

    # Top header fallback for vendor name
    if not candidates.vendor_name:
        ignore_headers = {
            "sample invoice", "invoice", "tax invoice", "bill of supply", "receipt",
            "statement", "estimate", "commercial invoice", "fictional document for software testing",
            "original for recipient", "duplicate for transporter", "invoiceiq demo invoice"
        }
        for line in lines[:8]:
            l_norm = re.sub(r"\s+", " ", line.strip().lower())
            if l_norm in ignore_headers or any(h in l_norm for h in ["sample invoice", "tax invoice", "testing only"]):
                continue
            if re.match(r"(?i)^(?:address|gstin|cin|pan|bill\s+to|customer|invoice\s+number|date|phone|email)", line):
                continue
            if re.search(r"\b(?:road|street|nagar|pune|mumbai|delhi|bangalore|maharashtra|\d{6})\b", l_norm):
                continue
            if len(line) >= 3 and not re.search(r"^\d+", line) and not re.search(r"^\W+$", line):
                clean_header_v = re.sub(r"\s*\((?:fictional|sample|test|demo|testing)[^)]*\)", "", line.strip(), flags=re.IGNORECASE).strip()
                candidates.vendor_name = clean_header_v
                field_confidence["vendor_name"] = "MEDIUM"
                break

    if not candidates.vendor_name:
        notes.append("Vendor name could not be reliably detected.")
        validation_warnings.append("Supplier / Vendor name was not detected automatically. Please enter it manually.")

    # Customer Name
    if not candidates.customer_name:
        customer_pattern = r"(?im)^\s*(?:bill\s*to\s*(?:/\s*customer)?|bill(?:ed)?\s+to|invoice\s+to|customer(?:\s+name)?|client(?:\s+name)?|buyer|sold\s+to|recipient)[^\S\r\n]*[:#][^\S\r\n]+([^\r\n]+)"
        c_match = re.search(customer_pattern, clean_text)
        if c_match:
            candidate_c = c_match.group(1).strip()
            clean_c = re.split(
                r"(?i)(?:\b|(?<=[a-z]))(?:address|gstin|cin|pan|phone|tel|email|invoice\s*(?:no|number)?|date)\b",
                candidate_c
            )[0].strip().rstrip(":, -")
            if "," in clean_c and re.search(r",\s*\d+\s+[A-Za-z]", clean_c):
                c_parts = clean_c.split(",", 1)
                clean_c = c_parts[0].strip()
                if not candidates.customer_billing_address:
                    candidates.customer_billing_address = c_parts[1].strip()
                    field_confidence["customer_billing_address"] = "HIGH"
            if len(clean_c) >= 2 and clean_c.lower() not in {"name", "details", "customer", "address"}:
                candidates.customer_name = clean_c
                field_confidence["customer_name"] = "HIGH"

    if not candidates.customer_name:
        for i, line in enumerate(lines[:-1]):
            if re.match(r"(?i)^(?:bill\s*to\s*(?:/\s*customer)?|bill(?:ed)?\s+to|invoice\s+to|customer|client|sold\s+to|buyer)\s*[:#]?$", line):
                for offset in range(1, 4):
                    if i + offset >= len(lines):
                        break
                    cand_line = lines[i + offset].strip()
                    if re.match(r"(?i)^(?:po|status|invoice|inv|date|due|terms|gstin|place\s+of\s+supply|phone|email)\b", cand_line):
                        continue
                    clean_c = re.split(
                        r"(?i)(?:\b|(?<=[a-z]))(?:address|gstin|cin|pan|phone|tel|email|invoice\s*(?:no|number)?|date)\b",
                        cand_line
                    )[0].strip().rstrip(":, -")
                    if len(clean_c) >= 2 and not clean_c.lower().startswith("address"):
                        candidates.customer_name = clean_c
                        field_confidence["customer_name"] = "HIGH"
                        if i + offset + 1 < len(lines) and not candidates.customer_billing_address:
                            addr_cand = lines[i + offset + 1].strip()
                            if not re.match(r"(?i)^(?:po|status|gstin|place\s+of\s+supply)", addr_cand):
                                candidates.customer_billing_address = addr_cand
                                field_confidence["customer_billing_address"] = "HIGH"
                        break
                if candidates.customer_name:
                    break

    # Vendor Address fallback if not yet captured
    if not candidates.vendor_address:
        v_addr_m = re.search(r"(?im)^\s*address\s*[:#]\s*([^\r\n]+)", clean_text)
        if v_addr_m:
            candidates.vendor_address = v_addr_m.group(1).strip()
            field_confidence["vendor_address"] = "HIGH"

    # GSTIN extraction fallback if not yet captured
    all_gstins = re.findall(r"\b([0-9]{2}[A-Za-z0-9]{13})\b", clean_text)
    if all_gstins:
        if not candidates.vendor_gstin:
            candidates.vendor_gstin = all_gstins[0].upper()
            candidates.vendor_state_code = candidates.vendor_gstin[:2]
            candidates.vendor_state = GST_STATE_CODES.get(candidates.vendor_state_code)
            field_confidence["vendor_gstin"] = "HIGH"
            field_confidence["vendor_state"] = "HIGH"
            field_confidence["vendor_state_code"] = "HIGH"
        if len(all_gstins) > 1 and not candidates.customer_gstin:
            candidates.customer_gstin = all_gstins[1].upper()
            candidates.customer_state_code = candidates.customer_gstin[:2]
            candidates.customer_state = GST_STATE_CODES.get(candidates.customer_state_code)
            field_confidence["customer_gstin"] = "HIGH"
            field_confidence["customer_state"] = "HIGH"
            field_confidence["customer_state_code"] = "HIGH"

    # Shipping Address extraction
    ship_m = re.search(r"(?im)^\s*(?:ship(?:ped)?\s+to|consignee|delivery\s+address|deliver\s+to)[^\S\r\n]*[:#]\s*([^\r\n]+)", clean_text)
    if ship_m:
        candidates.customer_shipping_address = ship_m.group(1).strip()
        field_confidence["customer_shipping_address"] = "HIGH"

    # 6. Amounts Extraction (Subtotal, Taxes, Discounts, Total)
    # A. Subtotal
    subtotal_m = re.search(
        rf"(?im)^\s*(?:subtotal|sub-total|sub\s+total|base\s+amount)[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )
    if subtotal_m:
        candidates.subtotal = parse_amount_string(subtotal_m.group(1))
        if candidates.subtotal is not None:
            field_confidence["subtotal"] = "HIGH"

    # Taxable Amount
    taxable_m = re.search(
        rf"(?im)^\s*(?:taxable\s+(?:amount|value))[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )
    if taxable_m:
        candidates.taxable_amount = parse_amount_string(taxable_m.group(1))
        if candidates.taxable_amount is not None:
            field_confidence["taxable_amount"] = "HIGH"

    # Discounts
    disc_m = re.search(
        rf"(?im)^\s*(?:discount|discounts|less\s+discount)[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )
    if disc_m:
        candidates.discounts = parse_amount_string(disc_m.group(1))
        if candidates.discounts is not None:
            field_confidence["discounts"] = "HIGH"

    # B. Taxes (CGST, SGST, IGST, Generic Tax)
    cgst_rate_str = ""
    sgst_rate_str = ""
    igst_rate_str = ""

    cgst_m = re.search(
        rf"(?im)^\s*cgst(?:\s*[@(]\s*(\d+(?:\.\d+)?%?)\s*\)?)?[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )
    if cgst_m:
        if cgst_m.group(1):
            cgst_rate_str = cgst_m.group(1).rstrip("%")
        candidates.cgst = parse_amount_string(cgst_m.group(2))
        if candidates.cgst is not None:
            field_confidence["cgst"] = "HIGH"

    sgst_m = re.search(
        rf"(?im)^\s*(?:sgst|utgst)(?:\s*[@(]\s*(\d+(?:\.\d+)?%?)\s*\)?)?[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )
    if sgst_m:
        if sgst_m.group(1):
            sgst_rate_str = sgst_m.group(1).rstrip("%")
        candidates.sgst = parse_amount_string(sgst_m.group(2))
        if candidates.sgst is not None:
            field_confidence["sgst"] = "HIGH"

    igst_m = re.search(
        rf"(?im)^\s*igst(?:\s*[@(]\s*(\d+(?:\.\d+)?%?)\s*\)?)?[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )
    if igst_m:
        if igst_m.group(1):
            igst_rate_str = igst_m.group(1).rstrip("%")
        candidates.igst = parse_amount_string(igst_m.group(2))
        if candidates.igst is not None:
            field_confidence["igst"] = "HIGH"

    gen_tax_m = re.search(
        rf"(?im)^\s*(?:total\s+tax|tax(?:\s+amount)?(?:\s*\(.*?\))?|gst(?:\s+amount)?(?:\s*\(.*?\))?|vat(?:\s+amount)?|sales\s+tax)[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX})",
        clean_text
    )

    # Reconcile tax_amount & tax_rate
    if candidates.cgst is not None and candidates.sgst is not None:
        candidates.tax_amount = (candidates.cgst + candidates.sgst).quantize(Decimal("0.01"))
        field_confidence["tax_amount"] = "HIGH"
        if cgst_rate_str and sgst_rate_str:
            total_rate = float(cgst_rate_str) + float(sgst_rate_str)
            candidates.tax_rate = f"{total_rate:.0f}% ({cgst_rate_str}% CGST + {sgst_rate_str}% SGST)"
        notes.append(
            f"Extracted Indian GST: CGST {candidates.currency} {candidates.cgst}, "
            f"SGST {candidates.currency} {candidates.sgst} (Combined: {candidates.currency} {candidates.tax_amount})."
        )
    elif candidates.igst is not None:
        candidates.tax_amount = candidates.igst
        field_confidence["tax_amount"] = "HIGH"
        if igst_rate_str:
            candidates.tax_rate = f"{igst_rate_str}% IGST"
        notes.append(f"Extracted IGST: {candidates.currency} {candidates.tax_amount}.")
    elif gen_tax_m:
        candidates.tax_amount = parse_amount_string(gen_tax_m.group(1))
        if candidates.tax_amount is not None:
            field_confidence["tax_amount"] = "HIGH"
        m_rate = re.search(r"(\d+(?:\.\d+)?%)", gen_tax_m.group(0))
        if m_rate:
            candidates.tax_rate = m_rate.group(1)

    # Other charges
    other_m = re.search(
        rf"(?im)^\s*(?:shipping(?:\s*charges|\s*fee)?|freight|handling(?:\s*charges|\s*fee)?|round\s+off|other\s+charges)[^\S\r\n]*[:\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX}){CURRENCY_SUFFIX_REGEX}",
        clean_text
    )
    if other_m:
        candidates.other_charges = parse_amount_string(other_m.group(1))
        if candidates.other_charges is not None:
            field_confidence["other_charges"] = "HIGH"

    # 7. Line Items Extraction (performed before total reconciliation and fallback)
    candidates.line_items = _extract_line_items(lines)
    if candidates.line_items:
        notes.append(f"Extracted {len(candidates.line_items)} line item(s) from document table.")

    # Calculate expected total from line items and/or subtotal + taxes + charges - discounts
    calculated_expected: Optional[Decimal] = None
    if candidates.line_items:
        valid_line_totals = [item.line_total for item in candidates.line_items if item.line_total is not None]
        if valid_line_totals:
            line_sum = sum(valid_line_totals, Decimal("0.00"))
            calc = line_sum
            if candidates.tax_amount is not None:
                calc += candidates.tax_amount
            if candidates.other_charges is not None:
                calc += candidates.other_charges
            if candidates.discounts is not None:
                calc -= candidates.discounts
            calculated_expected = calc.quantize(Decimal("0.01"))
    elif candidates.subtotal is not None:
        calc = candidates.subtotal
        if candidates.tax_amount is not None:
            calc += candidates.tax_amount
        if candidates.other_charges is not None:
            calc += candidates.other_charges
        if candidates.discounts is not None:
            calc -= candidates.discounts
        calculated_expected = calc.quantize(Decimal("0.01"))

    candidates.calculated_total = calculated_expected

    # C. Total Amount (Grand Total) Extraction
    total_patterns = [
        # Pattern 1: Same line with label at start of line
        rf"(?im)^\s*{TOTAL_LABEL_REGEX}[^\S\r\n]*(?:\([A-Za-z]{{3}}\))?[^\S\r\n]*[:=\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX}){CURRENCY_SUFFIX_REGEX}",
        # Pattern 2: Multiline layout where label is on one line and amount is on the next line
        rf"(?im)^\s*{TOTAL_LABEL_REGEX}[^\S\r\n]*(?:\([A-Za-z]{{3}}\))?[^\S\r\n]*[:=]?[^\S\r\n]*\r?\n\s*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX}){CURRENCY_SUFFIX_REGEX}",
        # Pattern 3: Explicit total label anywhere in a line (excluding subtotal / tax total)
        rf"(?im)\b(?:total\s+amount\s+due|total\s+amount\s+payable|total\s+payable|grand\s+total|invoice\s+total|total\s+invoice\s+amount|total\s+amount|total\s+due|amount\s+due|balance\s+due|amount\s+payable|net\s+payable|final\s+total)[^\S\r\n]*(?:\([A-Za-z]{{3}}\))?[^\S\r\n]*[:=\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX}){CURRENCY_SUFFIX_REGEX}",
    ]
    for pat in total_patterns:
        total_m = re.search(pat, clean_text)
        if total_m:
            candidates.total_amount = parse_amount_string(total_m.group(1))
            if candidates.total_amount is not None:
                field_confidence["total_amount"] = "HIGH"
                break

    # Line-by-line fallback (for tabular layouts, OCR offsets, and separate column blocks)
    if not candidates.total_amount:
        for idx, line in enumerate(lines):
            if re.search(r"(?i)\b(?:sub\s*total|sub-total|tax\s+total)\b", line):
                continue
            if re.search(rf"(?i)^\s*{TOTAL_LABEL_REGEX}\b", line):
                m_same = re.search(rf"{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX}){CURRENCY_SUFFIX_REGEX}", line)
                if m_same:
                    amt = parse_amount_string(m_same.group(1))
                    if amt is not None:
                        candidates.total_amount = amt
                        field_confidence["total_amount"] = "HIGH"
                        break
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1]
                    m_next = re.search(rf"^\s*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX}){CURRENCY_SUFFIX_REGEX}\s*$", next_line)
                    if m_next:
                        amt = parse_amount_string(m_next.group(1))
                        if amt is not None:
                            candidates.total_amount = amt
                            field_confidence["total_amount"] = "MEDIUM"
                            break

    # Bottom-up fallback scan from bottom of document upwards
    if not candidates.total_amount:
        for line in reversed(lines):
            if re.search(r"(?i)\b(?:sub\s*total|sub-total|tax\s+total)\b", line):
                continue
            m_rev = re.search(
                rf"(?i)\b{TOTAL_LABEL_REGEX}\b[^\S\r\n]*(?:\([A-Za-z]{{3}}\))?[^\S\r\n]*[:=\s]*{CURRENCY_PREFIX_REGEX}[^\S\r\n]*({AMOUNT_NUM_REGEX}){CURRENCY_SUFFIX_REGEX}",
                line
            )
            if m_rev:
                amt = parse_amount_string(m_rev.group(1))
                if amt is not None:
                    candidates.total_amount = amt
                    field_confidence["total_amount"] = "MEDIUM"
                    break

    # Fallback and Reconciliation handling
    if candidates.total_amount is not None:
        # Document printed total is preserved
        if candidates.calculated_total is not None:
            diff = abs(candidates.total_amount - candidates.calculated_total)
            if diff <= Decimal("0.05"):
                notes.append(
                    f"Financial reconciliation verified: Extracted Total ({candidates.total_amount}) matches calculated sum ({candidates.calculated_total})."
                )
                field_confidence["total_amount"] = "HIGH"
            else:
                field_confidence["total_amount"] = "MEDIUM"
                msg = (
                    f"Arithmetic Discrepancy: Extracted invoice total ({candidates.currency} {candidates.total_amount}) "
                    f"differs from calculated sum ({candidates.currency} {candidates.calculated_total}). "
                    "The original extracted figures have been preserved for your review."
                )
                notes.append(msg)
                validation_warnings.append(msg)
    else:
        # Fallback: calculate expected total if reliable line items / subtotal are present
        if candidates.calculated_total is not None and candidates.calculated_total > 0:
            candidates.total_amount = candidates.calculated_total
            field_confidence["total_amount"] = "CALCULATED"
            calc_note = (
                f"Calculated fallback: Stated total was not detected; expected total "
                f"({candidates.currency} {candidates.calculated_total}) was derived from line items and taxes."
            )
            calc_warn = (
                f"Notice: Stated total was not detected. A calculated total of {candidates.currency} {candidates.calculated_total} "
                "was derived from line items and taxes. Please verify before saving."
            )
            notes.append(calc_note)
            validation_warnings.append(calc_warn)
        else:
            notes.append("Total amount could not be reliably detected.")
            validation_warnings.append("Total amount was not detected automatically. Please enter the invoice total.")

    if candidates.subtotal is not None and candidates.total_amount is not None:
        if candidates.subtotal > candidates.total_amount:
            validation_warnings.append(
                f"Warning: Extracted Subtotal ({candidates.currency} {candidates.subtotal}) is greater than Grand Total ({candidates.currency} {candidates.total_amount}). Please review."
            )

    if candidates.invoice_date and candidates.due_date:
        if candidates.due_date < candidates.invoice_date:
            field_confidence["due_date"] = "MEDIUM"
            validation_warnings.append(
                f"Date Sequence Warning: Due date ({candidates.due_date}) is earlier than invoice date ({candidates.invoice_date}). Please verify."
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
