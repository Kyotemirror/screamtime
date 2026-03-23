import pygame
from datetime import datetime
import math
import json
import os

pygame.init()

# -----------------
# Load config.json (with safe defaults)
# -----------------
DEFAULT_CONFIG = {
    "display": {"fullscreen": False, "width": 480, "height": 320, "fps": 60},
    "clock": {"format": "12hr", "show_ampm": True},
    "animation": {
        "digit_duration": 0.20,
        "digit_slide_px": 18,
        "digit_stagger": 0.04,
        "ghost_bob_speed": 2.0,
        "ghost_bob_height": 6
    },
    "colors": {"background": [10, 10, 20], "text": [240, 240, 240]},
    "font": {
        "name": "consolas",
        "size": 64,
        "bold": True,
        "italic": False,
        "antialias": True
    }
}

def deep_merge(base, override):
    """Merge dict override into base recursively."""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out

config_path = os.path.join(os.path.dirname(__file__), "config.json")
CONFIG = DEFAULT_CONFIG
if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        CONFIG = deep_merge(DEFAULT_CONFIG, user_cfg)
    except Exception as e:
        print("Failed to load config.json, using defaults:", e)

# -----------------
# Display setup (fullscreen = one-line flag choice)
# pygame.display.set_mode supports flags like pygame.FULLSCREEN [1](https://www.pygame.org/docs/ref/display.html)[2](https://www.pygame.org/docs/tut/DisplayModes.html)
# -----------------
DISPLAY = CONFIG["display"]
WIDTH = int(DISPLAY.get("width", 480))
HEIGHT = int(DISPLAY.get("height", 320))
FPS = int(DISPLAY.get("fps", 60))

FLAGS = pygame.FULLSCREEN if DISPLAY.get("fullscreen", False) else 0
screen = pygame.display.set_mode((WIDTH, HEIGHT), FLAGS)
pygame.display.set_caption("Animated Ghost Clock")

clock = pygame.time.Clock()

# -----------------
# Colors
# -----------------
BG_COLOR = tuple(CONFIG["colors"]["background"])
TEXT_COLOR = tuple(CONFIG["colors"]["text"])

# -----------------
# System font
# pygame.font.SysFont creates a Font from system fonts [3](https://www.pygame.org/docs/ref/font.html?highlight=sysfont)
# -----------------
FONT_CFG = CONFIG["font"]
FONT_NAME = FONT_CFG.get("name", None)  # can be string or list
FONT_SIZE = int(FONT_CFG.get("size", 64))
FONT_BOLD = bool(FONT_CFG.get("bold", True))
FONT_ITALIC = bool(FONT_CFG.get("italic", False))
ANTIALIAS = bool(FONT_CFG.get("antialias", True))

font = pygame.font.SysFont(FONT_NAME, FONT_SIZE, bold=FONT_BOLD, italic=FONT_ITALIC)

# -----------------
# 8-bit Ghost Pixel Art (original)
# -----------------
def create_ghost_face(scale=4):
    pixels = [
        "  XXXXXXX  ",
        " XXXXXXXXX ",
        " XXX   XXX ",
        " XX  X X XX",
        " XX       X",
        " XX  XXX  X",
        " XXX     XX",
        "  XXXXXXXX ",
    ]
    w = len(pixels[0]) * scale
    h = len(pixels) * scale
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(pixels):
        for x, c in enumerate(row):
            if c == "X":
                pygame.draw.rect(surf, TEXT_COLOR, (x * scale, y * scale, scale, scale))
    return surf

ghost = create_ghost_face(scale=4)
ghost_rect = ghost.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 55))

# -----------------
# Animation config
# -----------------
ANIM = CONFIG["animation"]
DIGIT_DURATION = float(ANIM.get("digit_duration", 0.20))
DIGIT_SLIDE_PX = int(ANIM.get("digit_slide_px", 18))
DIGIT_STAGGER = float(ANIM.get("digit_stagger", 0.04))

BOB_SPEED = float(ANIM.get("ghost_bob_speed", 2.0))
BOB_HEIGHT = int(ANIM.get("ghost_bob_height", 6))
bob_t = 0.0

# -----------------
# Helpers
# -----------------
def smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)

# -----------------
# Per-character animated slot
# -----------------
class CharSlot:
    def __init__(self, char=" "):
        self.char = char
        self.old_char = char
        self.t = 1.0
        self.animating = False
        self.delay = 0.0

    def set_char(self, new_char, start_delay=0.0):
        if new_char != self.char:
            self.old_char = self.char
            self.char = new_char
            self.t = 0.0
            self.animating = True
            self.delay = start_delay

    def update(self, dt, duration):
        if not self.animating:
            return

        if self.delay > 0:
            self.delay -= dt
            return

        self.t += dt / duration
        if self.t >= 1.0:
            self.t = 1.0
            self.animating = False

    def draw(self, surface, x, y, cache, slide_px):
        new_surf = cache[self.char]
        old_surf = cache[self.old_char]

        if not self.animating or self.t >= 1.0 or self.delay > 0:
            surface.blit(new_surf, (x, y))
            return

        tt = smoothstep(self.t)

        old_alpha = int(255 * (1 - tt))
        new_alpha = int(255 * tt)

        old_y = y - int(slide_px * tt)
        new_y = y + int(slide_px * (1 - tt))

        old_draw = old_surf.copy()
        new_draw = new_surf.copy()
        old_draw.set_alpha(old_alpha)
        new_draw.set_alpha(new_alpha)

        surface.blit(old_draw, (x, old_y))
        surface.blit(new_draw, (x, new_y))

# -----------------
# Animated text (multiple CharSlots)
# -----------------
class AnimatedText:
    def __init__(self, initial_text, duration, slide_px, stagger):
        self.duration = duration
        self.slide_px = slide_px
        self.stagger = stagger
        self.text = initial_text

        self.slots = [CharSlot(c) for c in initial_text]
        self.cache = {}
        self._build_cache()

        self.slot_w = max(s.get_width() for s in self.cache.values())
        self.slot_h = max(s.get_height() for s in self.cache.values())

    def _build_cache(self):
        # Cache everything we might use in the time string
        allowed = set("0123456789: APM")
        for c in allowed:
            surf = font.render(c, ANTIALIAS, TEXT_COLOR)  # render(text, antialias, color) [4](https://pytutorial.com/python-pygame-sysfont-text-rendering-guide/)
            self.cache[c] = surf.convert_alpha()

    def set_text(self, new_text):
        if len(new_text) != len(self.slots):
            # Rebuild slots for new length
            self.slots = [CharSlot(c) for c in new_text]
            self.text = new_text
            return

        for i, c in enumerate(new_text):
            self.slots[i].set_char(c, start_delay=i * self.stagger)

        self.text = new_text

    def update(self, dt):
        for s in self.slots:
            s.update(dt, self.duration)

    def draw_centered(self, surface, center_x, y):
        total_w = len(self.slots) * self.slot_w
        start_x = center_x - total_w // 2

        for i, slot in enumerate(self.slots):
            x = start_x + i * self.slot_w
            # Ensure character exists in cache (space, digits, :, A,P,M)
            ch = slot.char
            if ch not in self.cache:
                # fallback render if something unexpected appears
                self.cache[ch] = font.render(ch, ANTIALIAS, TEXT_COLOR).convert_alpha()
            slot.draw(surface, x, y, self.cache, self.slide_px)

# -----------------
# Time formatting driven by config
# -----------------
CLOCK_CFG = CONFIG["clock"]
SHOW_AMPM = bool(CLOCK_CFG.get("show_ampm", True))
FORMAT = str(CLOCK_CFG.get("format", "12hr")).lower()

def get_time_string():
    now = datetime.now()

    if FORMAT == "24hr":
        # fixed length: "HH:MM" (5)
        return now.strftime("%H:%M")
    else:
        # 12hr
        hh = now.strftime("%I")  # 01..12
        mm = now.strftime("%M")

        # Keep stable width: replace leading 0 with space
        if hh[0] == "0":
            hh = " " + hh[1]

        if SHOW_AMPM:
            ap = now.strftime("%p")  # AM/PM
            # fixed length: " H:MM AM" (8)
            return f"{hh}:{mm} {ap}"
        else:
            # fixed length: " H:MM" (5)
            return f"{hh}:{mm}"

# Create animated clock
animated_clock = AnimatedText(
    get_time_string(),
    duration=DIGIT_DURATION,
    slide_px=DIGIT_SLIDE_PX,
    stagger=DIGIT_STAGGER
)

# -----------------
# Main loop
# -----------------
running = True
while running:
    dt = clock.tick(FPS) / 1000.0
    bob_t += dt

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # Optional: ESC to quit (nice for fullscreen)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    # Update time
    new_text = get_time_string()
    if new_text != animated_clock.text:
        animated_clock.set_text(new_text)

    animated_clock.update(dt)

    # Ghost bob
    bob_offset = math.sin(bob_t * BOB_SPEED) * BOB_HEIGHT
    ghost_rect.center = (WIDTH // 2, HEIGHT // 2 - 60 + int(bob_offset))

    # Draw
    screen.fill(BG_COLOR)
    screen.blit(ghost, ghost_rect)

    animated_clock.draw_centered(screen, WIDTH // 2, ghost_rect.bottom + 25)

    pygame.display.flip()

pygame.quit()
