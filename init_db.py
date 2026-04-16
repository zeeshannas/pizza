"""
Create tables and a default admin user. Run once after MySQL database exists:

  mysql -u root -e "CREATE DATABASE IF NOT EXISTS olive_pizza CHARACTER SET utf8mb4;"
  python init_db.py
"""

from app import app
from extensions import db
from models.ingredient import Ingredient
from models.user import User


def main():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email="admin@olivepizza.local").first():
            admin = User(name="Administrator", email="admin@olivepizza.local", role="admin")
            admin.set_password("ChangeMe123!")
            db.session.add(admin)
            db.session.commit()
            print("Created admin: admin@olivepizza.local / ChangeMe123!")
        else:
            print("Admin user already exists — skipped.")

        if Ingredient.query.count() == 0:
            for name, stock in [("Cheese", 500), ("Dough", 300), ("Sauce", 400)]:
                db.session.add(
                    Ingredient(
                        name=name,
                        stock_qty=float(stock),
                        low_stock_threshold=50.0,
                        unit_cost=0.0,
                    )
                )
            db.session.commit()
            print("Seeded base ingredients: Cheese, Dough, Sauce.")
        print("Done.")


if __name__ == "__main__":
    main()
