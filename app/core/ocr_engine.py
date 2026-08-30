import pdfplumber
import pytesseract
from PIL import Image

class OCREngine:
    @staticmethod
    def extract_text(file_path: str) -> tuple[str, str]:
        """
        Attempts digital text extraction via pdfplumber.
        If minimal or no text is found, falls back to pytesseract OCR.
        Returns: (extracted_text, method_used)
        """
        extracted_text = ""
        method = "pdfplumber"

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"
        except Exception:
            extracted_text = ""

        # If text is empty or extremely low character count, trigger OCR fallback
        if len(extracted_text.strip()) < 50:
            method = "tesseract_ocr"
            extracted_text = OCREngine._ocr_pdf(file_path)

        return extracted_text, method

    @staticmethod
    def _ocr_pdf(file_path: str) -> str:
        ocr_text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                # Convert PDF page to high-res image for pytesseract
                image = page.to_image(resolution=300).original
                ocr_text += pytesseract.image_to_string(image) + "\n"
        return ocr_text

ocr_engine = OCREngine()