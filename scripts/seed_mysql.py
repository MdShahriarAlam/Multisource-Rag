"""
Seed script: populates the MySQL rag_demo database with the same
realistic dummy data as the PostgreSQL seed.

Usage:
    python scripts/seed_mysql.py

Reads credentials from .env in the project root.
"""

import os
import random
import sys
from datetime import datetime, timedelta

import pymysql
import pymysql.cursors
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

HOST     = os.getenv("MYSQL_HOST", "127.0.0.1")
PORT     = int(os.getenv("MYSQL_PORT", 3306))
USER     = os.getenv("MYSQL_USER", "admin")
PASSWORD = os.getenv("MYSQL_PASSWORD", "")
DB       = os.getenv("MYSQL_DB", "rag_demo")


def connect():
    return pymysql.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD,
        database=DB, cursorclass=pymysql.cursors.DictCursor,
        autocommit=False, charset="utf8mb4",
    )


DDL = """
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id  INT AUTO_INCREMENT PRIMARY KEY,
    email        VARCHAR(255) UNIQUE NOT NULL,
    full_name    VARCHAR(255) NOT NULL,
    country      VARCHAR(100),
    phone        VARCHAR(50),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active    BOOLEAN DEFAULT TRUE
);

CREATE TABLE products (
    product_id      INT AUTO_INCREMENT PRIMARY KEY,
    product_name    VARCHAR(255) NOT NULL,
    category        VARCHAR(100),
    price           DECIMAL(10, 2),
    stock_quantity  INT DEFAULT 0,
    supplier        VARCHAR(255)
);

CREATE TABLE orders (
    order_id          INT AUTO_INCREMENT PRIMARY KEY,
    customer_id       INT,
    order_date        DATETIME,
    status            VARCHAR(50) DEFAULT 'pending',
    total_amount      DECIMAL(10, 2),
    shipping_country  VARCHAR(100),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    item_id     INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT,
    product_id  INT,
    quantity    INT NOT NULL,
    unit_price  DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id)   REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
"""

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
    ("Laptop Pro 15",       "Electronics",  1499.99,  40,  "TechCorp"),
    ("Laptop Air 13",       "Electronics",   999.99,  60,  "TechCorp"),
    ("Wireless Mouse",      "Accessories",    39.99, 200,  "PeriphPlus"),
    ("Mechanical Keyboard", "Accessories",    89.99, 150,  "PeriphPlus"),
    ("USB-C Hub 7-in-1",    "Accessories",    59.99, 120,  "PeriphPlus"),
    ("4K Monitor 27in",     "Electronics",   549.99,  25,  "DisplayTech"),
    ("Webcam HD 1080p",     "Electronics",    79.99,  80,  "DisplayTech"),
    ("Office Chair Pro",    "Furniture",     349.99,  20,  "ErgoFurn"),
    ("Standing Desk",       "Furniture",     699.99,  10,  "ErgoFurn"),
    ("Desk Lamp LED",       "Accessories",    44.99, 180,  "BrightHome"),
    ("Project Mgmt Suite",  "Software",      199.99,   0,  "SoftWave"),
    ("Antivirus License",   "Software",       49.99,   0,  "SecureIT"),
]

STATUSES = ["completed", "completed", "completed", "shipped", "pending", "refunded"]


def random_date(days_back=365):
    return datetime.now() - timedelta(days=random.randint(1, days_back))


def main():
    random.seed(42)
    print("=== Seeding MySQL ===\n")

    conn = connect()
    cur = conn.cursor()

    print("[1/3] Creating schema...")
    for statement in DDL.strip().split(";"):
        s = statement.strip()
        if s:
            cur.execute(s)
    conn.commit()
    print("  Tables created.")

    print("[2/3] Inserting data...")

    cur.executemany(
        "INSERT INTO customers (email, full_name, country, phone) VALUES (%s, %s, %s, %s)",
        CUSTOMERS,
    )
    cur.executemany(
        "INSERT INTO products (product_name, category, price, stock_quantity, supplier) VALUES (%s, %s, %s, %s, %s)",
        PRODUCTS,
    )
    print(f"  {len(CUSTOMERS)} customers, {len(PRODUCTS)} products.")

    cur.execute("SELECT customer_id, country FROM customers")
    customers = cur.fetchall()
    cur.execute("SELECT product_id, price FROM products")
    products = cur.fetchall()

    total_orders = total_items = 0
    for c in customers:
        for _ in range(random.randint(1, 4)):
            items = random.sample(products, k=random.randint(1, 3))
            total = sum(p["price"] * random.randint(1, 3) for p in items)
            cur.execute(
                "INSERT INTO orders (customer_id, order_date, status, total_amount, shipping_country) "
                "VALUES (%s, %s, %s, %s, %s)",
                (c["customer_id"], random_date(), random.choice(STATUSES), round(total, 2), c["country"]),
            )
            order_id = cur.lastrowid
            total_orders += 1
            for p in items:
                qty = random.randint(1, 3)
                cur.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                    (order_id, p["product_id"], qty, p["price"]),
                )
                total_items += 1

    conn.commit()
    print(f"  {total_orders} orders, {total_items} order items.")

    print("[3/3] Verifying...")
    for table in ("customers", "products", "orders", "order_items"):
        cur.execute(f"SELECT COUNT(*) AS n FROM {table}")
        print(f"  {table}: {cur.fetchone()['n']} rows")

    print("\n--- Top 5 customers by spend ---")
    cur.execute("""
        SELECT c.full_name, c.country, COUNT(o.order_id) AS orders,
               ROUND(SUM(o.total_amount), 2) AS total_spent
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id
        WHERE o.status != 'refunded'
        GROUP BY c.customer_id
        ORDER BY total_spent DESC
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  {row['full_name']} ({row['country']}) — {row['orders']} orders — ${row['total_spent']}")

    cur.close()
    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
