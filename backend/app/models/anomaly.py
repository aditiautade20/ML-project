from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class InvoiceAnomaly(Base):
    """
    Persistently stores machine learning anomaly detection assessments for invoices.
    
    This is an automated statistical screening signal (Isolation Forest), NOT proof
    of fraud, accounting error, or financial irregularity.
    """
    __tablename__ = "invoice_anomalies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_id = Column(
        Integer,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ML Assessment Results
    is_anomaly = Column(Boolean, nullable=False, default=False, index=True)
    anomaly_score = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False, default="NO_UNUSUAL_PATTERN", index=True)
    risk_level = Column(String(50), nullable=False, default="LOW", index=True)
    explanation = Column(Text, nullable=False)
    factors_json = Column(Text, nullable=True)  # JSON-encoded factor details
    model_version = Column(String(50), nullable=False, default="IsolationForest-v1.0")

    # User Review Tracking (Audit review confirmation without altering invoice balances)
    is_reviewed = Column(Boolean, nullable=False, default=False, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)

    # Timestamps
    assessed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
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
    invoice = relationship("Invoice", back_populates="anomaly")
    user = relationship("User", back_populates="anomalies")

    def __repr__(self) -> str:
        return (
            f"<InvoiceAnomaly(id={self.id}, invoice_id={self.invoice_id}, "
            f"status='{self.status}', is_anomaly={self.is_anomaly})>"
        )
