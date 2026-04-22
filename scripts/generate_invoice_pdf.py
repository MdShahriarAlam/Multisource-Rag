"""Generate a clean invoice PDF — single-column layout for clean pypdf extraction."""
from fpdf import FPDF
from pathlib import Path


class InvoicePDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")

    def rule(self, thick=False):
        self.set_draw_color(80, 120, 200) if thick else self.set_draw_color(200, 200, 200)
        lw = 0.8 if thick else 0.3
        self.set_line_width(lw)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_line_width(0.2)
        self.ln(3)

    def label_value(self, label, value, label_w=55):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(90, 90, 90)
        self.cell(label_w, 6, label)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        self.cell(0, 6, value, ln=True)

    def section(self, title):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(30, 70, 160)
        self.cell(0, 7, title, ln=True)
        self.rule(thick=True)


pdf = InvoicePDF()
pdf.set_auto_page_break(auto=True, margin=16)
pdf.add_page()
pdf.set_margins(14, 14, 14)

# ── TOP BANNER ──────────────────────────────────────────────────
pdf.set_fill_color(25, 80, 160)
pdf.rect(0, 0, 210, 26, "F")
pdf.set_font("Helvetica", "B", 17)
pdf.set_text_color(255, 255, 255)
pdf.set_xy(14, 5)
pdf.cell(90, 8, "ACME Commerce Inc.", ln=False)
pdf.set_font("Helvetica", "B", 20)
pdf.set_xy(140, 3)
pdf.cell(56, 10, "INVOICE", align="R", ln=True)
pdf.set_font("Helvetica", "", 8)
pdf.set_xy(14, 14)
pdf.cell(180, 5, "123 Business Avenue, Suite 400, New York, NY 10001  |  billing@acmecommerce.com  |  +1 212 555 0100", ln=True)
pdf.set_y(32)

# ── INVOICE HEADER ──────────────────────────────────────────────
pdf.set_font("Helvetica", "B", 11)
pdf.set_text_color(25, 80, 160)
pdf.cell(0, 7, "Invoice Details", ln=True)
pdf.rule(thick=True)

pdf.label_value("Invoice Number:", "INV-2024-00347")
pdf.label_value("Invoice Date:", "2024-11-15")
pdf.label_value("Payment Due Date:", "2024-11-30")
pdf.label_value("Order ID:", "1")
pdf.label_value("Order Status:", "DELIVERED")
pdf.label_value("Shipping Country:", "United States")
pdf.ln(3)

# ── CUSTOMER ────────────────────────────────────────────────────
pdf.section("Customer Information")
pdf.label_value("Customer ID:", "1")
pdf.label_value("Full Name:", "Alice Johnson")
pdf.label_value("Email Address:", "alice.johnson@email.com")
pdf.label_value("Phone:", "+1-555-0101")
pdf.label_value("Billing Address:", "14 Maple Street, Springfield, IL 62701")
pdf.label_value("Country:", "United States")
pdf.label_value("Account Status:", "Active")
pdf.ln(3)

# ── LINE ITEMS ──────────────────────────────────────────────────
pdf.section("Order Line Items")

# Table header
pdf.set_fill_color(235, 242, 255)
pdf.set_font("Helvetica", "B", 9)
pdf.set_text_color(25, 60, 140)
col = [10, 65, 28, 18, 26, 22, 13]
hdrs = ["Item", "Product Name", "Category", "Qty", "Unit Price", "Subtotal", "Disc"]
for h, w in zip(hdrs, col):
    pdf.cell(w, 7, h, fill=True, border=1)
pdf.ln()

rows = [
    (1, "Laptop Pro 15",    "Electronics", 1, 1299.99, 0),
    (2, "Wireless Mouse",   "Accessories", 2,   29.99, 0),
    (3, "USB-C Hub 7-port", "Accessories", 1,   49.99, 10),
]

subtotal = 0.0
for i, (no, name, cat, qty, price, disc_pct) in enumerate(rows):
    line_gross = qty * price
    disc_amt   = line_gross * disc_pct / 100
    line_net   = line_gross - disc_amt
    subtotal  += line_net
    bg = (255, 255, 255) if i % 2 == 0 else (247, 250, 255)
    pdf.set_fill_color(*bg)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 30, 30)
    disc_str = f"{disc_pct}%" if disc_pct else "-"
    pdf.cell(col[0], 6, str(no),           fill=True, border=1, align="C")
    pdf.cell(col[1], 6, name,              fill=True, border=1)
    pdf.cell(col[2], 6, cat,               fill=True, border=1)
    pdf.cell(col[3], 6, str(qty),          fill=True, border=1, align="C")
    pdf.cell(col[4], 6, f"${price:.2f}",   fill=True, border=1, align="R")
    pdf.cell(col[5], 6, f"${line_net:.2f}",fill=True, border=1, align="R")
    pdf.cell(col[6], 6, disc_str,          fill=True, border=1, align="C")
    pdf.ln()

pdf.ln(4)

# ── TOTALS ──────────────────────────────────────────────────────
pdf.section("Payment Summary")
tax_rate   = 0.08
tax_amount = subtotal * tax_rate
grand      = subtotal + tax_amount

pdf.label_value("Subtotal (before tax):", f"${subtotal:,.2f}")
pdf.label_value("Shipping:", "$0.00  (complimentary - delivered order)")
pdf.label_value("Sales Tax (8%):", f"${tax_amount:,.2f}")
pdf.set_font("Helvetica", "B", 11)
pdf.set_text_color(25, 80, 160)
pdf.cell(55, 7, "TOTAL AMOUNT DUE:")
pdf.cell(0, 7, f"${grand:,.2f}", ln=True)
pdf.set_font("Helvetica", "B", 9)
pdf.set_text_color(30, 130, 60)
pdf.cell(0, 6, "STATUS: PAID IN FULL", ln=True)
pdf.ln(3)

# ── PAYMENT ─────────────────────────────────────────────────────
pdf.section("Payment & Delivery Details")
pdf.label_value("Payment Method:", "Credit Card - Visa ending in 4242")
pdf.label_value("Payment Auth Code:", "TXN-8847-CC24")
pdf.label_value("Payment Date:", "2024-11-15")
pdf.label_value("Shipping Carrier:", "FedEx Ground")
pdf.label_value("Tracking Number:", "774899231920")
pdf.label_value("Shipped Date:", "2024-11-16")
pdf.label_value("Delivered Date:", "2024-11-19")
pdf.ln(3)

# ── PRODUCT DETAILS ─────────────────────────────────────────────
pdf.section("Product Details & SKUs")
pdf.label_value("Item 1 - Product ID:", "1  (database product_id = 1)")
pdf.label_value("Item 1 - SKU:", "LP15-2024")
pdf.label_value("Item 1 - Description:", "Laptop Pro 15 - 15-inch laptop with Intel Core i7, 16GB RAM, 512GB SSD")
pdf.label_value("Item 1 - Warranty:", "1-year manufacturer warranty included")
pdf.ln(2)
pdf.label_value("Item 2 - Product ID:", "2  (database product_id = 2)")
pdf.label_value("Item 2 - SKU:", "WM-BLK-001")
pdf.label_value("Item 2 - Description:", "Wireless Mouse - Ergonomic Bluetooth mouse, 1600 DPI, black")
pdf.ln(2)
pdf.label_value("Item 3 - Product ID:", "5  (database product_id = 5)")
pdf.label_value("Item 3 - SKU:", "USBC7-HUB")
pdf.label_value("Item 3 - Description:", "USB-C Hub 7-port - 7 ports including HDMI, USB-A x3, USB-C PD, SD card")
pdf.label_value("Item 3 - Discount:", "10% loyalty discount applied")
pdf.ln(3)

# ── NOTES ───────────────────────────────────────────────────────
pdf.section("Notes & Terms")
pdf.set_font("Helvetica", "", 9)
pdf.set_text_color(60, 60, 60)
notes = [
    "This invoice covers Order ID 1 placed by customer Alice Johnson (customer_id = 1).",
    "To look up this order in the database, query: SELECT * FROM orders WHERE order_id = 1;",
    "To look up this customer: SELECT * FROM customers WHERE email = 'alice.johnson@email.com';",
    "Returns are accepted within 30 days of delivery with original packaging.",
    "For billing enquiries reference invoice number INV-2024-00347.",
    "Payment terms: Net 15 days from invoice date. Late fee: 1.5% per month.",
]
for note in notes:
    pdf.set_x(14)
    pdf.multi_cell(0, 5, "- " + note)
pdf.ln(2)

# Save
out_dir = Path("./uploaded_files")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "invoice_INV-2024-00347.pdf"
pdf.output(str(out_path))
print(f"Saved: {out_path}")
