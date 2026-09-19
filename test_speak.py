import io, time
import pygame
from gtts import gTTS

buf = io.BytesIO()
gTTS("Hey, eyes back on your work, eh?", lang="en", tld="ca").write_to_fp(buf)
buf.seek(0)

pygame.mixer.init()
pygame.mixer.music.load(buf, "mp3")
pygame.mixer.music.play()
while pygame.mixer.music.get_busy():
    time.sleep(0.1)