from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from jz_watermark import JZDotGridWatermark
from watermarking_method import InvalidKeyError, SecretNotFoundError


@pytest.fixture
def real_pdf(tmp_path: Path) -> Path:
    """One A4 page with body text and one line running off the right edge."""
    path = tmp_path / "sample.pdf"

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Tatou dot grid watermark test")
    page.insert_text((300, 500), "This line runs past the right edge of the page on purpose")
    doc.save(path)
    doc.close()

    return path


def _rasterize(pdf_bytes: bytes) -> bytes:
    """Turn every page into a JPEG image, like a screenshot or print-to-image."""
    src = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out = pymupdf.open()

    for page in src:
        jpeg = page.get_pixmap(dpi=150).tobytes("jpeg", jpg_quality=90)
        new_page = out.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, stream=jpeg)

    return out.tobytes()


def test_roundtrip(real_pdf: Path):
    method = JZDotGridWatermark()

    watermarked = method.add_watermark(real_pdf, secret="individual-secret", key="correct-key")

    assert watermarked.startswith(b"%PDF")
    assert method.read_secret(watermarked, "correct-key") == "individual-secret"


def test_rmap_sized_secret_roundtrip(real_pdf: Path):
    method = JZDotGridWatermark()
    secret = "0123456789abcdef" * 2  # 32 hex characters, like an RMAP link

    watermarked = method.add_watermark(real_pdf, secret=secret, key="correct-key")

    assert method.read_secret(watermarked, "correct-key") == secret


def test_wrong_key_rejected(real_pdf: Path):
    method = JZDotGridWatermark()

    watermarked = method.add_watermark(real_pdf, secret="individual-secret", key="correct-key")

    with pytest.raises(InvalidKeyError):
        method.read_secret(watermarked, "wrong-key")


def test_unwatermarked_pdf_has_no_secret(real_pdf: Path):
    method = JZDotGridWatermark()

    with pytest.raises(SecretNotFoundError):
        method.read_secret(real_pdf, "correct-key")


def test_survives_rasterization(real_pdf: Path):
    method = JZDotGridWatermark()

    watermarked = method.add_watermark(real_pdf, secret="individual-secret", key="correct-key")

    assert method.read_secret(_rasterize(watermarked), "correct-key") == "individual-secret"


def test_deterministic(real_pdf: Path):
    method = JZDotGridWatermark()

    first = method.add_watermark(real_pdf, secret="individual-secret", key="correct-key")
    second = method.add_watermark(real_pdf, secret="individual-secret", key="correct-key")

    assert first == second


def test_too_long_secret_rejected(real_pdf: Path):
    method = JZDotGridWatermark()

    with pytest.raises(ValueError):
        method.add_watermark(real_pdf, secret="x" * 65, key="correct-key")


def test_applicability(real_pdf: Path):
    method = JZDotGridWatermark()
    assert method.is_watermark_applicable(real_pdf) is True
