import pygame
from datetime import datetime
import math

pygame.init()

# -----------------
# Window
# -----------------
WIDTH, HEIGHT = 480, 320
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Animated Clock (Per Digit)")

clock = pygame.time.Clock()

# -----------------
# Colors
# -----------------
BG_COLOR = (10, 10, 20)
WHITE = (240, 240, 240)

# -----------------
# System Font (monospace recommended for stable spacing)
# pygame.font.SysFont uses installed system fonts. [1](https://www.pygame.org/docs/ref/font.html?highlight=antialiased)
# -----------------
FONT_NAME = "consolas"   # try: "consolas", "couriernew", "dejavusansmono"
FONT_SIZE = 64
FONT_BOLD = True
FONT_ITALIC = False

font = pygame.font.SysFont(FONT_NAME, FONT_SIZE, bold=FONT_BOLD, italic=FONT_ITALIC)

# antialias=True makes text smoother; False makes it more pixel-crisp. [2](https://petlja.github.io/TxtProgInPythonEng/03_PyGame/03_PyGame_24_Animation_Text.html)
ANTIALIAS = True

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
                pygame.draw.rect(surf, WHITE, (x * scale, y * scale, scale, scale))
    return surf

ghost = create_ghost_face(scale=4)
ghost_rect = ghost.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 55))

# Ghost bob animation
bob_t = 0.0
BOB_SPEED = 2.0
BOB_HEIGHT = 6

# -----------------
# Animation helpers
# -----------------
def smoothstep(t: float) -> float:
    # smooth ease-in-out (0..1)
    return t * t * (3 - 2 * t)

# -----------------
# Per-character animated slot
# -----------------
class CharSlot:
    def __init__(self, char=" ", start_delay=0.0):
        self.char = char
        self.old_char = char
        self.t = 1.0
        self.animating = False
        self.delay = 0.0
        self.start_delay = start_delay

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

        # wait out the per-slot delay first (for a ripple effect)
        if self.delay > 0:
            self.delay -= dt
            return

        self.t += dt / duration
        if self.t >= 1.0:
            self.t = 1.0
            self.animating = False

    def draw(self, surface, x, y, cache, slide_px):
        # get cached base surfaces
        new_surf = cache.get(self.char)
        old_surf = cache.get(self.old_char)

        if not self.animating or self.t >= 1.0 or self.delay > 0:
            # steady state
            surface.blit(new_surf, (x, y))
            return

        tt = smoothstep(self.t)

        # Old moves up & fades out; New moves up into place & fades in
        old_alpha = int(255 * (1 - tt))
        new_alpha = int(255 * tt)

        old_y = y - int(slide_px * tt)
        new_y = y + int(slide_px * (1 - tt))

        # Copy so alpha doesn't affect cached surface
        old_draw = old_surf.copy()
        new_draw = new_surf.copy()
        old_draw.set_alpha(old_alpha)
        new_draw.set_alpha(new_alpha)

        surface.blit(old_draw, (x, old_y))
        surface.blit(new_draw, (x, new_y))

# -----------------
# Animated text object (manages multiple CharSlots)
# -----------------
class AnimatedText:
    def __init__(self, initial_text, duration=0.22, slide_px=18, stagger=0.03):
        self.duration = duration
        self.slide_px = slide_px
        self.stagger = stagger
        self.text = initial_text

        # Build slots
        self.slots = [CharSlot(c) for c in initial_text]

        # Cache rendered surfaces for speed
        self.cache = {}
        self._build_cache()

        # Fixed slot width for stable layout
        self.slot_w = max(self.cache[c].get_width() for c in self.cache)
        self.slot_h = max(self.cache[c].get_height() for c in self.cache)

    def _build_cache(self):
        # We will cache for all characters that might appear in time
        # digits, colon, space, A,P,M
        allowed = set("0123456789: APM")
        for c in allowed:
            surf = font.render(c, ANTIALIAS, WHITE)  # antialias flag is the 2nd argument. [2](https://petlja.github.io/TxtProgInPythonEng/03_PyGame/03_PyGame_24_Animation_Text.html)
            self.cache[c] = surf.convert_alpha()

    def set_text(self, new_text):
        # keep constant length to avoid layout shifts
        if len(new_text) != len(self.slots):
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
            slot.draw(surface, x, y, self.cache, self.slide_px)

# -----------------
# Format time as fixed-length 12hr string: " H:MM AM" style
# (Two-hour slots so your layout doesn't jump at 9->10)
# -----------------
def get_time_string():
    now = datetime.now()
    hh = now.strftime("%I")           # 01..12
    mm = now.strftime("%M")
    ap = now.strftime("%p")           # AM/PM
    if hh[0] == "0":
        hh = " " + hh[1]             # " 9" instead of "09"
    return f"{hh}:{mm} {ap}"         # length is always 8 (e.g., " 9:42 PM")

# Create animated text instance
animated_clock = AnimatedText(get_time_string(), duration=0.20, slide_px=18, stagger=0.04)

running = True
while running:
    # tick() returns elapsed ms since last call; convert to seconds for dt. [3](https://www.pygame.org/docs/ref/time.html)
    dt = clock.tick(60) / 1000.0
    bob_t += dt

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Update time string and trigger per-char animations
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

    # draw clock centered under ghost
    animated_clock.draw_centered(screen, WIDTH // 2, ghost_rect.bottom + 25)

    pygame.display.flip()

pygame.quit()
