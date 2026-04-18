"""Lightweight additive migrations for installs that already have tables."""

from sqlalchemy import inspect, text

from extensions import db


def ensure_order_extensions() -> None:
    """Add Order columns introduced after first release (MySQL / SQLite)."""
    insp = inspect(db.engine)
    if "orders" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("orders")}
    dialect = db.engine.dialect.name

    def run(sql_mysql: str, sql_sqlite: str | None = None) -> None:
        sql = sql_sqlite if dialect == "sqlite" and sql_sqlite else sql_mysql
        with db.engine.begin() as conn:
            conn.execute(text(sql))

    if "notes" not in existing:
        run(
            "ALTER TABLE orders ADD COLUMN notes VARCHAR(500) NULL",
            "ALTER TABLE orders ADD COLUMN notes VARCHAR(500)",
        )
        existing.add("notes")

    if "payment_method" not in existing:
        run(
            "ALTER TABLE orders ADD COLUMN payment_method VARCHAR(32) NOT NULL DEFAULT 'cash'",
            "ALTER TABLE orders ADD COLUMN payment_method VARCHAR(32) NOT NULL DEFAULT 'cash'",
        )
        existing.add("payment_method")

    if "payment_status" not in existing:
        run(
            "ALTER TABLE orders ADD COLUMN payment_status VARCHAR(24) NOT NULL DEFAULT 'paid'",
            "ALTER TABLE orders ADD COLUMN payment_status VARCHAR(24) NOT NULL DEFAULT 'paid'",
        )
        existing.add("payment_status")

    if "payment_reference" not in existing:
        run(
            "ALTER TABLE orders ADD COLUMN payment_reference VARCHAR(128) NULL",
            "ALTER TABLE orders ADD COLUMN payment_reference VARCHAR(128)",
        )
        existing.add("payment_reference")

    if "inventory_applied" not in existing:
        if dialect == "sqlite":
            run(
                "ALTER TABLE orders ADD COLUMN inventory_applied INTEGER NOT NULL DEFAULT 1",
                "ALTER TABLE orders ADD COLUMN inventory_applied INTEGER NOT NULL DEFAULT 1",
            )
        else:
            run(
                "ALTER TABLE orders ADD COLUMN inventory_applied TINYINT(1) NOT NULL DEFAULT 1",
                None,
            )


def _run_alter(
    run,
    existing: set,
    col: str,
    sql_mysql: str,
    sql_sqlite: str | None = None,
) -> None:
    if col in existing:
        return
    run(sql_mysql, sql_sqlite)
    existing.add(col)


def ensure_customer_extensions() -> None:
    insp = inspect(db.engine)
    if "customers" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("customers")}
    dialect = db.engine.dialect.name

    def run(sql_mysql: str, sql_sqlite: str | None = None) -> None:
        sql = sql_sqlite if dialect == "sqlite" and sql_sqlite else sql_mysql
        with db.engine.begin() as conn:
            conn.execute(text(sql))

    _run_alter(
        run,
        existing,
        "address",
        "ALTER TABLE customers ADD COLUMN address TEXT NULL",
        "ALTER TABLE customers ADD COLUMN address TEXT",
    )


def ensure_order_fulfillment_columns() -> None:
    insp = inspect(db.engine)
    if "orders" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("orders")}
    dialect = db.engine.dialect.name

    def run(sql_mysql: str, sql_sqlite: str | None = None) -> None:
        sql = sql_sqlite if dialect == "sqlite" and sql_sqlite else sql_mysql
        with db.engine.begin() as conn:
            conn.execute(text(sql))

    _run_alter(
        run,
        existing,
        "fulfillment_type",
        "ALTER TABLE orders ADD COLUMN fulfillment_type VARCHAR(24) NOT NULL DEFAULT 'takeaway'",
        "ALTER TABLE orders ADD COLUMN fulfillment_type VARCHAR(24) NOT NULL DEFAULT 'takeaway'",
    )
    _run_alter(
        run,
        existing,
        "delivery_address",
        "ALTER TABLE orders ADD COLUMN delivery_address TEXT NULL",
        "ALTER TABLE orders ADD COLUMN delivery_address TEXT",
    )


def ensure_purchase_payment_columns() -> None:
    insp = inspect(db.engine)
    if "purchases" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("purchases")}
    dialect = db.engine.dialect.name

    def run(sql_mysql: str, sql_sqlite: str | None = None) -> None:
        sql = sql_sqlite if dialect == "sqlite" and sql_sqlite else sql_mysql
        with db.engine.begin() as conn:
            conn.execute(text(sql))

    _run_alter(
        run,
        existing,
        "payment_method",
        "ALTER TABLE purchases ADD COLUMN payment_method VARCHAR(32) NOT NULL DEFAULT 'cash'",
        "ALTER TABLE purchases ADD COLUMN payment_method VARCHAR(32) NOT NULL DEFAULT 'cash'",
    )
    _run_alter(
        run,
        existing,
        "payment_reference",
        "ALTER TABLE purchases ADD COLUMN payment_reference VARCHAR(128) NULL",
        "ALTER TABLE purchases ADD COLUMN payment_reference VARCHAR(128)",
    )


def ensure_all_schema() -> None:
    ensure_order_extensions()
    ensure_customer_extensions()
    ensure_order_fulfillment_columns()
    ensure_purchase_payment_columns()
