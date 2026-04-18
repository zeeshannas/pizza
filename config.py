import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://root:@localhost/olive_pizza",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LOW_STOCK_DEFAULT = 10.0
    # PKR = Pakistan (default). USD = international — set env CURRENCY=USD or CURRENCY=PKR
    CURRENCY = os.environ.get("CURRENCY", "PKR").upper()
    # Full public origin for payment return URLs (e.g. https://pos.yourdomain.com)
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
