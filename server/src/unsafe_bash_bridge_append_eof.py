"""unsafe_bash_bridge_append_eof.py

Toy watermarking method that appends a payload after the PDF's final EOF marker.

This implementation avoids executing shell commands with user-controlled input.
"""

from __future__ import annotations

from typing import Final

from watermarking_method import (
    PdfSource,
    SecretNotFoundError,
    WatermarkingMethod,
    load_pdf_bytes,
)


class UnsafeBashBridgeAppendEOF(WatermarkingMethod):
    """Toy method that appends a watermark record after the PDF EOF."""

    name: Final[str] = "bash-bridge-eof"

    @staticmethod
    def get_usage() -> str:
        return (
            "Toy method that appends a watermark record after the PDF EOF. "
            "Position and key are ignored."
        )

    def add_watermark(
        self,
        pdf: PdfSource,
        secret: str,
        key: str,
        position: str | None = None,
    ) -> bytes:
        """Return a new PDF with a watermark record appended.

        The position and key parameters are accepted for API compatibility
        but ignored by this method.
        """
        data = load_pdf_bytes(pdf)
        return data + secret.encode("utf-8")

    def is_watermark_applicable(
        self,
        pdf: PdfSource,
        position: str | None = None,
    ) -> bool:
        return True

    def read_secret(
        self,
        pdf: PdfSource,
        key: str,
    ) -> str:
        """Extract the secret stored after the final PDF EOF marker."""
        data = load_pdf_bytes(pdf)

        marker = b"%%EOF"
        pos = data.rfind(marker)

        if pos == -1:
            raise SecretNotFoundError("PDF EOF marker not found")

        secret_data = data[pos + len(marker):]
        secret_data = secret_data.lstrip(b"\r\n")

        if not secret_data:
            raise SecretNotFoundError("No watermark secret found")

        return secret_data.decode("utf-8")


__all__ = ["UnsafeBashBridgeAppendEOF"]
