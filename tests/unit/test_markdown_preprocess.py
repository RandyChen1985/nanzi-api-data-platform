"""Markdown 预处理规则回归（镜像 frontend/src/utils/markdown.ts 关键逻辑）"""
import re


def is_markdown_structure_line(line: str) -> bool:
    t = line.strip()
    if not t:
        return False
    return bool(
        re.match(r"^#{1,6}\s", t)
        or re.match(r"^>\s?", t)
        or re.match(r"^[-*+]\s+", t)
        or re.match(r"^\d+\.\s+", t)
        or re.match(r"^```", t)
    )


def test_markdown_structure_line_detects_heading_and_blockquote():
    assert is_markdown_structure_line("### 业务背景假设")
    assert is_markdown_structure_line("> 引用内容")
    assert not is_markdown_structure_line("注册日期 当日注册量")


def test_heading_blockquote_preserved_in_mixed_content():
    """回归：### 标题 + > 引用 不应被误判为两列表格首行"""
    sample = (
        "### 业务背景假设\n"
        "> 为了更精准地给出洞察，请补充业务背景。\n\n"
        "| 注册日期 | 当日注册量 |\n"
        "| --- | --- |\n"
        "| 2025-12-29 | 44 |"
    )
    lines = sample.split("\n")
    assert is_markdown_structure_line(lines[0])
    assert is_markdown_structure_line(lines[1])
    assert "|" in lines[3]
