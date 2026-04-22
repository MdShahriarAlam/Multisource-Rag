"""SQL safety guard — injection and stacked-query rejection tests."""
import pytest

from src.errors import UnsafeQuery
from src.mcp_server.sql_safety import ensure_select_only


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM users",
        "select id, name from customers where id = 1",
        "WITH t AS (SELECT id FROM users) SELECT * FROM t",
        "  SELECT 1  ",
        "SELECT * FROM orders ORDER BY id LIMIT 10;",
    ],
)
def test_valid_selects_pass(query):
    ensure_select_only(query)


@pytest.mark.parametrize(
    "payload",
    [
        "DROP TABLE users",
        "DELETE FROM users WHERE 1=1",
        "UPDATE users SET admin=1",
        "INSERT INTO users VALUES (1)",
        "TRUNCATE users",
        "ALTER TABLE users ADD COLUMN pwn INT",
        "CREATE TABLE x (id INT)",
        "GRANT ALL ON users TO public",
        "EXEC sp_msforeachtable 'DROP TABLE ?'",
        "CALL sys.admin()",
        # Stacked queries
        "SELECT 1; DROP TABLE users",
        "SELECT * FROM users; DELETE FROM users",
        # CTE hiding DML
        "WITH t AS (DELETE FROM users RETURNING id) SELECT * FROM t",
        "WITH t AS (INSERT INTO users VALUES (1) RETURNING id) SELECT * FROM t",
        # Comment tricks still contain forbidden keywords
        "SELECT * FROM users; -- harmless?\nDROP TABLE users",
        # SET session parameters
        "SET search_path TO evil",
    ],
)
def test_malicious_queries_rejected(payload):
    with pytest.raises(UnsafeQuery):
        ensure_select_only(payload)


@pytest.mark.parametrize("empty", ["", "  ", ";", " ;  "])
def test_empty_rejected(empty):
    with pytest.raises(UnsafeQuery):
        ensure_select_only(empty)


def test_trailing_semicolon_stripped():
    out = ensure_select_only("SELECT 1;")
    assert out == "SELECT 1"
