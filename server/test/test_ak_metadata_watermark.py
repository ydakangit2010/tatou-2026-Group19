from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from ak_metadata_watermark import AKMetadataWatermark
from watermarking_method import InvalidKeyError, SecretNotFoundError


@pytest.fixture
def real_pdf(tmp_path: Path) -> Path:
    """Create a small valid one-page PDF that PyMuPDF can modify."""
    path = tmp_path / "sample.pdf"

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Tatou AK metadata watermark test")
    doc.save(path)
    doc.close()

    return path


def test_roundtrip(real_pdf: Path):
    method = AKMetadataWatermark()

    watermarked = method.add_watermark(
        real_pdf,
        secret="individual-secret",
        key="correct-key",
    )

    assert watermarked.startswith(b"%PDF")
    assert method.read_secret(watermarked, "correct-key") == "individual-secret"


def test_wrong_key_rejected(real_pdf: Path):
    method = AKMetadataWatermark()

    watermarked = method.add_watermark(
        real_pdf,
        secret="individual-secret",
        key="correct-key",
    )

    with pytest.raises(InvalidKeyError):
        method.read_secret(watermarked, "wrong-key")


def test_unwatermarked_pdf_has_no_secret(real_pdf: Path):
    method = AKMetadataWatermark()

    with pytest.raises(SecretNotFoundError):
        method.read_secret(real_pdf, "correct-key")


def test_existing_metadata_is_preserved(real_pdf: Path):
    doc = pymupdf.open(real_pdf)
    metadata = dict(doc.metadata or {})
    metadata["title"] = "Original title"
    metadata["keywords"] = "course; softsec"
    doc.set_metadata(metadata)
    doc.save(real_pdf.with_name("metadata.pdf"))
    doc.close()

    source = real_pdf.with_name("metadata.pdf")
    method = AKMetadataWatermark()

    watermarked = method.add_watermark(
        source,
        secret="metadata-secret",
        key="metadata-key",
    )

    check = pymupdf.open(stream=watermarked, filetype="pdf")
    result = check.metadata or {}
    check.close()

    assert result.get("title") == "Original title"
    assert "course" in (result.get("keywords") or "")
    assert "softsec" in (result.get("keywords") or "")


def test_applicability(real_pdf: Path):
    method = AKMetadataWatermark()
    assert method.is_watermark_applicable(real_pdf) is True
