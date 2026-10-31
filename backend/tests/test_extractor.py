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


def test_user_uploaded_gst_grid_invoice_pdf():
    """
    Verifies end-to-end extraction on the multi-column Indian GST Tax Invoice
    with header grid block and multi-line item table.
    """
    sample_pdf = Path(r"C:\Users\aditi\Downloads\InvoiceIQ_New\backend\data\uploads\inv_a6c7122557a347b3bd5dcba28b5454e7.pdf")
    if not sample_pdf.exists():
        pytest.skip("Sample PDF not found in uploads directory")

    candidates, notes = process_invoice_file(sample_pdf, "application/pdf")

    # Metadata grid block
    assert candidates.invoice_number == "INV-2026-001"
    assert candidates.invoice_type == "Tax Invoice"
    assert candidates.invoice_date == date(2026, 10, 28)
    assert candidates.due_date == date(2026, 11, 11)
    assert candidates.payment_terms == "Net 14 days"
    assert candidates.po_number == "PO-TEST-104"
    assert candidates.payment_status == "Unpaid"

    # Supplier / Vendor details
    assert "TechNova Solutions" in candidates.vendor_name
    assert "Pune" in (candidates.vendor_address or "")
    assert candidates.vendor_gstin == "27AAAAA0000A1Z5"
    assert candidates.vendor_state == "Maharashtra"
    assert candidates.vendor_state_code == "27"

    # Customer / Buyer details
    assert "ABC Enterprises" in (candidates.customer_name or "")
    assert "Nashik" in (candidates.customer_billing_address or "")
    assert candidates.customer_gstin == "27BBBBB1111B1Z6"
    assert candidates.customer_state == "Maharashtra"
    assert candidates.customer_state_code == "27"

    # Line items
    assert len(candidates.line_items) == 3
    assert any("Laptop accessories" in item.description for item in candidates.line_items)
    assert any("Software configuration services" in item.description for item in candidates.line_items)
    assert any("Office supplies" in item.description for item in candidates.line_items)

    # Financial breakdown & taxes
    assert candidates.subtotal == Decimal("20000.00")
    assert candidates.cgst == Decimal("1800.00")
    assert candidates.sgst == Decimal("1800.00")
    assert candidates.tax_amount == Decimal("3600.00")
    assert candidates.total_amount == Decimal("23600.00")
    assert candidates.currency == "INR"

    # Raw text preserved
    assert candidates.raw_text is not None and len(candidates.raw_text) > 50


def test_demo_sample_showcase_pdf_extraction():
    """Verifies extraction on the demo showcase PDF."""
    sample_pdf = Path(r"C:\Users\aditi\Downloads\InvoiceIQ_New\demo_samples\sample_invoice.pdf")
    if not sample_pdf.exists():
        pytest.skip("Showcase demo PDF not found")

    candidates, notes = process_invoice_file(sample_pdf, "application/pdf")
    assert candidates.invoice_number == "INV-2026-BD88"
    assert "BrightDesk Enterprise" in candidates.vendor_name
    assert candidates.subtotal == Decimal("850.00")
    assert candidates.tax_amount == Decimal("85.00")
    assert candidates.total_amount == Decimal("935.00")
    assert candidates.currency == "USD"
    assert len(candidates.line_items) >= 2


def test_invoice_with_discounts_and_extra_charges():
    """Verifies extraction of discounts, taxable amounts, and other charges."""
    invoice_text = """
    Vendor: Apex Industrial Hardware
    Invoice Number: AIH-4001
    Invoice Date: 2026-10-15
    Due Date: 2026-11-15
    
    Subtotal: $1,000.00
    Discount: $100.00
    Taxable Amount: $900.00
    Tax Amount: $90.00
    Shipping Charges: $25.00
    Grand Total: $1,015.00
    """
    candidates, notes = extract_candidate_fields(invoice_text)
    assert candidates.invoice_number == "AIH-4001"
    assert candidates.subtotal == Decimal("1000.00")
    assert candidates.discounts == Decimal("100.00")
    assert candidates.taxable_amount == Decimal("900.00")
    assert candidates.tax_amount == Decimal("90.00")
    assert candidates.other_charges == Decimal("25.00")
    assert candidates.total_amount == Decimal("1015.00")


def test_line_items_tabular_parsing():
    """Verifies structured tabular extraction into LineItemCandidate objects."""
    invoice_text = """
    Vendor: ToolCraft Ltd
    Invoice Number: TC-101
    Date: 2026-10-01
    
    Item   Description                 HSN/SAC   Qty   Unit Price   Total
    1      Industrial Drills Model X   84672100   2     150.00      300.00
    2      Safety Goggles Pack         90049090   5     20.00       100.00
    
    Subtotal: $400.00
    Total: $400.00
    """
    candidates, _ = extract_candidate_fields(invoice_text)
    assert len(candidates.line_items) == 2
    assert candidates.line_items[0].description == "Industrial Drills Model X"
    assert candidates.line_items[0].hsn_sac == "84672100"
    assert candidates.line_items[0].quantity == Decimal("2")
    assert candidates.line_items[0].unit_price == Decimal("150.00")
    assert candidates.line_items[0].line_total == Decimal("300.00")

    assert candidates.line_items[1].description == "Safety Goggles Pack"
    assert candidates.line_items[1].quantity == Decimal("5")
    assert candidates.line_items[1].unit_price == Decimal("20.00")
    assert candidates.line_items[1].line_total == Decimal("100.00")


def test_image_file_ocr_handling(tmp_path):
    """
    Verifies that uploading an image file triggers OCR execution or
    gracefully informs the user if the local tesseract executable is unavailable.
    """
    # Create a minimal 1x1 test PNG image
    test_img = tmp_path / "test_scan.png"
    # Minimal 1x1 valid PNG bytes
    png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    test_img.write_bytes(png_bytes)

    candidates, notes = process_invoice_file(test_img, "image/png")
    # Must never crash and must return clean candidate object and informative notes
    assert isinstance(candidates, InvoiceCandidateFields)
    assert len(notes) > 0
    # Must mention OCR in notes
    assert any("OCR" in n or "Optical Character Recognition" in n for n in notes)


def test_sample_invoice_1_pdf_comprehensive_extraction():
    """
    Verifies that sample-invoice (1).pdf extracts all required fields:
    - Invoice number: INV-2026-0042
    - Invoice date: 15 January 2026
    - Supplier: Northwind Fixtures Ltd
    - Customer: Example Customer
    - Standard widgets: 54.00 USD
    - Large widgets: 29.25 USD
    - Mounting brackets: 13.20 USD
    - Delivery: 15.00 USD
    - Invoice total: 111.45 USD
    """
    sample_pdf = Path("demo_samples/sample-invoice (1).pdf")
    if not sample_pdf.exists():
        sample_pdf = Path(r"C:\Users\aditi\Downloads\InvoiceIQ_New\demo_samples\sample-invoice (1).pdf")
    if not sample_pdf.exists():
        pytest.skip("sample-invoice (1).pdf not found in demo_samples")

    candidates, notes = process_invoice_file(sample_pdf, "application/pdf")
    assert candidates.invoice_number == "INV-2026-0042"
    assert candidates.invoice_date == date(2026, 1, 15)
    assert candidates.due_date == date(2026, 2, 14)
    assert candidates.vendor_name == "Northwind Fixtures Ltd"
    assert candidates.customer_name == "Example Customer"
    assert candidates.customer_billing_address == "1 Sample Street, Testville"
    assert candidates.currency == "USD"
    assert candidates.total_amount == Decimal("111.45")
    assert candidates.field_confidence.get("total_amount") == "HIGH"

    # Line items verification
    assert len(candidates.line_items) == 4
    items_by_desc = {it.description: it for it in candidates.line_items}

    assert "Widget, standard" in items_by_desc
    assert items_by_desc["Widget, standard"].quantity == Decimal("12")
    assert items_by_desc["Widget, standard"].unit_price == Decimal("4.50")
    assert items_by_desc["Widget, standard"].line_total == Decimal("54.00")

    assert "Widget, large" in items_by_desc
    assert items_by_desc["Widget, large"].quantity == Decimal("3")
    assert items_by_desc["Widget, large"].unit_price == Decimal("9.75")
    assert items_by_desc["Widget, large"].line_total == Decimal("29.25")

    assert "Mounting bracket" in items_by_desc
    assert items_by_desc["Mounting bracket"].quantity == Decimal("6")
    assert items_by_desc["Mounting bracket"].unit_price == Decimal("2.20")
    assert items_by_desc["Mounting bracket"].line_total == Decimal("13.20")

    assert "Delivery" in items_by_desc
    assert items_by_desc["Delivery"].quantity == Decimal("1")
    assert items_by_desc["Delivery"].unit_price == Decimal("15.00")
    assert items_by_desc["Delivery"].line_total == Decimal("15.00")


def test_printed_total_variations_and_currency_codes():
    """
    Verifies that diverse printed total labels and currency representations
    (currency code in parentheses, symbols, prefix, suffix) are reliably extracted.
    """
    cases = [
        ("Total (USD)                                             111.45", Decimal("111.45")),
        ("Total: $111.45", Decimal("111.45")),
        ("Grand Total: USD 111.45", Decimal("111.45")),
        ("Invoice Total: 111.45 USD", Decimal("111.45")),
        ("Total Amount Due: € 1,234.56", Decimal("1234.56")),
        ("Amount Due: ₹ 5,432.10", Decimal("5432.10")),
        ("Balance Due: £ 89.00", Decimal("89.00")),
        ("Final Total: 99.99", Decimal("99.99")),
        ("Net Amount: CAD 450.75", Decimal("450.75")),
        ("Total Payable: 3,450.00", Decimal("3450.00")),
    ]

    for line, expected_amt in cases:
        raw_text = f"INVOICE\nSupplier: Global Vendor\nInvoice Number: INV-999\nInvoice Date: 2026-03-01\n{line}\n"
        cand, notes = extract_candidate_fields(raw_text)
        assert cand.total_amount == expected_amt, f"Failed for '{line}': expected {expected_amt}, got {cand.total_amount}"
        assert cand.field_confidence.get("total_amount") == "HIGH"


def test_multiline_total_layout_extraction():
    """
    Verifies that invoices where the total label and amount appear on separate
    lines (e.g. OCR outputs or tabular summary blocks) are correctly captured.
    """
    cases = [
        ("Total\n$111.45", Decimal("111.45")),
        ("Grand Total (USD)\n111.45", Decimal("111.45")),
        ("Total Amount:\n   1,500.00 USD", Decimal("1500.00")),
        ("TOTAL DUE\nUSD 250.00", Decimal("250.00")),
        ("Balance Due:\n£ 75.50", Decimal("75.50")),
    ]

    for snippet, expected_amt in cases:
        raw_text = f"INVOICE\nSupplier: MultiLine Vendor\nInvoice Number: INV-ML-1\nInvoice Date: 2026-03-01\n{snippet}\n"
        cand, notes = extract_candidate_fields(raw_text)
        assert cand.total_amount == expected_amt, f"Failed for multiline snippet:\n{snippet}\nGot: {cand.total_amount}"


def test_distinguish_total_from_subtotal_tax_and_discounts():
    """
    Verifies that grand total is correctly isolated from subtotal, taxes,
    discounts, and intermediate amounts, and arithmetic consistency is checked.
    """
    raw_text = """
    TAX INVOICE
    Supplier: Tech Logistics Inc.
    Invoice Number: TL-4091
    Invoice Date: 2026-04-10
    Due Date: 2026-05-10
    Subtotal: $ 500.00
    Discount: $ 25.00
    Tax Amount: $ 50.00
    Shipping Charges: $ 15.00
    Grand Total: $ 540.00
    Amount Paid: $ 100.00
    """
    cand, notes = extract_candidate_fields(raw_text)
    assert cand.subtotal == Decimal("500.00")
    assert cand.discounts == Decimal("25.00")
    assert cand.tax_amount == Decimal("50.00")
    assert cand.other_charges == Decimal("15.00")
    assert cand.total_amount == Decimal("540.00")
    assert cand.field_confidence.get("total_amount") == "HIGH"
    # Verification: 500 - 25 + 50 + 15 = 540
    assert any("Financial reconciliation verified" in n for n in notes)


def test_fallback_calculation_when_printed_total_is_absent():
    """
    When no explicit printed total is detected, but valid line items and taxes exist,
    the system calculates the fallback total from available data, records it
    transparently, sets confidence to CALCULATED, and notes the fallback.
    """
    raw_text = """
    INVOICE
    Supplier: Itemized Parts Co.
    Invoice Number: IP-7788
    Invoice Date: 2026-02-01
    Description Qty Unit Price Amount
    Steel bolts 10 5.00 50.00
    Copper wire 2 25.00 50.00
    Tax Amount: 10.00
    """
    cand, notes = extract_candidate_fields(raw_text)
    # Line items sum = 100.00, Tax = 10.00 -> Calculated Total = 110.00
    assert cand.total_amount == Decimal("110.00")
    assert cand.calculated_total == Decimal("110.00")
    assert cand.field_confidence.get("total_amount") == "CALCULATED"
    assert any("Calculated fallback" in n for n in notes)


def test_missing_total_and_no_line_items_produces_warning():
    """
    When total cannot be detected and cannot be calculated from line items,
    total_amount remains None and a clear validation warning is provided.
    """
    raw_text = """
    INVOICE
    Supplier: Minimal Service Corp.
    Invoice Number: MIN-100
    Invoice Date: 2026-02-01
    Consulting services rendered for project Alpha.
    """
    cand, notes = extract_candidate_fields(raw_text)
    assert cand.total_amount is None
    assert cand.calculated_total is None
    assert any("Total amount could not be reliably detected" in n for n in notes)



