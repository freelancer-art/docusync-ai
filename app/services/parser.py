import os

from google import genai
from google.genai import types
from pydantic import ValidationError

from app.schemas.document import ExtractedInvoiceData

# Initialize Gemini client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def parse_document_data(file_bytes: bytes, mime_type: str) -> dict:
    """
    Extracts structured accounting data from raw PDF or image bytes using Gemini 2.5 Flash
    with strict JSON output constrained by Pydantic schema.
    """
    prompt = """
    You are an expert Chartered Accountant document parser. 
    Analyze the attached financial document (PDF or image) and extract all accounting fields.
    Accurately extract all totals, vendor GSTIN, invoice identifiers, and line item details.
    If a field is missing or unreadable, populate reasonable defaults or set strings to None.
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type=mime_type,
                ),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractedInvoiceData,
                temperature=0.1,  # Low temperature for precise factual extraction
            ),
        )

        # Parse output using Pydantic model for validation
        structured_data = ExtractedInvoiceData.model_validate_json(response.text)
        return structured_data.model_dump()

    except (ValidationError, ValueError, AttributeError, RuntimeError) as e:
        print(f"LLM Parsing failed: {e!s}")
        # Return empty structured schema fallback on failure
        return ExtractedInvoiceData().model_dump()