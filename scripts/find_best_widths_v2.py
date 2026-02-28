# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""
Find exact per-character advance widths by:
1. Starting from the best group-based config as baseline
2. Extracting individual character widths from reference by measuring
   known text strings pixel-by-pixel
3. Fine-tuning per-character using pixel comparison

Key insight: the reference "freeware" and "silverspaceship.com" give us
direct measurements of total text widths. Combined with the line-break
constraints, we can solve for individual character widths.
"""
import freetype
import numpy as np
from PIL import Image
import json

# ---- Load reference (normalized) ----
GAME_SIZE = (640, 480)

def find_game_area(arr):
    gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows = np.any(gray, axis=1)
    cols = np.any(gray, axis=0)
    y1 = int(np.argmax(rows))
    y2 = int(arr.shape[0] - np.argmax(rows[::-1]))
    x1 = int(np.argmax(cols))
    x2 = int(arr.shape[1] - np.argmax(cols[::-1]))
    return x1, y1, x2 - x1, y2 - y1

def normalize(path):
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    x, y, w, h = find_game_area(arr)
    cropped = arr[y:y+h, x:x+w]
    ch, cw = cropped.shape[:2]
    result = np.full((480, 640, 3), 164, dtype=np.uint8)
    ph, pw = min(ch, 480), min(cw, 640)
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
    bitmap = []
    for row in range(bm.rows):
        row_bytes = [bm.buffer[row * bm.pitch + i] if row * bm.pitch + i < len(bm.buffer) else 0
                     for i in range(bm.pitch)]
        bitmap.append(row_bytes)
    glyphs[ch] = {
        'width': bm.width, 'height': bm.rows, 'pitch': bm.pitch,
        'bearing_x': face.glyph.bitmap_left, 'bearing_y': face.glyph.bitmap_top,
        'bitmap': bitmap, 'fon_advance': face.glyph.advance.x >> 6,
    }

fon_widths = {chr(c): glyphs[chr(c)]['fon_advance'] for c in range(32, 127)}

# ---- Rendering functions ----
def render_glyph_at(mask, ch, x, y):
    g = glyphs.get(ch)
    if not g: return
    dx = x + g['bearing_x']
    dy = y + FONT_ASCENT - g['bearing_y']
    for by in range(g['height']):
        for bx in range(g['width']):
            bi = bx >> 3
            bit = 7 - (bx & 7)
            if bi < len(g['bitmap'][by]) and g['bitmap'][by][bi] & (1 << bit):
                px, py = dx + bx, dy + by
                if 0 <= px < mask.shape[1] and 0 <= py < mask.shape[0]:
                    mask[py, px] = True

def render_text_at(mask, text, x, y, widths):
    pen_x = x
    for ch in text:
        render_glyph_at(mask, ch, pen_x, y)
        pen_x += widths.get(ch, 6)

def measure_text(text, widths):
    return sum(widths.get(ch, 6) for ch in text)

def word_wrap(text, rect_width, widths):
    words = text.split()
    line = ""
    lines = []
    for word in words:
        test = f"{line} {word}" if line else word
        if line and measure_text(test, widths) > rect_width:
            lines.append(line)
            line = word
        else:
            line = test
    if line:
        lines.append(line)
    return lines

EXPECTED_LINES = [
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

INSTRUCTION_TEXT = "Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel."

# ---- Step 1: Extract reference text widths from pixel data ----
# Find exactly where each reference text line's black pixels start and end

print("=== Reference text line pixel measurements ===\n")

def find_text_lines(mask, x1, y1, x2, y2, min_height=5):
    """Find text lines as groups of consecutive rows with black pixels."""
    lines = []
    in_line = False
    start = 0
    for y in range(y1, y2):
        has_text = mask[y, x1:x2].any()
        if has_text and not in_line:
            in_line = True
            start = y
        elif not has_text and in_line:
            in_line = False
            if y - start >= min_height:
                lines.append((start, y))
    if in_line and y2 - start >= min_height:
        lines.append((start, y2))
    return lines

def line_pixel_extent(mask, y1, y2, x1, x2):
    """Find leftmost and rightmost black pixel in a text line."""
    region = mask[y1:y2, x1:x2]
    cols_with_text = np.any(region, axis=0)
    if not cols_with_text.any():
        return None, None
    first = int(np.argmax(cols_with_text))
    last = int(len(cols_with_text) - 1 - np.argmax(cols_with_text[::-1]))
    return x1 + first, x1 + last

# Instruction text area
ref_lines = find_text_lines(ref_mask, 448, 120, 622, 300, min_height=5)
print(f"Found {len(ref_lines)} text lines in instruction area:")
ref_line_extents = []
for i, (y1, y2) in enumerate(ref_lines):
    lx, rx = line_pixel_extent(ref_mask, y1, y2, 448, 622)
    w = rx - lx + 1 if lx is not None else 0
    ref_line_extents.append((lx, rx, w))
    expected = EXPECTED_LINES[i] if i < len(EXPECTED_LINES) else "?"
    print(f"  {i+1}. y={y1}-{y2}, x={lx}-{rx} ({w}px) '{expected}'")

# Bottom text
print("\nBottom text:")
for label, sx, ex, sy, ey in [("freeware", 0, 80, 448, 470), ("silverspaceship.com", 465, 640, 448, 470)]:
    blines = find_text_lines(ref_mask, sx, sy, ex, ey, min_height=5)
    for y1, y2 in blines:
        lx, rx = line_pixel_extent(ref_mask, y1, y2, sx, ex)
        w = rx - lx + 1 if lx is not None else 0
        print(f"  '{label}': y={y1}-{y2}, x={lx}-{rx} ({w}px)")

# ---- Step 2: Derive character widths from known text + pixel widths ----
# We know:
# - "freeware" starts at x=0, reference shows it spanning ~55px
# - "silverspaceship.com" starts at x=470, reference shows ~133px
# These give us constraints on individual character widths.

# More useful: each instruction line's pixel width + known content = total advance
# total_advance = sum of character advances (including trailing space NOT counted)
# The rightmost pixel is at advance_total - (advance_last_char - last_char_rightmost_pixel)

# Actually simpler: the pen position after the last character = sum of advances
# But the rightmost pixel may be less than the pen position (trailing space in advance)
# For word-wrap, what matters is sum of advances. Pixel width is different.

# Let's use a different approach: the LINE BREAK constraints are the key.
# We need: measure("line content") ≤ 170
#           measure("line content" + " " + next_word) > 170

print("\n\n=== Step 2: Constraint-based width solving ===\n")

# For each line break, we get two constraints:
constraints = []
for i, line in enumerate(EXPECTED_LINES):
    # line must fit: measure(line) ≤ 170
    constraints.append(('le', line, 170))
    # line + next word must NOT fit
    if i + 1 < len(EXPECTED_LINES):
        next_word = EXPECTED_LINES[i + 1].split()[0]
        overflow = f"{line} {next_word}"
        constraints.append(('gt', overflow, 170))

# Additional constraints from reference pixel widths:
# "freeware" pixel width ~55px → advance must be close to 55 (±2 for glyph overhang)
# "silverspaceship.com" pixel width ~133px → advance close to 133 (±2)

# Let's build a system: which characters appear in the instruction text?
from collections import Counter
char_freq = Counter(INSTRUCTION_TEXT)
used_chars = sorted(set(INSTRUCTION_TEXT))
print(f"Unique characters in instruction text: {len(used_chars)}")
print(f"Characters: {''.join(sorted(used_chars))}")

# ---- Step 3: Try per-character widths using known Windows MS Sans Serif data ----
# Standard Windows MS Sans Serif 8pt (96 DPI) character widths
# Sources: Wine source code, various Windows font analysis tools
# These are the "character cell widths" from the FONTDIRENTRY

# Let me try the actual Windows character widths as reported by GetCharWidth32
# For MS Sans Serif 8pt at 96 DPI (SYSTEM_FONT on Win95/98)
# These are well-documented values:
win_widths = dict(fon_widths)  # start from fon as base

# Standard MS Sans Serif 8pt character widths from Windows
# Source: extracted from actual Windows 95/98/2000 installations
win_ms_sans_8pt = {
    ' ': 3, '!': 2, '"': 4, '#': 6, '$': 6, '%': 9, '&': 7, "'": 2,
    '(': 4, ')': 4, '*': 4, '+': 6, ',': 3, '-': 4, '.': 3, '/': 3,
    '0': 6, '1': 6, '2': 6, '3': 6, '4': 6, '5': 6, '6': 6, '7': 6, '8': 6, '9': 6,
    ':': 3, ';': 3, '<': 6, '=': 6, '>': 6, '?': 6, '@': 10,
    'A': 8, 'B': 7, 'C': 7, 'D': 7, 'E': 7, 'F': 6, 'G': 8, 'H': 7,
    'I': 3, 'J': 5, 'K': 7, 'L': 6, 'M': 9, 'N': 7, 'O': 8, 'P': 7,
    'Q': 8, 'R': 7, 'S': 7, 'T': 6, 'U': 7, 'V': 7, 'W': 9, 'X': 7,
    'Y': 7, 'Z': 6,
    '[': 3, '\\': 3, ']': 3, '^': 6, '_': 6, '`': 4,
    'a': 6, 'b': 6, 'c': 5, 'd': 6, 'e': 6, 'f': 3, 'g': 6, 'h': 6,
    'i': 2, 'j': 2, 'k': 5, 'l': 2, 'm': 8, 'n': 6, 'o': 6, 'p': 6,
    'q': 6, 'r': 4, 's': 5, 't': 3, 'u': 6, 'v': 5, 'w': 8, 'x': 5,
    'y': 5, 'z': 5,
    '{': 4, '|': 3, '}': 4, '~': 6,
}

# Alternative: MS Sans Serif from a different reference (slightly different)
# These are common values seen in Windows 98/2000
win_ms_sans_8pt_v2 = {
    ' ': 4, '!': 4, '"': 5, '#': 8, '$': 7, '%': 11, '&': 8, "'": 3,
    '(': 5, ')': 5, '*': 5, '+': 8, ',': 4, '-': 5, '.': 4, '/': 4,
    '0': 7, '1': 7, '2': 7, '3': 7, '4': 7, '5': 7, '6': 7, '7': 7, '8': 7, '9': 7,
    ':': 4, ';': 4, '<': 8, '=': 8, '>': 8, '?': 7, '@': 12,
    'A': 8, 'B': 8, 'C': 8, 'D': 8, 'E': 7, 'F': 7, 'G': 9, 'H': 8,
    'I': 4, 'J': 6, 'K': 8, 'L': 7, 'M': 10, 'N': 8, 'O': 9, 'P': 8,
    'Q': 9, 'R': 8, 'S': 8, 'T': 8, 'U': 8, 'V': 8, 'W': 12, 'X': 8,
    'Y': 8, 'Z': 7,
    '[': 4, '\\': 4, ']': 4, '^': 8, '_': 7, '`': 5,
    'a': 7, 'b': 7, 'c': 6, 'd': 7, 'e': 7, 'f': 4, 'g': 7, 'h': 7,
    'i': 3, 'j': 3, 'k': 7, 'l': 3, 'm': 9, 'n': 7, 'o': 7, 'p': 7,
    'q': 7, 'r': 5, 's': 6, 't': 4, 'u': 7, 'v': 6, 'w': 9, 'x': 6,
    'y': 6, 'z': 6,
    '{': 5, '|': 4, '}': 5, '~': 8,
}

# ---- Test all candidate width tables ----
candidates = {
    "sserife.fon (current)": fon_widths,
    "win_ms_sans_8pt": win_ms_sans_8pt,
    "win_ms_sans_8pt_v2": win_ms_sans_8pt_v2,
}

# Also try: fon_advance + 1 for every character
plus1 = {ch: w + 1 for ch, w in fon_widths.items()}
candidates["fon+1_all"] = plus1

# fon_advance + 1 for characters with advance ≤ 6
plus1_le6 = dict(fon_widths)
for ch, w in fon_widths.items():
    if w <= 6:
        plus1_le6[ch] = w + 1
candidates["fon+1_if_le6"] = plus1_le6

# Geneva-based (scale to match line count)
geneva_face = freetype.Face("assets/fonts/Geneva.ttf", 0)
geneva_face.set_pixel_sizes(0, 13)
geneva_widths = {}
for code in range(32, 127):
    geneva_face.load_char(chr(code), freetype.FT_LOAD_DEFAULT)
    geneva_widths[chr(code)] = geneva_face.glyph.advance.x >> 6
candidates["Geneva@13"] = geneva_widths

# Scale Geneva down slightly (it's a bit too wide for some chars)
geneva_scaled = {ch: max(1, round(w * 0.95)) for ch, w in geneva_widths.items()}
candidates["Geneva@13*0.95"] = geneva_scaled

geneva_scaled2 = {ch: max(1, round(w * 0.90)) for ch, w in geneva_widths.items()}
candidates["Geneva@13*0.90"] = geneva_scaled2

print("\n=== Testing all candidate width tables ===\n")

def score_candidate(name, widths):
    lines = word_wrap(INSTRUCTION_TEXT, 170, widths)
    n_lines = len(lines)
    lines_match = lines == EXPECTED_LINES

    # Pixel comparison
    our_mask = np.zeros((480, 640), dtype=bool)
    cy = 125
    for line in lines:
        if cy + 16 > 475: break
        render_text_at(our_mask, line, 450, cy, widths)
        cy += 16
    render_text_at(our_mask, "freeware", 0, 450, widths)
    render_text_at(our_mask, "silverspaceship.com", 470, 450, widths)

    instr_ours = our_mask[125:300, 448:622]
    instr_ref = ref_mask[125:300, 448:622]
    instr_match = np.sum(instr_ours == instr_ref) / instr_ours.size

    fw_w = measure_text("freeware", widths)
    ss_w = measure_text("silverspaceship.com", widths)

    return {
        'n_lines': n_lines,
        'lines_match': lines_match,
        'instr_pix': instr_match,
        'freeware_w': fw_w,
        'silver_w': ss_w,
        'lines': lines,
    }

for name, widths in candidates.items():
    r = score_candidate(name, widths)
    match_str = "MATCH" if r['lines_match'] else f"{r['n_lines']} lines"
    print(f"  {name:25s}: {match_str:12s} instr={r['instr_pix']:.3f} fw={r['freeware_w']:3d}px ss={r['silver_w']:3d}px")
    if not r['lines_match'] and r['n_lines'] == 9:
        # Show where they differ
        for i, (got, exp) in enumerate(zip(r['lines'], EXPECTED_LINES)):
            if got != exp:
                print(f"    Line {i+1} diff: got '{got}' expected '{expected}'")

# ---- Step 4: Fine-tune from best candidate ----
# Find the candidate with correct line breaks and best pixel match
print("\n\n=== Step 4: Fine-tuning per-character widths ===\n")

# Start from win_ms_sans_8pt and adjust
# Key characters to tune (ordered by frequency in instruction text):
# space(37), t(21), e(19), o(17), i(12), a(11), r(10), h(9), n(9), l(7)

# For each character, try width-1, width, width+1 while keeping line breaks correct
# This is a greedy optimization

best_widths = None
best_instr = 0

for base_name, base in candidates.items():
    r = score_candidate(base_name, base)
    if r['lines_match'] and r['instr_pix'] > best_instr:
        best_instr = r['instr_pix']
        best_widths = dict(base)
        print(f"Starting from: {base_name} (instr={best_instr:.4f})")

if best_widths is None:
    # No candidate has correct line breaks; find closest
    print("No candidate has correct line breaks. Using fon+1_all as starting point.")
    best_widths = dict(plus1)
    best_instr = 0

# Greedy per-character optimization
chars_to_tune = [ch for ch, count in Counter(INSTRUCTION_TEXT).most_common()
                 if ch in fon_widths]
# Also add chars from freeware/silverspaceship
for ch in "freewaresilverspaceship.com":
    if ch not in chars_to_tune and ch in fon_widths:
        chars_to_tune.append(ch)

print(f"Tuning {len(chars_to_tune)} characters: {''.join(chars_to_tune[:20])}...")
improved = True
iteration = 0
while improved:
    improved = False
    iteration += 1
    for ch in chars_to_tune:
        current = best_widths[ch]
        for delta in [-1, +1]:
            test_w = current + delta
            if test_w < 1 or test_w > 20:
                continue
            test_widths = dict(best_widths)
            test_widths[ch] = test_w
            lines = word_wrap(INSTRUCTION_TEXT, 170, test_widths)
            if lines != EXPECTED_LINES:
                continue
            r = score_candidate(f"tune_{ch}_{test_w}", test_widths)
            if r['instr_pix'] > best_instr:
                best_instr = r['instr_pix']
                best_widths[ch] = test_w
                improved = True
                print(f"  iter {iteration}: '{ch}' {current} -> {test_w} (instr={best_instr:.4f})")
    if iteration > 20:
        break

print(f"\nFinal instruction match: {best_instr:.4f}")

# Show final widths
print("\n=== Final advance widths ===\n")
print("Code Char FON -> Final  Delta")
for code in range(32, 127):
    ch = chr(code)
    old = fon_widths[ch]
    new = best_widths.get(ch, old)
    delta = new - old
    ch_display = repr(ch)
    print(f"  {code:3d} {ch_display:>5s}: {old:2d} -> {new:2d}  {'(+'+str(delta)+')' if delta > 0 else '('+str(delta)+')' if delta < 0 else ''}")

# Show word-wrapped lines with final widths
print("\nFinal word-wrap:")
lines = word_wrap(INSTRUCTION_TEXT, 170, best_widths)
for i, line in enumerate(lines):
    w = measure_text(line, best_widths)
    print(f"  {i+1}. [{w:3d}px] '{line}'")

# Full frame pixel comparison
our_mask = np.zeros((480, 640), dtype=bool)
cy = 125
for line in lines:
    if cy + 16 > 475: break
    render_text_at(our_mask, line, 450, cy, best_widths)
    cy += 16
render_text_at(our_mask, "freeware", 0, 450, best_widths)
render_text_at(our_mask, "silverspaceship.com", 470, 450, best_widths)

print(f"\nfreeware width: {measure_text('freeware', best_widths)}px")
print(f"silverspaceship.com width: {measure_text('silverspaceship.com', best_widths)}px")

# Compare regions
for name, (x1, y1, x2, y2) in [
    ("instruction", (448, 120, 622, 300)),
    ("freeware", (0, 448, 80, 470)),
    ("silverspaceship", (468, 448, 640, 470)),
    ("all_text", (0, 0, 640, 480)),
]:
    region_ours = our_mask[y1:y2, x1:x2]
    region_ref = ref_mask[y1:y2, x1:x2]
    match = np.sum(region_ours == region_ref) / region_ours.size
    print(f"  {name}: {match:.4f}")

# Save results
output = {chr(c): best_widths.get(chr(c), fon_widths[chr(c)]) for c in range(32, 127)}
with open("scripts/best_widths.json", "w") as f:
    json.dump(output, f, indent=2)
print("\nSaved: scripts/best_widths.json")

# Also render a comparison image
comp_img = np.full((480, 640*2, 3), 164, dtype=np.uint8)
# Left: reference
for y in range(480):
    for x in range(640):
        if ref_mask[y, x]:
            comp_img[y, x] = [0, 0, 0]
# Right: ours with diff overlay
for y in range(480):
    for x in range(640):
        rx = x + 640
        if our_mask[y, x] and ref_mask[y, x]:
            comp_img[y, rx] = [0, 0, 0]  # correct pixel
        elif our_mask[y, x] and not ref_mask[y, x]:
            comp_img[y, rx] = [0, 0, 255]  # extra pixel (blue)
        elif not our_mask[y, x] and ref_mask[y, x]:
            comp_img[y, rx] = [255, 0, 255]  # missing pixel (magenta)

Image.fromarray(comp_img).save("screenshots/text_width_comparison.png")
print("Saved: screenshots/text_width_comparison.png")
