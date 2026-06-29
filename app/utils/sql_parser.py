"""Shared SQL parsing utilities."""
from __future__ import annotations

import logging
from typing import List, Set

import sqlparse

logger = logging.getLogger(__name__)


def extract_table_names(sql: str) -> List[str]:
    """
    Extract physical table names from SQL using sqlparse.
    Handles CTEs (WITH) and skips alias-only identifiers.
    """
    tables: Set[str] = set()
    ctes: Set[str] = set()

    try:
        formatted_sql = sqlparse.format(sql, strip_comments=True).strip()
        parsed = sqlparse.parse(formatted_sql)
        if not parsed:
            return []

        def walk_tokens(tokens) -> None:
            from_seen = False
            for token in tokens:
                if token.is_group:
                    walk_tokens(token.tokens)

                if token.ttype is sqlparse.tokens.Keyword and token.value.upper() in ("FROM", "JOIN"):
                    from_seen = True
                    continue

                if from_seen and isinstance(token, sqlparse.sql.Identifier):
                    table_name = token.get_real_name()
                    if table_name:
                        tables.add(table_name.lower())
                    from_seen = False
                elif from_seen and token.ttype is sqlparse.tokens.Name:
                    tables.add(token.value.lower())
                    from_seen = False

        for statement in parsed:
            for token in statement.tokens:
                if token.value.upper() == "WITH":
                    idx = statement.token_index(token) + 1
                    while idx < len(statement.tokens):
                        t = statement.tokens[idx]
                        if isinstance(t, sqlparse.sql.Identifier):
                            ctes.add(t.get_real_name().lower())
                        elif t.value == "(":
                            break
                        idx += 1
            walk_tokens(statement.tokens)

        return list(tables - ctes)
    except Exception as e:
        logger.warning("Failed to extract table names: %s", e)
        return []
