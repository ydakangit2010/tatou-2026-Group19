from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from ak_metadata_watermark import AKMetadataWatermark
from jz_watermark import JZDotGridWatermark
from watermarking_method import InvalidKeyError, SecretNotFoundError


@pytest.fixture
def real_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Tatou combined watermark test")
    doc.save(path)
    doc.close()

    return path


def _combined(pdf: Path, secret: str, key: str) -> bytes:
    dotted = JZDotGridWatermark().add_watermark(pdf, secret=secret, key=key)
    return AKMetadataWatermark().add_watermark(dotted, secret=secret, key=key)


def _rasterize(pdf_bytes: bytes) -> bytes:
    src = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out = pymupdf.open()

    for page in src:
        jpeg = page.get_pixmap(dpi=150).tobytes("jpeg", jpg_quality=90)
        new_page = out.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, stream=jpeg)

    return out.tobytes()


def test_both_layers_read_back(real_pdf: Path):
    watermarked = _combined(real_pdf, "Group_07", "derived-key")

    assert JZDotGridWatermark().read_secret(watermarked, "derived-key") == "Group_07"
    assert AKMetadataWatermark().read_secret(watermarked, "derived-key") == "Group_07"


def test_both_layers_reject_wrong_key(real_pdf: Path):
    watermarked = _combined(real_pdf, "Group_07", "derived-key")

    with pytest.raises(InvalidKeyError):
        JZDotGridWatermark().read_secret(watermarked, "wrong-key")

    with pytest.raises(InvalidKeyError):
        AKMetadataWatermark().read_secret(watermarked, "wrong-key")


def test_dot_layer_survives_when_metadata_is_lost(real_pdf: Path):
    rasterized = _rasterize(_combined(real_pdf, "Group_07", "derived-key"))

    with pytest.raises(SecretNotFoundError):
        AKMetadataWatermark().read_secret(rasterized, "derived-key")

    assert JZDotGridWatermark().read_secret(rasterized, "derived-key") == "Group_07"
