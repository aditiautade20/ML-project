from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base


class ReconciliationBatch(Base):
    __tablename__ = "reconciliation_batches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_type = Column(String(50), nullable=False)  # "LEDGER", "BANK", "COMBINED"
    title = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="COMPLETED")  # "COMPLETED", "APPLIED"

    # Source File Metadata & SHA256 Hashes for Duplicate Detection
    ledger_filename = Column(String(255), nullable=True)
    ledger_hash = Column(String(64), nullable=True, index=True)
    bank_filename = Column(String(255), nullable=True)
    bank_hash = Column(String(64), nullable=True, index=True)

    # Statistical Aggregates
    total_records = Column(Integer, nullable=False, default=0)
    exact_matches = Column(Integer, nullable=False, default=0)
    mismatches = Column(Integer, nullable=False, default=0)
    unmatched_records = Column(Integer, nullable=False, default=0)

    # Configurable tolerance used for this batch
    amount_tolerance = Column(Numeric(10, 2), nullable=False, default=Decimal("0.05"))

    # Serialized summary breakdown
    summary_json = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="reconciliation_batches")
    items = relationship(
        "ReconciliationItem",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="asc(ReconciliationItem.id)",
    )


class ReconciliationItem(Base):
    __tablename__ = "reconciliation_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_id = Column(
        Integer,
        ForeignKey("reconciliation_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        Integer,
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_id = Column(
        Integer,
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Classification
    item_type = Column(String(50), nullable=False)  # "LEDGER", "BANK", "COMBINED"
    match_status = Column(String(50), nullable=False, index=True)

    # Display Identifiers
    record_identifier = Column(String(100), nullable=False)
    vendor_or_counterparty = Column(String(255), nullable=True)
    transaction_date = Column(String(50), nullable=True)

    # Expected vs Actual Values
    expected_value = Column(String(100), nullable=True)
    actual_value = Column(String(100), nullable=True)
    discrepancy_amount = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(10), nullable=False, default="USD")

    # Diagnostic & Audit Evidence
    evidence_text = Column(Text, nullable=True)
    action_recommendation = Column(Text, nullable=True)

    # Review Status & User Confirmation
    review_status = Column(String(50), nullable=False, default="PENDING")  # "PENDING", "CONFIRMED", "DISMISSED"

    # Original Parsed Row for Non-Destructive Auditability
    raw_record_json = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    batch = relationship("ReconciliationBatch", back_populates="items")
    invoice = relationship("Invoice")
    payment = relationship("Payment")
