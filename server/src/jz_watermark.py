from __future__ import annotations

import hashlib
import hmac
import statistics
from typing import Final

import pymupdf

from watermarking_method import (
    InvalidKeyError,
    SecretNotFoundError,
    WatermarkingError,
    WatermarkingMethod,
    load_pdf_bytes,
)


class JZDotGridWatermark(WatermarkingMethod):
    """
    Hide an authenticated, encrypted watermark as faint grey dots in the
    page margins.

    Every bit uses a pair of neighbouring spots, A and B. A dot in A means 1,
    a dot in B means 0. The reader renders the page in greyscale and only
    asks which spot is darker, so a tinted, darkened or rasterized page can
    still be read.

    The dots carry one fixed-size frame, repeated as often as it fits:

        frame     = MAC (16 bytes) + ciphertext
        plaintext = length (1 byte) + secret, padded to _MAX_SECRET bytes
        MAC       = HMAC-SHA256(key, plaintext), first 16 bytes
        keystream = HMAC-SHA256(key, MAC + counter), so it is deterministic
                    and still unique per secret (synthetic IV)

    The reader combines the copies with a majority vote, decrypts, and
    accepts the result only if the MAC matches.
    """

    name: Final[str] = "JZ Dot Grid Watermark"

    _CONTEXT: Final[bytes] = b"tatou:dotgrid:v1:"
    _MAX_SECRET: Final[int] = 64            # bytes of UTF-8
    _MAC_SIZE: Final[int] = 16              # bytes
    _FRAME_BITS: Final[int] = (_MAC_SIZE + 1 + _MAX_SECRET) * 8

    # Layout, in points on an A4-wide page. Scaled with the page width,
    # so a page that was rescaled still lines up.
    _A4_WIDTH: Final[float] = 595.0
    _INSET: Final[float] = 6.0              # gap between page edge and band
    _DEPTH: Final[float] = 24.0             # how far the band reaches inwards
    _PITCH: Final[float] = 3.0              # distance between spot centres
    _DOT: Final[float] = 1.2                # dot width and height
    _GREY: Final[float] = 0.96              # about 245 of 255

    # Reading
    _DPI: Final[int] = 150
    _CLEAN_STD: Final[float] = 5.0          # max brightness spread of a usable band
    _MIN_DIFF: Final[int] = 2               # smaller A/B differences are noise
    _MIN_CONTRAST: Final[float] = 5.0       # Check X: average |A - B| of the best band

    @staticmethod
    def get_usage() -> str:
        return (
            "Embeds an authenticated watermark in the page content. "
            f"Secrets up to {JZDotGridWatermark._MAX_SECRET} bytes. "
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
            applicable = (
                doc.page_count > 0
                and not doc.is_encrypted
                and any(any(self._writable_slots(page)) for page in doc)
            )
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

        bits = self._to_bits(self._build_frame(secret, key))

        doc = pymupdf.open(stream=data, filetype="pdf")
        written = False

        for page in doc:
            unit = self._unit(page.rect)
            shape = page.new_shape()
            drawn = False

            for index, spot_a, spot_b in self._writable_slots(page):
                centre = spot_a if bits[index % len(bits)] else spot_b
                shape.draw_rect(self._dot_rect(centre, unit))
                drawn = True

            if drawn:
                shape.finish(color=None, fill=(self._GREY,) * 3, width=0)
                shape.commit()
                written = True

        if not written:
            doc.close()
            raise WatermarkingError("No page has a clean margin large enough for the watermark")

        # Keep the file /ID, which PyMuPDF would otherwise make random on every save.
        output = doc.tobytes(no_new_id=True)
        doc.close()

        return output

    def read_secret(self, pdf, key: str) -> str:
        data = load_pdf_bytes(pdf)

        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string")

        doc = pymupdf.open(stream=data, filetype="pdf")
        votes = [0] * self._FRAME_BITS
        best_contrast = 0.0

        for page in doc:
            pix = self._render(page)
            bands = self._bands(page.rect)
            usable = self._usable_slots(bands)
            index = 0

            for _, pairs in bands:
                # B - A is positive when A is darker, which means a 1.
                diffs = [self._brightness(pix, b) - self._brightness(pix, a) for a, b in pairs]

                if diffs:
                    best_contrast = max(best_contrast, statistics.mean(abs(d) for d in diffs))

                for diff in diffs:
                    if index < usable and abs(diff) >= self._MIN_DIFF:
                        votes[index % self._FRAME_BITS] += 1 if diff > 0 else -1
                    index += 1

        doc.close()

        # Check X: are there dots at all? This does not use the key.
        if best_contrast < self._MIN_CONTRAST:
            raise SecretNotFoundError("No dot grid watermark found")

        frame = self._from_bits([1 if vote > 0 else 0 for vote in votes])
        stored_mac = frame[: self._MAC_SIZE]
        ciphertext = frame[self._MAC_SIZE :]

        plaintext = self._xor(ciphertext, self._keystream(key, stored_mac, len(ciphertext)))

        # Check Y: does the watermark belong to this key, and is it intact?
        if not hmac.compare_digest(stored_mac, self._mac(key, plaintext)):
            raise InvalidKeyError("Provided key failed to authenticate the watermark")

        length = plaintext[0]
        return plaintext[1 : 1 + length].decode("utf-8")

    # ------------------------------------------------------------------
    # Payload: MAC + encrypted, padded secret
    # ------------------------------------------------------------------

    def _build_frame(self, secret: str, key: str) -> bytes:
        secret_bytes = secret.encode("utf-8")

        if len(secret_bytes) > self._MAX_SECRET:
            raise ValueError(f"Secret must be at most {self._MAX_SECRET} bytes")

        plaintext = bytes([len(secret_bytes)]) + secret_bytes.ljust(self._MAX_SECRET, b"\0")
        mac = self._mac(key, plaintext)

        return mac + self._xor(plaintext, self._keystream(key, mac, len(plaintext)))

    def _mac(self, key: str, plaintext: bytes) -> bytes:
        return hmac.new(
            key.encode("utf-8"),
            self._CONTEXT + b"mac:" + plaintext,
            hashlib.sha256,
        ).digest()[: self._MAC_SIZE]

    def _keystream(self, key: str, nonce: bytes, length: int) -> bytes:
        stream = b""
        counter = 0

        while len(stream) < length:
            stream += hmac.new(
                key.encode("utf-8"),
                self._CONTEXT + b"stream:" + nonce + counter.to_bytes(4, "big"),
                hashlib.sha256,
            ).digest()
            counter += 1

        return stream[:length]

    @staticmethod
    def _xor(data: bytes, stream: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(data, stream))

    @staticmethod
    def _to_bits(data: bytes) -> list[int]:
        return [(byte >> (7 - i)) & 1 for byte in data for i in range(8)]

    @staticmethod
    def _from_bits(bits: list[int]) -> bytes:
        return bytes(
            int("".join(str(bit) for bit in bits[i : i + 8]), 2)
            for i in range(0, len(bits), 8)
        )

    # ------------------------------------------------------------------
    # Layout: where the A/B spots are on a page
    # ------------------------------------------------------------------

    def _unit(self, rect: pymupdf.Rect) -> float:
        return rect.width / self._A4_WIDTH

    def _bands(self, rect: pymupdf.Rect) -> list[tuple[pymupdf.Rect, list]]:
        """Return the four edge bands as (band rectangle, list of (A, B) spot centres)."""
        unit = self._unit(rect)
        inset = self._INSET * unit
        depth = self._DEPTH * unit
        width, height = rect.width, rect.height

        areas = [
            pymupdf.Rect(inset, inset, width - inset, inset + depth),                           # top
            pymupdf.Rect(inset, height - inset - depth, width - inset, height - inset),         # bottom
            pymupdf.Rect(inset, inset + depth, inset + depth, height - inset - depth),          # left
            pymupdf.Rect(width - inset - depth, inset + depth, width - inset, height - inset - depth),  # right
        ]

        return [(area, self._pairs_in(area, self._PITCH * unit)) for area in areas]

    @staticmethod
    def _pairs_in(area: pymupdf.Rect, pitch: float) -> list:
        """Fill an area row by row with side-by-side (A, B) spot centres."""
        pairs = []
        y = area.y0 + pitch / 2

        while y < area.y1:
            x = area.x0 + pitch / 2
            while x + pitch < area.x1:
                pairs.append(((x, y), (x + pitch, y)))
                x += 2 * pitch
            y += pitch

        return pairs

    def _usable_slots(self, bands: list) -> int:
        """Number of slots holding whole copies of the frame."""
        total = sum(len(pairs) for _, pairs in bands)
        return total - total % self._FRAME_BITS

    def _writable_slots(self, page: pymupdf.Page):
        """Yield (slot index, A, B) for every slot that gets a dot on this page.

        Bands whose margin is not plain background (text, images) are skipped.
        Slot indexes stay fixed, so the reader never needs to know which bands
        were skipped: those slots just give no votes.
        """
        pix = self._render(page)
        bands = self._bands(page.rect)
        usable = self._usable_slots(bands)
        index = 0

        for area, pairs in bands:
            clean = self._is_clean(pix, area)
            for spot_a, spot_b in pairs:
                if clean and index < usable:
                    yield index, spot_a, spot_b
                index += 1

    def _dot_rect(self, centre: tuple[float, float], unit: float) -> pymupdf.Rect:
        half = self._DOT * unit / 2
        x, y = centre
        return pymupdf.Rect(x - half, y - half, x + half, y + half)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, page: pymupdf.Page) -> pymupdf.Pixmap:
        return page.get_pixmap(dpi=self._DPI, colorspace=pymupdf.csGRAY)

    def _brightness(self, pix: pymupdf.Pixmap, point: tuple[float, float]) -> int:
        zoom = self._DPI / 72
        return pix.pixel(int(point[0] * zoom), int(point[1] * zoom))[0]

    def _is_clean(self, pix: pymupdf.Pixmap, area: pymupdf.Rect) -> bool:
        zoom = self._DPI / 72
        values = [
            pix.pixel(x, y)[0]
            for y in range(int(area.y0 * zoom), int(area.y1 * zoom))
            for x in range(int(area.x0 * zoom), int(area.x1 * zoom))
        ]
        return bool(values) and statistics.pstdev(values) < self._CLEAN_STD


__all__ = ["JZDotGridWatermark"]
