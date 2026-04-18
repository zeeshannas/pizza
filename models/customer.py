from extensions import db


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(32), nullable=False, index=True)
    address = db.Column(db.Text, nullable=True)

    orders = db.relationship("Order", back_populates="customer")
