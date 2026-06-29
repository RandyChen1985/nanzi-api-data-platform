"""Unit tests for SQL table name extraction."""
from app.utils.sql_parser import extract_table_names


def test_extract_simple_select():
    sql = "SELECT * FROM users u JOIN orders o ON u.id = o.user_id"
    tables = extract_table_names(sql)
    assert "users" in tables
    assert "orders" in tables


def test_extract_subquery_tables():
    sql = "SELECT * FROM orders o WHERE o.user_id IN (SELECT id FROM users)"
    tables = extract_table_names(sql)
    assert "orders" in tables
    assert "users" in tables


def test_extract_invalid_sql_returns_empty():
    assert extract_table_names("") == []
