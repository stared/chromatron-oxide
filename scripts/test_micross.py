# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""Test Microsoft Sans Serif (micross.ttf) rendering vs reference-extracted glyphs.

Renders all ASCII 32-126 at 8pt/96dpi with mono hinting and compares
against the 41 reference-extracted glyphs from screenshots.
"""
import numpy as np
from PIL import Image
import freetype
import json

MICROSS_PATH = "assets/fonts/micross.ttf"
WINE_FON_PATH = "assets/fonts/sserife.fon"
WIDTHS_PATH = "scripts/final_widths.json"
REF_PATH = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"

FONT_HEIGHT = 13
FONT_ASCENT = 11

# Load advance widths
with open(WIDTHS_PATH) as f:
    advances = json.load(f)

# ---- Load micross.ttf at various sizes ----
print("=== Testing micross.ttf ===")
face = freetype.Face(MICROSS_PATH)

# Try different sizes to find the best match
# 8pt at 96dpi = 8 * 96/72 = 10.67px
# Common pixel sizes to try
sizes_to_try = [
    ("8pt/96dpi", 8, 96),
    ("8pt/72dpi", 8, 72),
    ("10pt/96dpi", 10, 96),
    ("11pt/96dpi", 11, 96),
    ("10px", None, None),  # pixel size
    ("11px", None, None),
    ("12px", None, None),
    ("13px", None, None),
]

# Load reference for comparison
def normalize(path):
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows, cols = np.any(gray, axis=1), np.any(gray, axis=0)
    y1, y2 = int(np.argmax(rows)), int(arr.shape[0] - np.argmax(rows[::-1]))
    x1, x2 = int(np.argmax(cols)), int(arr.shape[1] - np.argmax(cols[::-1]))
    cropped = arr[y1:y2, x1:x2]
    result = np.full((480, 640, 3), 164, dtype=np.uint8)
    ph, pw = min(cropped.shape[0], 480), min(cropped.shape[1], 640)
    result[:ph, :pw] = cropped[:ph, :pw]
    return result

ref = normalize(REF_PATH)
ref_mask = np.all(ref < 50, axis=2)

# Extract reference 'e' glyph for comparison (appears many times, easy to find)
# From level 1, line 1 "Drag the REFLECTOR in" - 'e' in "the" at position ~
# Actually, let's just use the extraction from the main script's output
# Instead, let's render each size and show metrics

for label, pt_size, dpi in sizes_to_try:
    face = freetype.Face(MICROSS_PATH)
    if pt_size:
        face.set_char_size(pt_size * 64, 0, dpi, 0)
    else:
        px = int(label.replace("px", ""))
        face.set_pixel_sizes(0, px)

    # Get font metrics
    asc = face.size.ascender / 64
    desc = face.size.descender / 64
    height = face.size.height / 64

    # Render 'e' as test
    face.load_char('e', freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bm = face.glyph.bitmap
    adv = face.glyph.advance.x / 64

    print(f"\n{label}: ascender={asc:.1f} descender={desc:.1f} height={height:.1f}")
    print(f"  'e': bitmap {bm.width}x{bm.rows}, advance={adv:.0f}, "
          f"bearing=({face.glyph.bitmap_left}, {face.glyph.bitmap_top})")

    # Render all printable ASCII and count total black pixels
    total_px = 0
    for code in range(33, 127):
        face.load_char(chr(code), freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
        bm = face.glyph.bitmap
        for by in range(bm.rows):
            for bx in range(bm.width):
                if bm.buffer[by * bm.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                    total_px += 1
    print(f"  Total black pixels (all glyphs): {total_px}")

# ---- Now do detailed comparison for best candidate ----
print("\n\n=== Detailed comparison: 8pt/96dpi ===")
face = freetype.Face(MICROSS_PATH)
face.set_char_size(8 * 64, 0, 96, 0)

# Also load Wine sserife.fon for 3-way comparison
wine_face = freetype.Face(WINE_FON_PATH, 0)
wine_face.select_size(0)
wine_face.set_charmap(wine_face.charmaps[0])

# Build sprite sheet: 3 rows per char (REF, micross, wine)
OFFSET_0_CHARS = {'t', 'f', 'T'}

# First, extract REF glyphs from level 1 screenshot (simplified)
# We know instruction text starts at y=128, pen_x=450
INSTRUCTION_LINES = [
    "Drag the REFLECTOR in",
    "the toolbox above onto",
    "the board and place it in",
    "front of the laser beam.",
    "Click on it to rotate it.",
    "Position the mirror so that",
    "the laser beam is",
    "reflected into the",
    "pinwheel.",
]
Y_STARTS = [128, 144, 160, 176, 192, 208, 224, 240, 256]

def get_islands(mask, y_start, x_left, x_right, height=13):
    strip = mask[y_start:y_start+height, x_left:x_right]
    col_profile = np.sum(strip, axis=0)
    islands = []
    in_island = False
    start = 0
    for i in range(len(col_profile)):
        if col_profile[i] > 0:
            if not in_island:
                start = i
                in_island = True
        else:
            if in_island:
                islands.append((x_left + start, x_left + i - 1))
                in_island = False
    if in_island:
        islands.append((x_left + start, x_left + len(col_profile) - 1))
    return islands

ref_glyphs = {}  # ch -> bitmap_2d
for line_text, y in zip(INSTRUCTION_LINES, Y_STARTS):
    islands = get_islands(ref_mask, y, 445, 625)
    non_space = [c for c in line_text if c != ' ']
    if len(islands) == len(non_space):
        for ch, (s, e) in zip(non_space, islands):
            bm = ref_mask[y:y+13, s:e+1]
            if ch not in ref_glyphs:
                ref_glyphs[ch] = bm
    elif len(islands) == len(non_space) - 1:
        # Handle 1 merge - just skip for this test
        pass

print(f"Extracted {len(ref_glyphs)} reference glyphs from level 1")

# Compare micross vs reference for each extracted char
print("\nChar  REF_px  micro_px  wine_px  micro_match  wine_match")
print("-" * 60)

match_count_micro = 0
match_count_wine = 0
total_compared = 0

for ch in sorted(ref_glyphs.keys()):
    ref_bm = ref_glyphs[ch]
    ref_px = int(np.sum(ref_bm))

    # Render with micross
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bm = face.glyph.bitmap
    micro_bitmap = np.zeros((bm.rows, bm.width), dtype=bool)
    for by in range(bm.rows):
        for bx in range(bm.width):
            if bm.buffer[by * bm.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                micro_bitmap[by, bx] = True
    micro_px = int(np.sum(micro_bitmap))

    # Render with wine
    wine_face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bm_w = wine_face.glyph.bitmap
    wine_bitmap = np.zeros((bm_w.rows, bm_w.width), dtype=bool)
    for by in range(bm_w.rows):
        for bx in range(bm_w.width):
            if bm_w.buffer[by * bm_w.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                wine_bitmap[by, bx] = True
    wine_px = int(np.sum(wine_bitmap))

    # Shape comparison (pad to same size if needed)
    def compare_bitmaps(a, b):
        h = max(a.shape[0], b.shape[0])
        w = max(a.shape[1], b.shape[1])
        pa = np.zeros((h, w), dtype=bool)
        pb = np.zeros((h, w), dtype=bool)
        pa[:a.shape[0], :a.shape[1]] = a
        pb[:b.shape[0], :b.shape[1]] = b
        return np.array_equal(pa, pb), int(np.sum(pa != pb))

    micro_match, micro_diff = compare_bitmaps(ref_bm, micro_bitmap)
    wine_match, wine_diff = compare_bitmaps(ref_bm, wine_bitmap)

    if micro_match:
        match_count_micro += 1
    if wine_match:
        match_count_wine += 1
    total_compared += 1

    m_tag = "EXACT" if micro_match else f"diff={micro_diff}"
    w_tag = "EXACT" if wine_match else f"diff={wine_diff}"

    print(f"  {ch}   {ref_px:4d}    {micro_px:4d}      {wine_px:4d}     {m_tag:<12s}  {w_tag}")

print(f"\nMicross exact matches: {match_count_micro}/{total_compared}")
print(f"Wine exact matches: {match_count_wine}/{total_compared}")

# Also try different hinting modes
print("\n\n=== Trying different FreeType load flags ===")
load_modes = [
    ("MONO", freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO),
    ("MONO+FORCE_AUTOHINT", freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO | freetype.FT_LOAD_FORCE_AUTOHINT),
    ("MONO+NO_HINTING", freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO | freetype.FT_LOAD_NO_HINTING),
    ("MONO+NO_AUTOHINT", freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO | freetype.FT_LOAD_NO_AUTOHINT),
]

for mode_name, flags in load_modes:
    face = freetype.Face(MICROSS_PATH)
    face.set_char_size(8 * 64, 0, 96, 0)

    matches = 0
    total_diff = 0
    for ch in ref_glyphs:
        ref_bm = ref_glyphs[ch]
        face.load_char(ch, flags)
        bm = face.glyph.bitmap
        micro_bitmap = np.zeros((bm.rows, bm.width), dtype=bool)
        for by in range(bm.rows):
            for bx in range(bm.width):
                if bm.buffer[by * bm.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                    micro_bitmap[by, bx] = True

        h = max(ref_bm.shape[0], micro_bitmap.shape[0])
        w = max(ref_bm.shape[1], micro_bitmap.shape[1])
        pa = np.zeros((h, w), dtype=bool)
        pb = np.zeros((h, w), dtype=bool)
        pa[:ref_bm.shape[0], :ref_bm.shape[1]] = ref_bm
        pb[:micro_bitmap.shape[0], :micro_bitmap.shape[1]] = micro_bitmap

        if np.array_equal(pa, pb):
            matches += 1
        total_diff += int(np.sum(pa != pb))

    print(f"  {mode_name}: {matches}/{len(ref_glyphs)} exact, total_diff={total_diff} px")
