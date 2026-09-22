"""Burn the institutional watermark into served PDF bytes.

WHY THIS EXISTS
---------------
The watermark used to be a React DOM layer floating over the preview iframe
(``frontend/src/components/pdf/WatermarkOverlay.jsx``). The PDF bytes behind it
were clean, so DevTools → Network gave anyone the unwatermarked original. A
watermark that lives in the browser is decoration, not protection.

This module puts it in the bytes instead, for BOTH dispositions. Watermarking
only the download would achieve nothing: the clean file would still be one
network-tab click away on the preview page.

NON-DESTRUCTIVE
---------------
``Thesis.uploaded_file`` is never touched. Stamping happens at serve time on a
copy held in memory, so the stored original stays pristine and the watermark
can be reworded or dropped later without having damaged any archived document.

GEOMETRY NOTES — the two things that are easy to get wrong
----------------------------------------------------------
1. **Per-page sizing.** Theses routinely mix a letter-size body with a
   differently-sized scanned appendix. One fixed-size overlay would sit wrong
   on every page that isn't letter, so an overlay is built per distinct page
   size and merged scaled to that page's own mediabox.

2. **Page rotation.** ``/Rotate`` is applied by the *viewer*, after page
   content is composed. Merging an upright overlay onto a ``/Rotate 90`` page
   means the viewer then rotates the watermark too, and it reads sideways. So
   for rotated pages the overlay is built at the page's *displayed* dimensions
   and counter-rotated on the way in, cancelling out the viewer's rotation.
"""

from __future__ import annotations

import io
import logging
import math

from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.colors import Color
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Watermark text
# ---------------------------------------------------------------------------

# Deliberately NOT reusing WatermarkOverlay.jsx's WATERMARK_TEXT: that string
# mixes a hyphen and a bullet ('Studies - ... University • Preview Only'). These
# use a single consistent separator, and the two dispositions say different
# things — a preview is marked as a preview, a download is marked as property.
PREVIEW_WATERMARK = 'College of Computing Studies · Pampanga State University · Preview Only'
DOWNLOAD_WATERMARK = 'Property of Pampanga State University · College of Computing Studies'

# Bump whenever the text or the geometry below changes. This participates in
# the serve-time cache key, so incrementing it invalidates every previously
# cached artifact instead of serving stale stamps forever.
WATERMARK_VERSION = 1


# ---------------------------------------------------------------------------
# Appearance — approximates the DOM overlay this replaces
# ---------------------------------------------------------------------------

_FONT_NAME = 'Helvetica-Bold'
_FONT_SIZE = 11
_ROTATION_DEG = -30          # matches the CSS overlay's tilt
_ALPHA = 0.15                # matches the CSS overlay's opacity
_INK = (0.25, 0.25, 0.30)    # slate-ish grey, legible on white without shouting
_COLUMN_GAP = 64             # horizontal gap between repeats of the text
_ROW_GAP = 116               # vertical gap between tiled rows


class WatermarkError(Exception):
    """Base class for a watermark that could not be applied.

    Callers catch this to convert a stamping failure into a structured
    "document unavailable" response rather than letting it surface as a 500.
    """


class EncryptedPdfError(WatermarkError):
    """The source PDF is encrypted, so it cannot be stamped.

    Raised for ANY encrypted source, including the common owner-password-only
    case that pypdf could open with an empty password. Two reasons for the
    blanket refusal: stamping would require writing out a decrypted copy,
    which silently strips whatever protection the author applied, and a
    partially-readable encrypted file is exactly the input most likely to
    produce corrupt output. An explicit refusal is the safer failure.
    """


# ---------------------------------------------------------------------------
# Overlay generation
# ---------------------------------------------------------------------------

def _build_overlay(width: float, height: float, text: str) -> bytes:
    """Render a single-page PDF of tiled, rotated watermark text.

    ``width``/``height`` are the dimensions the overlay must cover in its own
    upright space — for a rotated page that is the page's *displayed* size,
    not its mediabox.
    """
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width, height))

    pdf.saveState()
    pdf.setFont(_FONT_NAME, _FONT_SIZE)
    pdf.setFillColor(Color(*_INK, alpha=_ALPHA))
    pdf.rotate(_ROTATION_DEG)

    text_width = stringWidth(text, _FONT_NAME, _FONT_SIZE)
    step_x = text_width + _COLUMN_GAP

    # Tiling happens in the ROTATED frame, so the area that needs covering is
    # no longer the page rectangle. Sweeping ±diagonal on both axes covers the
    # page for any rotation angle without needing per-angle corner math.
    reach = math.hypot(width, height)

    row = 0
    y = -reach
    while y <= reach:
        # Stagger alternate rows so the tile reads as a texture rather than a
        # rigid grid of columns.
        x = -reach + (step_x / 2 if row % 2 else 0)
        while x <= reach:
            pdf.drawString(x, y, text)
            x += step_x
        y += _ROW_GAP
        row += 1

    pdf.restoreState()
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _overlay_transform(
    rotation: int,
    box_width: float,
    box_height: float,
    offset_x: float,
    offset_y: float,
) -> Transformation:
    """Map an overlay into a page's coordinate space, cancelling ``/Rotate``.

    ``box_width``/``box_height`` are the page's mediabox dimensions (unrotated).
    The returned transform places an overlay built at the page's displayed size
    so that, once the viewer applies ``/Rotate``, the text reads upright.

    The SIGN here matters and is not self-evident: for each quarter turn both
    rotation directions produce a box that fits the mediabox, but one of them
    lands the text upside down. Picking by "does it fit" gets it wrong half the
    time. The composition below is what actually cancels out, verified by
    measuring the on-screen baseline angle (see
    ``test_rotated_pages_render_upright``):

    * 90  — viewer maps (x,y) → (y, w−x). Overlay (h × w) through
            rotate(+90)·translate(w, 0) → (w−v, u), which the viewer then maps
            back to (u, v): the identity. Text reads exactly as drawn.
    * 270 — viewer maps (x,y) → (h−y, x). Overlay (h × w) through
            rotate(−90)·translate(0, h) → (v, h−u) → viewer → (u, v).
    * 180 — viewer maps (x,y) → (w−x, h−y). Overlay (w × h) through
            rotate(180)·translate(w, h) → (w−u, h−v) → viewer → (u, v).
    * 0   — identity.

    ``offset_x``/``offset_y`` carry the mediabox's own origin, which is not
    always (0, 0) — a cropped or imposed page can sit anywhere in user space.
    """
    if rotation == 90:
        base = Transformation().rotate(90).translate(box_width, 0)
    elif rotation == 270:
        base = Transformation().rotate(-90).translate(0, box_height)
    elif rotation == 180:
        base = Transformation().rotate(180).translate(box_width, box_height)
    else:
        base = Transformation()

    if offset_x or offset_y:
        base = base.translate(offset_x, offset_y)
    return base


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def stamp_pdf(pdf_bytes: bytes, text: str) -> bytes:
    """Return ``pdf_bytes`` with ``text`` tiled across every page.

    Page count, page sizes and page rotations are preserved. The input is not
    modified.

    Raises:
        EncryptedPdfError: the source is encrypted/password-protected.
        WatermarkError: the source is unreadable or stamping failed.
    """
    if not pdf_bytes:
        raise WatermarkError('Cannot watermark an empty byte string')

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:
        raise WatermarkError(f'Source PDF could not be parsed: {exc}') from exc

    if reader.is_encrypted:
        raise EncryptedPdfError('Source PDF is encrypted and cannot be watermarked')

    try:
        writer = PdfWriter()
        # Keyed by the overlay's own dimensions, so a mixed-size document
        # generates one overlay per distinct size instead of one per page.
        overlay_bytes_by_size: dict[tuple[float, float], bytes] = {}

        for page in reader.pages:
            mediabox = page.mediabox
            box_width = float(mediabox.width)
            box_height = float(mediabox.height)
            rotation = int(page.rotation or 0) % 360

            # A quarter-turn swaps what the reader actually sees.
            if rotation in (90, 270):
                overlay_width, overlay_height = box_height, box_width
            else:
                overlay_width, overlay_height = box_width, box_height

            size_key = (round(overlay_width, 2), round(overlay_height, 2))
            if size_key not in overlay_bytes_by_size:
                overlay_bytes_by_size[size_key] = _build_overlay(
                    overlay_width, overlay_height, text,
                )

            # Re-parsed per page rather than sharing one PageObject: merging
            # mutates the object graph, and a shared overlay page would alias
            # across pages.
            overlay_page = PdfReader(
                io.BytesIO(overlay_bytes_by_size[size_key])
            ).pages[0]

            page.merge_transformed_page(
                overlay_page,
                _overlay_transform(
                    rotation,
                    box_width,
                    box_height,
                    float(mediabox.left),
                    float(mediabox.bottom),
                ),
            )
            writer.add_page(page)

        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except WatermarkError:
        raise
    except Exception as exc:
        raise WatermarkError(f'Watermark stamping failed: {exc}') from exc
