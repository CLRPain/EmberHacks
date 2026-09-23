# The TA

A study buddy that watches you through your webcam and tells you off when you get distracted.

You pick a TA persona on the title screen, and the app opens your webcam. Every few seconds it sends a frame to Google Gemini, which decides whether you're focused and writes a line in your TA's voice. If you're distracted, the TA says that line out loud.

## Quick start

On Windows (PowerShell):

```powershell
git clone https://github.com/CLRPain/EmberHacks.git
cd EmberHacks
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Set-Content .env "GEMINI_API_KEY=your-key-here"
python run.py
```

- **Use Python 3.11.** `py -3.11` picks it even if you have a newer Python installed. The app also runs on 3.13 and newer, but `mediapipe` gets skipped there, so the eye-tracking demo (`tests/test_eyes.py`) won't work.
- **Use `python -m pip`, not `pip`.** Plain `pip` can belong to a different Python, which leaves `gtts`, `pygame` and `pyttsx3` missing when you run the app.

On macOS or Linux, see [step 2](#2-install-the-python-packages). The sections below go through each step in detail.

## Setup

### 1. What you need

- **Python 3.10–3.12** (3.11 recommended). Newer versions run the app, but MediaPipe 0.10.14 doesn't support them, so pip skips it and the eye-tracking demo won't work.
- **A webcam.**
- **Speakers or headphones** to hear the TA.
- **An internet connection**, for Gemini and for Google's text-to-speech.
- **A Gemini API key.** You can get one free at <https://aistudio.google.com/apikey>.

### 2. Install the Python packages

Create a virtual environment with Python 3.10-3.12 and install into it from
the repo root. On Windows, use the Python launcher so the supported interpreter
is selected explicitly:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -c "import gtts, pygame, pyttsx3; print('TTS dependencies installed')"
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process
Bypass` in that terminal and activate again. Always use `python -m pip` after
activating the environment; bare `pip` may belong to a different Python
installation, which can make the packages appear installed but unavailable to
`python run.py`.

On macOS or Linux, replace the environment commands with:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -c "import gtts, pygame, pyttsx3; print('TTS dependencies installed')"
```

The same `requirements.txt` works on every OS. Packages that only apply to some platforms have markers, so pip skips them where they don't apply: `pywin32`, `pypiwin32` and `comtypes` install only on Windows, and `mediapipe` only on Python 3.12 or older.

**Linux system packages.** Tkinter, OpenCV, the offline voice and audio playback need these system packages:

```bash
sudo apt install python3-tk libgl1 libglib2.0-0 espeak-ng libsdl2-mixer-2.0-0
```

### 3. Add your API key

Create a file named `.env` in the repo root:

```
GEMINI_API_KEY=your-key-here
# Optional: use a different Gemini model (default is gemini-3.6-flash)
# GEMINI_MODEL=gemini-3.6-flash
```

`.env` is in `.gitignore`, so git won't commit your key. An exported `GEMINI_API_KEY` environment variable also works, and it takes priority over the file.

### 4. Run it

**Run the app from the repo root.** The title screen loads `./yellingTA.png` from the directory you're in.

```bash
python run.py
```

1. Pick a TA on the title screen.
2. The webcam window opens. The top shows a countdown to the next check, and the bottom bar shows the latest verdict.
3. When you look distracted, the TA speaks. It waits at least 45 seconds between warnings.
4. To quit, press **q** or close the window.

**Running over SSH.** The windows can be forwarded to your screen with `ssh -Y`, but the webcam and speakers are the ones on the remote machine. If the webcam is on the computer you're using, run the app on that computer.

## How it works

```
run.py
  │
  ├─ ui/title_screen.py   choose_ta() ──► "The Torontonian"
  │
  └─ main.py              run_camera("The Torontonian")
        │
        ├─ vision/camera.py      read a fresh frame every loop
        │
        ├─ every CHECK_INTERVAL seconds, on a background thread:
        │     ai/detector.py     analyzeAttention(frame) ──► Gemini
        │        └─ ai/scorer.py build_system_prompt()  (persona + rules)
        │     ◄── { distracted, confidence, script }
        │
        └─ if distracted and the cooldown has passed: speak(script)
              gTTS + pygame  (falls back to offline pyttsx3)
```

The Gemini request runs on a worker thread, so the video keeps playing while it waits. The same API call returns both the verdict and the TA's line.

## Project layout

```
EmberHacks/
├── run.py                     Entry point: title screen, then camera loop
├── requirements.txt           Pinned Python dependencies
├── yellingTA.png              Title screen image (loaded from the working directory)
├── test_speak.py              Checks that text-to-speech plays on this machine
├── src/focus_checker/
│   ├── main.py                Camera loop, background checker, text-to-speech
│   ├── ai/
│   │   ├── detector.py        Sends a frame to Gemini, parses the JSON verdict
│   │   └── scorer.py          TA personas and the system prompt built from them
│   ├── vision/
│   │   ├── camera.py          OpenCV webcam wrapper that returns fresh frames
│   │   ├── motion_buffer.py   MotionGate: captures only when the scene changes
│   │   └── eye_gate.py        EyeGate: captures only when your gaze shifts
│   ├── ui/
│   │   └── title_screen.py    Tkinter window for choosing a TA
│   └── testImages/            Sample photos for testing without a camera (gitignored)
└── tests/                     Manual camera demos (these aren't pytest tests)
```

### `run.py`

This is the entry point. It shows the title screen, waits for you to pick a TA, and then starts the camera loop with that TA. If you close the title screen without choosing, the app exits.

### `src/focus_checker/main.py`

This file contains the main loop.

- **`run_camera(ta_name)`** opens the webcam and draws the overlay: a status bar at the bottom, and the TA name with a countdown at the top. Every `CHECK_INTERVAL` seconds it passes a frame to the `Checker`.
- **`Checker`** runs each Gemini call on a background thread and sends status messages back to the video loop through a queue. It skips a tick if the previous call is still running. If the daily Gemini quota runs out, it stops making calls.
- **`speak(text, ta_name)`** turns the line into speech with gTTS and plays it with pygame. Each TA has its own accent, set in `TA_VOICES`. If gTTS fails, for example because there's no internet, it falls back to the computer's built-in voice through `pyttsx3`. A lock stops two lines from playing at the same time.

Settings at the top of the file:

| Setting          | Default                        | What it does                            |
| ---------------- | ------------------------------ | --------------------------------------- |
| `CHECK_INTERVAL` | `2`                            | Seconds between Gemini calls            |
| `ALERT_COOLDOWN` | `45`                           | Minimum seconds between spoken warnings |
| `FALLBACK_LINE`  | "Hey, eyes back on your work." | Spoken if Gemini returns an empty line  |

### `src/focus_checker/ai/detector.py`

This file sends frames to Gemini.

- **`analyzeAttention(image, ta_key, recent_lines)`** takes either an OpenCV frame or an image path. It sends the image to Gemini and returns an `AttentionResult` with `distracted`, `confidence` (0–1) and `script`, the line to speak.
- It uses Gemini's structured output (`RESPONSE_SCHEMA`), so the reply is always valid JSON.
- It sends the TA's last few lines with each request, so the TA doesn't keep saying the same thing.
- The client retries rate-limit and server errors with exponential backoff.
- It loads the API key from `.env` the first time it's needed. You can import the module without a key.

To test on a saved image without a camera:

```bash
python -m src.focus_checker.ai.detector path/to/photo.jpg 3    # 3 = TA number
```

### `src/focus_checker/ai/scorer.py`

This file defines the TA personas.

- **`TAS`** maps a key to each TA's name and style description. Edit this dict to add or change personas.
- **`BASE_RULES`** holds the rules every persona follows: under 40 words, plain text, playful but never insulting, and no comments on the person's appearance.
- **`build_system_prompt(ta_key)`** combines the rules with the persona's description into the system instruction sent to Gemini.
- **`select_ta(option)`** accepts either a key (`"3"`) or a display name (`"The Torontonian"`).

To score the images in `testImages/` from the terminal:

```bash
python -m src.focus_checker.ai.scorer
```

### `src/focus_checker/vision/camera.py`

This is a small wrapper around `cv2.VideoCapture`. Use it as `with Camera() as cam:` so the webcam is released when you're done. `read()` throws away a couple of buffered frames first, so you get the current image rather than one from a few seconds ago. If the camera can't be opened, it raises `CameraError` with a message suggesting what to check.

### `src/focus_checker/vision/motion_buffer.py` and `eye_gate.py`

These are two ways to decide when a frame is worth sending to Gemini, instead of sending one on a fixed timer. **Neither is used by `main.py` yet.**

- **`MotionGate`** captures a frame when enough pixels have changed since the last capture. It compares shrunk, grayscale, blurred copies, so it doesn't use any machine learning and is cheap to run.
- **`EyeGate`** uses MediaPipe Face Mesh to track your irises. It captures a frame when your gaze direction shifts past a threshold, or when your face appears or disappears. It ignores blinks.

Both keep the last few captured frames in a buffer and have an optional `heartbeat` setting, which forces a capture after a period with no changes.

### `src/focus_checker/ui/title_screen.py`

This is the Tkinter title screen. `choose_ta()` opens the window and waits until you click a TA, then returns that TA's name. If you close the window instead, it returns `None`. The window also has "Instruction Manual" and "Program Description" buttons that open popups.

The button values must match the names in `scorer.TAS` and `main.TA_VOICES`. If you add a TA, add it in all three places.

### `tests/` and `test_speak.py`

These are manual scripts, not automated tests. Run them from the repo root:

| Script                               | What it does                                                                  |
| ------------------------------------ | ----------------------------------------------------------------------------- |
| `python test_speak.py`               | Speaks one line so you can check your audio                                   |
| `python tests/test_camera.py`        | Shows the webcam and saves `tests/test_frame.jpg` (press **s** to save again) |
| `python -m tests.test_motion_buffer` | Live demo of `MotionGate` (press **d** to save the buffered frames)           |
| `python -m tests.test_eyes`          | Live demo of `EyeGate`, saving a frame each time your gaze shifts             |

The camera test scripts use `cv2.CAP_DSHOW`, which only exists on Windows. On macOS or Linux, change `cv2.VideoCapture(0, cv2.CAP_DSHOW)` to `cv2.VideoCapture(0)`.

## Troubleshooting

| Problem                            | Fix                                                                                                                   |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `GEMINI_API_KEY is not set`        | Create `.env` in the repo root (see [step 3](#3-add-your-api-key)).                                                   |
| `Could not open camera 0`          | Close other apps using the camera and check your OS camera permission. On Linux, add yourself to the `video` group.   |
| `Daily Gemini quota used up`       | The free tier has a daily limit. Wait until tomorrow, or raise `CHECK_INTERVAL` in `main.py` so it lasts longer.      |
| Title screen image is missing      | Run from the repo root so `./yellingTA.png` can be found.                                                             |
| `No module named '_tkinter'`       | Install Tkinter: `sudo apt install python3-tk` on Linux, or `brew install python-tk` on macOS.                        |
| `No module named 'mediapipe'` in `test_eyes.py` | MediaPipe is skipped on Python 3.13 and newer. Make the venv with Python 3.11: `py -3.11 -m venv .venv`. |
| `No module named 'pygame'` (or `pyttsx3`) | Activate the venv and reinstall with `python -m pip install -r requirements.txt`. Plain `pip` may have installed into a different Python. |
| No sound                           | Run `python test_speak.py`. If gTTS fails, the app falls back to the offline voice, which needs `espeak-ng` on Linux. |
