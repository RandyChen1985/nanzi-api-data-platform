import re
from pathlib import Path


DASHBOARD_SOURCE = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "views" / "Dashboard.vue"
).read_text(encoding="utf-8")


def test_sidebar_brand_text_uses_parent_centering_without_vertical_offset():
    brand_header = re.search(
        r"<!-- Brand Header -->(?P<section>.*?)(?=<!-- Navigation)",
        DASHBOARD_SOURCE,
        flags=re.DOTALL,
    )

    assert brand_header, "Dashboard brand header markup should remain discoverable"
    section = brand_header.group("section")
    assert "h-16 flex items-center" in section
    assert "w-8 h-8" in section
    assert "flex flex-col justify-center" in section
    assert "-translate-y" not in section
