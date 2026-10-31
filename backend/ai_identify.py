"""Asks Google's Gemini to identify a clothing photo's traits.

Note: on Google's free tier, the photos you send may be used to improve
Google's products.
"""
import json
import os

from dotenv import load_dotenv

import models

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

FALLBACK = {
    "category": models.CATEGORIES[0],
    "colour": models.COLOURS[0],
    "pattern": "solid",
    "season": models.SEASONS[0],
}

_client = None


def _get_client():
    global _client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    if _client is None:
        from google import genai 
        _client = genai.Client(api_key=api_key)
    return _client


def identify_clothing(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """Returns {"category", "colour", "pattern", "season"}, each guaranteed
    to be one of the allowed values in models.py."""
    client = _get_client()
    if client is None:
        return dict(FALLBACK)

    prompt = (
        "Look at this photo of one clothing item. Reply with ONLY a JSON object "
        "with exactly these keys:\n"
        f'"category": one of {models.CATEGORIES}\n'
        f'"colour": the closest one of {models.COLOURS}\n'
        f'"pattern": one of {models.PATTERNS}\n'
        f'"season": one of {models.SEASONS} (which season the item best suits)'
    )

    try:
        from google.genai import types

        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=media_type),
                prompt,
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        result = json.loads(response.text.strip().strip("`"))

       
        # for any field that isn't one of the allowed values.
        for field, allowed in (
            ("category", models.CATEGORIES),
            ("colour", models.COLOURS),
            ("pattern", models.PATTERNS),
            ("season", models.SEASONS),
        ):
            if result.get(field) not in allowed:
                result[field] = FALLBACK[field]
        return result
    except Exception:
        return dict(FALLBACK)
