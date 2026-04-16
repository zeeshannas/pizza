from extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    size = db.Column(db.String(10), nullable=False)  # S, M, L
    price = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    ingredients_map = db.relationship(
        "ProductIngredient", back_populates="product", cascade="all, delete-orphan"
    )
    order_items = db.relationship("OrderItem", back_populates="product")

    __table_args__ = (db.UniqueConstraint("name", "size", name="uq_product_name_size"),)

    def display_label(self) -> str:
        return f"{self.name} ({self.size})"
