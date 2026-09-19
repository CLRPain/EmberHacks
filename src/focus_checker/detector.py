"""Attention detection via Gemini vision.

Sends a webcam frame to Gemini and asks for a structured JSON verdict on
whether the person in the frame is distracted, plus the line the selected TA
persona would say about it (see :mod:`.scorer`). One API call does both.

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

from .scorer import build_system_prompt

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
    "Then write the line you would say to them about it, in character. "
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
        "script": {
            "type": "string",
            "description": "What the TA says aloud to the person about this frame.",
        },
    },
    "required": ["distracted", "confidence", "script"],
}


@dataclass
class AttentionResult:
    distracted: bool
    confidence: float
    script: str


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


def analyzeAttention(
    img_location: str,
    ta_key: str | None = None,
    recent_lines: list[str] | None = None,
) -> AttentionResult:
    """Send an image to Gemini and return the verdict plus the TA's spoken line.

    ta_key: persona to use; defaults to the one set by scorer.select_ta().
    recent_lines: previous scripts, so the TA doesn't repeat itself.
    """
    path = Path(img_location)
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {img_location}")

    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type is None or not mime_type.startswith("image/"):
        mime_type = "image/jpeg"

    prompt = PROMPT
    if recent_lines:
        prompt += (
            "\n\nYou already said these recently, so say something different:\n- "
            + "\n- ".join(recent_lines[-3:])
        )

    response = _get_client().models.generate_content(
        model=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
        contents=[
            types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(
            system_instruction=build_system_prompt(ta_key),
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            # Compromise: low enough for a stable verdict, high enough that the
            # script doesn't come out identical every time.
            temperature=0.7,
            # We pass no tools; this silences the SDK's AFC warning.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )

    data = json.loads(response.text)
    return AttentionResult(
        distracted=bool(data["distracted"]),
        confidence=max(0.0, min(1.0, float(data["confidence"]))),
        script=str(data["script"]).strip().strip('"'),
    )


def checkAttention(img_location: str) -> bool:
    """Return True if the person in the image appears to be paying attention.

    Wraps :func:`analyzeAttention` and discards the confidence/script.
    """

    res = analyzeAttention(img_location)

    print(res.confidence)
    print(res.script)

    return not res.distracted


if __name__ == "__main__":
    import sys

    from .scorer import select_ta

    if len(sys.argv) not in (2, 3):
        sys.exit("usage: python -m focus_checker.detector <image> [ta_number]")
    select_ta(sys.argv[2] if len(sys.argv) == 3 else "1")
    result = analyzeAttention(sys.argv[1])
    print(json.dumps(result.__dict__, indent=2))
