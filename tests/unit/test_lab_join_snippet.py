"""JOIN 片段生成：join_type 规范化"""
from app.services.lab_enhancement_service import LabEnhancementService


def test_normalize_join_type_strips_trailing_join():
    assert LabEnhancementService._normalize_join_type("LEFT JOIN") == "LEFT"
    assert LabEnhancementService._normalize_join_type("inner join") == "INNER"
    assert LabEnhancementService._normalize_join_type("RIGHT") == "RIGHT"


def test_build_join_snippet_no_double_join():
    snippet = LabEnhancementService._build_join_snippet(
        "LEFT JOIN",
        "api_users",
        "sys_user_role_relation.user_id = api_users.id",
    )
    assert snippet == "LEFT JOIN api_users ON sys_user_role_relation.user_id = api_users.id"
    assert "JOIN JOIN" not in snippet
