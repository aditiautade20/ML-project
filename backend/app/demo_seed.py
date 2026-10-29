import argparse
from datetime import date, timedelta
from decimal import Decimal
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.anomaly import InvoiceAnomaly
from app.services.auth_service import hash_password
from app.services.payment_service import calculate_invoice_financials
from app.services.anomaly_service import assess_user_invoices

logger = logging.getLogger("invoiceiq.demo")

DEMO_USER_EMAIL = "demo@invoiceiq.local"
DEMO_USER_NAME = "Demo Showcase User"
DEMO_USER_PASSWORD = "DemoUser123!"


def get_or_create_demo_user(db: Session) -> User:
    """
    Retrieves the dedicated demo account or creates it if it does not exist.
    Guarantees isolation: real users have distinct emails and accounts.
    """
    user = db.query(User).filter(User.email == DEMO_USER_EMAIL).first()
    if not user:
        user = User(
            name=DEMO_USER_NAME,
            email=DEMO_USER_EMAIL,
            hashed_password=hash_password(DEMO_USER_PASSWORD),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created demo user: {DEMO_USER_EMAIL}")
    return user


def clean_demo_data(db: Session) -> int:
    """
    Safely removes ONLY the dedicated demo user and their associated invoices,
    payments, and anomaly records via foreign key cascade.
    Never modifies or touches real user accounts.
    """
    demo_user = db.query(User).filter(User.email == DEMO_USER_EMAIL).first()
    if not demo_user:
        logger.info("No demo user found. Database is already clean of demo records.")
        return 0

    count_invoices = db.query(Invoice).filter(Invoice.user_id == demo_user.id).count()
    db.delete(demo_user)
    db.commit()
    logger.info(f"Removed demo user and {count_invoices} associated demo invoices cleanly.")
    return count_invoices


def seed_demo_data(db: Session, run_ml_assessment: bool = True) -> User:
    """
    Creates a curated, realistic set of demo invoices and payments for the
    dedicated demo account (demo@invoiceiq.local).
    
    Idempotent: Re-running cleans and re-creates only the demo account's records,
    ensuring a pristine, predictable state without duplicates.
    """
    # 1. Clean existing demo data to ensure a fresh, repeatable state
    clean_demo_data(db)

    # 2. Create demo user
    demo_user = get_or_create_demo_user(db)
    today = date.today()

    # 3. Define curated demo invoices representing all business states
    demo_invoices_def = [
        # 1. Unpaid, due in 12 days
        {
            "invoice_number": "INV-DEMO-001",
            "vendor_name": "Apex Cloud Infrastructure",
            "invoice_date": today - timedelta(days=5),
            "due_date": today + timedelta(days=12),
            "subtotal": Decimal("400.00"),
            "tax_amount": Decimal("50.00"),
            "total_amount": Decimal("450.00"),
            "notes": "[Sample Data] Monthly cloud hosting subscription.",
            "payments": [],
        },
        # 2. Partially paid, due in 4 days (within 7 days)
        {
            "invoice_number": "INV-DEMO-002",
            "vendor_name": "Acme Office Supplies",
            "invoice_date": today - timedelta(days=10),
            "due_date": today + timedelta(days=4),
            "subtotal": Decimal("560.00"),
            "tax_amount": Decimal("60.00"),
            "total_amount": Decimal("620.00"),
            "notes": "[Sample Data] Ergonomic workstations and office equipment.",
            "payments": [
                {
                    "amount": Decimal("250.00"),
                    "payment_date": today - timedelta(days=2),
                    "payment_method": "Credit Card",
                    "reference": "TXN-CC-8491",
                    "notes": "[Sample Data] Initial deposit.",
                }
            ],
        },
        # 3. Fully paid (was due 10 days ago, but fully settled so NOT overdue)
        {
            "invoice_number": "INV-DEMO-003",
            "vendor_name": "FastTrack Courier & Logistics",
            "invoice_date": today - timedelta(days=35),
            "due_date": today - timedelta(days=10),
            "subtotal": Decimal("750.00"),
            "tax_amount": Decimal("100.00"),
            "total_amount": Decimal("850.00"),
            "notes": "[Sample Data] Regional freight shipping services.",
            "payments": [
                {
                    "amount": Decimal("400.00"),
                    "payment_date": today - timedelta(days=20),
                    "payment_method": "Bank Transfer",
                    "reference": "WIRE-00391",
                    "notes": "[Sample Data] Milestone 1 payment.",
                },
                {
                    "amount": Decimal("450.00"),
                    "payment_date": today - timedelta(days=12),
                    "payment_method": "Bank Transfer",
                    "reference": "WIRE-00412",
                    "notes": "[Sample Data] Final settlement in full.",
                },
            ],
        },
        # 4. Overdue (due 14 days ago, unpaid)
        {
            "invoice_number": "INV-DEMO-004",
            "vendor_name": "Global Telecom Services",
            "invoice_date": today - timedelta(days=45),
            "due_date": today - timedelta(days=14),
            "subtotal": Decimal("290.00"),
            "tax_amount": Decimal("30.00"),
            "total_amount": Decimal("320.00"),
            "notes": "[Sample Data] Fiber optic communications line.",
            "payments": [],
        },
        # 5. No Due Date (must not be marked overdue)
        {
            "invoice_number": "INV-DEMO-005",
            "vendor_name": "Precision Hardware Tools",
            "invoice_date": today - timedelta(days=8),
            "due_date": None,  # No due date
            "subtotal": Decimal("160.00"),
            "tax_amount": Decimal("15.00"),
            "total_amount": Decimal("175.00"),
            "notes": "[Sample Data] Replacement hand tools and workshop supplies.",
            "payments": [],
        },
        # 6. Apex Cloud Services baseline 1 (historical)
        {
            "invoice_number": "INV-DEMO-006",
            "vendor_name": "Apex Cloud Infrastructure",
            "invoice_date": today - timedelta(days=65),
            "due_date": today - timedelta(days=35),
            "subtotal": Decimal("380.00"),
            "tax_amount": Decimal("40.00"),
            "total_amount": Decimal("420.00"),
            "notes": "[Sample Data] Standard compute cluster baseline.",
            "payments": [
                {
                    "amount": Decimal("420.00"),
                    "payment_date": today - timedelta(days=36),
                    "payment_method": "Bank Transfer",
                    "reference": "WIRE-00109",
                    "notes": "[Sample Data] Paid on time.",
                }
            ],
        },
        # 7. Apex Cloud Services baseline 2 (historical)
        {
            "invoice_number": "INV-DEMO-007",
            "vendor_name": "Apex Cloud Infrastructure",
            "invoice_date": today - timedelta(days=95),
            "due_date": today - timedelta(days=65),
            "subtotal": Decimal("410.00"),
            "tax_amount": Decimal("50.00"),
            "total_amount": Decimal("460.00"),
            "notes": "[Sample Data] Standard compute cluster baseline.",
            "payments": [
                {
                    "amount": Decimal("460.00"),
                    "payment_date": today - timedelta(days=66),
                    "payment_method": "Bank Transfer",
                    "reference": "WIRE-00084",
                    "notes": "[Sample Data] Paid on time.",
                }
            ],
        },
        # 8. ML Anomaly Example: Extreme statistical outlier for Apex ($12,850 vs ~$440 typical)
        {
            "invoice_number": "INV-DEMO-008",
            "vendor_name": "Apex Cloud Infrastructure",
            "invoice_date": today - timedelta(days=3),
            "due_date": today + timedelta(days=25),
            "subtotal": Decimal("11850.00"),
            "tax_amount": Decimal("1000.00"),
            "total_amount": Decimal("12850.00"),
            "notes": "[Sample Data] Large scale GPU training cluster reservation (Screening outlier example).",
            "payments": [],
        },
        # 9. Acme Office Supplies baseline 2
        {
            "invoice_number": "INV-DEMO-009",
            "vendor_name": "Acme Office Supplies",
            "invoice_date": today - timedelta(days=40),
            "due_date": today - timedelta(days=10),
            "subtotal": Decimal("530.00"),
            "tax_amount": Decimal("60.00"),
            "total_amount": Decimal("590.00"),
            "notes": "[Sample Data] Quarterly stationery re-order.",
            "payments": [
                {
                    "amount": Decimal("590.00"),
                    "payment_date": today - timedelta(days=11),
                    "payment_method": "Credit Card",
                    "reference": "TXN-CC-7712",
                    "notes": "[Sample Data] Full payment.",
                }
            ],
        },
        # 10. FastTrack Logistics - due tomorrow (within 7 days)
        {
            "invoice_number": "INV-DEMO-010",
            "vendor_name": "FastTrack Courier & Logistics",
            "invoice_date": today - timedelta(days=14),
            "due_date": today + timedelta(days=1),
            "subtotal": Decimal("710.00"),
            "tax_amount": Decimal("70.00"),
            "total_amount": Decimal("780.00"),
            "notes": "[Sample Data] Express overnight delivery service.",
            "payments": [],
        },
    ]

    # Insert invoices and associated payments
    for item in demo_invoices_def:
        payments_def = item.pop("payments", [])
        invoice = Invoice(
            user_id=demo_user.id,
            invoice_number=item["invoice_number"],
            vendor_name=item["vendor_name"],
            invoice_date=item["invoice_date"],
            due_date=item["due_date"],
            subtotal=item["subtotal"],
            tax_amount=item["tax_amount"],
            total_amount=item["total_amount"],
            currency="USD",
            status="CONFIRMED",
            notes=item["notes"],
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        for p in payments_def:
            payment = Payment(
                invoice_id=invoice.id,
                user_id=demo_user.id,
                amount=p["amount"],
                payment_date=p["payment_date"],
                payment_method=p["payment_method"],
                reference=p.get("reference"),
                notes=p.get("notes"),
            )
            db.add(payment)
        db.commit()

    # 4. Optionally run the ML anomaly assessment so demo outlier is pre-flagged
    if run_ml_assessment:
        logger.info("Running Isolation Forest assessment on demo data...")
        assess_user_invoices(demo_user.id, db)

    logger.info(f"Successfully seeded {len(demo_invoices_def)} demo invoices for {DEMO_USER_EMAIL}.")
    return demo_user


def main():
    parser = argparse.ArgumentParser(description="InvoiceIQ Demo Data Management Utility")
    parser.add_argument("--clean", action="store_true", help="Remove all demo data and delete the demo user")
    parser.add_argument("--seed", action="store_true", help="Seed or reset the demo account with fresh sample data")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.clean:
            count = clean_demo_data(db)
            print(f"Cleaned up demo account and {count} demo records.")
        else:
            user = seed_demo_data(db, run_ml_assessment=True)
            print("==================================================")
            print("  InvoiceIQ Demo Account Ready!")
            print("==================================================")
            print(f"  Login Email:    {DEMO_USER_EMAIL}")
            print(f"  Password:       {DEMO_USER_PASSWORD}")
            print("  Invoices:       10 curated sample records")
            print("  States Covered: Unpaid, Partial, Paid, Overdue, No Due Date, ML Outlier")
            print("==================================================")
            print("  To remove demo data later, run: python -m app.demo_seed --clean")
    finally:
        db.close()


if __name__ == "__main__":
    main()
