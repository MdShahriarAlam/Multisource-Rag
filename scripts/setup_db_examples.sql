-- Example PostgreSQL database setup
-- This creates sample tables to demonstrate the multi-source RAG capabilities

-- Create customers table
CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    country VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    total_amount DECIMAL(10, 2)
);

-- Create products table
CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(10, 2),
    stock_quantity INTEGER DEFAULT 0
);

-- Insert sample customers
INSERT INTO customers (email, full_name, country) VALUES
    ('john.doe@example.com', 'John Doe', 'USA'),
    ('jane.smith@example.com', 'Jane Smith', 'UK'),
    ('bob.wilson@example.com', 'Bob Wilson', 'Canada'),
    ('alice.brown@example.com', 'Alice Brown', 'USA'),
    ('charlie.davis@example.com', 'Charlie Davis', 'Australia')
ON CONFLICT (email) DO NOTHING;

-- Insert sample products
INSERT INTO products (product_name, category, price, stock_quantity) VALUES
    ('Laptop Pro', 'Electronics', 1299.99, 50),
    ('Wireless Mouse', 'Electronics', 29.99, 200),
    ('Office Chair', 'Furniture', 249.99, 30),
    ('Standing Desk', 'Furniture', 599.99, 15),
    ('USB-C Hub', 'Electronics', 49.99, 100)
ON CONFLICT DO NOTHING;

-- Insert sample orders
INSERT INTO orders (customer_id, total_amount, status) VALUES
    (1, 1299.99, 'completed'),
    (1, 79.98, 'completed'),
    (2, 849.98, 'pending'),
    (3, 1329.98, 'completed'),
    (4, 249.99, 'shipped')
ON CONFLICT DO NOTHING;

-- Example query to verify data
SELECT
    c.full_name,
    c.email,
    COUNT(o.order_id) as total_orders,
    SUM(o.total_amount) as total_spent
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.full_name, c.email
ORDER BY total_spent DESC NULLS LAST;
