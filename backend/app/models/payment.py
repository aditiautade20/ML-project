from datetime import datetime, timezone
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

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, invoice_id={self.invoice_id}, amount={self.amount}, date={self.payment_date})>"
