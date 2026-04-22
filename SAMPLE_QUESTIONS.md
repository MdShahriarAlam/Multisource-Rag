# Sample Questions for the Multi-Source RAG Chatbot

Use these questions to test the application after running `python scripts/seed_postgres.py`.

---

## Simple Single-Table Queries

```
Show me all customers from the USA
```
```
Which products are in the Electronics category?
```
```
How many orders are currently pending?
```
```
What products have less than 30 units in stock?
```
```
List all customers from Germany
```
```
Which products does TechCorp supply?
```

---

## Aggregation Queries

```
Who are the top 5 customers by total spending?
```
```
What is the total revenue from completed orders?
```
```
Which product category generates the most revenue?
```
```
What is the average order value?
```
```
How many orders has each customer placed?
```
```
What is the total inventory value across all products?
```

---

## Multi-Table Join Queries

```
Show me all orders placed by Alice Johnson
```
```
Which customers have never placed an order?
```
```
What is the most popular product by units sold?
```
```
Show me the order history for customers in Germany
```
```
What products did customers from Australia buy?
```
```
Which customers ordered a Laptop Pro 15?
```

---

## Date-Based Queries

```
How many orders were placed in the last 30 days?
```
```
What were our top-selling products last month?
```
```
Show me monthly revenue for the past 6 months
```
```
Which customers joined in the last 90 days?
```

---

## Business Intelligence Queries

```
Which customers have placed more than 3 orders?
```
```
What is the refund rate by product category?
```
```
Which countries have the highest average order value?
```
```
Show me customers who ordered Electronics
```
```
What is the revenue breakdown by country?
```
```
Which products are low stock and need restocking?
```
```
What is the total revenue per supplier?
```
```
Show me all refunded orders and which customers made them
```

---

## Cross-Source / Hybrid Queries (if documents are also ingested)

```
Compare our top customers with the company policy on volume discounts
```
```
Show me revenue trends and summarize any relevant reports
```

---

## Tips

- Start the MCP server and API before sending queries:
  ```bash
  python -m src.mcp_server.server   # terminal 1
  python -m src.main                # terminal 2
  streamlit run streamlit_app.py    # terminal 3 (optional UI)
  ```

- Or use curl directly:
  ```bash
  curl -X POST http://localhost:8000/api/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Who are the top 5 customers by total spending?", "session_id": "demo"}'
  ```
