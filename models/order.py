from datetime import datetime
from extensions import db


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    total = db.Column(db.Float, nullable=False, default=0.0)
    # completed | pending_payment | cancelled
    status = db.Column(db.String(32), nullable=False, default="completed")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.String(500), nullable=True)
    # cash | card | jazzcash | easypaisa | meezan — wallet flows may leave stock uncommitted until paid
    payment_method = db.Column(db.String(32), nullable=False, default="cash")
    # pending | paid | failed
    payment_status = db.Column(db.String(24), nullable=False, default="paid")
    payment_reference = db.Column(db.String(128), nullable=True)
    inventory_applied = db.Column(db.Boolean, nullable=False, default=True)
    fulfillment_type = db.Column(db.String(24), nullable=False, default="takeaway")
    delivery_address = db.Column(db.Text, nullable=True)

    customer = db.relationship("Customer", back_populates="orders")
    items = db.relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
