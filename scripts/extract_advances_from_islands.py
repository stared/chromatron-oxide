# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""
Extract per-character advance widths from reference screenshot by mapping
glyph islands to known text characters.

Method:
1. For each known text line, find glyph islands (contiguous columns with black pixels)
2. Map islands to characters (handling multi-island chars like 'i', 'j', '!', etc.)
3. Compute advance = distance between consecutive pen positions
4. Cross-validate across multiple occurrences
"""
import freetype
import numpy as np
from PIL import Image
import json
from collections import defaultdict

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

# ---- Load sserife.fon for bearing_x values ----
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

# ---- Known text ----
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

# Bottom text - need to find exact y
# From row profile: y=453 is where the actual text starts (ascenders start a few rows earlier)
BOTTOM_LINES = [
    (453, 0, 80, "freeware"),
    (453, 465, 640, "silverspaceship.com"),
]

def get_islands(y_start, x_left, x_right, height=13):
    """Find contiguous columns with black pixels."""
    strip = ref_mask[y_start:y_start+height, x_left:x_right]
    col_profile = np.sum(strip, axis=0)

    islands = []
    in_island = False
    island_start = 0
    for i in range(len(col_profile)):
        if col_profile[i] > 0:
            if not in_island:
                island_start = i
                in_island = True
        else:
            if in_island:
                islands.append((x_left + island_start, x_left + i - 1))
                in_island = False
    if in_island:
        islands.append((x_left + island_start, x_left + len(col_profile) - 1))
    return islands

def map_islands_to_chars(text, islands, x_start_approx):
    """
    Map glyph islands to characters in text.

    Key challenge: some characters have detached parts (dots on i, j, colon, etc.)
    that create separate islands. We need to merge these.

    Strategy:
    - Walk through text character by character
    - For each non-space character, consume one or more islands
    - Characters with dots above (i, j, !, ?, ;, :) may have 2 islands
    - Space characters consume the gap between islands
    """
    # Multi-island characters (have detached dots or parts)
    MULTI_ISLAND = set('ij!?;:')

    char_positions = []  # (char, first_pixel_x, last_pixel_x)
    island_idx = 0

    for ch in text:
        if ch == ' ':
            # Space: no island consumed, just record gap
            char_positions.append((ch, None, None))
            continue

        if island_idx >= len(islands):
            print(f"  WARNING: ran out of islands at char '{ch}'")
            char_positions.append((ch, None, None))
            continue

        first_x = islands[island_idx][0]
        last_x = islands[island_idx][1]
        island_idx += 1

        # Check if this character has a second island (detached dot)
        if ch in MULTI_ISLAND and island_idx < len(islands):
            next_island = islands[island_idx]
            gap = next_island[0] - last_x - 1
            # If the next island is close (within the character cell), merge it
            if gap <= 3:  # dot is typically 1-2 pixels away
                last_x = max(last_x, next_island[1])
                first_x = min(first_x, next_island[0])
                island_idx += 1

        char_positions.append((ch, first_x, last_x))

    if island_idx < len(islands):
        print(f"  WARNING: {len(islands) - island_idx} unused islands")

    return char_positions

# ---- Process all lines ----
print("=== Mapping islands to characters ===\n")

all_char_positions = []  # (char, first_pixel_x, last_pixel_x, line_idx)

for line_idx, (y, text) in enumerate(LINES):
    islands = get_islands(y, 445, 625)
    mapping = map_islands_to_chars(text, islands, 450)

    print(f"Line {line_idx+1} (y={y}): '{text}'")
    print(f"  Islands: {len(islands)}, non-space chars: {len([c for c in text if c != ' '])}")

    for ch, first_x, last_x in mapping:
        if first_x is not None:
            width = last_x - first_x + 1
            print(f"    '{ch}' pixels [{first_x}, {last_x}] width={width}")
            all_char_positions.append((ch, first_x, last_x, line_idx))
        else:
            if ch != ' ':
                print(f"    '{ch}' -- NOT FOUND")
    print()

# ---- Process bottom text ----
for y, x_left, x_right, text in BOTTOM_LINES:
    # Check multiple y values for bottom text
    for test_y in range(450, 458):
        islands = get_islands(test_y, x_left, x_right)
        if len(islands) > 0:
            # Check if we have enough islands
            non_space = len([c for c in text if c != ' '])
            if len(islands) >= non_space * 0.5:  # rough check
                print(f"Bottom '{text}' at y={test_y}: {len(islands)} islands (need ~{non_space})")
                mapping = map_islands_to_chars(text, islands, x_left)
                for ch, first_x, last_x in mapping:
                    if first_x is not None:
                        width = last_x - first_x + 1
                        print(f"    '{ch}' pixels [{first_x}, {last_x}] width={width}")
                        all_char_positions.append((ch, first_x, last_x, -1))
                print()
                break

# ---- Compute advance widths from character positions ----
print("\n=== Computing advance widths ===\n")

# For each line, compute advance = first_pixel(char_i+1) - first_pixel(char_i)
# adjusted for bearing_x difference
#
# Actually, simpler: advance = first_pixel(next_char) - first_pixel(this_char)
# This is approximately correct if all characters have similar bearing_x.
# We'll cross-validate by comparing across lines.

char_advance_observations = defaultdict(list)  # char -> [(advance, line_idx, context)]

for line_idx, (y, text) in enumerate(LINES):
    islands = get_islands(y, 445, 625)
    mapping = map_islands_to_chars(text, islands, 450)

    # Get the first_pixel_x for each character (including spaces)
    # For spaces, interpolate between neighboring characters
    first_pixels = []
    for ch, first_x, last_x in mapping:
        first_pixels.append((ch, first_x, last_x))

    # Compute advances between consecutive non-None positions
    for i in range(len(first_pixels) - 1):
        ch_i, fp_i, lp_i = first_pixels[i]
        ch_j, fp_j, lp_j = first_pixels[i + 1]

        if fp_i is None or fp_j is None:
            # One is a space. Find the next/prev non-space
            continue

        if ch_i == ' ':
            continue

        # Direct advance (may include spaces between them)
        gap_text = text[i:i+2]  # the two chars

        # Check if there are any spaces between them
        spaces_between = 0
        for k in range(i+1, len(text)):
            if k >= len(first_pixels):
                break
            if first_pixels[k][1] is not None:
                break
            if first_pixels[k][0] == ' ':
                spaces_between += 1

        # If no spaces between, it's a direct character-to-character advance
        if spaces_between == 0:
            advance = fp_j - fp_i
            if 1 <= advance <= 20:
                char_advance_observations[ch_i].append((advance, line_idx, f"→{ch_j}"))

# Also compute word-level advances for space width
# For each occurrence of "word1 word2", advance from last char of word1 to first char of word2
# = advance(last_char) + advance(space)
for line_idx, (y, text) in enumerate(LINES):
    islands = get_islands(y, 445, 625)
    mapping = map_islands_to_chars(text, islands, 450)

    words = text.split()
    word_start_idx = 0
    for w_idx, word in enumerate(words):
        word_end_idx = word_start_idx + len(word) - 1

        if w_idx + 1 < len(words):
            # Space after this word, then next word
            space_idx = word_end_idx + 1  # index of space in text
            next_word_start_idx = space_idx + 1

            if (word_end_idx < len(mapping) and
                next_word_start_idx < len(mapping) and
                mapping[word_end_idx][1] is not None and
                mapping[next_word_start_idx][1] is not None):

                last_char = mapping[word_end_idx]
                next_first = mapping[next_word_start_idx]

                # advance from last char of word through space to first char of next word
                total_advance = next_first[1] - last_char[1]
                # This = advance(last_char) + advance(space)
                # We'll store as "X+space" observation
                char_advance_observations[f"{last_char[0]}+sp"].append(
                    (total_advance, line_idx, f"→{next_first[0]}"))

        word_start_idx = word_end_idx + 2  # +1 for space

# ---- Print collected advance observations ----
print("Character advance observations (first_pixel to first_pixel of next char):\n")

# Sort by character
for ch in sorted(char_advance_observations.keys()):
    observations = char_advance_observations[ch]
    values = [v for v, _, _ in observations]
    if not values:
        continue

    median = sorted(values)[len(values) // 2]
    mean = sum(values) / len(values)

    # Determine the most common value
    from collections import Counter
    counts = Counter(values)
    most_common = counts.most_common(1)[0]

    fon_adv = fon_info.get(ch, {}).get('advance', '?') if '+' not in ch else '?'

    print(f"  '{ch:>3}': fon={fon_adv}, observed={sorted(values)}, "
          f"most_common={most_common[0]} (×{most_common[1]}), median={median}")

# ---- Derive best advance width per character ----
print("\n\n=== Derived advance widths ===\n")

derived = {}
for ch in sorted(char_advance_observations.keys()):
    if '+' in ch:
        continue
    observations = char_advance_observations[ch]
    values = [v for v, _, _ in observations]
    if not values:
        continue
    counts = Counter(values)
    best = counts.most_common(1)[0][0]
    derived[ch] = best

# Derive space width from "X+sp" observations
space_widths = []
for ch_sp in char_advance_observations:
    if '+sp' in ch_sp:
        base_ch = ch_sp.replace('+sp', '')
        if base_ch in derived:
            for total, _, _ in char_advance_observations[ch_sp]:
                space_w = total - derived[base_ch]
                if 1 <= space_w <= 10:
                    space_widths.append(space_w)

if space_widths:
    space_counts = Counter(space_widths)
    space_advance = space_counts.most_common(1)[0][0]
    print(f"Space advance: {space_advance} (from {len(space_widths)} observations: {space_counts})")
    derived[' '] = space_advance
else:
    print("Could not determine space advance!")
    derived[' '] = 5

# Print derived widths table
print(f"\n{'Char':>6} {'FON':>4} {'Derived':>8} {'Delta':>6}")
for code in range(32, 127):
    ch = chr(code)
    fon = fon_info[ch]['advance']
    der = derived.get(ch, None)
    if der is not None:
        delta = der - fon
        ch_display = repr(ch) if ch != ' ' else "'SP'"
        print(f"  {ch_display:>5}: {fon:3d}  →  {der:3d}    {'+' if delta > 0 else ''}{delta}")

# ---- Verify with word wrapping ----
print("\n\n=== Word wrap verification ===\n")

# Build a full width table: use derived where available, fallback to fon + estimated delta
# Average delta for lowercase:
lower_deltas = [derived[ch] - fon_info[ch]['advance'] for ch in derived
                if ch.islower() and ch in fon_info]
upper_deltas = [derived[ch] - fon_info[ch]['advance'] for ch in derived
                if ch.isupper() and ch in fon_info]

avg_lower = sum(lower_deltas) / len(lower_deltas) if lower_deltas else 2
avg_upper = sum(upper_deltas) / len(upper_deltas) if upper_deltas else 2

print(f"Average delta: lowercase={avg_lower:.1f}, uppercase={avg_upper:.1f}")

full_widths = {}
for code in range(32, 127):
    ch = chr(code)
    if ch in derived:
        full_widths[ch] = derived[ch]
    elif ch.islower():
        full_widths[ch] = fon_info[ch]['advance'] + round(avg_lower)
    elif ch.isupper():
        full_widths[ch] = fon_info[ch]['advance'] + round(avg_upper)
    else:
        full_widths[ch] = fon_info[ch]['advance'] + 1  # conservative default

INSTRUCTION = "Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel."

def word_wrap(text, rect_width, widths):
    words = text.split()
    line, lines = "", []
    for word in words:
        test = f"{line} {word}" if line else word
        if line and sum(widths.get(ch, 6) for ch in test) > rect_width:
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

lines = word_wrap(INSTRUCTION, 170, full_widths)
print(f"\nWord wrap result ({len(lines)} lines):")
all_match = True
for i, line in enumerate(lines):
    w = sum(full_widths.get(ch, 6) for ch in line)
    expected = EXPECTED_LINES[i] if i < len(EXPECTED_LINES) else "???"
    match = "✓" if line == expected else "✗"
    if line != expected:
        all_match = False
    print(f"  {i+1}. {match} [{w:3d}px] '{line}' {'== EXPECTED' if line == expected else f'(expected: {expected})'}")

if all_match:
    print("\n ALL LINES MATCH! ")
else:
    print("\n Some lines don't match. Adjusting...")
    # Try small adjustments to get line breaks right
    # The space width has the most impact on line breaks
    for sp_w in range(3, 8):
        test_widths = dict(full_widths)
        test_widths[' '] = sp_w
        test_lines = word_wrap(INSTRUCTION, 170, test_widths)
        if test_lines == EXPECTED_LINES:
            print(f"  Space width {sp_w} gives correct line breaks!")
            full_widths[' '] = sp_w
            break

# Save the derived widths
with open("scripts/island_derived_widths.json", "w") as f:
    json.dump(full_widths, f, indent=2)
print(f"\nSaved: scripts/island_derived_widths.json")

# Also print total line pixel widths for verification
print("\n=== Total line pixel widths vs computed ===")
for line_idx, (y, text) in enumerate(LINES):
    computed_w = sum(full_widths.get(ch, 6) for ch in text)
    islands = get_islands(y, 445, 625)
    if islands:
        first_px = islands[0][0]
        last_px = islands[-1][1]
        ref_pixel_w = last_px - first_px + 1
        # Note: pixel width ≈ text_advance - advance(last_char) + bitmap_width(last_char)
        print(f"  Line {line_idx+1}: computed={computed_w}px, ref_pixels={ref_pixel_w}px, diff={computed_w - ref_pixel_w}")
