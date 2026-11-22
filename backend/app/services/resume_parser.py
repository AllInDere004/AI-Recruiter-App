import re

import pymupdf as fitz
from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool


MAX_PDF_BYTES = 10 * 1024 * 1024


class PDFExtractionError(ValueError):
    pass


class PDFTooLargeError(PDFExtractionError):
    pass


def _extract_pdf_text(content: bytes) -> str:
    try:
        with fitz.open(stream=content, filetype="pdf") as document:
            if document.needs_pass:
                raise PDFExtractionError("Password-protected PDFs are not supported. Upload an unlocked PDF.")
            text = "\n".join(page.get_text("text", sort=True) for page in document)
    except PDFExtractionError:
        raise
    except (fitz.FileDataError, RuntimeError, ValueError):
        raise PDFExtractionError("The uploaded file is not a readable PDF.") from None

    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise PDFExtractionError("No readable text was found. Scanned resumes require OCR; upload a text-based PDF.")
    return text


async def extract_text_from_pdf(file: UploadFile) -> str:
    content = await file.read(MAX_PDF_BYTES + 1)
    if len(content) > MAX_PDF_BYTES:
        raise PDFTooLargeError("PDF must be 10 MB or smaller.")
    if not content:
        raise PDFExtractionError("The uploaded PDF is empty.")
    return await run_in_threadpool(_extract_pdf_text, content)
