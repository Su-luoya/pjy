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
