"""SQL safety: parse-tree validation that a query is read-only and single-statement."""
from __future__ import annotations

import logging
from typing import Iterable

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import DML, Keyword

from ..errors import UnsafeQuery

log = logging.getLogger(__name__)

# Any of these keywords appearing at statement level is a hard reject.
FORBIDDEN_KEYWORDS = frozenset(
    {
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
        "CREATE", "GRANT", "REVOKE", "MERGE", "CALL", "EXEC", "EXECUTE",
        "REPLACE", "RENAME", "ATTACH", "DETACH", "VACUUM", "REINDEX",
        "COPY", "LOAD", "HANDLER", "LOCK", "UNLOCK", "SET",
    }
)


def _iter_keywords(statement: Statement) -> Iterable[str]:
    """Yield uppercase keyword/DML strings from a parsed statement, recursively."""
    for token in statement.flatten():
        if token.ttype in (Keyword, Keyword.DML, Keyword.DDL, Keyword.CTE):
            yield token.normalized.upper()
        elif token.ttype is DML:
            yield token.normalized.upper()


def ensure_select_only(query: str) -> str:
    """
    Validate that `query` is a single read-only statement and return it stripped.

    Rules:
    - must parse to exactly one non-empty statement (blocks stacked queries)
    - first DML token must be SELECT (or WITH ... SELECT)
    - no forbidden keywords anywhere in the token stream
    """
    if not query or not query.strip():
        raise UnsafeQuery("Empty query")

    parsed = [s for s in sqlparse.parse(query) if str(s).strip() and str(s).strip() != ";"]
    if len(parsed) != 1:
        raise UnsafeQuery(
            "Only a single SELECT statement is allowed",
            details={"statements_found": len(parsed)},
        )

    statement = parsed[0]
    keywords = list(_iter_keywords(statement))

    # First meaningful keyword must be SELECT or WITH
    first = next((k for k in keywords if k), None)
    if first not in {"SELECT", "WITH"}:
        raise UnsafeQuery(
            f"Only SELECT / WITH queries are allowed (got {first!r})",
            details={"first_keyword": first},
        )

    # No forbidden keywords anywhere (catches nested DML inside CTEs, subqueries, etc.)
    found = [k for k in keywords if k in FORBIDDEN_KEYWORDS]
    if found:
        raise UnsafeQuery(
            "Query contains forbidden keywords",
            details={"forbidden": sorted(set(found))},
        )

    return query.strip().rstrip(";")
