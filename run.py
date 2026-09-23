"""Entry point for The TA. Run with ``python run.py`` from the repo root.

Flow: title screen (pick a TA persona) -> webcam loop that periodically sends
a frame to Gemini and has the chosen TA speak up when you look distracted.
"""

from src.focus_checker.ui.title_screen import choose_ta
from src.focus_checker.main import run_camera


def main():
    ta = choose_ta()          # blocks until a TA is picked or the window is closed
    if ta is None:
        return                # window closed without choosing, so exit
    run_camera(ta)


if __name__ == "__main__":
    main()