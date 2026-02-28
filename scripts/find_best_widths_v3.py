# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""
Find exact per-character advance widths. v3: Start from the group-based
configs that produce correct line breaks, then do per-character greedy
optimization for pixel match.
"""
import freetype
import numpy as np
from PIL import Image
import json
from itertools import product
from collections import Counter

# ---- Load reference (normalized) ----
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

# ---- Helpers ----
def render_glyph_at(mask, ch, x, y):
    g = glyphs.get(ch)
    if not g: return
    dx, dy = x + g['bearing_x'], y + FONT_ASCENT - g['bearing_y']
    for by in range(g['height']):
        for bx in range(g['width']):
            if g['bitmap'][by][bx >> 3] & (1 << (7 - (bx & 7))):
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

def render_and_score(widths):
    """Render full text overlay and score against reference."""
    our_mask = np.zeros((480, 640), dtype=bool)
    lines = word_wrap(INSTRUCTION_TEXT, 170, widths)
    cy = 125
    for line in lines:
        if cy + 16 > 475: break
        render_text_at(our_mask, line, 450, cy, widths)
        cy += 16
    render_text_at(our_mask, "freeware", 0, 450, widths)
    render_text_at(our_mask, "silverspaceship.com", 470, 450, widths)

    instr_match = np.sum(our_mask[120:300, 448:622] == ref_mask[120:300, 448:622]) / ref_mask[120:300, 448:622].size
    bottom_match = np.sum(our_mask[448:475, 0:640] == ref_mask[448:475, 0:640]) / ref_mask[448:475, 0:640].size
    all_match = np.sum(our_mask == ref_mask) / our_mask.size
    return instr_match, bottom_match, all_match, our_mask

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

# ---- Step 1: Find ALL group-based configs with correct line breaks ----
# Characters used in the text
used_chars = set(INSTRUCTION_TEXT + "freewaresilverspaceship.com")

width_groups = {
    2: [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 2],
    3: [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 3],
    5: [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 5],
    6: [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 6],
    7: [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 7],
    8: [ch for ch in used_chars if ch in fon_widths and fon_widths[ch] == 8],
}

print("=== Step 1: Group-based search for correct line breaks ===\n")
correct_configs = []
deltas = [0, 1, 2]

for d2, d3, d5, d6, d7, d8 in product(deltas, repeat=6):
    test_widths = dict(fon_widths)
    for ch in width_groups[2]: test_widths[ch] = fon_widths[ch] + d2
    for ch in width_groups[3]: test_widths[ch] = fon_widths[ch] + d3
    for ch in width_groups[5]: test_widths[ch] = fon_widths[ch] + d5
    for ch in width_groups[6]: test_widths[ch] = fon_widths[ch] + d6
    for ch in width_groups[7]: test_widths[ch] = fon_widths[ch] + d7
    for ch in width_groups[8]: test_widths[ch] = fon_widths[ch] + d8
    if word_wrap(INSTRUCTION_TEXT, 170, test_widths) == EXPECTED_LINES:
        correct_configs.append((d2, d3, d5, d6, d7, d8, dict(test_widths)))

print(f"Found {len(correct_configs)} group configs with correct line breaks")

# Score each and pick the best
print("\nScoring each config (pixel match)...")
scored = []
for d2, d3, d5, d6, d7, d8, widths in correct_configs:
    instr, bottom, overall, _ = render_and_score(widths)
    scored.append((instr + bottom * 0.3, (d2, d3, d5, d6, d7, d8), widths, instr, bottom))

scored.sort(key=lambda x: -x[0])
print("\nTop 5 group configs:")
for score, config, widths, instr, bottom in scored[:5]:
    fw = measure_text("freeware", widths)
    ss = measure_text("silverspaceship.com", widths)
    print(f"  +{config}: instr={instr:.4f} bottom={bottom:.4f} fw={fw}px ss={ss}px")

# ---- Step 2: Per-character greedy optimization from best group config ----
print("\n=== Step 2: Per-character greedy optimization ===\n")

best_widths = dict(scored[0][2])
best_score = scored[0][0]
best_instr = scored[0][3]

# Order characters by frequency in the texts
all_text = INSTRUCTION_TEXT + "freewaresilverspaceship.com"
chars_by_freq = [ch for ch, _ in Counter(all_text).most_common() if ch in fon_widths]

print(f"Starting from config +{scored[0][1]}, instr={best_instr:.4f}")
print(f"Optimizing {len(chars_by_freq)} characters...\n")

iteration = 0
improved = True
while improved and iteration < 50:
    improved = False
    iteration += 1
    for ch in chars_by_freq:
        current_w = best_widths[ch]
        for test_w in [current_w - 1, current_w + 1]:
            if test_w < 1 or test_w > 20:
                continue
            test_widths = dict(best_widths)
            test_widths[ch] = test_w
            if word_wrap(INSTRUCTION_TEXT, 170, test_widths) != EXPECTED_LINES:
                continue
            instr, bottom, overall, _ = render_and_score(test_widths)
            score = instr + bottom * 0.3
            if score > best_score + 0.0001:
                old_w = best_widths[ch]
                best_widths[ch] = test_w
                best_score = score
                best_instr = instr
                improved = True
                print(f"  iter {iteration}: '{ch}' {old_w}->{test_w} instr={instr:.4f} bottom={bottom:.4f}")

print(f"\nAfter optimization: instr={best_instr:.4f}")

# ---- Step 3: Wider search — try +/- 2 for each character ----
print("\n=== Step 3: Wider per-character search (±2) ===\n")
improved = True
iteration = 0
while improved and iteration < 20:
    improved = False
    iteration += 1
    for ch in chars_by_freq:
        current_w = best_widths[ch]
        for test_w in [current_w - 2, current_w + 2]:
            if test_w < 1 or test_w > 20:
                continue
            test_widths = dict(best_widths)
            test_widths[ch] = test_w
            if word_wrap(INSTRUCTION_TEXT, 170, test_widths) != EXPECTED_LINES:
                continue
            instr, bottom, overall, _ = render_and_score(test_widths)
            score = instr + bottom * 0.3
            if score > best_score + 0.0001:
                old_w = best_widths[ch]
                best_widths[ch] = test_w
                best_score = score
                best_instr = instr
                improved = True
                print(f"  iter {iteration}: '{ch}' {old_w}->{test_w} instr={instr:.4f}")

# ---- Final results ----
print("\n=== Final advance widths ===\n")
print("Code Char FON -> Final")
for code in range(32, 127):
    ch = chr(code)
    old = fon_widths[ch]
    new = best_widths.get(ch, old)
    delta = new - old
    ch_display = repr(ch) if ch not in (' ',) else "'SP'"
    marker = f" (+{delta})" if delta > 0 else f" ({delta})" if delta < 0 else ""
    print(f"  {code:3d} {ch_display:>6s}: {old:2d} -> {new:2d}{marker}")

# Word-wrap
print("\nFinal word-wrap:")
lines = word_wrap(INSTRUCTION_TEXT, 170, best_widths)
for i, line in enumerate(lines):
    w = measure_text(line, best_widths)
    print(f"  {i+1}. [{w:3d}px] '{line}'")

# Scores
instr, bottom, overall, our_mask = render_and_score(best_widths)
print(f"\nInstruction: {instr:.4f}")
print(f"Bottom text: {bottom:.4f}")
print(f"Overall:     {overall:.4f}")
print(f"freeware:    {measure_text('freeware', best_widths)}px (ref ~55px)")
print(f"silver:      {measure_text('silverspaceship.com', best_widths)}px (ref ~133px)")

# Save
output = {chr(c): best_widths.get(chr(c), fon_widths[chr(c)]) for c in range(32, 127)}
with open("scripts/best_widths.json", "w") as f:
    json.dump(output, f, indent=2)
print("\nSaved: scripts/best_widths.json")

# Comparison image
comp = np.full((480, 640*2, 3), 164, dtype=np.uint8)
comp[ref_mask, :3] = [0, 0, 0]  # left: reference
for y in range(480):
    for x in range(640):
        rx = x + 640
        if our_mask[y, x] and ref_mask[y, x]:
            comp[y, rx] = [0, 0, 0]
        elif our_mask[y, x]:
            comp[y, rx] = [0, 0, 255]  # extra (blue)
        elif ref_mask[y, x]:
            comp[y, rx] = [255, 0, 255]  # missing (magenta)
Image.fromarray(comp).save("screenshots/text_width_comparison.png")
print("Saved: screenshots/text_width_comparison.png")
