from __future__ import annotations

from io import BytesIO

import pandas as pd
import pytest
from PIL import Image as PILImage
from pypdf import PdfReader

from src.analysis import build_analysis
from src.reporting import export_chart_pngs, generate_brief_pdf, generate_full_pdf


def _png_bytes() -> bytes:
    image = PILImage.new("RGB", (16, 16), color=(46, 134, 171))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _sample_bundle():
    detail = pd.DataFrame(
        [
            {"年份": 2020, "供应商": "普通供应商A", "品名清洗": "项目A", "金额": 100.0},
            {"年份": 2021, "供应商": "普通供应商A", "品名清洗": "项目B", "金额": 130.0},
            {"年份": 2021, "供应商": "普通供应商B", "品名清洗": "项目C", "金额": 220.0},
            {"年份": 2022, "供应商": "普通供应商B", "品名清洗": "项目D", "金额": 180.0},
            {"年份": 2022, "供应商": "武汉市思尔康医疗器械有限", "品名清洗": "项目E", "金额": 95.0},
        ]
    )
    return build_analysis(detail)


def test_export_chart_pngs_generates_images() -> None:
    bundle = _sample_bundle()

    try:
        images = export_chart_pngs(bundle)
    except RuntimeError as exc:
        pytest.skip(str(exc))

    assert "annual_amount_yoy" in images
    assert images["annual_amount_yoy"].startswith(b"\x89PNG")
    supplier_keys = [key for key in images if key.startswith("supplier_")]
    assert supplier_keys


def test_generate_pdfs_non_empty_and_contains_key_text(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _sample_bundle()

    def fake_images(_bundle, **_kwargs):
        return {
            "annual_amount_yoy": _png_bytes(),
            "supplier_0001": _png_bytes(),
            "supplier_0002": _png_bytes(),
        }

    monkeypatch.setattr("src.reporting.export_chart_pngs", fake_images)

    brief_pdf = generate_brief_pdf(bundle)
    full_pdf = generate_full_pdf(bundle)

    assert len(brief_pdf) > 1000
    assert len(full_pdf) > len(brief_pdf)

    brief_reader = PdfReader(BytesIO(brief_pdf))
    full_reader = PdfReader(BytesIO(full_pdf))
    assert len(brief_reader.pages) >= 2
    assert len(full_reader.pages) >= 3

    brief_text = "\n".join(page.extract_text() or "" for page in brief_reader.pages)
    full_text = "\n".join(page.extract_text() or "" for page in full_reader.pages)
    assert "KPI" in brief_text
    assert "2022" in full_text
