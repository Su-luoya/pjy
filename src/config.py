"""Project-wide constants and reusable regex patterns."""

from __future__ import annotations

import re

REQUIRED_COLUMNS = ["Unnamed: 0", "开单日期", "单据号", "品名规格", "金额"]
INVALID_OPEN_DATE_MARKERS = {"", "合计", "小计"}

YEAR_PATTERN = re.compile(r"(20\d{2})")
SUPPLIER_MARKER_PATTERN = re.compile(r"^\s*供应商\s*:\s*(.*)\s*$")

# Remove trailing source ID in product names, supporting both closed and unclosed brackets.
CLOSED_TRAILING_ID_PATTERN = re.compile(r"\[[0-9]{6,}[^\]]*\]\s*$")
UNCLOSED_TRAILING_ID_PATTERN = re.compile(r"\[[0-9]{6,}.*$")

SUPPLIER_ALIAS_MAP = {
    "郁小梅": "柳辉",
}

EXCLUDED_SUPPLIER_KEYWORDS = []


def supplier_filter_short_label(excluded_keywords: list[str] | None = None) -> str:
    """Short label for supplier filtering mode."""
    keywords = EXCLUDED_SUPPLIER_KEYWORDS if excluded_keywords is None else excluded_keywords
    active = [keyword for keyword in keywords if keyword]
    if not active:
        return "当前未排除"
    return "按关键词排除"


def supplier_filter_description(excluded_keywords: list[str] | None = None) -> str:
    """Detailed description for supplier filtering mode."""
    keywords = EXCLUDED_SUPPLIER_KEYWORDS if excluded_keywords is None else excluded_keywords
    active = [keyword for keyword in keywords if keyword]
    if not active:
        return "当前未排除供应商"
    return "按关键词排除：" + "、".join(active)
