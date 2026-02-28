# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""Generate pre-rendered text images from vgasys.fon for font_lab comparison.

Renders the instruction text for each level using the System font with the
exact same layout as the game (170px wide, word-wrapped, 16px line spacing).
Also generates a full glyph sprite sheet.
"""
import numpy as np
from PIL import Image
import freetype
import json

SYS_FON = "assets/fonts/vgasys.fon"
WIDTHS_PATH = "scripts/final_widths.json"
OUTPUT_DIR = "font_lab"

FONT_HEIGHT = 13
LINE_SPACING = 16
RECT_WIDTH = 170

# Load corrected advance widths (derived from reference screenshot)
with open(WIDTHS_PATH) as f:
    advances = json.load(f)

# Load System font
face = freetype.Face(SYS_FON, 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])

def load_glyph(ch):
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bm = face.glyph.bitmap
    bitmap = np.zeros((bm.rows, bm.width), dtype=bool)
    for by in range(bm.rows):
        for bx in range(bm.width):
            if bm.buffer[by * bm.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                bitmap[by, bx] = True
    return bitmap

# Pre-load all glyphs and crop to 13px (dy=3, dx varies)
OFFSET_0_CHARS = {'t', 'f', 'T', 'v', 'w', 'x'}

glyphs = {}
for code in range(32, 127):
    ch = chr(code)
    raw = load_glyph(ch)
    # Crop: rows [3:16] = 13px height
    if raw.shape[0] >= 16:
        cropped = raw[3:16, :]
    else:
        cropped = raw
    # dx: offset 0 chars have dx=0, others dx=1
    dx = 0 if ch in OFFSET_0_CHARS else 1
    glyphs[ch] = {'bitmap': cropped, 'dx': dx}

def word_wrap(text, max_width):
    words = text.split(' ')
    lines = []
    current = ""
    width = 0
    space_w = advances.get(' ', 3)
    for word in words:
        word_w = sum(advances.get(ch, 6) for ch in word)
        if current:
            test_w = width + space_w + word_w
            if test_w > max_width:
                lines.append(current)
                current = word
                width = word_w
            else:
                current += " " + word
                width = test_w
        else:
            current = word
            width = word_w
    if current:
        lines.append(current)
    return lines

def render_text(text, max_width=170, bg_color=(164, 164, 164), fg_color=(0, 0, 0)):
    """Render wrapped text to a PIL Image."""
    lines = word_wrap(text, max_width)
    img_h = len(lines) * LINE_SPACING + (FONT_HEIGHT - LINE_SPACING)  # last line doesn't need full spacing
    img_h = max(img_h, FONT_HEIGHT)
    img = Image.new('RGB', (max_width, img_h), bg_color)
    pixels = img.load()

    for line_idx, line in enumerate(lines):
        y_base = line_idx * LINE_SPACING
        pen_x = 0
        for ch in line:
            if ch == ' ':
                pen_x += advances.get(' ', 3)
                continue
            g = glyphs.get(ch)
            if g is None:
                pen_x += advances.get(ch, 6)
                continue
            bm = g['bitmap']
            dx = g['dx']
            for by in range(bm.shape[0]):
                for bx in range(bm.shape[1]):
                    if bm[by, bx]:
                        px = pen_x + dx + bx
                        py = y_base + by
                        if 0 <= px < max_width and 0 <= py < img_h:
                            pixels[px, py] = fg_color
            pen_x += advances.get(ch, 6)

    return img

# Level texts
LEVELS = [
    {
        'label': 'level1',
        'text': 'Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel.',
    },
    {
        'label': 'level4_splitter',
        'text': 'If a laser hits a SPLITTER at the correct angle, it bounces off at an angle and also goes straight through. If it hits head on, it just goes through.',
    },
    {
        'label': 'level3_colors',
        'text': 'Some pinwheels require multiple lasers to light them up. You get magenta from red and blue. Yellow is formed by green plus red. Combining green and blue yields a color known variously as cyan, teal, or aqua.',
    },
]

for level in LEVELS:
    img = render_text(level['text'])
    path = f"{OUTPUT_DIR}/system_font_{level['label']}.png"
    img.save(path)
    print(f"Wrote {path} ({img.width}x{img.height})")

# Also render bottom bar text
for text, label in [("freeware", "freeware"), ("silverspaceship.com", "silverspaceship")]:
    img = render_text(text, max_width=200)
    path = f"{OUTPUT_DIR}/system_font_bottom_{label}.png"
    img.save(path)
    print(f"Wrote {path} ({img.width}x{img.height})")

# Generate glyph sprite sheet
print("\nGenerating glyph sprite sheet...")
cell_w = 14
cell_h = 16
cols = 16
rows_count = (95 + cols - 1) // cols
sheet_w = cols * cell_w
sheet_h = rows_count * cell_h

sheet = Image.new('RGB', (sheet_w, sheet_h), (164, 164, 164))
px = sheet.load()

for idx, code in enumerate(range(32, 127)):
    ch = chr(code)
    g = glyphs.get(ch)
    if g is None:
        continue
    col = idx % cols
    row = idx // cols
    base_x = col * cell_w
    base_y = row * cell_h

    bm = g['bitmap']
    dx = g['dx']
    for by in range(bm.shape[0]):
        for bx in range(bm.shape[1]):
            if bm[by, bx]:
                x = base_x + dx + bx
                y = base_y + by
                if 0 <= x < sheet_w and 0 <= y < sheet_h:
                    px[x, y] = (0, 0, 0)

path = f"{OUTPUT_DIR}/system_font_glyphs.png"
sheet.save(path)
print(f"Wrote {path} ({sheet_w}x{sheet_h})")
print("\nDone!")
