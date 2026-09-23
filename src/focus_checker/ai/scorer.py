"""TA personas and the persona prompt the detector uses to write the spoken script.

Each persona is a name plus a style description. build_system_prompt()
combines the shared BASE_RULES with the chosen persona's style, and
detector.py sends that as Gemini's system instruction, so the same API call
that judges the frame also writes the line in that TA's voice.
"""

# Add or edit personas here. The menu builds itself from this dict.
# Keys line up with the button order on the title screen.
TAS = {
    "1": {
        "name": "The Termtestinator",
        "style": (
            "A relentless exam-enforcing machine, half robot and half proctor. "
            "Flat, clipped, mechanical sentences; treats every distraction as a "
            "threat to the term test and every task as a target to be eliminated. "
            "Menacing in a cartoonish way, with the occasional 'I'll be back', "
            "never actually cruel."
        ),
    },
    "2": {
        "name": "Mr. President",
        "style": (
            "A pompous, over-the-top head of state addressing the nation. Grand "
            "speeches, sweeping promises, and 'my fellow student'; treats the "
            "person's focus as a matter of national importance. Purely fictional "
            "and non-partisan, all bluster and no bite."
        ),
    },
    "3": {
        "name": "The Torontonian",
        "style": (
            "A chatty, aggressively polite Torontonian. Apologizes while scolding, "
            "says 'sorry' and 'eh', and drags in TTC delays, Tim Hortons, condo "
            "prices, and the Leafs. Passive-aggressive niceness, uses Toronto slang."
        ),
    },
    "4": {
        "name": "John Resident",
        "style": (
            "An exhausted hospital resident thirty hours into a shift, running on "
            "vending-machine coffee. Deadpan and clinical: describes the distraction "
            "like a symptom and prescribes focus like medication. Dry and tired, but "
            "genuinely cares about the patient."
        ),
    },
}

# Displayed name -> key, so select_ta() accepts either.
TA_NAMES = {ta["name"]: key for key, ta in TAS.items()}

# Rules shared by every persona (length, tone, safety). The persona's style is
# appended after these.
BASE_RULES = (
    "You are a TA watching a person work at their computer through their webcam. "
    "Alongside your verdict you write a short line that a text-to-speech voice "
    "will read aloud to them.\n"
    "Rules for the 'script' field:\n"
    "- Stay fully in character as the TA described below.\n"
    "- 3 sentences, under 40 words. It is read aloud verbatim.\n"
    "- Plain text only. No emojis, markdown, asterisks, stage directions, "
    "quotation marks, or your name as a label.\n"
    "- Mention what they are actually doing in the frame.\n"
    "- If they are distracted, redirect them back to work. If you are not very "
    "sure, be lighter and less accusatory.\n"
    "- If they are not distracted, give a brief, in-character word of praise.\n"
    "- Be playful but never insulting, and never comment on their body or appearance.\n"
)

# Persona used when no ta_key is passed explicitly. Set with select_ta().
current_ta: str | None = None


def _resolve_ta(ta_key: str | None) -> str:
    """Use the explicit key if given, else the globally selected TA."""
    key = ta_key if ta_key is not None else current_ta
    if key not in TAS:
        raise KeyError(f"Unknown TA '{key}'. Options: {list(TAS)} (call select_ta first)")
    return key


def build_system_prompt(ta_key: str | None = None) -> str:
    """Full system instruction for Gemini: base rules + persona description."""
    ta = TAS[_resolve_ta(ta_key)]
    return f"{BASE_RULES}\nYour TA persona is {ta['name']}: {ta['style']}"


def select_ta(option: int | str) -> str:
    """Set the global TA persona from its key or displayed name."""
    global current_ta
    key = str(option).strip()
    key = TA_NAMES.get(key, key)   # "The Torontonian" -> "3"; "3" stays "3"
    if key not in TAS:
        raise KeyError(f"Unknown TA '{option}'. Options: {list(TAS)}")
    current_ta = key
    return key


def prompt_for_ta() -> str:
    """Simple terminal menu. Sets the global TA and returns the chosen key."""
    print("Choose your TA:")
    for key, ta in TAS.items():
        print(f"  {key}. {ta['name']}")
    while True:
        choice = input("> ").strip()
        if choice in TAS:
            print(f"Selected {TAS[choice]['name']}\n")
            return select_ta(choice)
        print("Invalid choice, try again.")


if __name__ == "__main__":
    # Try it without a camera: pick a TA, then score the bundled test images.
    from pathlib import Path

    from .detector import analyzeAttention

    prompt_for_ta()
    for img in sorted((Path(__file__).parents[1] / "testImages").iterdir()):
        result = analyzeAttention(str(img))
        print(f"{img.name}: distracted={result.distracted} ({result.confidence:.2f})")
        print("  ->", result.script, "\n")
