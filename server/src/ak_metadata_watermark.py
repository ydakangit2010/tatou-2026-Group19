from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Final

import pymupdf

from watermarking_method import (
    InvalidKeyError,
    SecretNotFoundError,
    WatermarkingMethod,
    load_pdf_bytes,
)


class AKMetadataWatermark(WatermarkingMethod):
    """
    Store an authenticated watermark inside the PDF metadata.

    The secret is Base64 encoded and protected with HMAC-SHA256.
    The watermark record is stored in the PDF keywords metadata field.
    """

    name: Final[str] = "ak-metadata"

    _PREFIX: Final[str] = "TATOU-AK-META:v1:"
    _CONTEXT: Final[bytes] = b"tatou:ak-metadata:v1:"

    @staticmethod
    def get_usage() -> str:
        return (
            "Stores an authenticated watermark in the PDF metadata keywords field. "
            "Position is ignored."
        )

    def is_watermark_applicable(
        self,
        pdf,
        position: str | None = None,
    ) -> bool:
        try:
            data = load_pdf_bytes(pdf)
            doc = pymupdf.open(stream=data, filetype="pdf")
            applicable = doc.page_count > 0 and not doc.is_encrypted
            doc.close()
            return applicable
        except Exception:
            return False

    def add_watermark(
        self,
        pdf,
        secret: str,
        key: str,
        position: str | None = None,
    ) -> bytes:
        data = load_pdf_bytes(pdf)

        if not isinstance(secret, str) or not secret:
            raise ValueError("Secret must be a non-empty string")

        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string")

        secret_bytes = secret.encode("utf-8")

        mac = hmac.new(
            key.encode("utf-8"),
            self._CONTEXT + secret_bytes,
            hashlib.sha256,
        ).hexdigest()

        payload = {
            "v": 1,
            "alg": "HMAC-SHA256",
            "secret": base64.b64encode(secret_bytes).decode("ascii"),
            "mac": mac,
        }

        payload_json = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        encoded = base64.urlsafe_b64encode(payload_json).decode("ascii")
        watermark = self._PREFIX + encoded

        doc = pymupdf.open(stream=data, filetype="pdf")

        metadata = dict(doc.metadata or {})
        existing_keywords = metadata.get("keywords", "") or ""

        # Remove any older watermark made by this method.
        kept = [
            item.strip()
            for item in existing_keywords.split(";")
            if item.strip() and not item.strip().startswith(self._PREFIX)
        ]

        kept.append(watermark)
        metadata["keywords"] = "; ".join(kept)

        doc.set_metadata(metadata)
        output = doc.tobytes()
        doc.close()

        return output

    def read_secret(self, pdf, key: str) -> str:
        data = load_pdf_bytes(pdf)

        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string")

        doc = pymupdf.open(stream=data, filetype="pdf")
        metadata = doc.metadata or {}
        keywords = metadata.get("keywords", "") or ""
        doc.close()

        watermark = None

        for item in keywords.split(";"):
            item = item.strip()
            if item.startswith(self._PREFIX):
                watermark = item[len(self._PREFIX):]
                break

        if not watermark:
            raise SecretNotFoundError("No AK metadata watermark found")

        try:
            payload_json = base64.urlsafe_b64decode(watermark.encode("ascii"))
            payload = json.loads(payload_json)
            secret_bytes = base64.b64decode(payload["secret"])
            stored_mac = str(payload["mac"])
        except Exception as exc:
            raise SecretNotFoundError("Malformed AK metadata watermark") from exc

        if payload.get("v") != 1 or payload.get("alg") != "HMAC-SHA256":
            raise SecretNotFoundError("Unsupported AK metadata watermark format")

        expected_mac = hmac.new(
            key.encode("utf-8"),
            self._CONTEXT + secret_bytes,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(stored_mac, expected_mac):
            raise InvalidKeyError("Provided key failed to authenticate the watermark")

        return secret_bytes.decode("utf-8")


__all__ = ["AKMetadataWatermark"]
