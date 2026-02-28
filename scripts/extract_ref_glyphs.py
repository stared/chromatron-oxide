# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""
Extract actual glyph bitmaps from the reference screenshot.

The reference has purely binary pixels (only black and gray-164).
We know the exact text on each line. By analyzing the column-by-column
black pixel profile, we can find character boundaries and extract
the actual glyph bitmaps used by the original Windows game.

Strategy:
1. Extract each known text line's pixel strip from the reference
2. Use column profile analysis to find character boundaries
3. Align with known text to map each segment to a character
4. Average across multiple occurrences to get clean glyph bitmaps
5. Output the extracted glyph set with measured advance widths
"""
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
ref_mask = np.all(ref < 50, axis=2)  # True where pixel is black

# ---- First: find the exact y positions of text lines ----
# Look at columns of black pixels in the instruction area
print("=== Finding text line y-positions ===\n")

# Horizontal profile: count black pixels per row in instruction area (x: 448-622)
row_profile = np.sum(ref_mask[:, 448:622], axis=1)
print("Row profile (y: black_pixel_count) for instruction area:")
for y in range(115, 275):
    if row_profile[y] > 0:
        print(f"  y={y}: {'#' * min(row_profile[y], 60)} ({row_profile[y]})")

# Find text line starts: rows where black pixels appear after a gap
line_starts = []
in_text = False
for y in range(115, 275):
    if row_profile[y] > 0 and not in_text:
        line_starts.append(y)
        in_text = True
    elif row_profile[y] == 0 and in_text:
        in_text = False

print(f"\nText line y-starts: {line_starts}")
print(f"Line spacing: {[line_starts[i+1] - line_starts[i] for i in range(len(line_starts)-1)]}")

# ---- Find bottom text y-positions ----
print("\n=== Finding bottom text y-positions ===\n")
row_profile_bottom = np.sum(ref_mask[440:475, :], axis=1)
for y in range(35):
    if row_profile_bottom[y] > 0:
        print(f"  y={440+y}: {'#' * min(row_profile_bottom[y], 60)} ({row_profile_bottom[y]})")

bottom_starts = []
in_text = False
for y in range(35):
    if row_profile_bottom[y] > 0 and not in_text:
        bottom_starts.append(440 + y)
        in_text = True
    elif row_profile_bottom[y] == 0 and in_text:
        in_text = False
print(f"Bottom text y-starts: {bottom_starts}")

# ---- For each text line, analyze column profile ----
LINES = [
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

# Use discovered y-starts
if len(line_starts) >= 9:
    LINE_YS = line_starts[:9]
else:
    # Fallback: use spacing from first found start
    y0 = line_starts[0] if line_starts else 127
    LINE_YS = [y0 + 16 * i for i in range(9)]

X_START = 450  # Will refine

print("\n=== Column profile analysis per line ===\n")

def analyze_line(text, y_start, x_left, x_right, label=""):
    """Analyze a text line's column profile to find character boundaries."""
    # Extract the line strip (13 pixels tall for the font + some padding)
    height = 13
    y1 = y_start
    y2 = min(y_start + height, ref_mask.shape[0])

    strip = ref_mask[y1:y2, x_left:x_right]

    # Column profile: count of black pixels per column
    col_profile = np.sum(strip, axis=0)

    # Find the first and last column with black pixels
    has_pixel = col_profile > 0
    if not np.any(has_pixel):
        print(f"  No black pixels found for '{text}' at y={y_start}")
        return None

    first_col = int(np.argmax(has_pixel))
    last_col = int(len(has_pixel) - 1 - np.argmax(has_pixel[::-1]))

    actual_x_start = x_left + first_col
    actual_x_end = x_left + last_col

    print(f"  {label}'{text}'")
    print(f"    y={y_start}, x_range=[{actual_x_start}, {actual_x_end}], width={actual_x_end - actual_x_start + 1}px")

    # Try to find character boundaries using gaps (columns with 0 black pixels)
    # within the text range
    text_strip = strip[:, first_col:last_col + 1]
    text_cols = col_profile[first_col:last_col + 1]

    # Find gaps (runs of zero-columns)
    gaps = []
    in_gap = False
    gap_start = 0
    for i in range(len(text_cols)):
        if text_cols[i] == 0:
            if not in_gap:
                gap_start = i
                in_gap = True
        else:
            if in_gap:
                gaps.append((gap_start, i - 1))
                in_gap = False
    if in_gap:
        gaps.append((gap_start, len(text_cols) - 1))

    # The number of gaps should relate to the number of spaces and inter-character gaps
    # Count spaces in text
    space_count = text.count(' ')
    print(f"    Gaps found: {len(gaps)}, spaces in text: {space_count}")

    # Print gaps
    for g_start, g_end in gaps:
        g_width = g_end - g_start + 1
        if g_width >= 2:  # Only show significant gaps
            print(f"      gap at col {g_start + first_col + x_left}-{g_end + first_col + x_left} (width={g_width})")

    return actual_x_start, actual_x_end, text_strip, gaps, first_col + x_left

# Instruction lines
line_data = []
for i, (text, y) in enumerate(zip(LINES, LINE_YS)):
    data = analyze_line(text, y, 445, 625, f"Line {i+1}: ")
    line_data.append((text, y, data))

# Bottom text: "freeware" and "silverspaceship.com"
print()
if bottom_starts:
    by = bottom_starts[0]
    fw_data = analyze_line("freeware", by, 0, 80, "Bottom: ")
    ss_data = analyze_line("silverspaceship.com", by, 465, 640, "Bottom: ")
else:
    fw_data = analyze_line("freeware", 451, 0, 80, "Bottom: ")
    ss_data = analyze_line("silverspaceship.com", 451, 465, 640, "Bottom: ")

# ---- Character-level extraction using template sliding ----
# We know the text content. We can use a sliding window approach:
# Starting from x_start, for each character in the text, determine
# the advance width by finding where the NEXT character's pixels begin.
#
# Method: for each character transition, scan forward to find where
# the current character's pixels end and the next character's begin.

print("\n\n=== Character position extraction ===\n")

# For better extraction, let's look at the pixel columns more carefully.
# Use the fact that between most characters there's at least 1 blank column.

def extract_char_positions(text, y_start, x_start_actual, height=13):
    """
    Extract per-character positions by analyzing the black pixel patterns.
    Returns list of (char, x_start, x_end, width) tuples.
    """
    y1, y2 = y_start, min(y_start + height, ref_mask.shape[0])
    positions = []

    # Get the full strip
    strip = ref_mask[y1:y2, x_start_actual:min(x_start_actual + 250, ref_mask.shape[1])]
    col_profile = np.sum(strip, axis=0)

    # For each character, find its extent
    # Strategy: walk through the text character by character.
    # For non-space characters, find runs of columns with black pixels.
    # For spaces, find gaps.

    col_idx = 0  # Current column position (relative to x_start_actual)
    char_positions = []

    # First pass: identify all "islands" of black columns
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
                islands.append((island_start, i - 1))
                in_island = False
    if in_island:
        islands.append((island_start, len(col_profile) - 1))

    return islands, col_profile

for i, (text, y, data) in enumerate(line_data):
    if data is None:
        continue
    x_start_actual = data[0]
    islands, col_profile = extract_char_positions(text, y, x_start_actual - 1)

    print(f"Line {i+1} (y={y}): '{text}'")
    print(f"  x_start={x_start_actual}, {len(islands)} glyph islands")

    # Count expected glyph islands
    # Each non-space character contributes to an island, but adjacent characters
    # may merge into one island if there's no gap between them.
    # Spaces should create gaps.
    words = text.split()
    expected_word_islands = len(words)  # minimum islands = word count

    # Print island extents
    for j, (start, end) in enumerate(islands):
        width = end - start + 1
        abs_start = x_start_actual - 1 + start
        print(f"    island {j}: col {abs_start}-{abs_start + width - 1} (width={width}px)")

    # Check if number of islands == number of words (clean segmentation)
    # If so, we can compute per-word widths
    if len(islands) == len(words):
        print(f"  >> Clean word segmentation!")
        for j, word in enumerate(words):
            island_start, island_end = islands[j]
            word_pixel_width = island_end - island_start + 1
            abs_start = x_start_actual - 1 + island_start
            print(f"    '{word}' at x={abs_start}, pixel_width={word_pixel_width}")
    elif len(islands) > len(words):
        # Some characters have gaps within them (like 'i' dot separate from body)
        print(f"  >> More islands ({len(islands)}) than words ({len(words)}) - multi-island chars")
    print()

# ---- Direct advance width measurement from word pixel widths ----
print("\n=== Direct word-width measurements ===\n")

# For each word in each line, measure the total pixel width from the reference
# Then: total_advance_of_word = word_pixel_width + rightmost_bearing_adjustment
# Approximately: advance(word) ≈ pixel_width_of_word + (advance_last_char - bitmap_width_last_char)

word_measurements = defaultdict(list)

for i, (text, y, data) in enumerate(line_data):
    if data is None:
        continue
    x_start_actual = data[0]
    y1, y2 = y, min(y + 13, ref_mask.shape[0])

    # For each line, find precise word boundaries
    # Words are separated by spaces, which create blank columns
    strip = ref_mask[y1:y2, x_start_actual - 2:x_start_actual + 200]
    col_profile = np.sum(strip, axis=0)

    words = text.split()

    # Find all gaps of >= 2 blank columns (these are likely word separators)
    gaps = []
    in_gap = False
    gap_start = 0
    for c in range(len(col_profile)):
        if col_profile[c] == 0:
            if not in_gap:
                gap_start = c
                in_gap = True
        else:
            if in_gap:
                gap_width = c - gap_start
                if gap_width >= 2:
                    gaps.append((gap_start, c - 1, gap_width))
                in_gap = False

    # If we have exactly (word_count - 1) gaps, we can segment words perfectly
    if len(gaps) == len(words) - 1:
        # Compute word pixel boundaries
        # First word: from first black pixel to first gap start
        first_col = int(np.argmax(col_profile > 0))
        word_bounds = []

        prev_end = first_col
        for j in range(len(words)):
            word_start = prev_end
            if j < len(gaps):
                word_end = gaps[j][0]  # gap start = end of word's pixels + blank space
                word_pixel_w = word_end - word_start
                # Find the actual last black column in this word
                last_black = word_start
                for c in range(word_start, word_end):
                    if col_profile[c] > 0:
                        last_black = c
                actual_pixel_w = last_black - word_start + 1
                word_bounds.append((words[j], word_start, last_black, actual_pixel_w))
                # Next word starts after gap
                gap_end = gaps[j][1]
                # Find first black pixel after gap
                next_start = gap_end + 1
                while next_start < len(col_profile) and col_profile[next_start] == 0:
                    next_start += 1
                prev_end = next_start
            else:
                # Last word: from prev_end to last black pixel
                last_black = word_start
                for c in range(word_start, len(col_profile)):
                    if col_profile[c] > 0:
                        last_black = c
                actual_pixel_w = last_black - word_start + 1
                word_bounds.append((words[j], word_start, last_black, actual_pixel_w))

        # Now compute advance widths between word starts
        # advance of word + space = next_word_start - this_word_start
        print(f"Line {i+1}: '{text}'")
        for j, (word, ws, we, pw) in enumerate(word_bounds):
            if j + 1 < len(word_bounds):
                advance_to_next = word_bounds[j+1][1] - ws
                word_advance = advance_to_next  # this includes the space after the word
                space_advance = advance_to_next - pw  # rough: gap = space width
                # But actually: total advance = sum of char advances in word
                print(f"    '{word}' start={ws + x_start_actual - 2} pixel_w={pw} advance_to_next={advance_to_next}")
            else:
                print(f"    '{word}' start={ws + x_start_actual - 2} pixel_w={pw} (last)")
        print()
    else:
        print(f"Line {i+1}: '{text}' - {len(gaps)} gaps (need {len(words)-1}) - cannot cleanly segment")
        print()

# ---- Direct measurement: total line advance widths ----
print("\n=== Total line pixel widths ===\n")
for i, (text, y, data) in enumerate(line_data):
    if data is None:
        continue
    x_start_actual, x_end_actual = data[0], data[1]
    pixel_width = x_end_actual - x_start_actual + 1
    print(f"  Line {i+1}: '{text}' total_pixels={pixel_width}px (from x={x_start_actual} to x={x_end_actual})")

# ---- Bottom text measurements ----
print("\n=== Bottom text pixel widths ===")
if fw_data:
    pixel_w = fw_data[1] - fw_data[0] + 1
    print(f"  'freeware': {pixel_w}px (from x={fw_data[0]} to x={fw_data[1]})")
if ss_data:
    pixel_w = ss_data[1] - ss_data[0] + 1
    print(f"  'silverspaceship.com': {pixel_w}px (from x={ss_data[0]} to x={ss_data[1]})")

# ---- Key finding: reference uses DIFFERENT glyph shapes ----
# Let's quantify the shape difference
print("\n\n=== Glyph shape comparison: sserife.fon vs reference ===\n")

import freetype
face = freetype.Face("assets/fonts/sserife.fon", 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])

# For first line, count total black pixels in reference vs our render
y1 = LINE_YS[0]
y2 = y1 + 13
x1 = line_data[0][2][0] if line_data[0][2] else 450
x2 = x1 + 175

ref_black = np.sum(ref_mask[y1:y2, x1:x2])
print(f"First line '{LINES[0]}' at y={y1}, x={x1}:")
print(f"  Reference black pixels: {ref_black}")

# Count our render's black pixels using v4 widths
with open("scripts/best_widths_v4.json") as f:
    v4_widths = json.load(f)

our_mask = np.zeros((480, 640), dtype=bool)
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
    }

pen_x = x1
for ch in LINES[0]:
    g = glyphs.get(ch)
    if g:
        dx = pen_x + g['bearing_x']
        dy = y1 + 11 - g['bearing_y']
        bm = g['bitmap']
        for by in range(bm.shape[0]):
            for bx in range(bm.shape[1]):
                if bm[by, bx]:
                    px, py = dx + bx, dy + by
                    if 0 <= px < 640 and 0 <= py < 480:
                        our_mask[py, px] = True
    pen_x += v4_widths.get(ch, 6)

our_black = np.sum(our_mask[y1:y2, x1:x2])
overlap = np.sum(our_mask[y1:y2, x1:x2] & ref_mask[y1:y2, x1:x2])

print(f"  Our (sserife.fon) black pixels: {our_black}")
print(f"  Overlap: {overlap}")
print(f"  Ratio ref/ours: {ref_black / our_black:.2f}x")
print(f"  Our pixels covered by ref: {overlap/our_black:.1%}")
print(f"  Ref pixels covered by ours: {overlap/ref_black:.1%}")

# ---- Save extracted reference glyph strip images ----
print("\n=== Saving reference text strip images ===\n")

# Save each line's reference strip as an image for visual inspection
strips = np.full((13 * 11, 200, 3), 164, dtype=np.uint8)  # 11 rows of strips
row = 0
for i, (text, y, data) in enumerate(line_data):
    if data is None:
        continue
    x_start_actual = data[0]
    y1 = y
    y2 = min(y + 13, 480)
    for dy in range(y2 - y1):
        for dx in range(min(200, 640 - x_start_actual)):
            if ref_mask[y1 + dy, x_start_actual + dx]:
                strips[row * 13 + dy, dx] = [0, 0, 0]
    row += 1

# Also add bottom text
if fw_data:
    by = bottom_starts[0] if bottom_starts else 451
    for dy in range(min(13, 480 - by)):
        for dx in range(min(200, 640)):
            if ref_mask[by + dy, dx]:
                strips[row * 13 + dy, dx] = [0, 0, 0]
    row += 1

Image.fromarray(strips[:row*13]).save("screenshots/ref_text_strips.png")
print("Saved: screenshots/ref_text_strips.png")

# ---- Also save our render's strips for comparison ----
our_full = np.zeros((480, 640), dtype=bool)
cy = LINE_YS[0]
for line in LINES:
    if cy + 16 > 475: break
    pen_x = 450
    for ch in line:
        g = glyphs.get(ch)
        if g:
            dx = pen_x + g['bearing_x']
            dy = cy + 11 - g['bearing_y']
            bm = g['bitmap']
            for by in range(bm.shape[0]):
                for bx in range(bm.shape[1]):
                    if bm[by, bx]:
                        px, py = dx + bx, dy + by
                        if 0 <= px < 640 and 0 <= py < 480:
                            our_full[py, px] = True
        pen_x += v4_widths.get(ch, 6)
    cy += 16

our_strips = np.full((13 * 9, 200, 3), 164, dtype=np.uint8)
cy = LINE_YS[0]
for i in range(9):
    for dy in range(13):
        for dx in range(200):
            y_pos = cy + dy
            x_pos = 450 + dx
            if 0 <= y_pos < 480 and 0 <= x_pos < 640:
                if our_full[y_pos, x_pos] and ref_mask[y_pos, x_pos]:
                    our_strips[i * 13 + dy, dx] = [0, 0, 0]  # match: black
                elif our_full[y_pos, x_pos]:
                    our_strips[i * 13 + dy, dx] = [0, 0, 255]  # extra: blue
                elif ref_mask[y_pos, x_pos]:
                    our_strips[i * 13 + dy, dx] = [255, 0, 255]  # missing: magenta
    cy += 16

Image.fromarray(our_strips).save("screenshots/our_vs_ref_strips.png")
print("Saved: screenshots/our_vs_ref_strips.png")
