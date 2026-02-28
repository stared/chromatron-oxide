# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""
Solve for character advance widths using constraint satisfaction.

We have these constraints:
1. Line-break constraints: each line fits in ≤170px, adding next word would exceed 170px
2. Total text width constraints from reference pixel measurements:
   - "freeware" ≈ 55px total advance (rightmost pixel at x=54 from start)
   - "silverspaceship.com" ≈ 133px (x=471 to x=603 = 133px)

Approach: enumerate all possible widths for the ~15 unique characters
that appear in the critical text, using the constraints to prune.

Key observation from the survey: the correct widths are between
sserife.fon widths and Geneva widths. For each character, the
correct width is fon_advance + delta where delta ∈ {0, 1, 2, 3}.
"""
import freetype
import numpy as np
from PIL import Image
import json
from collections import Counter

# ---- Load reference ----
def normalize(path):
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows, cols = np.any(gray, axis=1), np.any(gray, axis=0)
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
    bitmap = np.zeros((bm.rows, bm.width), dtype=bool)
    for by in range(bm.rows):
        for bx in range(bm.width):
            if bm.buffer[by * bm.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                bitmap[by, bx] = True
    glyphs[ch] = {'bitmap': bitmap, 'bearing_x': face.glyph.bitmap_left,
                   'bearing_y': face.glyph.bitmap_top, 'fon_advance': face.glyph.advance.x >> 6}

fon_widths = {chr(c): glyphs[chr(c)]['fon_advance'] for c in range(32, 127)}

# ---- Text rendering ----
def render_text_at(mask, text, x, y, widths):
    pen_x = x
    for ch in text:
        g = glyphs.get(ch)
        if g is not None:
            dx = pen_x + g['bearing_x']
            dy = y + FONT_ASCENT - g['bearing_y']
            bm = g['bitmap']
            for by in range(bm.shape[0]):
                for bx in range(bm.shape[1]):
                    if bm[by, bx]:
                        px, py = dx + bx, dy + by
                        if 0 <= px < mask.shape[1] and 0 <= py < mask.shape[0]:
                            mask[py, px] = True
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

INSTRUCTION = "Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel."

# ---- Identify unique characters and their roles ----
all_text = INSTRUCTION + "freeware" + "silverspaceship.com"
char_freq = Counter(all_text)

# Characters that appear, sorted by frequency
used_chars = sorted(set(all_text) - {' '})  # handle space separately
print(f"Unique non-space chars: {len(used_chars)}")
print(f"Characters: {''.join(used_chars)}")

# ---- Build constraints ----
# For each pair (line, next_first_word), we need:
# measure(line) ≤ 170 AND measure(line + " " + next_word) > 170
#
# measure(text) = sum of widths[ch] for ch in text
# = sum of (count_of_ch_in_text * width[ch]) for each unique ch

# Let's express constraints in terms of character widths
# Each line's total = sum of character widths
# We can compute: for each character ch, how many times does it appear in each line?

print("\n=== Character counts per line ===\n")
for i, line in enumerate(EXPECTED_LINES):
    counts = Counter(line)
    next_word = EXPECTED_LINES[i + 1].split()[0] if i + 1 < len(EXPECTED_LINES) else None
    overflow_text = f"{line} {next_word}" if next_word else None

    line_w = measure_text(line, fon_widths)
    overflow_w = measure_text(overflow_text, fon_widths) if overflow_text else None

    print(f"  Line {i+1}: '{line}'")
    print(f"    fon_width={line_w}, need ≤170")
    if overflow_text:
        print(f"    overflow: '{overflow_text}' fon_width={overflow_w}, need >170")

# ---- Strategy: systematic enumeration ----
# There are ~30 unique chars, each can be fon+0..fon+3 → 4^30 = too many
# But most characters appear only in a few lines, so we can prune heavily

# Better: for each line, we know the total width must be in range (line_fits, line+nextword_overflows)
# This gives us range constraints on sum(char_counts * widths)

# Let me use a different approach: test widths character by character,
# checking consistency with all constraints after each assignment

# First, compute the "budget" for each line: how much total width can we add
# (over fon_widths) while still keeping line breaks correct

print("\n=== Per-line budgets ===\n")
for i, line in enumerate(EXPECTED_LINES):
    fon_w = measure_text(line, fon_widths)
    max_extra = 170 - fon_w  # max total extra width we can add to this line

    next_word = EXPECTED_LINES[i + 1].split()[0] if i + 1 < len(EXPECTED_LINES) else None
    if next_word:
        overflow = f"{line} {next_word}"
        fon_overflow = measure_text(overflow, fon_widths)
        min_extra_overflow = 171 - fon_overflow  # min extra to make overflow > 170
        print(f"  Line {i+1}: fon={fon_w}, max_extra={max_extra}, overflow_fon={fon_overflow}, min_overflow_extra={min_extra_overflow}")
    else:
        print(f"  Line {i+1}: fon={fon_w}, max_extra={max_extra} (last line)")

# ---- Approach: brute-force the high-frequency characters, derive the rest ----
# High-frequency chars (appearing >5 times in instruction text):
# space(37), t(21), e(19), o(17), i(12), a(11), r(10), h(9), n(9), l(7), b(5), s(5)
# These 12 chars dominate. If we try 4 options each: 4^12 = 16M — too many.
# But with pruning via constraints, it's manageable.

# Even smarter: the total width of each line = sum of char widths
# Line 1 "Drag the REFLECTOR in" has these character counts:
# D:1 r:2 a:1 g:1 ' ':3 t:1 h:1 e:2 R:2 E:2 F:1 L:1 C:1 T:1 O:1 i:1 n:1
# Total = w(D) + 2*w(r) + w(a) + w(g) + 3*w(' ') + w(t) + w(h) + 2*w(e) + ...

# Let me focus on the MOST CONSTRAINED lines first.
# Line 6 "Position the mirror so that" is tightest:
#   fon=118, max_extra=52, but overflow needs >170
#   The overflow would be "Position the mirror so that the"
#   which adds " the" = w(' ') + w(t) + w(h) + w(e)

# For now, let me just use the greedy optimizer result from v3 as starting point
# and manually adjust based on known Windows MS Sans Serif patterns.

# Actually, the KEY insight I've been missing: maybe the reference screenshot
# text was NOT rendered with MS Sans Serif at all, or it's a different size.
# Let me check: does the reference use anti-aliased text? If so, it's not a bitmap font.

print("\n=== Checking reference text for anti-aliasing ===\n")
# Look at the instruction text area: are pixel values binary (0 or 164) or graduated?
text_area = ref[125:300, 448:622]
unique_values = set()
for y in range(text_area.shape[0]):
    for x in range(text_area.shape[1]):
        r, g, b = text_area[y, x]
        if r < 164 or g < 164 or b < 164:  # darker than background
            unique_values.add((int(r), int(g), int(b)))

print(f"Unique dark pixel values in instruction text area: {len(unique_values)}")
for v in sorted(unique_values)[:20]:
    count = np.sum(np.all(text_area == v, axis=2))
    print(f"  RGB{v}: {count} pixels")

# ---- Check the reference "freeware" text precisely ----
print("\n=== Reference 'freeware' precise pixel analysis ===\n")
# "freeware" is at (0, 450) in our coords
# In normalized reference, starts around (0, 453)
fw_area = ref[450:470, 0:60]
print("Unique dark values in freeware area:")
for y in range(fw_area.shape[0]):
    for x in range(fw_area.shape[1]):
        r, g, b = fw_area[y, x]
        if r < 100:
            unique_values.add((int(r), int(g), int(b)))

# Count black vs near-black
black_count = np.sum(np.all(fw_area < 10, axis=2))
dark_count = np.sum(np.all(fw_area < 100, axis=2))
gray_count = np.sum(np.all(np.abs(fw_area.astype(int) - 164) <= 5, axis=2))
total = fw_area.shape[0] * fw_area.shape[1]
print(f"  Black (<10): {black_count}/{total}")
print(f"  Dark (<100): {dark_count}/{total}")
print(f"  Gray (~164): {gray_count}/{total}")
print(f"  Other: {total - black_count - gray_count}/{total}")

# The reference likely uses ClearType or no anti-aliasing.
# If it's purely black + gray (no intermediate values), it's bitmap/no AA.

# ---- Now use the BEST approach: render with each possible width table ----
# and find which width table best reproduces the reference pixel pattern
# in a per-LINE comparison

print("\n\n=== Per-line width optimization ===\n")

# For each line, we know the reference pixel pattern.
# Try rendering the line with different width tables and score the match.

def render_line_and_score(text, x, y, widths, ref_mask):
    """Render one line of text and score against reference."""
    our = np.zeros_like(ref_mask)
    render_text_at(our, text, x, y, widths)

    # Compare just the line's bounding box (y to y+16, x to x+170)
    y1, y2 = y, min(y + 16, ref_mask.shape[0])
    x1, x2 = x, min(x + 170, ref_mask.shape[1])

    region_ours = our[y1:y2, x1:x2]
    region_ref = ref_mask[y1:y2, x1:x2]

    # Score: fraction of pixels that match
    return np.sum(region_ours == region_ref) / region_ref.size

# Reference line y positions
line_ys = [125, 141, 157, 173, 189, 205, 221, 237, 253]  # 16px spacing from 125

# Actually, from reference analysis, lines start at y=128, 144, 160, 176, 192, 208, 224, 240, 256
# But our code draws at y=125, 141, 157, ... (starting at top=125, +16 each)
# The reference has a ~3px offset. Let me check...

# In our code: draw_text_wrapped_in_rect(canvas, font, text, 450, 125, 620, 475)
# So first line at y=125, then 141, 157, etc.
# Reference shows first text at y=128. So there's a 3px offset.
# This might be because the reference image normalization is slightly off,
# or because the original y=125 + some internal offset.

# Let me try both y=125 and y=128 for the first line
for y_start in [125, 126, 127, 128]:
    our = np.zeros_like(ref_mask)
    render_text_at(our, "Drag the REFLECTOR in", 450, y_start, fon_widths)
    for dy in range(-2, 3):
        y1 = y_start + dy
        score = np.sum(our[y1:y1+16, 448:622] == ref_mask[y1:y1+16, 448:622])
        total = ref_mask[y1:y1+16, 448:622].size
        if total > 0:
            pct = score / total
        else:
            pct = 0
        # Only print if interesting
    # Compare the full line region
    score_full = np.sum(our[y_start:y_start+13, 448:622] == ref_mask[y_start:y_start+13, 448:622])
    total_full = ref_mask[y_start:y_start+13, 448:622].size
    print(f"  y_start={y_start}: line match = {score_full/total_full:.4f}")

# Use y_start=125 (our code's value) and let the comparison handle the offset

# ---- Final approach: use the group-based best + manual adjustment ----
# From the v3 greedy search, the best config was +(1,2,1,2,2,1)
# After per-char optimization: instr=0.8653
# The widths that MATTER for pixel match are the ones in the actual text.
# But many optimized values look wrong (e.g. 'b'=9, 'v'=9, '.'=6)

# Let me take a step back. The REFERENCE image is NOT pixel-perfect.
# It's a JPEG screenshot from a website (mobygames.com), with compression.
# The comparison will NEVER reach 100%. The goal is >89.1%.

# The v3 result already gives 86.5% instruction match, which is below Geneva's 89.1%.
# This suggests the glyph SHAPES from sserife.fon are also slightly different
# from the original, not just the widths.

# Let me check: what if we use Geneva glyph bitmaps with Geneva widths?
# (That was the previous best at 89.1%)

print("\n=== Testing: Geneva glyph shapes vs sserife.fon glyph shapes ===")
print("(Both with their native advance widths)")

# Load Geneva glyphs
geneva_face = freetype.Face("assets/fonts/Geneva.ttf", 0)
geneva_face.set_pixel_sizes(0, 13)

geneva_glyphs = {}
for code in range(32, 127):
    ch = chr(code)
    geneva_face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bm = geneva_face.glyph.bitmap
    bitmap = np.zeros((bm.rows, bm.width), dtype=bool)
    for by in range(bm.rows):
        for bx in range(bm.width):
            if bm.buffer[by * bm.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                bitmap[by, bx] = True
    geneva_glyphs[ch] = {'bitmap': bitmap, 'bearing_x': geneva_face.glyph.bitmap_left,
                          'bearing_y': geneva_face.glyph.bitmap_top,
                          'advance': geneva_face.glyph.advance.x >> 6}

geneva_widths = {chr(c): geneva_glyphs[chr(c)]['advance'] for c in range(32, 127)}

# Render with Geneva shapes and widths
def render_text_geneva(mask, text, x, y, widths):
    pen_x = x
    for ch in text:
        g = geneva_glyphs.get(ch)
        if g is not None:
            dx = pen_x + g['bearing_x']
            dy = y + 11 - g['bearing_y']  # Geneva ascent might differ
            bm = g['bitmap']
            for by in range(bm.shape[0]):
                for bx in range(bm.shape[1]):
                    if bm[by, bx]:
                        px, py = dx + bx, dy + by
                        if 0 <= px < mask.shape[1] and 0 <= py < mask.shape[0]:
                            mask[py, px] = True
        pen_x += widths.get(ch, 6)

# Test Geneva
our_geneva = np.zeros((480, 640), dtype=bool)
lines = word_wrap(INSTRUCTION, 170, geneva_widths)
cy = 125
for line in lines:
    if cy + 16 > 475: break
    render_text_geneva(our_geneva, line, 450, cy, geneva_widths)
    cy += 16
render_text_geneva(our_geneva, "freeware", 0, 450, geneva_widths)
render_text_geneva(our_geneva, "silverspaceship.com", 470, 450, geneva_widths)

instr_match = np.sum(our_geneva[120:300, 448:622] == ref_mask[120:300, 448:622]) / ref_mask[120:300, 448:622].size
print(f"\nGeneva shapes + Geneva widths: instr={instr_match:.4f}, {len(lines)} lines")
for i, line in enumerate(lines):
    match = "✓" if i < len(EXPECTED_LINES) and line == EXPECTED_LINES[i] else "✗"
    print(f"  {i+1}. {match} '{line}'")

# Test: sserife.fon shapes + Geneva widths
our_fon_geneva = np.zeros((480, 640), dtype=bool)
lines = word_wrap(INSTRUCTION, 170, geneva_widths)
cy = 125
for line in lines:
    if cy + 16 > 475: break
    render_text_at(our_fon_geneva, line, 450, cy, geneva_widths)
    cy += 16
render_text_at(our_fon_geneva, "freeware", 0, 450, geneva_widths)
render_text_at(our_fon_geneva, "silverspaceship.com", 470, 450, geneva_widths)

instr_match2 = np.sum(our_fon_geneva[120:300, 448:622] == ref_mask[120:300, 448:622]) / ref_mask[120:300, 448:622].size
print(f"\nsserife.fon shapes + Geneva widths: instr={instr_match2:.4f}, {len(lines)} lines")

# Test: sserife.fon shapes + v3 optimized widths (from find_best_widths_v3)
best_v3 = dict(fon_widths)
# Apply the v3 result (from the output above)
v3_overrides = {
    ' ': 5, '.': 6, 'C': 9, 'D': 8, 'E': 9, 'F': 9, 'L': 8, 'O': 9,
    'P': 9, 'R': 9, 'T': 9, 'Y': 7, 'a': 8, 'b': 9, 'c': 6, 'd': 6,
    'e': 8, 'f': 5, 'g': 8, 'h': 8, 'i': 3, 'k': 7, 'l': 3, 'm': 10,
    'n': 8, 'o': 7, 'p': 9, 'r': 5, 's': 7, 't': 5, 'u': 6, 'v': 9, 'w': 10, 'x': 6,
}
best_v3.update(v3_overrides)

our_v3 = np.zeros((480, 640), dtype=bool)
lines_v3 = word_wrap(INSTRUCTION, 170, best_v3)
cy = 125
for line in lines_v3:
    if cy + 16 > 475: break
    render_text_at(our_v3, line, 450, cy, best_v3)
    cy += 16
render_text_at(our_v3, "freeware", 0, 450, best_v3)
render_text_at(our_v3, "silverspaceship.com", 470, 450, best_v3)

instr_match3 = np.sum(our_v3[120:300, 448:622] == ref_mask[120:300, 448:622]) / ref_mask[120:300, 448:622].size
print(f"\nsserife.fon shapes + v3 widths: instr={instr_match3:.4f}, {len(lines_v3)} lines")

# ---- Save comparison image ----
comp = np.full((480, 640 * 3, 3), 164, dtype=np.uint8)

# Left: reference text only
for y in range(480):
    for x in range(640):
        if ref_mask[y, x]:
            comp[y, x] = [0, 0, 0]

# Middle: sserife.fon + v3 widths with diff
for y in range(480):
    for x in range(640):
        rx = x + 640
        if our_v3[y, x] and ref_mask[y, x]:
            comp[y, rx] = [0, 0, 0]
        elif our_v3[y, x]:
            comp[y, rx] = [0, 0, 255]
        elif ref_mask[y, x]:
            comp[y, rx] = [255, 0, 255]

# Right: Geneva shapes + Geneva widths with diff
for y in range(480):
    for x in range(640):
        rx = x + 640 * 2
        if our_geneva[y, x] and ref_mask[y, x]:
            comp[y, rx] = [0, 0, 0]
        elif our_geneva[y, x]:
            comp[y, rx] = [0, 0, 255]
        elif ref_mask[y, x]:
            comp[y, rx] = [255, 0, 255]

Image.fromarray(comp).save("screenshots/width_comparison_3way.png")
print("\nSaved: screenshots/width_comparison_3way.png")
print("[Reference | sserife.fon+v3 | Geneva]")
