from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Date, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Core Invoice Details
    invoice_number = Column(String(100), nullable=False, index=True)
    vendor_name = Column(String(255), nullable=False, index=True)
    customer_name = Column(String(255), nullable=True)
    invoice_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=True, index=True)

    # Financial breakdown (Decimal-safe 12 digits, 2 decimal places)
    subtotal = Column(Numeric(12, 2), nullable=True)
    tax_amount = Column(Numeric(12, 2), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")

    # Workflow & File References
    status = Column(String(50), nullable=False, default="CONFIRMED")
    file_path = Column(String(255), nullable=True)
    file_name = Column(String(255), nullable=True)
    file_content_type = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    # Timestamps
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
    user = relationship("User", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan", order_by="desc(Payment.payment_date)")
    anomaly = relationship("InvoiceAnomaly", back_populates="invoice", uselist=False, cascade="all, delete-orphan")
    audit_logs = relationship("PaymentAuditLog", back_populates="invoice", cascade="all, delete-orphan", order_by="desc(PaymentAuditLog.timestamp)")

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, number='{self.invoice_number}', vendor='{self.vendor_name}', total={self.total_amount})>"
