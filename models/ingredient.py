from extensions import db


class Ingredient(db.Model):
    __tablename__ = "ingredients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    stock_qty = db.Column(db.Float, nullable=False, default=0.0)
    unit_cost = db.Column(db.Float, nullable=False, default=0.0)
    low_stock_threshold = db.Column(db.Float, nullable=False, default=10.0)

    product_links = db.relationship(
        "ProductIngredient", back_populates="ingredient", cascade="all, delete-orphan"
    )
    purchases = db.relationship("Purchase", back_populates="ingredient")

    @property
    def is_low_stock(self) -> bool:
        return self.stock_qty <= self.low_stock_threshold
