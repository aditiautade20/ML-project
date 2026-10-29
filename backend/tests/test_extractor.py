from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest
from app.services.extractor import (
    extract_candidate_fields,
    parse_amount_string,
    parse_date_string,
    parse_date_flexible,
    process_invoice_file,
)
from app.schemas.invoice import InvoiceCandidateFields


def test_extract_all_candidate_fields():
    invoice_text = """
    Acme Cloud Services Inc.
    123 Tech Way, Silicon Valley, CA
    
    INVOICE
    Invoice Number: INV-98765
    Invoice Date: 2026-05-15
    Due Date: 2026-06-15
    
    Billed To:
    Client Corp
    
    Description        Amount
    Server Hosting     $1,000.00
    Subtotal:          $1,000.00
    Tax:               $100.00
    Total Amount:      $1,100.00
    """
    candidates, notes = extract_candidate_fields(invoice_text)

    assert candidates.invoice_number == "INV-98765"
    assert "Acme Cloud Services" in candidates.vendor_name
    assert candidates.invoice_date == date(2026, 5, 15)
    assert candidates.due_date == date(2026, 6, 15)
    assert candidates.subtotal == Decimal("1000.00")
    assert candidates.tax_amount == Decimal("100.00")
    assert candidates.total_amount == Decimal("1100.00")
    assert candidates.currency == "USD"


def test_sample_invoice_pdf_extraction():
    """Verifies extraction against the actual sample invoice PDF provided by the user."""
    sample_pdf = Path(r"C:\Users\aditi\Downloads\InvoiceIQ_New\backend\data\uploads\inv_b72f0490c51846a0873df5664bd448f7.pdf")
    if not sample_pdf.exists():
        pytest.skip("Sample PDF not found in uploads directory")

    candidates, notes = process_invoice_file(sample_pdf, "application/pdf")

    assert candidates.invoice_number == "INV-TEST-1001"
    assert candidates.vendor_name == "BrightDesk Office Supplies"
    # Verify customer and payment status extraction
    assert candidates.customer_name == "Demo Customer"
    assert candidates.payment_status == "Unpaid"
    # Verify no accidental label merging
    assert "Address" not in candidates.vendor_name
    assert "GSTIN" not in candidates.vendor_name

    assert candidates.invoice_date == date(2026, 10, 25)
    assert candidates.due_date == date(2026, 11, 8)
    assert candidates.currency == "INR"
    assert candidates.subtotal == Decimal("3700.00")
    assert candidates.cgst == Decimal("333.00")
    assert candidates.sgst == Decimal("333.00")
    assert candidates.tax_amount == Decimal("666.00")
    assert candidates.total_amount == Decimal("4366.00")

    # Field confidence
    assert candidates.field_confidence.get("invoice_number") == "HIGH"
    assert candidates.field_confidence.get("vendor_name") == "HIGH"
    assert candidates.field_confidence.get("customer_name") == "HIGH"
    assert candidates.field_confidence.get("total_amount") == "HIGH"

    # Reconciliation note present
    assert any("Financial reconciliation verified" in n for n in notes)


def test_vendor_name_does_not_merge_unrelated_labels():
    """Ensures vendor names do not capture trailing labels on same or adjacent lines."""
    text = """
    Vendor: Apex Business Solvers Address: 124 Park Ave, Suite 400
    GSTIN: 27AAAAA0000A1Z5
    Bill To: Recipient Corp
    Invoice No: AP-8801
    Date: 25/10/2026
    Total: $1,250.00
    """
    candidates, _ = extract_candidate_fields(text)
    assert candidates.vendor_name == "Apex Business Solvers"
    assert "Address" not in candidates.vendor_name
    assert "GSTIN" not in candidates.vendor_name
    assert candidates.invoice_number == "AP-8801"
    assert candidates.invoice_date == date(2026, 10, 25)
    assert candidates.total_amount == Decimal("1250.00")


def test_date_format_normalization():
    """Tests various valid date formats normalized to ISO date objects."""
    # 25 October 2026
    d1 = parse_date_flexible("25 October 2026")
    assert d1 == date(2026, 10, 25)

    # 25 Oct 2026
    d2 = parse_date_flexible("25 Oct 2026")
    assert d2 == date(2026, 10, 25)

    # 25/10/2026
    d3 = parse_date_flexible("25/10/2026")
    assert d3 == date(2026, 10, 25)

    # 25-10-2026
    d4 = parse_date_flexible("25-10-2026")
    assert d4 == date(2026, 10, 25)

    # 2026-10-25
    d5 = parse_date_flexible("2026-10-25")
    assert d5 == date(2026, 10, 25)

    # October 25, 2026
    d6 = parse_date_flexible("October 25, 2026")
    assert d6 == date(2026, 10, 25)


def test_correct_total_selection_when_subtotal_and_taxes_present():
    """Ensures total is not confused with subtotal or individual tax lines."""
    text = """
    Vendor: Clean Supplies Co.
    Invoice Number: CS-9912
    Date: 2026-08-01
    Subtotal: INR 10,000.00
    CGST (9%): INR 900.00
    SGST (9%): INR 900.00
    TOTAL DUE: INR 11,800.00
    """
    candidates, notes = extract_candidate_fields(text)
    assert candidates.subtotal == Decimal("10000.00")
    assert candidates.cgst == Decimal("900.00")
    assert candidates.sgst == Decimal("900.00")
    assert candidates.tax_amount == Decimal("1800.00")
    assert candidates.total_amount == Decimal("11800.00")
    assert candidates.total_amount != candidates.subtotal
    assert candidates.total_amount != candidates.tax_amount


def test_missing_due_date_remains_none():
    invoice_text = """
    Global Supplies Ltd.
    Invoice #: GS-1102
    Date: October 10, 2026
    
    Office Equipment: $450.00
    Total: $450.00
    """
    candidates, notes = extract_candidate_fields(invoice_text)

    assert candidates.invoice_number == "GS-1102"
    assert candidates.invoice_date == date(2026, 10, 10)
    # Crucial rule: missing due date must NEVER be invented
    assert candidates.due_date is None
    assert candidates.total_amount == Decimal("450.00")
    assert any("Due date not specified" in note for note in notes)


def test_currency_detection():
    # Euro
    text_eur = "Vendor: EuroTech\nInvoice: E-1\nDate: 2026-01-01\nTotal: €500.00"
    cand_eur, _ = extract_candidate_fields(text_eur)
    assert cand_eur.currency == "EUR"
    assert cand_eur.total_amount == Decimal("500.00")

    # GBP
    text_gbp = "Vendor: British Telecom\nInvoice: BT-55\nDate: 2026-01-01\nTotal: £250.00"
    cand_gbp, _ = extract_candidate_fields(text_gbp)
    assert cand_gbp.currency == "GBP"
    assert cand_gbp.total_amount == Decimal("250.00")

    # INR
    text_inr = "Vendor: Pune Tools\nInvoice: PT-10\nDate: 25/10/2026\nTotal: INR 1,500.00"
    cand_inr, _ = extract_candidate_fields(text_inr)
    assert cand_inr.currency == "INR"
    assert cand_inr.total_amount == Decimal("1500.00")


def test_empty_or_unreadable_text_handling():
    candidates, notes = extract_candidate_fields("   \n   \t  ")
    assert candidates.invoice_number is None
    assert candidates.total_amount is None
    assert candidates.invoice_date is None
    assert candidates.due_date is None
    assert any("No readable text" in note for note in notes)


def test_multipage_pdf_simulation():
    """Simulates multi-page invoice where header is on page 1 and totals are on page 2."""
    multipage_text = """
    --- PAGE 1 ---
    Vendor: Enterprise Logistics Corp
    Invoice Number: ELC-2026-990
    Invoice Date: 25 October 2026
    Due Date: 15 November 2026
    
    Item 1: Freight Services
    
    --- PAGE 2 ---
    Item 2: Customs Clearance
    Subtotal: $5,000.00
    Tax: $500.00
    TOTAL AMOUNT: $5,500.00
    """
    candidates, notes = extract_candidate_fields(multipage_text)
    assert candidates.vendor_name == "Enterprise Logistics Corp"
    assert candidates.invoice_number == "ELC-2026-990"
    assert candidates.invoice_date == date(2026, 10, 25)
    assert candidates.due_date == date(2026, 11, 15)
    assert candidates.subtotal == Decimal("5000.00")
    assert candidates.tax_amount == Decimal("500.00")
    assert candidates.total_amount == Decimal("5500.00")
    assert any("Financial reconciliation verified" in n for n in notes)


def test_scanned_pdf_without_ocr_fails_gracefully(tmp_path):
    """
    A PDF with no extractable text should report a clear diagnostic message
    without raising an unhandled exception or claiming false success.
    """
    # Create empty mock file
    empty_pdf = tmp_path / "mock_scanned.pdf"
    empty_pdf.write_bytes(b"%PDF-1.4\n% mock scanned without text\n%%EOF")

    candidates, notes = process_invoice_file(empty_pdf, "application/pdf")
    # Must not crash and must not fabricate fields
    assert candidates.invoice_number is None
    assert candidates.total_amount is None
    assert len(notes) > 0


def test_customer_name_and_payment_status_extraction():
    """Verifies customer/bill-to extraction and explicit payment status parsing."""
    invoice_text = """
    Supplier: TechSphere Global
    Bill To: Vertex Enterprises
    Invoice Number: TS-4410
    Date: 2026-07-20
    Payment Status: Paid
    
    Subtotal: $2,000.00
    Tax: $200.00
    Total: $2,200.00
    """
    candidates, _ = extract_candidate_fields(invoice_text)
    assert candidates.vendor_name == "TechSphere Global"
    assert candidates.customer_name == "Vertex Enterprises"
    assert candidates.payment_status == "Paid"
    assert candidates.invoice_number == "TS-4410"
    assert candidates.field_confidence.get("customer_name") == "HIGH"
    assert candidates.field_confidence.get("payment_status") == "HIGH"


def test_clean_merged_text_function():
    """Verifies that fused keywords from PDF rendering without whitespace are separated."""
    from app.services.extractor import clean_merged_text
    
    merged = "BrightDesk Office SuppliesAddress: 24 Market Road"
    cleaned = clean_merged_text(merged)
    assert "Supplies Address" in cleaned

    merged_customer = "Demo CustomerInvoice Number: INV-1001"
    cleaned_c = clean_merged_text(merged_customer)
    assert "Customer Invoice" in cleaned_c


def test_arithmetic_discrepancy_generates_warning_without_altering_amounts():
    """
    When Subtotal + Tax does not match the stated Grand Total, a clear warning
    must be generated and the numbers MUST NOT be silently changed.
    """
    invoice_text = """
    Vendor: Mismatch Logistics
    Invoice Number: ML-991
    Invoice Date: 2026-08-10
    Due Date: 2026-08-25
    Subtotal: $1,000.00
    Tax: $100.00
    Total Amount: $1,250.00
    """
    candidates, notes = extract_candidate_fields(invoice_text)
    # Stated amounts must be preserved exactly as extracted
    assert candidates.subtotal == Decimal("1000.00")
    assert candidates.tax_amount == Decimal("100.00")
    assert candidates.total_amount == Decimal("1250.00")
    
    # Check that discrepancy warning is present
    assert any("Arithmetic Discrepancy" in n for n in notes)
    # Check confidence marked accordingly
    assert candidates.field_confidence.get("total_amount") == "MEDIUM"


def test_date_sequence_warning():
    """Flags a warning when due date is earlier than invoice date."""
    invoice_text = """
    Vendor: Time Travel LLC
    Invoice Number: TT-100
    Invoice Date: 2026-09-20
    Due Date: 2026-09-10
    Total: $500.00
    """
    candidates, notes = extract_candidate_fields(invoice_text)
    assert candidates.invoice_date == date(2026, 9, 20)
    assert candidates.due_date == date(2026, 9, 10)
    assert candidates.field_confidence.get("due_date") == "MEDIUM"


def test_igst_extraction_and_reconciliation():
    """Verifies Indian IGST extraction for inter-state transactions."""
    text = """
    Vendor: Bangalore Server Systems
    GSTIN: 29ABCDE1234F1Z5
    Bill To: Mumbai Client Ltd
    Invoice Number: BSS-1004
    Date: 25/10/2026
    Subtotal: INR 50,000.00
    IGST (18%): INR 9,000.00
    TOTAL DUE: INR 59,000.00
    """
    candidates, notes = extract_candidate_fields(text)
    assert candidates.vendor_name == "Bangalore Server Systems"
    assert candidates.customer_name == "Mumbai Client Ltd"
    assert candidates.subtotal == Decimal("50000.00")
    assert candidates.igst == Decimal("9000.00")
    assert candidates.tax_amount == Decimal("9000.00")
    assert candidates.total_amount == Decimal("59000.00")
    assert candidates.currency == "INR"
    assert any("Financial reconciliation verified" in n for n in notes)

