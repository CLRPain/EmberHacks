"""Attention detection via Gemini vision.

Sends a webcam frame to Gemini and asks for a structured JSON verdict on
whether the person in the frame is distracted.

Reads ``GEMINI_API_KEY`` from the environment, falling back to the ``.env``
file at the repo root. Optionally set ``GEMINI_MODEL`` to override the
default model.
"""

import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Repo root is two levels up from src/focus_checker/detector.py.
# Real environment variables take precedence over the .env file.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_MODEL = "gemini-3.6-flash"

PROMPT = (
    "You are monitoring a person working at a computer via their webcam. "
    "Look at this frame and decide whether they are distracted from their work. "
    "Signs of distraction include: looking away from the screen for a non-trivial "
    "reason, using a phone, talking to someone else, eating, sleeping, or being "
    "absent from the frame. Brief glances or normal posture shifts are NOT distraction. "
    "Respond only with the requested JSON."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "distracted": {
            "type": "boolean",
            "description": "True if the person appears distracted from their work.",
        },
        "confidence": {
            "type": "number",
            "description": "Confidence from 0.0 to 1.0 that the person is distracted.",
        },
        "explanation": {
            "type": "string",
            "description": "One short sentence explaining the verdict.",
        },
    },
    "required": ["distracted", "confidence", "explanation"],
}


@dataclass
class AttentionResult:
    distracted: bool
    confidence: float
    explanation: str


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to the .env file at the repo "
                "root or export it. Get a key from https://aistudio.google.com/apikey"
            )
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                # Retry transient failures (rate limits, 5xx / "high demand")
                # with exponential backoff instead of failing a single frame.
                retry_options=types.HttpRetryOptions(
                    attempts=5,
                    initial_delay=1.0,
                    max_delay=10.0,
                    exp_base=2.0,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )
    return _client


def analyzeAttention(img_location: str) -> AttentionResult:
    """Send an image to Gemini and return the full structured verdict."""
    path = Path(img_location)
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {img_location}")

    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type is None or not mime_type.startswith("image/"):
        mime_type = "image/jpeg"

    response = _get_client().models.generate_content(
        model=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
        contents=[
            types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type),
            PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            temperature=0.0,
            # We pass no tools; this silences the SDK's AFC warning.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )

    data = json.loads(response.text)
    return AttentionResult(
        distracted=bool(data["distracted"]),
        confidence=max(0.0, min(1.0, float(data["confidence"]))),
        explanation=str(data["explanation"]),
    )


def checkAttention(img_location: str) -> bool:
    """Return True if the person in the image appears to be paying attention.

    Wraps :func:`analyzeAttention` and discards the confidence/explanation.
    """

    res = analyzeAttention(img_location)

    print(res.confidence)
    print(res.explanation)

    return not res.distracted


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        sys.exit("usage: python -m focus_checker.detector <image>")
    result = analyzeAttention(sys.argv[1])
    print(json.dumps(result.__dict__, indent=2))
