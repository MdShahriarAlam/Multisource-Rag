"""
Seed script: creates the rag_demo database and populates it with realistic dummy data.

Usage:
    python scripts/seed_postgres.py

Reads credentials from .env in the project root.
"""

import os
import sys
from datetime import datetime, timedelta
import random

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

HOST = os.getenv("POSTGRES_HOST", "localhost")
PORT = int(os.getenv("POSTGRES_PORT", 5432))
USER = os.getenv("POSTGRES_USER", "postgres")
PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
TARGET_DB = "rag_demo"

# ── Helpers ────────────────────────────────────────────────────────────────────

def connect(dbname):
    return psycopg2.connect(host=HOST, port=PORT, user=USER, password=PASSWORD, dbname=dbname)


def create_database():
    """Create rag_demo if it doesn't already exist."""
    conn = connect("postgres")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TARGET_DB,))
    if cur.fetchone():
        print(f"  Database '{TARGET_DB}' already exists — skipping creation.")
    else:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TARGET_DB)))
        print(f"  Created database '{TARGET_DB}'.")
    cur.close()
    conn.close()


# ── Schema ─────────────────────────────────────────────────────────────────────

DDL = """
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders      CASCADE;
DROP TABLE IF EXISTS products    CASCADE;
DROP TABLE IF EXISTS customers   CASCADE;

CREATE TABLE customers (
    customer_id  SERIAL PRIMARY KEY,
    email        VARCHAR(255) UNIQUE NOT NULL,
    full_name    VARCHAR(255) NOT NULL,
    country      VARCHAR(100),
    phone        VARCHAR(50),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active    BOOLEAN DEFAULT TRUE
);

CREATE TABLE products (
    product_id      SERIAL PRIMARY KEY,
    product_name    VARCHAR(255) NOT NULL,
    category        VARCHAR(100),
    price           DECIMAL(10, 2),
    stock_quantity  INTEGER DEFAULT 0,
    supplier        VARCHAR(255)
);

CREATE TABLE orders (
    order_id          SERIAL PRIMARY KEY,
    customer_id       INTEGER REFERENCES customers(customer_id),
    order_date        TIMESTAMP,
    status            VARCHAR(50) DEFAULT 'pending',
    total_amount      DECIMAL(10, 2),
    shipping_country  VARCHAR(100)
);

CREATE TABLE order_items (
    item_id     SERIAL PRIMARY KEY,
    order_id    INTEGER REFERENCES orders(order_id),
    product_id  INTEGER REFERENCES products(product_id),
    quantity    INTEGER NOT NULL,
    unit_price  DECIMAL(10, 2) NOT NULL
);
"""

# ── Seed Data ──────────────────────────────────────────────────────────────────

CUSTOMERS = [
    ("alice.johnson@email.com",   "Alice Johnson",   "USA",       "+1-555-0101"),
    ("bob.martinez@email.com",    "Bob Martinez",    "USA",       "+1-555-0102"),
    ("carol.white@email.com",     "Carol White",     "USA",       "+1-555-0103"),
    ("david.lee@email.com",       "David Lee",       "USA",       "+1-555-0104"),
    ("emma.taylor@email.com",     "Emma Taylor",     "UK",        "+44-20-0105"),
    ("frank.brown@email.com",     "Frank Brown",     "UK",        "+44-20-0106"),
    ("grace.wilson@email.com",    "Grace Wilson",    "UK",        "+44-20-0107"),
    ("henry.chen@email.com",      "Henry Chen",      "Canada",    "+1-604-0108"),
    ("irene.park@email.com",      "Irene Park",      "Canada",    "+1-604-0109"),
    ("jack.schmidt@email.com",    "Jack Schmidt",    "Germany",   "+49-30-0110"),
    ("kate.mueller@email.com",    "Kate Mueller",    "Germany",   "+49-30-0111"),
    ("liam.vogel@email.com",      "Liam Vogel",      "Germany",   "+49-30-0112"),
    ("mia.dupont@email.com",      "Mia Dupont",      "France",    "+33-1-0113"),
    ("noah.bernard@email.com",    "Noah Bernard",    "France",    "+33-1-0114"),
    ("olivia.smith@email.com",    "Olivia Smith",    "Australia", "+61-2-0115"),
    ("peter.jones@email.com",     "Peter Jones",     "Australia", "+61-2-0116"),
    ("quinn.evans@email.com",     "Quinn Evans",     "Australia", "+61-2-0117"),
    ("rachel.kim@email.com",      "Rachel Kim",      "USA",       "+1-555-0118"),
    ("sam.nguyen@email.com",      "Sam Nguyen",      "USA",       "+1-555-0119"),
    ("tina.costa@email.com",      "Tina Costa",      "Canada",    "+1-604-0120"),
]

PRODUCTS = [
    # (product_name, category, price, stock_quantity, supplier)
    ("Laptop Pro 15",       "Electronics",  1499.99,  40,  "TechCorp"),
    ("Laptop Air 13",       "Electronics",   999.99,  60,  "TechCorp"),
    ("Wireless Mouse",      "Accessories",    39.99, 200,  "PeriphPlus"),
    ("Mechanical Keyboard", "Accessories",    89.99, 150,  "PeriphPlus"),
    ("USB-C Hub 7-in-1",    "Accessories",    59.99, 120,  "PeriphPlus"),
    ("4K Monitor 27\"",     "Electronics",   549.99,  25,  "DisplayTech"),
    ("Webcam HD 1080p",     "Electronics",    79.99,  80,  "DisplayTech"),
    ("Office Chair Pro",    "Furniture",     349.99,  20,  "ErgoFurn"),
    ("Standing Desk",       "Furniture",     699.99,  10,  "ErgoFurn"),
    ("Desk Lamp LED",       "Accessories",    44.99, 180,  "BrightHome"),
    ("Project Mgmt Suite",  "Software",      199.99,   0,  "SoftWave"),  # digital, no stock
    ("Antivirus License",   "Software",       49.99,   0,  "SecureIT"),
]

STATUSES = ["completed", "completed", "completed", "shipped", "pending", "refunded"]


def random_date(days_back=365):
    return datetime.now() - timedelta(days=random.randint(1, days_back))


def seed_data(conn):
    cur = conn.cursor()

    # Customers
    cur.executemany(
        "INSERT INTO customers (email, full_name, country, phone) VALUES (%s, %s, %s, %s)",
        CUSTOMERS,
    )
    print(f"  Inserted {len(CUSTOMERS)} customers.")

    # Products
    cur.executemany(
        "INSERT INTO products (product_name, category, price, stock_quantity, supplier) "
        "VALUES (%s, %s, %s, %s, %s)",
        PRODUCTS,
    )
    print(f"  Inserted {len(PRODUCTS)} products.")

    # Orders + order_items
    cur.execute("SELECT customer_id FROM customers")
    customer_ids = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT product_id, price FROM products")
    product_rows = cur.fetchall()  # [(id, price), ...]

    total_orders = 0
    total_items = 0

    for customer_id in customer_ids:
        # Each customer gets 1–4 orders
        num_orders = random.randint(1, 4)
        for _ in range(num_orders):
            order_date = random_date(365)
            status = random.choice(STATUSES)

            # Pick 1–3 products for this order
            items = random.sample(product_rows, k=random.randint(1, 3))
            order_total = sum(price * random.randint(1, 3) for _, price in items)

            # Get customer's country for shipping
            cur.execute("SELECT country FROM customers WHERE customer_id = %s", (customer_id,))
            shipping_country = cur.fetchone()[0]

            cur.execute(
                "INSERT INTO orders (customer_id, order_date, status, total_amount, shipping_country) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING order_id",
                (customer_id, order_date, status, round(order_total, 2), shipping_country),
            )
            order_id = cur.fetchone()[0]
            total_orders += 1

            for product_id, unit_price in items:
                qty = random.randint(1, 3)
                cur.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
                    "VALUES (%s, %s, %s, %s)",
                    (order_id, product_id, qty, unit_price),
                )
                total_items += 1

    print(f"  Inserted {total_orders} orders.")
    print(f"  Inserted {total_items} order items.")
    conn.commit()
    cur.close()


def verify(conn):
    cur = conn.cursor()
    print("\n--- Verification ---")
    for table in ("customers", "products", "orders", "order_items"):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cur.fetchone()[0]} rows")

    print("\n--- Top 5 customers by spend ---")
    cur.execute("""
        SELECT c.full_name, c.country, COUNT(o.order_id) AS orders,
               ROUND(SUM(o.total_amount)::numeric, 2) AS total_spent
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id
        WHERE o.status != 'refunded'
        GROUP BY c.customer_id, c.full_name, c.country
        ORDER BY total_spent DESC
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  {row[0]} ({row[1]}) — {row[2]} orders — ${row[3]}")

    cur.close()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    random.seed(42)  # reproducible data

    print("=== Seeding PostgreSQL ===\n")

    print("[1/4] Creating database...")
    create_database()

    print("[2/4] Creating schema...")
    conn = connect(TARGET_DB)
    cur = conn.cursor()
    cur.execute(DDL)
    conn.commit()
    cur.close()
    print("  Tables created (customers, products, orders, order_items).")

    print("[3/4] Inserting dummy data...")
    seed_data(conn)

    print("[4/4] Verifying...")
    verify(conn)

    conn.close()
    print("\nDone! Update your .env: POSTGRES_DB=rag_demo")


if __name__ == "__main__":
    main()
