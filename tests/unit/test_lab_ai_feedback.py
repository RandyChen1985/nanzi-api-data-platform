"""AI 反馈时间范围工具"""
from app.services.lab_enhancement_service import LabEnhancementService


def test_feedback_time_bounds_defaults():
    start, end = LabEnhancementService._feedback_time_bounds(None, None)
    assert len(start) == 19
    assert len(end) == 19
    assert start < end


def test_feedback_time_bounds_custom():
    start, end = LabEnhancementService._feedback_time_bounds("2026-01-01T00:00", "2026-01-02T23:59")
    assert start.startswith("2026-01-01")
    assert end.startswith("2026-01-02")
