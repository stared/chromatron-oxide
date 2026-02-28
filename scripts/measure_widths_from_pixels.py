# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""
Extract actual character advance widths from the reference screenshot
by comparing glyph shapes at known positions.

Key insight: we know what text is on each line and where each line starts.
We can use glyph shape matching to find the exact x-position of each
character, which gives us the advance widths directly.

Method: for each known text line, slide the sserife.fon glyph bitmap
across the reference image and find where it matches. The distance between
consecutive character positions = advance width.
"""
import freetype
import numpy as np
from PIL import Image

# ---- Load reference ----
def normalize(path):
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows = np.any(gray, axis=1)
    cols = np.any(gray, axis=0)
    y1 = int(np.argmax(rows))
    y2 = int(arr.shape[0] - np.argmax(rows[::-1]))
    x1 = int(np.argmax(cols))
    x2 = int(arr.shape[1] - np.argmax(cols[::-1]))
    cropped = arr[y1:y2, x1:x2]
    result = np.full((480, 640, 3), 164, dtype=np.uint8)
    ph, pw = min(cropped.shape[0], 480), min(cropped.shape[1], 640)
    result[:ph, :pw] = cropped[:ph, :pw]
    return result

ref = normalize("screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png")
ref_mask = np.all(ref < 50, axis=2)

# ---- Load glyph bitmaps ----
face = freetype.Face("assets/fonts/sserife.fon", 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])
FONT_ASCENT = 11

glyphs = {}
for code in range(32, 127):
    ch = chr(code)
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bm = face.glyph.bitmap
    # Convert to numpy bool array
    bitmap = np.zeros((bm.rows, bm.width), dtype=bool)
    for by in range(bm.rows):
        for bx in range(bm.width):
            if bm.buffer[by * bm.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                bitmap[by, bx] = True
    glyphs[ch] = {
        'bitmap': bitmap,
        'bearing_x': face.glyph.bitmap_left,
        'bearing_y': face.glyph.bitmap_top,
        'fon_advance': face.glyph.advance.x >> 6,
    }

# ---- Known reference text positions ----
# From the reference analysis, instruction text lines start at x≈450, y values:
# Line 1: y=128 "Drag the REFLECTOR in"
# Line 2: y=144 "the toolbox above onto"
# Line 3: y=160 "the board and place it in"
# etc. with 16px spacing

LINES_WITH_Y = [
    (128, "Drag the REFLECTOR in"),
    (144, "the toolbox above onto"),
    (160, "the board and place it in"),
    (176, "front of the laser beam."),
    (192, "Click on it to rotate it."),
    (208, "Position the mirror so that"),
    (224, "the laser beam is"),
    (240, "reflected into the"),
    (256, "pinwheel."),
]

# Bottom text
BOTTOM_LINES = [
    (453, 0, "freeware"),
    (453, 470, "silverspaceship.com"),
]

# ---- Glyph matching ----
def glyph_match_score(ref_mask, glyph_bitmap, x, y, bearing_x, bearing_y):
    """Score how well a glyph bitmap matches the reference at position (x, y)."""
    dx = x + bearing_x
    dy = y + FONT_ASCENT - bearing_y
    gh, gw = glyph_bitmap.shape

    if dy < 0 or dy + gh > ref_mask.shape[0] or dx < 0 or dx + gw > ref_mask.shape[1]:
        return -1

    ref_region = ref_mask[dy:dy+gh, dx:dx+gw]
    # Count matching pixels (both true or both false within the glyph area)
    matches = np.sum(glyph_bitmap == ref_region)
    # Also penalize: glyph pixels that don't match reference
    glyph_pixels = np.sum(glyph_bitmap)
    if glyph_pixels == 0:
        return 0
    correct_glyph = np.sum(glyph_bitmap & ref_region)
    return correct_glyph / glyph_pixels

def find_best_position(ref_mask, ch, approx_x, y, search_range=8):
    """Find the x position where glyph 'ch' best matches the reference."""
    g = glyphs.get(ch)
    if g is None or g['bitmap'].sum() == 0:
        return approx_x, 0.0

    best_x = approx_x
    best_score = -1
    for dx in range(-search_range, search_range + 1):
        test_x = approx_x + dx
        score = glyph_match_score(ref_mask, g['bitmap'], test_x, y, g['bearing_x'], g['bearing_y'])
        if score > best_score:
            best_score = score
            best_x = test_x
    return best_x, best_score

# ---- Extract advance widths ----
print("=== Extracting character advance widths from reference ===\n")

# For each line, find where each character starts
char_advances = {}  # ch -> list of observed advances
line_start_x = 450  # All instruction lines start at x=450

for y, text in LINES_WITH_Y:
    print(f"\nLine at y={y}: '{text}'")
    pen_x = line_start_x

    # First, find the exact starting x by matching the first character
    first_ch = text[0]
    actual_x, score = find_best_position(ref_mask, first_ch, pen_x, y, search_range=5)
    if score > 0.5:
        pen_x = actual_x

    positions = []
    for i, ch in enumerate(text):
        if ch == ' ':
            positions.append((ch, pen_x, 1.0))
            pen_x += glyphs[ch]['fon_advance'] + 2  # guess: space is fon+2
            continue

        actual_x, score = find_best_position(ref_mask, ch, pen_x, y, search_range=4)
        positions.append((ch, actual_x, score))

        # Next character position: glyph advance from actual position
        pen_x = actual_x + glyphs[ch]['fon_advance'] + 1  # rough estimate for next

    # Now compute advances from consecutive positions
    for i in range(len(positions) - 1):
        ch, x1, s1 = positions[i]
        _, x2, s2 = positions[i + 1]

        if s1 < 0.3:  # poor match, skip
            continue

        advance = x2 - x1
        if advance < 1 or advance > 20:
            continue

        if ch not in char_advances:
            char_advances[ch] = []
        char_advances[ch].append(advance)

    # Print character positions
    for ch, x, score in positions:
        ch_display = ch if ch != ' ' else 'SP'
        print(f"  '{ch_display}' at x={x:3d} (score={score:.2f})")

# Also process bottom text
for y, start_x, text in BOTTOM_LINES:
    print(f"\nBottom line at y={y}, x={start_x}: '{text}'")
    pen_x = start_x

    first_ch = text[0]
    actual_x, score = find_best_position(ref_mask, first_ch, pen_x, y, search_range=5)
    if score > 0.5:
        pen_x = actual_x

    positions = []
    for ch in text:
        if ch == ' ':
            positions.append((ch, pen_x, 1.0))
            pen_x += 5
            continue
        actual_x, score = find_best_position(ref_mask, ch, pen_x, y, search_range=4)
        positions.append((ch, actual_x, score))
        pen_x = actual_x + glyphs[ch]['fon_advance'] + 1

    for i in range(len(positions) - 1):
        ch, x1, s1 = positions[i]
        _, x2, s2 = positions[i + 1]
        if s1 < 0.3:
            continue
        advance = x2 - x1
        if 1 <= advance <= 20:
            if ch not in char_advances:
                char_advances[ch] = []
            char_advances[ch].append(advance)

    for ch, x, score in positions:
        ch_display = ch if ch != ' ' else 'SP'
        print(f"  '{ch_display}' at x={x:3d} (score={score:.2f})")

# ---- Compute average advance widths ----
print("\n\n=== Derived advance widths ===\n")
print(f"{'Char':>6} {'FON':>4} {'Measured':>10} {'Median':>7} {'Samples':>8}")

derived_widths = {}
for code in range(32, 127):
    ch = chr(code)
    fon_w = glyphs[ch]['fon_advance']
    if ch in char_advances and len(char_advances[ch]) >= 1:
        values = sorted(char_advances[ch])
        median = values[len(values) // 2]
        avg = sum(values) / len(values)
        derived_widths[ch] = median
        ch_display = repr(ch)
        print(f"  {ch_display:>5}: {fon_w:3d}  {str(values):>30s}  {median:3d}     {len(values):3d}")
    else:
        derived_widths[ch] = fon_w + 1  # default: add 1

# Save
import json
with open("scripts/measured_widths.json", "w") as f:
    json.dump(derived_widths, f, indent=2)
print("\nSaved: scripts/measured_widths.json")
