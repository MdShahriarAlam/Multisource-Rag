"""Generate a sample PDF that references both the PostgreSQL and MySQL databases."""
from fpdf import FPDF
from pathlib import Path


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.cell(0, 8, "RAG Demo - Database Reference Guide", align="C")
        self.ln(4)
        self.set_draw_color(180, 180, 180)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")

    def section_title(self, title: str):
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(230, 240, 255)
        self.set_text_color(20, 60, 120)
        self.cell(0, 8, title, fill=True, ln=True)
        self.ln(2)

    def sub_title(self, title: str):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(50, 50, 50)
        self.cell(0, 7, title, ln=True)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def table_row(self, cols, widths, bold=False):
        style = "B" if bold else ""
        self.set_font("Helvetica", style, 9)
        self.set_text_color(30, 30, 30)
        for text, w in zip(cols, widths):
            self.cell(w, 6, str(text), border=1)
        self.ln()

    def kv(self, key: str, value: str):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(60, 60, 60)
        self.cell(45, 5, key + ":", ln=False)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, value, ln=True)


pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()

# ──────────────────────────────────────────────────────────────
# OVERVIEW
# ──────────────────────────────────────────────────────────────
pdf.section_title("1. Overview")
pdf.body(
    "This document describes the two relational databases used in the RAG Demo system: "
    "a PostgreSQL instance (company_postgres) and a MySQL instance (mysql_db). "
    "Both databases share the same schema design and contain customer, product, and order data "
    "for a fictitious e-commerce company. The data can be queried live through the RAG agent, "
    "which generates SQL on the fly and returns results with citations."
)

pdf.kv("PostgreSQL host", "localhost:5433  |  database: rag_demo")
pdf.kv("MySQL host", "localhost:3306  |  database: rag_demo")
pdf.ln(4)

# ──────────────────────────────────────────────────────────────
# SHARED SCHEMA
# ──────────────────────────────────────────────────────────────
pdf.section_title("2. Shared Schema (PostgreSQL & MySQL)")

pdf.body(
    "Both databases contain four tables: customers, products, orders, and order_items. "
    "The relationships are: orders reference customers via customer_id; "
    "order_items reference both orders (order_id) and products (product_id). "
    "This forms a standard star-schema suitable for revenue, customer, and inventory analytics."
)

# customers
pdf.sub_title("2.1  customers")
headers = ["Column", "Type", "Notes"]
widths  = [50, 45, 95]
pdf.table_row(headers, widths, bold=True)
rows = [
    ("customer_id", "SERIAL / INT AUTO_INC", "Primary key"),
    ("email",       "VARCHAR(255)",          "Unique, not null"),
    ("full_name",   "VARCHAR(255)",          "Customer's full name"),
    ("country",     "VARCHAR(100)",          "Country of residence"),
    ("phone",       "VARCHAR(50)",           "International format"),
    ("created_at",  "TIMESTAMP",             "Account creation date, default NOW()"),
    ("is_active",   "BOOLEAN",               "TRUE = active account"),
]
for r in rows:
    pdf.table_row(r, widths)
pdf.ln(3)

# products
pdf.sub_title("2.2  products")
pdf.table_row(headers, widths, bold=True)
rows = [
    ("product_id",     "SERIAL / INT AUTO_INC", "Primary key"),
    ("product_name",   "VARCHAR(255)",          "Product display name"),
    ("category",       "VARCHAR(100)",          "Electronics, Accessories, Furniture, Software"),
    ("price",          "DECIMAL(10,2)",         "Unit retail price in USD"),
    ("stock_quantity", "INTEGER",               "Current units in stock, default 0"),
    ("supplier",       "VARCHAR(255)",          "Supplier/vendor name"),
]
for r in rows:
    pdf.table_row(r, widths)
pdf.ln(3)

pdf.add_page()

# orders
pdf.sub_title("2.3  orders")
pdf.table_row(headers, widths, bold=True)
rows = [
    ("order_id",         "SERIAL / INT AUTO_INC", "Primary key"),
    ("customer_id",      "INTEGER",               "FK -> customers(customer_id)"),
    ("order_date",       "TIMESTAMP / DATETIME",  "When order was placed"),
    ("status",           "VARCHAR(50)",           "'pending', 'processing', 'shipped', 'delivered', 'cancelled'"),
    ("total_amount",     "DECIMAL(10,2)",         "Total value of the order in USD"),
    ("shipping_country", "VARCHAR(100)",          "Destination country for shipping"),
]
for r in rows:
    pdf.table_row(r, widths)
pdf.ln(3)

# order_items
pdf.sub_title("2.4  order_items")
pdf.table_row(headers, widths, bold=True)
rows = [
    ("item_id",    "SERIAL / INT AUTO_INC", "Primary key"),
    ("order_id",   "INTEGER",               "FK -> orders(order_id)"),
    ("product_id", "INTEGER",               "FK -> products(product_id)"),
    ("quantity",   "INTEGER",               "Number of units ordered, not null"),
    ("unit_price", "DECIMAL(10,2)",         "Price at time of purchase, not null"),
]
for r in rows:
    pdf.table_row(r, widths)
pdf.ln(4)

# ──────────────────────────────────────────────────────────────
# BUSINESS RULES
# ──────────────────────────────────────────────────────────────
pdf.section_title("3. Business Rules & Constraints")
pdf.body(
    "- An order must belong to exactly one customer (customer_id NOT NULL, FK enforced).\n"
    "- Each order_items row captures the unit_price at time of purchase, so historical "
    "revenue figures remain accurate even if product prices change later.\n"
    "- total_amount on the orders table is a denormalised summary; the exact breakdown "
    "is computed from order_items (SUM(quantity * unit_price)).\n"
    "- stock_quantity in products is NOT automatically decremented on order creation; "
    "it must be updated separately by the inventory management process.\n"
    "- A customer marked is_active = FALSE should not receive marketing communications "
    "and may have limited portal access.\n"
    "- Order status flow: pending -> processing -> shipped -> delivered. "
    "A cancelled status can be set from pending or processing only."
)

# ──────────────────────────────────────────────────────────────
# SAMPLE DATA SNAPSHOT
# ──────────────────────────────────────────────────────────────
pdf.section_title("4. Sample Data Snapshot")
pdf.body(
    "The seed scripts insert 20 customers, 12 products (across 4 categories), "
    "and randomly generated orders (1-4 per customer) with 1-3 line items each. "
    "Representative sample rows are shown below."
)

pdf.sub_title("customers (sample)")
c_headers = ["customer_id", "full_name",        "country",      "is_active"]
c_widths   = [28,            60,                 45,             27]
pdf.table_row(c_headers, c_widths, bold=True)
c_rows = [
    (1,  "Alice Johnson",   "United States", "TRUE"),
    (2,  "Bob Smith",       "Canada",        "TRUE"),
    (3,  "Carlos Rivera",   "Mexico",        "TRUE"),
    (4,  "Diana Chen",      "China",         "FALSE"),
    (5,  "Eve Williams",    "UK",            "TRUE"),
]
for r in c_rows:
    pdf.table_row(r, c_widths)
pdf.ln(3)

pdf.sub_title("products (sample)")
p_headers = ["product_id", "product_name",         "category",    "price", "stock"]
p_widths   = [24,           62,                     32,            22,      20]
pdf.table_row(p_headers, p_widths, bold=True)
p_rows = [
    (1,  "Laptop Pro 15",          "Electronics",  "$1,299.99", 45),
    (2,  "Wireless Mouse",         "Accessories",  "$29.99",    200),
    (3,  "Standing Desk",          "Furniture",    "$549.00",   30),
    (4,  "Cloud Storage 1TB/yr",   "Software",     "$99.99",    999),
    (5,  "USB-C Hub 7-port",       "Accessories",  "$49.99",    150),
    (6,  "4K Monitor 27in",        "Electronics",  "$649.00",   60),
]
for r in p_rows:
    pdf.table_row(r, p_widths)
pdf.ln(3)

pdf.add_page()

pdf.sub_title("orders (sample)")
o_headers = ["order_id", "customer_id", "status",      "total_amount", "ship_country"]
o_widths   = [22,         28,            28,             32,             50]
pdf.table_row(o_headers, o_widths, bold=True)
o_rows = [
    (1,  1, "delivered",   "$1,329.98", "United States"),
    (2,  1, "shipped",     "$49.99",    "United States"),
    (3,  2, "processing",  "$549.00",   "Canada"),
    (4,  3, "pending",     "$129.98",   "Mexico"),
    (5,  5, "delivered",   "$649.00",   "UK"),
    (6,  5, "cancelled",   "$29.99",    "UK"),
]
for r in o_rows:
    pdf.table_row(r, o_widths)
pdf.ln(4)

# ──────────────────────────────────────────────────────────────
# ANALYTICS QUERIES
# ──────────────────────────────────────────────────────────────
pdf.section_title("5. Common Analytics Queries")
pdf.body(
    "The RAG agent supports the following types of questions against these databases. "
    "Each question causes the agent to generate and execute a SQL query, then cite the source."
)

queries = [
    ("Top customers by revenue",
     "SELECT c.full_name, SUM(o.total_amount) AS revenue\n"
     "FROM customers c JOIN orders o ON c.customer_id = o.customer_id\n"
     "WHERE o.status = 'delivered'\n"
     "GROUP BY c.full_name ORDER BY revenue DESC LIMIT 5;"),

    ("Low-stock products (under 50 units)",
     "SELECT product_name, category, stock_quantity\n"
     "FROM products WHERE stock_quantity < 50\n"
     "ORDER BY stock_quantity ASC;"),

    ("Monthly revenue breakdown",
     "SELECT DATE_TRUNC('month', order_date) AS month,\n"
     "       SUM(total_amount) AS monthly_revenue\n"
     "FROM orders WHERE status != 'cancelled'\n"
     "GROUP BY month ORDER BY month;"),

    ("Average order value by country",
     "SELECT shipping_country,\n"
     "       ROUND(AVG(total_amount), 2) AS avg_order_value,\n"
     "       COUNT(*) AS order_count\n"
     "FROM orders GROUP BY shipping_country\n"
     "ORDER BY avg_order_value DESC;"),

    ("Products never ordered",
     "SELECT p.product_name, p.category\n"
     "FROM products p\n"
     "WHERE p.product_id NOT IN (SELECT DISTINCT product_id FROM order_items);"),
]

for title, sql in queries:
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 6, title, ln=True)
    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(10, 80, 10)
    pdf.set_fill_color(245, 255, 245)
    pdf.multi_cell(0, 5, sql, fill=True)
    pdf.ln(2)

# ──────────────────────────────────────────────────────────────
# CROSS-DATABASE NOTES
# ──────────────────────────────────────────────────────────────
pdf.section_title("6. PostgreSQL vs MySQL Differences")
pdf.body(
    "Although the schemas are identical in structure, there are minor dialect differences:\n\n"
    "- Auto-increment syntax: PostgreSQL uses SERIAL; MySQL uses INT AUTO_INCREMENT.\n"
    "- Date truncation: PostgreSQL supports DATE_TRUNC(); MySQL uses DATE_FORMAT() or "
    "YEAR()/MONTH() functions.\n"
    "- Boolean literals: PostgreSQL accepts TRUE/FALSE; MySQL uses 1/0.\n"
    "- Case sensitivity: MySQL table/column names are case-insensitive on Windows; "
    "PostgreSQL folds unquoted identifiers to lower-case.\n\n"
    "When the RAG agent queries both sources, it automatically adapts the SQL to the "
    "correct dialect based on the connector type."
)

# ──────────────────────────────────────────────────────────────
# VERIFICATION CHECKLIST
# ──────────────────────────────────────────────────────────────
pdf.section_title("7. Verification Checklist for RAG Upload Test")
checks = [
    "Upload this PDF via the sidebar 'Upload Files' section.",
    "Ask: 'What tables are in the database?' - agent should cite this PDF and both live DBs.",
    "Ask: 'Who are the top 5 customers by total spending?' - agent queries orders + customers.",
    "Ask: 'Which products have less than 50 units in stock?' - agent queries products table.",
    "Ask: 'What is Alice Johnson's order history?' - cross-references customers and orders.",
    "Ask: 'Explain the order_items table schema.' - agent should cite this PDF directly.",
    "Ask: 'Are there any products that have never been ordered?' - complex JOIN query.",
    "Verify document_sources in the response cites 'local_uploads / database_reference_guide.pdf'.",
]
for i, check in enumerate(checks, 1):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 5, f"{i}. {check}")
pdf.ln(2)

pdf.body(
    "A successful test means the agent blends live SQL results with context from this PDF, "
    "returning a single coherent answer that cites both structured (SQL) and unstructured "
    "(PDF) sources in the same response."
)

# Save
out_dir = Path("./uploaded_files")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "database_reference_guide.pdf"
pdf.output(str(out_path))
print(f"PDF saved to: {out_path}")
