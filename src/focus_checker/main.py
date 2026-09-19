import time
from collections import deque
from .camera import frames
from .analyzer import analyze, State

INTERVAL = 15        # seconds between API calls
WINDOW = 4           # look at the last 4 results
last_call = 0
history = deque(maxlen=WINDOW)

for frame in frames():
    now = time.time()
    if now - last_call < INTERVAL:
        continue
    last_call = now

    try:
        result = analyze(frame)
    except Exception as e:
        print("API error:", e)
        continue

    history.append(result.state)
    print(f"{result.state.value:10} ({result.confidence:.2f}) {result.reason}")

    # Only alert on sustained slacking, not one bad frame
    if list(history).count(State.DISTRACTED) >= 3:
        print("⚠️  You've been off-task for a while. Back to work!")