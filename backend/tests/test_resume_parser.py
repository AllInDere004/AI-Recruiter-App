import unittest
from io import BytesIO
from unittest.mock import patch

import pymupdf as fitz
from starlette.datastructures import UploadFile

from app.services.resume_parser import PDFExtractionError, PDFTooLargeError, extract_text_from_pdf


def make_pdf(*pages, encrypted=False):
    with fitz.open() as document:
        for text in pages or [""]:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        options = {"encryption": fitz.PDF_ENCRYPT_AES_256, "owner_pw": "owner", "user_pw": "password"} if encrypted else {}
        return document.tobytes(**options)


class ResumeParserTests(unittest.IsolatedAsyncioTestCase):
    async def extract(self, content):
        upload = UploadFile(filename="resume.pdf", file=BytesIO(content))
        try:
            return await extract_text_from_pdf(upload)
        finally:
            await upload.close()

    async def test_extracts_and_cleans_multiple_pages(self):
        text = await self.extract(make_pdf("Jane   Doe\nPython developer", "Education: Computer Science"))
        self.assertIn("Jane Doe", text)
        self.assertIn("Python developer", text)
        self.assertIn("Education: Computer Science", text)
        self.assertNotIn("   ", text)

    async def test_rejects_empty_upload(self):
        with self.assertRaisesRegex(PDFExtractionError, "empty"):
            await self.extract(b"")

    async def test_rejects_corrupt_pdf(self):
        with self.assertRaisesRegex(PDFExtractionError, "readable PDF"):
            await self.extract(b"%PDF-1.7 this is not a valid PDF")

    async def test_rejects_textless_pdf(self):
        with self.assertRaisesRegex(PDFExtractionError, "OCR"):
            await self.extract(make_pdf(""))

    async def test_rejects_encrypted_pdf(self):
        with self.assertRaisesRegex(PDFExtractionError, "Password-protected"):
            await self.extract(make_pdf("Private resume", encrypted=True))

    async def test_limits_in_memory_upload_size(self):
        with patch("app.services.resume_parser.MAX_PDF_BYTES", 16):
            with self.assertRaises(PDFTooLargeError):
                await self.extract(b"x" * 17)
