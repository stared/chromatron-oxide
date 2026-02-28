# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""
Derive TRUE advance widths from reference screenshot, correcting for bearing_x.

Key insight: the first_pixel_to_first_pixel distance between chars i and j is:
  fp(j) - fp(i) = advance(i) + bearing_x(j) - bearing_x(i)

So: advance(i) = fp_diff - bearing_x(j) + bearing_x(i)

We determine bearing_x from:
1. Line-start positions (pen=450, first pixel = 450+bearing_x)
2. sserife.fon bearing_x values (should match original MS Sans Serif)
"""
import freetype
import numpy as np
from PIL import Image
import json
from collections import defaultdict, Counter

# ---- Load reference ----
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

ref = normalize("screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png")
ref_mask = np.all(ref < 50, axis=2)

# ---- Load sserife.fon ----
face = freetype.Face("assets/fonts/sserife.fon", 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])

fon_bearing_x = {}
fon_advance = {}
fon_bmp_width = {}
for code in range(32, 127):
    ch = chr(code)
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    fon_bearing_x[ch] = face.glyph.bitmap_left
    fon_advance[ch] = face.glyph.advance.x >> 6
    fon_bmp_width[ch] = face.glyph.bitmap.width

print("=== sserife.fon bearing_x values ===\n")
for code in range(32, 127):
    ch = chr(code)
    bx = fon_bearing_x[ch]
    if bx != 1:
        ch_d = repr(ch) if ch != ' ' else "'SP'"
        print(f"  {ch_d}: bearing_x={bx} (advance={fon_advance[ch]}, bmp_width={fon_bmp_width[ch]})")

# ---- Configuration ----
LINES = [
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

PEN_START = 450  # text starts at x=450

def get_islands(y_start, x_left, x_right, height=13):
    strip = ref_mask[y_start:y_start+height, x_left:x_right]
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

# ---- Determine bearing_x from line starts ----
print("\n=== Determining bearing_x from line-start positions ===\n")

# Characters that start lines, and their first pixel x:
line_start_chars = {}
for y, text in LINES:
    ch = text[0]
    islands = get_islands(y, 445, 625)
    if islands:
        fp = islands[0][0]
        bx = fp - PEN_START
        line_start_chars[ch] = bx
        print(f"  Line '{text[:10]}...' starts with '{ch}': first_pixel={fp}, bearing_x={bx}")

# Known bearing_x from line starts:
# These are the REFERENCE font's bearing_x, which should match sserife.fon
known_bx = dict(fon_bearing_x)  # Start with sserife.fon values

# Override with measured values from line starts
for ch, bx in line_start_chars.items():
    if bx != known_bx.get(ch, 1):
        print(f"  NOTE: measured bearing_x('{ch}')={bx} differs from fon={known_bx.get(ch, 1)}")
    known_bx[ch] = bx

# Also determine bearing_x for uppercase chars using REFLECTOR context
# If we trace through the whole REFLECTOR word, we can determine each char's bearing_x
print("\n=== REFLECTOR bearing_x analysis ===\n")

reflector_line = LINES[0]
y_refl = reflector_line[0]
islands_refl = get_islands(y_refl, 445, 625)
text_refl = reflector_line[1]

# Map non-space chars to islands
non_space = [c for c in text_refl if c != ' ']
if len(islands_refl) == len(non_space):
    # Trace through knowing pen starts at 450 for 'D'
    pen = PEN_START
    idx = 0
    for ch in text_refl:
        if ch == ' ':
            # Space: advance the pen by space_width (we'll determine this)
            # For now, skip - we'll compute it from the gap
            continue
        fp = islands_refl[idx][0]
        measured_bx = fp - pen
        if measured_bx < 0 or measured_bx > 3:
            # Pen position must be wrong - need to figure out space advance
            pass
        else:
            if ch not in line_start_chars:  # Don't override line-start measurements
                if measured_bx != known_bx.get(ch, 1):
                    print(f"  '{ch}' at pen={pen}: fp={fp}, measured_bx={measured_bx} (fon={known_bx.get(ch, 1)})")
                known_bx[ch] = measured_bx
        idx += 1

print("\n=== Using sserife.fon bearing_x for correction ===")
print("(These should match the original MS Sans Serif)\n")
# Print non-default bearing_x
for code in range(32, 127):
    ch = chr(code)
    bx = known_bx.get(ch, 1)
    if bx != 1:
        ch_d = repr(ch) if ch != ' ' else "'SP'"
        print(f"  {ch_d}: bearing_x={bx}")

# ---- Map islands to characters and compute CORRECTED advances ----
print("\n\n=== Computing bearing_x-corrected advance widths ===\n")

advance_obs = defaultdict(list)  # ch -> [corrected_advance]
space_obs = []  # (pen_before_space, pen_after_space, line_idx)

for line_idx, (y, text) in enumerate(LINES):
    islands = get_islands(y, 445, 625)
    non_space = [c for c in text if c != ' ']

    if len(islands) != len(non_space):
        print(f"Line {line_idx+1}: SKIP (island mismatch: {len(islands)} vs {len(non_space)})")
        continue

    # Build character positions: (char, first_pixel, pen_position)
    # Start with pen = 450
    pen = PEN_START
    island_idx = 0
    char_data = []  # (char, island_first_pixel, island_last_pixel, pen, is_space)

    for ci, ch in enumerate(text):
        if ch == ' ':
            char_data.append((ch, None, None, pen, True))
            # Space advances pen but we don't know by how much yet
            # Will be computed after we know surrounding char positions
            continue

        fp = islands[island_idx][0]
        lp = islands[island_idx][1]
        bx = known_bx.get(ch, 1)

        # The pen for this char should be fp - bx
        actual_pen = fp - bx

        # If this is the first char of a word (after a space), update pen from actual_pen
        # If this is a continuation, use the expected pen
        if ci == 0 or text[ci - 1] == ' ':
            # First char of word or line
            if ci == 0:
                # First char of line: pen is exactly PEN_START
                pen = PEN_START
            else:
                # First char after space: pen = actual_pen gives us the space advance
                # Space advance = actual_pen - pen_before_space
                pass  # We'll handle this below

        char_data.append((ch, fp, lp, actual_pen, False))
        island_idx += 1

    # Now compute advances between consecutive non-space characters
    non_space_data = [(ch, fp, lp, pen, is_sp) for ch, fp, lp, pen, is_sp in char_data if not is_sp]

    for i in range(len(non_space_data) - 1):
        ch_i, fp_i, lp_i, pen_i, _ = non_space_data[i]
        ch_j, fp_j, lp_j, pen_j, _ = non_space_data[i + 1]

        bx_i = known_bx.get(ch_i, 1)
        bx_j = known_bx.get(ch_j, 1)

        # Check if there's a space between them
        # Find their positions in text
        idx_i = None
        idx_j = None
        ns_count = 0
        for ci, ch in enumerate(text):
            if ch != ' ':
                if ns_count == i:
                    idx_i = ci
                if ns_count == i + 1:
                    idx_j = ci
                ns_count += 1

        spaces_between = 0
        if idx_i is not None and idx_j is not None:
            for ci in range(idx_i + 1, idx_j):
                if text[ci] == ' ':
                    spaces_between += 1

        if spaces_between == 0:
            # Direct advance: advance(i) = fp(j) - fp(i) - bx(j) + bx(i)
            advance = fp_j - fp_i - bx_j + bx_i
            if 1 <= advance <= 20:
                advance_obs[ch_i].append(advance)

        elif spaces_between == 1:
            # advance(i) + advance(space) = fp(j) - fp(i) - bx(j) + bx(i)
            total = fp_j - fp_i - bx_j + bx_i
            space_obs.append((total, ch_i, ch_j, line_idx))

# ---- Derive advance widths ----
print("Corrected advance observations:\n")
derived = {}
for ch in sorted(advance_obs.keys()):
    vals = advance_obs[ch]
    counts = Counter(vals)
    best_val, best_count = counts.most_common(1)[0]
    derived[ch] = best_val
    fon = fon_advance.get(ch, '?')
    ch_d = repr(ch)
    print(f"  {ch_d:>5}: fon={fon}, corrected={sorted(vals)}, best={best_val} (×{best_count})")

# Derive space width
print("\n\nSpace width from word gaps:\n")
space_widths = []
for total, ch_i, ch_j, li in space_obs:
    if ch_i in derived:
        sp = total - derived[ch_i]
        if 1 <= sp <= 10:
            space_widths.append(sp)
            if sp not in (3, 4, 5):
                print(f"  Unusual: '{ch_i}'+sp+'{ch_j}' total={total}, adv('{ch_i}')={derived[ch_i]}, sp={sp} (line {li+1})")

sp_counts = Counter(space_widths)
print(f"Space observations: {sp_counts}")
sp_advance = sp_counts.most_common(1)[0][0]
derived[' '] = sp_advance
print(f"Space advance: {sp_advance}")

# ---- Print final table ----
print(f"\n\n{'='*50}")
print(f"FINAL DERIVED ADVANCE WIDTHS")
print(f"{'='*50}\n")

print(f"{'Char':>6} {'FON':>4} {'Derived':>8} {'Delta':>6} {'bx':>3}")
for code in range(32, 127):
    ch = chr(code)
    fon = fon_advance[ch]
    bx = known_bx.get(ch, 1)
    der = derived.get(ch, None)
    if der is not None:
        delta = der - fon
        ch_d = repr(ch) if ch != ' ' else "'SP'"
        print(f"  {ch_d:>5}: {fon:3d}  →  {der:3d}    {'+' if delta >= 0 else ''}{delta}   {bx}")

# ---- Build full width table ----
full = {}
for code in range(32, 127):
    ch = chr(code)
    if ch in derived:
        full[ch] = derived[ch]
    else:
        # Estimate: most chars are fon + 2
        full[ch] = fon_advance[ch] + 2

# ---- Verify word wrapping ----
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

INSTRUCTION = "Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel."
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

lines = word_wrap(INSTRUCTION, 170, full)
print(f"\n\nWord wrap ({len(lines)} lines):")
all_match = True
for i, line in enumerate(lines):
    w = measure_text(line, full)
    expected = EXPECTED_LINES[i] if i < len(EXPECTED_LINES) else "???"
    match = "✓" if line == expected else "✗"
    if line != expected: all_match = False
    print(f"  {i+1}. {match} [{w:3d}px] '{line}'")

# Detailed line-break check
if not all_match:
    print("\nLine-break analysis:")
    for i, expected in enumerate(EXPECTED_LINES):
        w = measure_text(expected, full)
        if i + 1 < len(EXPECTED_LINES):
            next_word = EXPECTED_LINES[i + 1].split()[0]
            overflow = f"{expected} {next_word}"
            ow = measure_text(overflow, full)
            status = "OK" if w <= 170 and ow > 170 else "BAD"
            if status == "BAD":
                print(f"  L{i+1}: w={w} (≤170:{w<=170}), overflow='{next_word}' ow={ow} (>170:{ow>170})")
        else:
            print(f"  L{i+1}: w={w} (last)")

# Check if 'e' adjustment is needed
if all_match:
    print("\nALL LINES MATCH PERFECTLY!")
else:
    print("\nNeed adjustment. Checking individual characters...")

    # Try fine-tuning characters that appear in problematic lines
    adjusted = dict(full)
    for attempt in range(100):
        test_lines = word_wrap(INSTRUCTION, 170, adjusted)
        if test_lines == EXPECTED_LINES:
            print(f"Fixed after {attempt+1} adjustments!")
            full = adjusted
            break

        # Find first mismatched line
        for i in range(min(len(test_lines), len(EXPECTED_LINES))):
            if test_lines[i] != EXPECTED_LINES[i]:
                actual_w = measure_text(EXPECTED_LINES[i], adjusted)
                if actual_w > 170:
                    # Line too wide, reduce a non-critical char
                    chars = Counter(EXPECTED_LINES[i])
                    for ch, cnt in chars.most_common():
                        if ch == ' ': continue
                        if adjusted[ch] > fon_advance.get(ch, 2) + 1:
                            adjusted[ch] -= 1
                            break
                elif i + 1 < len(EXPECTED_LINES):
                    # Check overflow
                    next_word = EXPECTED_LINES[i + 1].split()[0]
                    overflow = f"{EXPECTED_LINES[i]} {next_word}"
                    ow = measure_text(overflow, adjusted)
                    if ow <= 170:
                        # Need to make overflow wider
                        overflow_chars = Counter(overflow)
                        for ch, cnt in overflow_chars.most_common():
                            if ch == ' ': continue
                            test = dict(adjusted)
                            test[ch] = adjusted[ch] + 1
                            if word_wrap(INSTRUCTION, 170, test) == EXPECTED_LINES:
                                adjusted[ch] += 1
                                break
                break

    lines2 = word_wrap(INSTRUCTION, 170, full)
    print(f"\nFinal wrap ({len(lines2)} lines):")
    for i, line in enumerate(lines2):
        w = measure_text(line, full)
        expected = EXPECTED_LINES[i] if i < len(EXPECTED_LINES) else "???"
        match = "✓" if line == expected else "✗"
        print(f"  {i+1}. {match} [{w:3d}px] '{line}'")

# ---- Key metrics ----
print(f"\n\nKey metrics:")
print(f"  'freeware' width: {measure_text('freeware', full)}px (ref ~55px)")
print(f"  'silverspaceship.com' width: {measure_text('silverspaceship.com', full)}px (ref ~133px)")

# ---- Save ----
output = {chr(c): full.get(chr(c), fon_advance[chr(c)] + 2) for c in range(32, 127)}
with open("scripts/true_advances.json", "w") as f:
    json.dump(output, f, indent=2)
print(f"\nSaved: scripts/true_advances.json")
