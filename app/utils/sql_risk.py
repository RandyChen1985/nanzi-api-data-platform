"""SQL Lab 查询风险与敏感字段检测"""
import re
from typing import Any, Dict, List, Optional

SENSITIVE_FIELD_PATTERNS = [
    (r"(?i)(phone|mobile|tel)", "手机号"),
    (r"(?i)(id_?card|identity|ssn)", "身份证号"),
    (r"(?i)(password|passwd|pwd|secret|token|api_?key)", "密码/密钥"),
    (r"(?i)(email|mail)", "邮箱"),
    (r"(?i)(bank_?card|credit_?card)", "银行卡"),
    (r"(?i)(salary|income|wage)", "薪资"),
    (r"(?i)(address|addr)", "地址"),
]

RISK_LEVEL_INFO = "info"
RISK_LEVEL_WARN = "warn"
RISK_LEVEL_DANGER = "danger"


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
    return sql


def detect_sensitive_fields(sql: str, column_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """检测 SQL 或结果列中的敏感字段引用"""
    warnings: List[Dict[str, Any]] = []
    targets = list(column_names or [])
    if not targets:
        clean = _strip_comments(sql)
        targets = re.findall(r"(?:`|\")?([a-zA-Z_][\w]*)`?\.(?:`|\")?([a-zA-Z_][\w]*)`?", clean)
        targets += [(m,) for m in re.findall(r"(?:SELECT|,)\s+(?:`|\")?([a-zA-Z_*][\w]*)`?", clean, re.I)]

    seen = set()
    for item in targets:
        name = item[-1] if isinstance(item, tuple) else str(item)
        if not name or name == "*" or name in seen:
            continue
        seen.add(name)
        for pattern, label in SENSITIVE_FIELD_PATTERNS:
            if re.search(pattern, name):
                warnings.append({
                    "level": RISK_LEVEL_WARN,
                    "code": "SENSITIVE_FIELD",
                    "message": f"字段「{name}」可能涉及{label}，请注意脱敏与合规",
                    "field": name,
                })
                break
    return warnings


def check_sql_risks(sql: str) -> List[Dict[str, Any]]:
    """执行前风险拦截（返回警告列表，不阻断执行）"""
    warnings: List[Dict[str, Any]] = []
    clean = _strip_comments(sql).strip()
    upper = clean.upper()

    if re.search(r"SELECT\s+\*", upper):
        if "WHERE" not in upper:
            warnings.append({
                "level": RISK_LEVEL_DANGER,
                "code": "SELECT_STAR_NO_WHERE",
                "message": "全表 SELECT * 且无 WHERE 条件，可能扫描大量数据",
            })
        else:
            warnings.append({
                "level": RISK_LEVEL_WARN,
                "code": "SELECT_STAR",
                "message": "使用了 SELECT *，建议明确指定所需字段",
            })

    if "WHERE" not in upper and "LIMIT" not in upper and "ROWNUM" not in upper and "TOP " not in upper:
        if upper.startswith("SELECT") or upper.startswith("WITH"):
            warnings.append({
                "level": RISK_LEVEL_WARN,
                "code": "NO_FILTER_NO_LIMIT",
                "message": "查询未包含 WHERE 或 LIMIT，可能返回大量数据",
            })

    # 跨库引用（简单启发式）
    if re.search(r"(?i)\bFROM\s+[\w`]+\.[\w`]+\.[\w`]+", clean):
        warnings.append({
            "level": RISK_LEVEL_INFO,
            "code": "CROSS_CATALOG",
            "message": "检测到跨库/跨 Catalog 引用，请确认权限与性能影响",
        })

    warnings.extend(detect_sensitive_fields(sql))
    return warnings
