from datetime import datetime
from extensions import db


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey("ingredients.id"), nullable=False)
    qty = db.Column(db.Float, nullable=False)
    cost = db.Column(db.Float, nullable=False)
    supplier_name = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    ingredient = db.relationship("Ingredient", back_populates="purchases")
