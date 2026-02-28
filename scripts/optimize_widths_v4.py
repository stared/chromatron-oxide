# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""
Comprehensive width optimizer v4.

Key improvements over v3:
1. Search for optimal (x_start, y_start) text origin
2. Use pixel-level scoring (TP/FP/FN of black pixels, not just region %)
3. Multi-pass optimization with wider search ranges
4. Try measured_widths.json as alternative starting point
5. Per-line diagnostic output
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
ref_mask = np.all(ref < 50, axis=2)  # True where pixel is black in reference

# ---- Load glyph bitmaps from sserife.fon ----
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
    glyphs[ch] = {
        'bitmap': bitmap,
        'bearing_x': face.glyph.bitmap_left,
        'bearing_y': face.glyph.bitmap_top,
        'fon_advance': face.glyph.advance.x >> 6,
    }

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
            h, w = bm.shape
            for by in range(h):
                for bx in range(w):
                    if bm[by, bx]:
                        px, py = dx + bx, dy + by
                        if 0 <= px < mask.shape[1] and 0 <= py < mask.shape[0]:
                            mask[py, px] = True
        pen_x += widths.get(ch, 6)

def measure_text(text, widths):
    return sum(widths.get(ch, 6) for ch in text)

def word_wrap(text, rect_width, widths):
    words = text.split()
    line, lines = "", []
    for word in words:
        test = f"{line} {word}" if line else word
        if line and measure_text(test, widths) > rect_width:
            lines.append(line)
            line = word
        else:
            line = test
    if line: lines.append(line)
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

# ---- Scoring function: F1 score of black pixels ----
def render_full(widths, x_start=450, y_start=125):
    """Render all text, return mask."""
    our = np.zeros((480, 640), dtype=bool)
    lines = word_wrap(INSTRUCTION, 170, widths)
    cy = y_start
    for line in lines:
        if cy + 16 > 475: break
        render_text_at(our, line, x_start, cy, widths)
        cy += 16
    render_text_at(our, "freeware", 0, y_start + 325, widths)  # y_start + 325 ≈ 450
    render_text_at(our, "silverspaceship.com", 470, y_start + 325, widths)
    return our, lines

def score_region(our, ref_mask, y1, y2, x1, x2):
    """F1-style score: precision & recall of black pixels in region."""
    o = our[y1:y2, x1:x2]
    r = ref_mask[y1:y2, x1:x2]
    tp = np.sum(o & r)
    fp = np.sum(o & ~r)
    fn = np.sum(~o & r)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    agreement = np.sum(o == r) / r.size
    return f1, precision, recall, agreement

# ---- Step 1: Find optimal text origin ----
print("=== Step 1: Find optimal text origin (x_start, y_start) ===\n")

# Load v3 best widths
with open("scripts/best_widths.json") as f:
    v3_widths = json.load(f)

best_origin = None
best_f1 = -1

# The freeware/silverspaceship are at fixed y=450, not relative to instruction text
# Let me score them separately

for y_start in range(123, 130):
    for x_start in range(448, 453):
        our = np.zeros((480, 640), dtype=bool)
        lines = word_wrap(INSTRUCTION, 170, v3_widths)
        cy = y_start
        for line in lines:
            if cy + 16 > 475: break
            render_text_at(our, line, x_start, cy, v3_widths)
            cy += 16

        f1, prec, recall, agree = score_region(our, ref_mask, 120, 300, 446, 624)
        if f1 > best_f1:
            best_f1 = f1
            best_origin = (x_start, y_start)
        if f1 > 0.5:
            print(f"  ({x_start}, {y_start}): F1={f1:.4f} P={prec:.4f} R={recall:.4f} Agree={agree:.4f}")

print(f"\nBest origin: ({best_origin[0]}, {best_origin[1]}) F1={best_f1:.4f}")

# Also find best origin for bottom text (freeware, silverspaceship.com)
print("\n--- Bottom text origin search ---")
best_bottom_y = 450
best_bottom_f1 = -1
for bottom_y in range(448, 456):
    our = np.zeros((480, 640), dtype=bool)
    render_text_at(our, "freeware", 0, bottom_y, v3_widths)
    render_text_at(our, "silverspaceship.com", 470, bottom_y, v3_widths)
    f1, prec, recall, agree = score_region(our, ref_mask, 446, 475, 0, 640)
    if f1 > best_bottom_f1:
        best_bottom_f1 = f1
        best_bottom_y = bottom_y
    if f1 > 0.1:
        print(f"  bottom_y={bottom_y}: F1={f1:.4f} P={prec:.4f} R={recall:.4f}")

print(f"Best bottom_y: {best_bottom_y} F1={best_bottom_f1:.4f}")

X_START = best_origin[0]
Y_START = best_origin[1]
BOTTOM_Y = best_bottom_y

# ---- Step 2: Full render + score with correct positions ----
def render_and_score(widths):
    """Render with optimal positions, return (instr_f1, bottom_f1, overall_agree, mask, lines)."""
    our = np.zeros((480, 640), dtype=bool)
    lines = word_wrap(INSTRUCTION, 170, widths)
    cy = Y_START
    for line in lines:
        if cy + 16 > 475: break
        render_text_at(our, line, X_START, cy, widths)
        cy += 16
    render_text_at(our, "freeware", 0, BOTTOM_Y, widths)
    render_text_at(our, "silverspaceship.com", 470, BOTTOM_Y, widths)

    instr_f1 = score_region(our, ref_mask, 120, 300, 446, 624)[0]
    bottom_f1 = score_region(our, ref_mask, 446, 475, 0, 640)[0]
    overall_agree = np.sum(our == ref_mask) / our.size
    return instr_f1, bottom_f1, overall_agree, our, lines

# Score the v3 widths at optimal position
instr_f1, bottom_f1, overall, our, lines = render_and_score(v3_widths)
print(f"\n=== v3 widths at optimal position ===")
print(f"Instruction F1: {instr_f1:.4f}")
print(f"Bottom F1: {bottom_f1:.4f}")
print(f"Overall agree: {overall:.6f}")
print(f"Lines: {len(lines)}")
for i, line in enumerate(lines):
    match = "✓" if i < len(EXPECTED_LINES) and line == EXPECTED_LINES[i] else "✗"
    w = measure_text(line, v3_widths)
    print(f"  {i+1}. {match} [{w:3d}px] '{line}'")

# ---- Step 3: Per-line score diagnostics ----
print(f"\n=== Per-line F1 scores ===")
cy = Y_START
for i, line in enumerate(EXPECTED_LINES):
    our_line = np.zeros((480, 640), dtype=bool)
    render_text_at(our_line, line, X_START, cy, v3_widths)
    f1, prec, recall, agree = score_region(our_line, ref_mask, cy, cy + 16, X_START - 2, X_START + 175)
    print(f"  Line {i+1} (y={cy}): F1={f1:.4f} P={prec:.4f} R={recall:.4f} '{line}'")
    cy += 16

# ---- Step 4: Greedy per-character optimization at optimal position ----
print(f"\n=== Step 4: Per-character greedy optimization ===\n")

all_text = INSTRUCTION + "freewaresilverspaceship.com"
chars_by_freq = [ch for ch, _ in Counter(all_text).most_common() if ch in fon_widths]

best_widths = dict(v3_widths)
best_score = instr_f1 + bottom_f1 * 0.3

print(f"Starting score: {best_score:.4f} (instr={instr_f1:.4f} bottom={bottom_f1:.4f})")

iteration = 0
improved = True
while improved and iteration < 100:
    improved = False
    iteration += 1
    for ch in chars_by_freq:
        current_w = best_widths[ch]
        for delta in [-1, +1, -2, +2]:
            test_w = current_w + delta
            if test_w < 1 or test_w > 20:
                continue
            test_widths = dict(best_widths)
            test_widths[ch] = test_w
            if word_wrap(INSTRUCTION, 170, test_widths) != EXPECTED_LINES:
                continue
            instr_f1, bottom_f1, _, _, _ = render_and_score(test_widths)
            score = instr_f1 + bottom_f1 * 0.3
            if score > best_score + 0.0001:
                old_w = best_widths[ch]
                best_widths[ch] = test_w
                best_score = score
                improved = True
                print(f"  iter {iteration}: '{ch}' {old_w}->{test_w} score={score:.4f} (instr={instr_f1:.4f} bottom={bottom_f1:.4f})")

print(f"\nAfter optimization: score={best_score:.4f}")

# ---- Step 5: Try pairs of changes ----
print(f"\n=== Step 5: Pairwise optimization ===\n")
# Try changing pairs of high-frequency characters
top_chars = chars_by_freq[:15]
pair_improved = True
pair_iter = 0
while pair_improved and pair_iter < 10:
    pair_improved = False
    pair_iter += 1
    for i in range(len(top_chars)):
        for j in range(i+1, len(top_chars)):
            ch1, ch2 = top_chars[i], top_chars[j]
            for d1 in [-1, +1]:
                for d2 in [-1, +1]:
                    w1 = best_widths[ch1] + d1
                    w2 = best_widths[ch2] + d2
                    if w1 < 1 or w1 > 20 or w2 < 1 or w2 > 20:
                        continue
                    test_widths = dict(best_widths)
                    test_widths[ch1] = w1
                    test_widths[ch2] = w2
                    if word_wrap(INSTRUCTION, 170, test_widths) != EXPECTED_LINES:
                        continue
                    instr_f1, bottom_f1, _, _, _ = render_and_score(test_widths)
                    score = instr_f1 + bottom_f1 * 0.3
                    if score > best_score + 0.0001:
                        best_widths[ch1] = w1
                        best_widths[ch2] = w2
                        best_score = score
                        pair_improved = True
                        print(f"  pair iter {pair_iter}: '{ch1}'{best_widths[ch1]-d1}->{w1} '{ch2}'{best_widths[ch2]-d2}->{w2} score={score:.4f}")

print(f"\nAfter pair optimization: score={best_score:.4f}")

# ---- Final results ----
instr_f1, bottom_f1, overall, our, lines = render_and_score(best_widths)
print(f"\n=== FINAL RESULTS ===")
print(f"Instruction F1: {instr_f1:.4f}")
print(f"Bottom F1: {bottom_f1:.4f}")
print(f"Overall agreement: {overall:.6f}")
print(f"Text origin: ({X_START}, {Y_START}), bottom: {BOTTOM_Y}")

print(f"\nLine breaks:")
for i, line in enumerate(lines):
    match = "✓" if i < len(EXPECTED_LINES) and line == EXPECTED_LINES[i] else "✗"
    w = measure_text(line, best_widths)
    print(f"  {i+1}. {match} [{w:3d}px] '{line}'")

print(f"\nAdvance widths (changes from fon):")
for code in range(32, 127):
    ch = chr(code)
    fon = fon_widths[ch]
    new = best_widths.get(ch, fon)
    if new != fon:
        print(f"  {repr(ch):>5}: {fon} -> {new} (+{new-fon})")

print(f"\nKey metrics:")
print(f"  'freeware' width: {measure_text('freeware', best_widths)}px")
print(f"  'silverspaceship.com' width: {measure_text('silverspaceship.com', best_widths)}px")

# Per-line F1 at final widths
print(f"\nPer-line F1 scores:")
cy = Y_START
for i, line in enumerate(EXPECTED_LINES):
    our_line = np.zeros((480, 640), dtype=bool)
    render_text_at(our_line, line, X_START, cy, best_widths)
    f1, prec, recall, agree = score_region(our_line, ref_mask, cy, cy + 16, X_START - 2, X_START + 175)
    print(f"  Line {i+1} (y={cy}): F1={f1:.4f} P={prec:.4f} R={recall:.4f}")
    cy += 16

# Save
output = {chr(c): best_widths.get(chr(c), fon_widths[chr(c)]) for c in range(32, 127)}
with open("scripts/best_widths_v4.json", "w") as f:
    json.dump(output, f, indent=2)
print("\nSaved: scripts/best_widths_v4.json")

# ---- Comparison image ----
comp = np.full((480, 640 * 2, 3), 164, dtype=np.uint8)
for y in range(480):
    for x in range(640):
        if ref_mask[y, x]:
            comp[y, x] = [0, 0, 0]
        rx = x + 640
        if our[y, x] and ref_mask[y, x]:
            comp[y, rx] = [0, 0, 0]  # correct (black)
        elif our[y, x]:
            comp[y, rx] = [0, 0, 255]  # extra (blue)
        elif ref_mask[y, x]:
            comp[y, rx] = [255, 0, 255]  # missing (magenta)

Image.fromarray(comp).save("screenshots/width_v4_comparison.png")
print("Saved: screenshots/width_v4_comparison.png")
