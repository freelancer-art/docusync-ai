import logging

import instructor
from google import genai
from groq import Groq, GroqError
from instructor import Instructor

from app.config import settings

logger = logging.getLogger("docusync.ai_client")


def get_groq_client() -> Instructor | None:
    """Instantiates an instructor-wrapped Groq client if GROQ_API_KEY is configured."""
    api_key = getattr(settings, "GROQ_API_KEY", None)
    if not api_key:
        logger.warning("GROQ_API_KEY not set in settings.")
        return None
    try:
        raw_client = Groq(api_key=api_key)
        return instructor.from_groq(raw_client)
    except (GroqError, ValueError, RuntimeError, Exception) as e:  # noqa: BLE001
        logger.error(f"Failed to initialize Groq client: {e}")
        return None


def get_gemini_client() -> Instructor | None:
    """Instantiates an instructor-wrapped Google GenAI client if GEMINI_API_KEY is configured."""
    api_key = getattr(settings, "GEMINI_API_KEY", None) or getattr(settings, "GOOGLE_API_KEY", None)
    if not api_key:
        logger.warning("GEMINI_API_KEY / GOOGLE_API_KEY not set in settings.")
        return None
    try:
        raw_client = genai.Client(api_key=api_key)
        # Wrap Google GenAI client with explicit GEMINI_JSON mode for instructor compatibility
        return instructor.from_provider(raw_client, mode=instructor.Mode.GEMINI_JSON)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to initialize Gemini client: {e}")
        return None


def get_ai_client() -> tuple[Instructor | None, str]:
    """
    Returns the primary available Instructor client and model string.
    Prioritizes Groq, then falls back to Gemini.
    """
    groq_client = get_groq_client()
    if groq_client:
        model = getattr(settings, "PRIMARY_EXTRACTION_MODEL", "llama-3.3-70b-versatile")
        return groq_client, model

    gemini_client = get_gemini_client()
    if gemini_client:
        model = settings.VISION_EXTRACTION_MODEL
        return gemini_client, model

    return None, "NONE"
