"""Turns an AttentionResult into a spoken script for the selected TA persona."""

import json
import os
from dataclasses import asdict

from google.genai import types

from .detector import DEFAULT_MODEL, AttentionResult, _get_client

# Add or edit personas here. The menu builds itself from this dict.
TAS = {
    "1": {
        "name": "Coach Riley",
        "style": (
            "An upbeat, high-energy sports coach. Motivating and encouraging, "
            "uses short punchy sentences and light coaching lingo. Never mean."
        ),
    },
    "2": {
        "name": "Professor Whitmore",
        "style": (
            "A dry, witty, slightly sarcastic professor. Deadpan humor and "
            "understated disappointment, but clearly wants the student to succeed."
        ),
    },
    "3": {
        "name": "Sage",
        "style": (
            "A calm, gentle mindfulness guide. Soft, kind, and reassuring, "
            "nudges the person back to focus without any guilt."
        ),
    },
    "4": {
        "name": "Sergeant Stern",
        "style": (
            "A strict drill sergeant. Loud, blunt, and commanding, with playful "
            "exaggeration. Tough love, never insulting or cruel."
        ),
    },
}

BASE_RULES = (
    "You write short scripts that a text-to-speech voice will read aloud to a "
    "person who is working at their computer. You are given a JSON attention "
    "report produced from their webcam.\n"
    "Report fields: 'distracted' (bool), 'confidence' (0-1, how sure the "
    "analysis is that they are distracted), 'explanation' (what was observed).\n"
    "Rules:\n"
    "- Stay fully in character as the TA described below.\n"
    "- Output ONLY the words to be spoken: 3 sentences, under 40 words.\n"
    "- Plain text only. No emojis, markdown, asterisks, stage directions, "
    "quotation marks, or the TA's name as a label.\n"
    "- Mention what they were actually doing, based on 'explanation'.\n"
    "- If distracted is true, redirect them back to work. If confidence is "
    "low, be lighter and less accusatory.\n"
    "- If distracted is false, give a brief, in-character word of praise.\n"
    "- Be playful but never insulting, and never comment on their body or appearance.\n"
)


def build_system_prompt(ta_key: str) -> str:
    ta = TAS[ta_key]
    return f"{BASE_RULES}\nYour TA persona is {ta['name']}: {ta['style']}"


def generate_script(
    result: AttentionResult,
    ta_key: str,
    recent_lines: list[str] | None = None,
) -> str:
    """Ask Gemini for the line the TTS should read for this attention result.

    recent_lines: previous scripts, so the TA doesn't repeat itself.
    """
    if ta_key not in TAS:
        raise KeyError(f"Unknown TA '{ta_key}'. Options: {list(TAS)}")

    user_prompt = "Attention report:\n" + json.dumps(asdict(result), indent=2)
    if recent_lines:
        user_prompt += (
            "\n\nYou already said these recently, so say something different:\n- "
            + "\n- ".join(recent_lines[-3:])
        )

    response = _get_client().models.generate_content(
        model=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=build_system_prompt(ta_key),
            temperature=0.9,          # more variety than the detector's 0.0
            max_output_tokens=1024,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )

    text = (response.text or "").strip().strip('"')
    if not text:
        raise RuntimeError("Gemini returned an empty script")
    return text


def select_ta() -> str:
    """Simple terminal menu. Returns the chosen key from TAS."""
    print("Choose your TA:")
    for key, ta in TAS.items():
        print(f"  {key}. {ta['name']}")
    while True:
        choice = input("> ").strip()
        if choice in TAS:
            print(f"Selected {TAS[choice]['name']}\n")
            return choice
        print("Invalid choice, try again.")


if __name__ == "__main__":
    # Try it without a camera: fake results for each persona.
    ta = select_ta()
    samples = [
        AttentionResult(True, 0.92, "The person is looking at their phone."),
        AttentionResult(True, 0.55, "The person is looking away from the screen."),
        AttentionResult(False, 0.05, "The person is typing and looking at the screen."),
    ]
    for s in samples:
        print(s.explanation)
        print("  ->", generate_script(s, ta), "\n")