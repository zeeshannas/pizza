from extensions import db


class ProductIngredient(db.Model):
    __tablename__ = "product_ingredients"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey("ingredients.id"), nullable=False)
    quantity_required = db.Column(db.Float, nullable=False)

    product = db.relationship("Product", back_populates="ingredients_map")
    ingredient = db.relationship("Ingredient", back_populates="product_links")

    __table_args__ = (
        db.UniqueConstraint("product_id", "ingredient_id", name="uq_product_ingredient"),
    )
