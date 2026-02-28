# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""
Find the correct MS Sans Serif character advance widths by comparing
rendered text against the reference screenshot.

Strategy:
1. Extract glyph bitmaps from sserife.fon (shapes are correct)
2. Try width tables from different sources + interpolations
3. For each candidate: simulate word-wrap, render text, compare to reference
4. Find the width table that produces identical line breaks AND best pixel match

Known reference line breaks for Level 1 instruction text:
  1. "Drag the REFLECTOR in"
  2. "the toolbox above onto"
  3. "the board and place it in"
  4. "front of the laser beam."
  5. "Click on it to rotate it."
  6. "Position the mirror so that"
  7. "the laser beam is"
  8. "reflected into the"
  9. "pinwheel."
"""
import freetype
import numpy as np
from PIL import Image
import json
from itertools import product

# ---- Load reference ----
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
ref_text_mask = np.all(ref < 50, axis=2)  # black pixels = text

# ---- Load glyph bitmaps from sserife.fon ----
face = freetype.Face("assets/fonts/sserife.fon", 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])

FONT_HEIGHT = 13
FONT_ASCENT = 11

glyphs = {}
for code in range(32, 127):
    ch = chr(code)
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bm = face.glyph.bitmap
    bw, bh, pitch = bm.width, bm.rows, bm.pitch
    bitmap = []
    for row in range(bh):
        row_bytes = []
        for col_byte in range(pitch):
            idx = row * pitch + col_byte
            row_bytes.append(bm.buffer[idx] if idx < len(bm.buffer) else 0)
        bitmap.append(row_bytes)
    glyphs[ch] = {
        'width': bw, 'height': bh, 'pitch': pitch,
        'bearing_x': face.glyph.bitmap_left,
        'bearing_y': face.glyph.bitmap_top,
        'bitmap': bitmap,
        'fon_advance': face.glyph.advance.x >> 6,
    }

# ---- Word-wrap simulation ----
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

# ---- Render text to numpy array ----
def render_glyph(arr, ch, x, y, widths):
    """Render a single glyph at (x, y) onto arr. Returns advance width."""
    g = glyphs.get(ch)
    if not g:
        return widths.get(ch, 6)

    dst_x = x + g['bearing_x']
    dst_y = y + FONT_ASCENT - g['bearing_y']

    for by in range(g['height']):
        for bx in range(g['width']):
            byte_idx = bx >> 3
            bit_idx = 7 - (bx & 7)
            if byte_idx < len(g['bitmap'][by]) and g['bitmap'][by][byte_idx] & (1 << bit_idx):
                px = dst_x + bx
                py = dst_y + by
                if 0 <= px < arr.shape[1] and 0 <= py < arr.shape[0]:
                    arr[py, px] = True
    return widths.get(ch, g['fon_advance'])

def render_text_at(arr, text, x, y, widths):
    """Render a string at (x, y)."""
    pen_x = x
    for ch in text:
        adv = render_glyph(arr, ch, pen_x, y, widths)
        pen_x += adv

def render_full_frame(widths):
    """Render the complete Level 1 text overlay matching game layout."""
    text_mask = np.zeros((480, 640), dtype=bool)

    # Instruction text: word-wrapped in rect (450, 125, 620, 475)
    instruction = "Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel."
    lines = word_wrap(instruction, 170, widths)
    cy = 125
    for line in lines:
        if cy + 16 > 475:
            break
        render_text_at(text_mask, line, 450, cy, widths)
        cy += 16

    # "freeware" at (0, 450)
    render_text_at(text_mask, "freeware", 0, 450, widths)

    # "silverspaceship.com" at (470, 450)
    render_text_at(text_mask, "silverspaceship.com", 470, 450, widths)

    return text_mask

def compare_text_regions(our_mask, ref_mask):
    """Compare text pixels in key regions. Returns dict of scores."""
    regions = {
        "instruction": (450, 125, 620, 350),
        "freeware": (0, 448, 80, 470),
        "silverspaceship": (468, 448, 640, 470),
    }
    scores = {}
    for name, (x1, y1, x2, y2) in regions.items():
        our_region = our_mask[y1:y2, x1:x2]
        ref_region = ref_mask[y1:y2, x1:x2]
        total = our_region.size
        identical = int(np.sum(our_region == ref_region))
        scores[name] = identical / total
    # Overall text area
    our_all = our_mask[125:475, 0:640]
    ref_all = ref_mask[125:475, 0:640]
    scores["overall_text"] = int(np.sum(our_all == ref_all)) / our_all.size
    return scores

# ---- Reference line breaks (known from reference screenshot analysis) ----
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

# ---- Candidate width tables ----
# Start with sserife.fon widths as base
fon_widths = {chr(c): glyphs[chr(c)]['fon_advance'] for c in range(32, 127)}

# Characters that appear in the instruction text + bottom labels
used_chars = set(INSTRUCTION_TEXT + "freeware" + "silverspaceship.com" + "You win!(won)")

# Strategy: for each character, try widths from fon_advance to fon_advance + 3
# But first, identify which characters MUST be wider based on line-break constraints

print("=== Constraint Analysis ===\n")
print("Line-break constraints (each line must fit in 170px):")
for i, line in enumerate(EXPECTED_LINES):
    fon_w = measure_text(line, fon_widths)
    print(f"  {i+1}. [{fon_w:3d}px fon] '{line}'")

# The key constraint: "Position the mirror so that" must fit in ≤ 170px
# But adding "the" on the next word would exceed 170px
# So: measure("Position the mirror so that") ≤ 170
#     measure("Position the mirror so that the") > 170

# Also: "Drag the REFLECTOR in" is on its own line
# So: measure("Drag the REFLECTOR in") ≤ 170
#     measure("Drag the REFLECTOR in the") > 170

print("\n=== Critical overflow constraints ===")
for line, next_word in [
    ("Drag the REFLECTOR in", "the"),
    ("the toolbox above onto", "the"),
    ("the board and place it in", "front"),
    ("front of the laser beam.", "Click"),
    ("Click on it to rotate it.", "Position"),
    ("Position the mirror so that", "the"),
    ("the laser beam is", "reflected"),
    ("reflected into the", "pinwheel."),
]:
    must_fit = measure_text(line, fon_widths)
    with_next = measure_text(f"{line} {next_word}", fon_widths)
    print(f"  '{line}' = {must_fit}px (fon), +'{next_word}' = {with_next}px")
    # The constraint: line ≤ 170 AND line + " " + next_word > 170

# Now let's try systematically adding 1px to certain character widths
# Since fon widths are ~74% of needed, we need roughly +1px per ~4 chars
# The most common characters in the text will have the most impact

print("\n=== Character frequency in instruction text ===")
from collections import Counter
freq = Counter(INSTRUCTION_TEXT)
for ch, count in freq.most_common(20):
    fon_w = fon_widths[ch]
    print(f"  '{ch}': appears {count}x, fon_advance={fon_w}")

# Key insight: space appears 38 times. If space goes from 3→4, total gains 38px
# across 9 lines that's ~4px per line. Let's test.

print("\n\n=== Systematic Width Search ===\n")

# Try adding +1 to different character groups and see which combination
# produces the correct 9 line breaks

# Group characters by their fon_advance width:
# 2px: i, j, l, |
# 3px: space, !, (, ), *, ,, -, ., :, ;, f, r, t, [, ]
# 5px: $, s, x, y, z, J, /, \
# 6px: a-h, k, n-q, u-w, 0-9, +, <, =, >, ^, _, #
# 7px: A-C, E, K, P, S, T, V-Z, ~
# 8px: %, D, G, H, N, O, Q, R, U, m, w
# 9px: M
# 11px: @, W

best_score = 0
best_config = None
best_lines = None

# Try different delta patterns for key width groups
# Focus on the most impactful: space (38x), 'e' (22x), 't' (17x), 'o' (13x), etc.
configs_tested = 0

# Build candidates: try adding 0 or +1 to each width group
width_groups = {
    'w2': [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 2],  # i,j,l
    'w3': [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 3],  # space,!,f,r,t,...
    'w5': [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 5],  # s,x,y,z
    'w6': [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 6],  # a-h,k,n-q,...
    'w7': [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 7],  # A,B,C,...
    'w8': [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 8],  # D,G,H,...
}

print("Width groups (used chars only):")
for gname, chars in width_groups.items():
    print(f"  {gname}: {sorted(chars)}")

# Try all combinations of +0/+1/+2 for each group
# But that's 3^6 = 729 combinations - manageable
deltas = [0, 1, 2]
results = []

for d2, d3, d5, d6, d7, d8 in product(deltas, repeat=6):
    test_widths = dict(fon_widths)
    for ch in width_groups['w2']: test_widths[ch] = fon_widths[ch] + d2
    for ch in width_groups['w3']: test_widths[ch] = fon_widths[ch] + d3
    for ch in width_groups['w5']: test_widths[ch] = fon_widths[ch] + d5
    for ch in width_groups['w6']: test_widths[ch] = fon_widths[ch] + d6
    for ch in width_groups['w7']: test_widths[ch] = fon_widths[ch] + d7
    for ch in width_groups['w8']: test_widths[ch] = fon_widths[ch] + d8

    lines = word_wrap(INSTRUCTION_TEXT, 170, test_widths)
    configs_tested += 1

    if lines == EXPECTED_LINES:
        # This config produces correct line breaks! Score it.
        our_mask = render_full_frame(test_widths)
        scores = compare_text_regions(our_mask, ref_text_mask)
        config = (d2, d3, d5, d6, d7, d8)
        results.append((config, scores, test_widths))

        if scores['instruction'] > best_score:
            best_score = scores['instruction']
            best_config = config
            best_lines = lines

print(f"Tested {configs_tested} configurations")
print(f"Correct line breaks found: {len(results)}")

if results:
    print("\n=== Configs with correct line breaks (sorted by instruction match) ===\n")
    results.sort(key=lambda x: -x[1]['instruction'])
    for config, scores, widths in results[:10]:
        d2, d3, d5, d6, d7, d8 = config
        freeware_w = measure_text("freeware", widths)
        silver_w = measure_text("silverspaceship.com", widths)
        print(f"  +({d2},{d3},{d5},{d6},{d7},{d8}) w2-w8: "
              f"instr={scores['instruction']:.3f} "
              f"freeware={scores['freeware']:.3f} "
              f"silver={scores['silverspaceship']:.3f} "
              f"overall={scores['overall_text']:.3f} "
              f"| freeware={freeware_w}px silver={silver_w}px")

    # Show best config details
    print(f"\n=== Best Config: +{best_config} ===\n")
    best_widths = results[0][2]
    lines = word_wrap(INSTRUCTION_TEXT, 170, best_widths)
    for i, line in enumerate(lines):
        w = measure_text(line, best_widths)
        print(f"  {i+1}. [{w:3d}px] '{line}'")

    # Show the advance widths for all ASCII 32-126
    print("\n=== Best advance widths (all ASCII 32-126) ===\n")
    for code in range(32, 127):
        ch = chr(code)
        old = fon_widths[ch]
        new = best_widths[ch]
        delta = new - old
        marker = " *" if delta else ""
        if ch == ' ':
            ch_display = "SP"
        elif ch == '\\':
            ch_display = "\\\\"
        else:
            ch_display = ch
        print(f"  {code:3d} '{ch_display:>2s}': {old} -> {new}{marker}")

    # Save best widths
    with open("scripts/best_widths.json", "w") as f:
        json.dump({ch: best_widths[ch] for ch in sorted(best_widths.keys()) if 32 <= ord(ch) <= 126}, f, indent=2)
    print("\nSaved: scripts/best_widths.json")

else:
    print("\nNo configuration produces the expected line breaks!")
    print("Trying finer-grained search: different deltas per individual characters...")

    # If group-based search fails, we need per-character search
    # But first, let's check what's closest
    print("\n=== Closest matches (by line count) ===")
    closest = []
    for d2, d3, d5, d6, d7, d8 in product(deltas, repeat=6):
        test_widths = dict(fon_widths)
        for ch in width_groups['w2']: test_widths[ch] = fon_widths[ch] + d2
        for ch in width_groups['w3']: test_widths[ch] = fon_widths[ch] + d3
        for ch in width_groups['w5']: test_widths[ch] = fon_widths[ch] + d5
        for ch in width_groups['w6']: test_widths[ch] = fon_widths[ch] + d6
        for ch in width_groups['w7']: test_widths[ch] = fon_widths[ch] + d7
        for ch in width_groups['w8']: test_widths[ch] = fon_widths[ch] + d8
        lines = word_wrap(INSTRUCTION_TEXT, 170, test_widths)
        if len(lines) == 9:
            closest.append(((d2,d3,d5,d6,d7,d8), lines))

    print(f"  Configs giving 9 lines: {len(closest)}")
    for config, lines in closest[:5]:
        print(f"\n  Config +{config}:")
        for i, line in enumerate(lines):
            match = "OK" if i < len(EXPECTED_LINES) and line == EXPECTED_LINES[i] else "DIFF"
            expected = EXPECTED_LINES[i] if i < len(EXPECTED_LINES) else ""
            if match == "DIFF":
                print(f"    {i+1}. [{match}] '{line}'")
                print(f"       expected: '{expected}'")
            else:
                print(f"    {i+1}. [{match}] '{line}'")
