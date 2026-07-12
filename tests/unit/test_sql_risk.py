"""SQL Lab 增强功能单元测试"""
import pytest
from app.utils.sql_risk import check_sql_risks, detect_sensitive_fields


def test_check_sql_risks_select_star_no_where():
    warnings = check_sql_risks("SELECT * FROM users")
    codes = [w["code"] for w in warnings]
    assert "SELECT_STAR_NO_WHERE" in codes or "NO_FILTER_NO_LIMIT" in codes


def test_detect_sensitive_phone_field():
    warnings = detect_sensitive_fields("SELECT phone FROM users", ["phone", "name"])
    assert any(w["code"] == "SENSITIVE_FIELD" for w in warnings)


def test_check_sql_risks_safe_query():
    warnings = check_sql_risks("SELECT id, name FROM users WHERE id = 1 LIMIT 10")
    danger = [w for w in warnings if w["level"] == "danger"]
    assert len(danger) == 0
