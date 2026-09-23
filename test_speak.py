"""Quick manual check that text-to-speech works on this machine.

Generates one line with Google TTS (needs internet) and plays it through
pygame, the same way main.speak() does. If you hear it, audio is set up.
"""

import io, time
import pygame
from gtts import gTTS

# Render the speech to an in-memory MP3 instead of a temp file.
# tld="ca" selects the Canadian accent (the Torontonian's voice).
buf = io.BytesIO()
gTTS("Hey, eyes back on your work, eh?", lang="en", tld="ca").write_to_fp(buf)
buf.seek(0)   # rewind so pygame reads from the start

pygame.mixer.init()
pygame.mixer.music.load(buf, "mp3")
pygame.mixer.music.play()
# play() returns immediately; wait so the script doesn't exit mid-sentence.
while pygame.mixer.music.get_busy():
    time.sleep(0.1)