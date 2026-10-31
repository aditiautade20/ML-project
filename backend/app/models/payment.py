from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Date, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_id = Column(
        Integer,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    amount = Column(Numeric(12, 2), nullable=False)
    payment_date = Column(Date, nullable=False, index=True)
    payment_method = Column(String(50), nullable=False, default="Bank Transfer")
    reference = Column(String(100), nullable=True, index=True)
    notes = Column(Text, nullable=True)

    # Verification & Audit Tracking (Stage 8)
    # Verification statuses: 'UNVERIFIED', 'VERIFIED', 'FLAGGED'
    verification_status = Column(String(50), nullable=False, default="UNVERIFIED", index=True)
    # Evidence sources: 'MANUAL_ENTRY', 'BANK_STATEMENT', 'GENERAL_LEDGER', 'RECEIPT', 'RECONCILIATION'
    evidence_source = Column(String(100), nullable=False, default="MANUAL_ENTRY")
    # Matched bank or ledger reference ID
    matched_reference = Column(String(100), nullable=True)
    # Reason for any discrepancy or mismatch
    mismatch_reason = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    invoice = relationship("Invoice", back_populates="payments")
    user = relationship("User", back_populates="payments")
    audit_logs = relationship(
        "PaymentAuditLog",
        back_populates="payment",
        cascade="all, delete-orphan",
        order_by="desc(PaymentAuditLog.timestamp)",
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, invoice_id={self.invoice_id}, amount={self.amount}, status={self.verification_status})>"


class PaymentAuditLog(Base):
    """
    Immutable audit log preserving history whenever a payment is
    recorded, modified, verified, or deleted.
    """
    __tablename__ = "payment_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    payment_id = Column(
        Integer,
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invoice_id = Column(
        Integer,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Action type: 'CREATED', 'UPDATED', 'DELETED', 'VERIFIED', 'UNVERIFIED'
    action = Column(String(50), nullable=False, index=True)
    previous_amount = Column(Numeric(12, 2), nullable=True)
    new_amount = Column(Numeric(12, 2), nullable=True)
    previous_payment_date = Column(Date, nullable=True)
    new_payment_date = Column(Date, nullable=True)
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    verification_status = Column(String(50), nullable=True)
    evidence_source = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    payment = relationship("Payment", back_populates="audit_logs")
    invoice = relationship("Invoice", back_populates="audit_logs")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<PaymentAuditLog(id={self.id}, action='{self.action}', invoice_id={self.invoice_id})>"
