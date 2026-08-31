import io

import pdfplumber
import pytesseract


class OCREngine:
    @staticmethod
    def _to_stream_or_path(
        file_input: str | bytes | io.BytesIO,
    ) -> str | io.BytesIO:
        """Ensures bytes inputs are converted to seekable BytesIO streams for pdfplumber."""
        if isinstance(file_input, bytes):
            return io.BytesIO(file_input)
        return file_input

    @staticmethod
    def extract_text(file_path: str | bytes | io.BytesIO, filename: str = "") -> str:
        """
        Attempts digital text extraction via pdfplumber.
        If minimal or no text is found, falls back to pytesseract OCR.
        Returns extracted_text string.
        """
        extracted_text = ""
        target_input = OCREngine._to_stream_or_path(file_path)

        try:
            with pdfplumber.open(target_input) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"
        except (pdfplumber.pdf.PDFSyntaxError, OSError, ValueError, TypeError):
            extracted_text = ""

        # If text is empty or low character count, trigger OCR fallback
        if len(extracted_text.strip()) < 50:
            extracted_text = OCREngine._ocr_pdf(file_path)

        return extracted_text

    @staticmethod
    def _ocr_pdf(file_path: str | bytes | io.BytesIO) -> str:
        ocr_text = ""
        target_input = OCREngine._to_stream_or_path(file_path)

        try:
            with pdfplumber.open(target_input) as pdf:
                for page in pdf.pages:
                    # Convert PDF page to high-res image for pytesseract
                    image = page.to_image(resolution=300).original
                    ocr_text += pytesseract.image_to_string(image) + "\n"
        except (pdfplumber.pdf.PDFSyntaxError, pytesseract.TesseractError, OSError, ValueError, TypeError):
            # Safely handle malformed PDF streams or unparseable files
            return ocr_text

        return ocr_text


ocr_engine = OCREngine()