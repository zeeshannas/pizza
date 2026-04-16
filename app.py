from flask import Flask, redirect, request, url_for
from flask_login import current_user

from config import Config
from extensions import db, login_manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.inventory import inventory_bp
    from routes.products import products_bp
    from routes.customers import customers_bp
    from routes.pos import pos_bp
    from routes.purchases import purchases_bp
    from routes.reports import reports_bp
    from routes.admin_users import admin_users_bp
    from routes.orders import orders_bp
    from utils.currency import format_money

    @app.template_filter("money")
    def _money_filter(value):
        return format_money(value)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(purchases_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(orders_bp)

    @app.before_request
    def _login_required_global():
        if request.endpoint and (
            request.endpoint.startswith("auth.")
            or request.endpoint == "static"
        ):
            return None
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.url))

    with app.app_context():
        import models  # noqa: F401 — register models with SQLAlchemy metadata
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
