# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""
Extract per-character advance widths from reference screenshot v2.
Fixed: no multi-island merging (bitmap font glyphs are single islands).
Each island = one character. Map sequentially.
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

# ---- Load sserife.fon for reference ----
face = freetype.Face("assets/fonts/sserife.fon", 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])

fon_info = {}
for code in range(32, 127):
    ch = chr(code)
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    fon_info[ch] = {
        'bearing_x': face.glyph.bitmap_left,
        'bitmap_width': face.glyph.bitmap.width,
        'advance': face.glyph.advance.x >> 6,
    }

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

def get_islands(y_start, x_left, x_right, height=13):
    """Find contiguous columns with black pixels."""
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

# ---- Map islands to characters: 1 island per non-space char ----
print("=== Island-to-character mapping ===\n")

all_char_data = []  # (char, first_px, last_px, line_idx, char_idx_in_text)

for line_idx, (y, text) in enumerate(LINES):
    islands = get_islands(y, 445, 625)
    non_space_chars = [c for c in text if c != ' ']

    print(f"Line {line_idx+1} (y={y}): '{text}'")
    print(f"  Islands: {len(islands)}, non-space chars: {len(non_space_chars)}")

    if len(islands) != len(non_space_chars):
        print(f"  MISMATCH! islands={len(islands)} vs chars={len(non_space_chars)}")
        # Try to diagnose: print islands
        for j, (s, e) in enumerate(islands):
            print(f"    island {j}: [{s}, {e}] width={e-s+1}")
        print()
        continue

    # Map sequentially: skip spaces, consume islands for non-space chars
    island_idx = 0
    char_idx_in_text = 0
    for ch in text:
        if ch == ' ':
            all_char_data.append((ch, None, None, line_idx, char_idx_in_text))
        else:
            s, e = islands[island_idx]
            all_char_data.append((ch, s, e, line_idx, char_idx_in_text))
            print(f"    '{ch}' [{s}, {e}] width={e-s+1}")
            island_idx += 1
        char_idx_in_text += 1
    print()

# ---- Also process bottom text ----
# Find exact y for bottom text
print("=== Bottom text ===\n")
for test_y in range(448, 458):
    fw_islands = get_islands(test_y, 0, 80)
    ss_islands = get_islands(test_y, 465, 640)
    fw_non_space = 8  # "freeware"
    ss_non_space = 19  # "silverspaceship.com" has '.' which is 1 island
    if len(fw_islands) == fw_non_space:
        print(f"'freeware' at y={test_y}: {len(fw_islands)} islands ✓")
        for j, (s, e) in enumerate(fw_islands):
            ch = "freeware"[j]
            print(f"    '{ch}' [{s}, {e}] width={e-s+1}")
            all_char_data.append((ch, s, e, -1, j))
        break

for test_y in range(448, 458):
    ss_islands = get_islands(test_y, 465, 640)
    text = "silverspaceship.com"
    non_space = len(text)  # no spaces
    if len(ss_islands) == non_space:
        print(f"'silverspaceship.com' at y={test_y}: {len(ss_islands)} islands ✓")
        for j, (s, e) in enumerate(ss_islands):
            ch = text[j]
            print(f"    '{ch}' [{s}, {e}] width={e-s+1}")
            all_char_data.append((ch, s, e, -2, j))
        break
    elif abs(len(ss_islands) - non_space) <= 2:
        print(f"'silverspaceship.com' at y={test_y}: {len(ss_islands)} islands (need {non_space})")
        for j, (s, e) in enumerate(ss_islands):
            print(f"    island {j}: [{s}, {e}] width={e-s+1}")

print()

# ---- Compute advance widths ----
print("=== Computing advance widths from first_pixel distances ===\n")

# Group char_data by line
from itertools import groupby
line_groups = defaultdict(list)
for ch, fp, lp, li, ci in all_char_data:
    line_groups[li].append((ch, fp, lp, ci))

char_advances = defaultdict(list)  # ch -> [advance_values]
space_observations = []  # (total_advance_across_space, last_char, next_char)

for li in sorted(line_groups.keys()):
    chars = line_groups[li]

    for i in range(len(chars) - 1):
        ch_i, fp_i, lp_i, ci_i = chars[i]
        ch_j, fp_j, lp_j, ci_j = chars[i + 1]

        if ch_i == ' ' or fp_i is None:
            continue
        if ch_j == ' ':
            # Need to find the next non-space char after this space
            for k in range(i + 2, len(chars)):
                ch_k, fp_k, lp_k, ci_k = chars[k]
                if ch_k != ' ' and fp_k is not None:
                    # ch_i + space(s) + ch_k
                    n_spaces = ci_k - ci_i - 1  # count spaces between
                    # In our case it's always 1 space
                    total = fp_k - fp_i
                    space_observations.append((total, ch_i, ch_k, n_spaces, li))
                    break
            continue

        if fp_j is None:
            continue

        advance = fp_j - fp_i
        if 1 <= advance <= 20:
            char_advances[ch_i].append(advance)

# Print observations
print("Direct char-to-char advances (first_pixel difference):\n")
for ch in sorted(char_advances.keys()):
    vals = char_advances[ch]
    counts = Counter(vals)
    most_common_val, most_common_count = counts.most_common(1)[0]
    fon = fon_info.get(ch, {}).get('advance', '?')
    print(f"  '{ch}': fon={fon}, observed={sorted(vals)}, "
          f"best={most_common_val} (×{most_common_count})")

# ---- Determine space width ----
print("\n\nSpace width determination:\n")

# For each "char + space + char" observation:
# total = advance(ch_i) + advance(space)
# If we know advance(ch_i), we can derive advance(space)

# First, determine char advances (use most common value)
derived = {}
for ch in char_advances:
    vals = char_advances[ch]
    counts = Counter(vals)
    derived[ch] = counts.most_common(1)[0][0]

# Now derive space width from observations
space_widths = []
for total, ch_i, ch_k, n_spaces, li in space_observations:
    if ch_i in derived and n_spaces == 1:
        space_w = total - derived[ch_i]
        if 1 <= space_w <= 10:
            space_widths.append(space_w)
            if space_w not in (3, 4, 5):
                print(f"  Unusual space: '{ch_i}'+sp+'{ch_k}' total={total} adv({ch_i})={derived[ch_i]} → space={space_w} (line {li+1})")

if space_widths:
    sp_counts = Counter(space_widths)
    print(f"\nSpace width observations: {sp_counts}")
    derived[' '] = sp_counts.most_common(1)[0][0]
    print(f"Best space width: {derived[' ']}")
else:
    print("No space width observations!")
    derived[' '] = 4

# ---- Print final derived widths ----
print(f"\n\n=== Final derived advance widths ===\n")
print(f"{'Char':>6} {'FON':>4} {'Derived':>8} {'Delta':>6}")
for code in range(32, 127):
    ch = chr(code)
    fon = fon_info[ch]['advance']
    der = derived.get(ch, None)
    if der is not None:
        delta = der - fon
        ch_display = repr(ch) if ch != ' ' else "'SP'"
        print(f"  {ch_display:>5}: {fon:3d}  →  {der:3d}    {'+' if delta >= 0 else ''}{delta}")

# ---- Build full width table and verify word wrap ----
print(f"\n\n=== Word wrap verification ===\n")

# For characters not in our text, estimate delta
# Most characters have delta = +2
for code in range(32, 127):
    ch = chr(code)
    if ch not in derived:
        fon = fon_info[ch]['advance']
        derived[ch] = fon + 2  # default delta of +2

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

lines = word_wrap(INSTRUCTION, 170, derived)
print(f"Word wrap ({len(lines)} lines):")
all_match = True
for i, line in enumerate(lines):
    w = measure_text(line, derived)
    expected = EXPECTED_LINES[i] if i < len(EXPECTED_LINES) else "???"
    match = "✓" if line == expected else "✗"
    if line != expected: all_match = False
    print(f"  {i+1}. {match} [{w:3d}px] '{line}'")

if not all_match:
    print("\nLine breaks don't match. Trying adjustments...")

    # The key issue might be specific character widths affecting line breaks.
    # Let me check which lines overflow and which are too short.
    for i, expected in enumerate(EXPECTED_LINES):
        w = measure_text(expected, derived)
        if i + 1 < len(EXPECTED_LINES):
            next_word = EXPECTED_LINES[i + 1].split()[0]
            overflow = f"{expected} {next_word}"
            ow = measure_text(overflow, derived)
            fits = "OK" if w <= 170 and ow > 170 else "BAD"
            print(f"    Line {i+1}: '{expected}' w={w}, overflow='{overflow}' w={ow} [{fits}]")
        else:
            print(f"    Line {i+1}: '{expected}' w={w} (last)")

    # Try iterative adjustment
    # Systematically reduce widths that cause overflow issues
    adjusted = dict(derived)
    for _ in range(50):
        test_lines = word_wrap(INSTRUCTION, 170, adjusted)
        if test_lines == EXPECTED_LINES:
            print("\nFound matching widths!")
            derived = adjusted
            break
        # Find which expected lines fail
        # If a line has too many words, some char widths are too small
        # If a line has too few words, some char widths are too large
        # Focus on characters that appear in the problem lines
        for i, expected in enumerate(EXPECTED_LINES):
            w = measure_text(expected, adjusted)
            if w > 170:
                # This line is too wide. Reduce the most common char's width
                char_counts = Counter(expected)
                for ch, cnt in char_counts.most_common():
                    if ch == ' ': continue
                    if adjusted[ch] > fon_info[ch]['advance']:
                        adjusted[ch] -= 1
                        break
                break
            if i + 1 < len(EXPECTED_LINES):
                next_word = EXPECTED_LINES[i + 1].split()[0]
                overflow = f"{expected} {next_word}"
                ow = measure_text(overflow, adjusted)
                if ow <= 170:
                    # Overflow line fits, meaning we need to make something wider
                    # to push the next word to the next line
                    char_counts = Counter(overflow)
                    for ch, cnt in char_counts.most_common():
                        if ch == ' ': continue
                        test = dict(adjusted)
                        test[ch] = adjusted[ch] + 1
                        if word_wrap(INSTRUCTION, 170, test) == EXPECTED_LINES:
                            adjusted[ch] += 1
                            break
                    else:
                        # Try space
                        adjusted[' '] += 1
                    break

    lines2 = word_wrap(INSTRUCTION, 170, derived)
    if lines2 == EXPECTED_LINES:
        print("\nAfter adjustment - all lines match!")
        for i, line in enumerate(lines2):
            w = measure_text(line, derived)
            print(f"  {i+1}. ✓ [{w:3d}px] '{line}'")

# ---- Key measurements ----
print(f"\n\n=== Key measurements ===")
print(f"  'freeware' width: {measure_text('freeware', derived)}px")
print(f"  'silverspaceship.com' width: {measure_text('silverspaceship.com', derived)}px")

# Save
with open("scripts/island_widths_v2.json", "w") as f:
    json.dump({chr(c): derived.get(chr(c), fon_info[chr(c)]['advance'] + 2) for c in range(32, 127)}, f, indent=2)
print(f"\nSaved: scripts/island_widths_v2.json")
