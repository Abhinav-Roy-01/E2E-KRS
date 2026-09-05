"""
Text extraction: PyMuPDF for direct/selectable text (fast path), PaddleOCR-VL
for scanned pages with no extractable text (fallback path).

SWAPPED FROM TESSERACT -- flag for the team: PaddleOCR-VL's documented
language support explicitly confirms Devanagari (Hindi/Marathi), Telugu,
and Tamil. Malayalam and Kannada are NOT explicitly confirmed in its
release notes as of this writing. The earlier comparative benchmark found
Tesseract was the only tested library supporting Malayalam at all -- if
Malayalam documents are a real, frequent case, test PaddleOCR-VL against
a real Malayalam scan before trusting this swap for that language
specifically. Not yet verified either way here -- flagging honestly rather
than assuming it works.

Plain text/markdown files (.md, .txt) are handled by the caller directly
(decode bytes) -- they never reach this module.
"""
import fitz  # PyMuPDF
from paddleocr import PaddleOCR

_ocr_engine = None


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        # lang="en" is PaddleOCR's default multi-script detection model;
        # swap per-language if you need to force a specific script.
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="en")
    return _ocr_engine


def extract_text_pdf(filepath: str) -> str:
    """Direct text extraction -- try this first, it's much faster than OCR."""
    doc = fitz.open(filepath)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text.strip()


def extract_text_ocr(filepath: str) -> str:
    """Fallback for scanned PDFs with no selectable text, via PaddleOCR-VL."""
    doc = fitz.open(filepath)
    engine = _get_ocr_engine()
    full_text = []

    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")

        tmp_path = f"/tmp/_ocr_page_{page.number}.png"
        with open(tmp_path, "wb") as f:
            f.write(img_bytes)

        result = engine.ocr(tmp_path, cls=True)
        page_text = "\n".join(line[1][0] for block in result for line in block)
        full_text.append(page_text)

    doc.close()
    return "\n".join(full_text).strip()


def parse_pdf(filepath: str) -> tuple[str, bool]:
    """
    Returns (text, ocr_used). Tries direct extraction first; falls back to
    OCR only if the PDF appears to be a scanned image (near-empty direct
    extraction).
    """
    text = extract_text_pdf(filepath)
    if len(text) < 20:
        return extract_text_ocr(filepath), True
    return text, False
