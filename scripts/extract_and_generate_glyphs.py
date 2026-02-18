# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""Extract pixel-perfect glyph bitmaps from reference screenshot + generate Rust source.

The reference PNG has purely binary pixels (black 0,0,0 on gray 164,164,164).
We know every character's pen_x position from corrected advance widths.
For each character cell [pen_x, pen_x+advance) x [y, y+13), extract the bitmap.

Characters not in the reference text fall back to Wine's sserife.fon bitmaps.

Output: src/ms_sans_serif.rs (same format, new bitmaps) + debug sprite sheet.
"""
import numpy as np
from PIL import Image
import freetype
import json

# ---- Configuration ----
REF_PATH = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
FON_PATH = "assets/fonts/sserife.fon"
WIDTHS_PATH = "scripts/final_widths.json"
RUST_OUTPUT = "src/ms_sans_serif.rs"
SPRITE_OUTPUT = "scripts/extracted_glyphs.png"

FONT_HEIGHT = 13
FONT_ASCENT = 11
LINE_SPACING = 16

INSTRUCTION_LINES = [
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

print("Loading reference screenshot...")
ref = normalize(REF_PATH)
ref_mask = np.all(ref < 50, axis=2)  # True where black

print("Loading advance widths...")
with open(WIDTHS_PATH) as f:
    advances = json.load(f)

# ---- Auto-detect text line y-starts ----
print("\n=== Detecting text y-positions ===")
row_profile = np.sum(ref_mask[:, 448:622], axis=1)
line_starts = []
in_text = False
for y in range(115, 275):
    if row_profile[y] > 0 and not in_text:
        line_starts.append(y)
        in_text = True
    elif row_profile[y] == 0 and in_text:
        in_text = False

print(f"Instruction line y-starts: {line_starts}")
assert len(line_starts) >= 9, f"Expected 9 lines, found {len(line_starts)}"

# ---- Auto-detect instruction text pen_x ----
# Line 1 starts with 'D' which has offset 1 (first pixel at pen_x+1)
# Find first black pixel column in line 1's y-range
y0 = line_starts[0]
first_pixel_x = None
for x in range(445, 460):
    if np.any(ref_mask[y0:y0+13, x]):
        first_pixel_x = x
        break
# 'D' has offset 1 → pen_x = first_pixel - 1
INSTR_PEN_X = first_pixel_x - 1 if first_pixel_x else 450
print(f"Instruction pen_x: {INSTR_PEN_X} (first pixel of 'D' at x={first_pixel_x})")

# ---- Detect bottom text y-start ----
# "freeware" is at the very bottom. Look for black text pixels in x=[0,60], y=[448,465]
# (avoid level number grid above y=448)
bottom_y = None
for y in range(448, 465):
    if np.sum(ref_mask[y, :60]) > 0:
        bottom_y = y
        break
print(f"Bottom text y-start: {bottom_y}")

# Auto-detect bottom text x-starts
# "freeware" starts with 'f' (offset 0 → first pixel at pen_x)
FW_PEN_X = None
if bottom_y:
    for x in range(0, 20):
        if np.any(ref_mask[bottom_y:bottom_y+13, x]):
            FW_PEN_X = x  # 'f' has offset 0
            break
print(f"'freeware' pen_x: {FW_PEN_X}")

# "silverspaceship.com" starts with 's' (offset 1 → first pixel at pen_x+1)
SS_PEN_X = None
if bottom_y:
    for x in range(465, 485):
        if np.any(ref_mask[bottom_y:bottom_y+13, x]):
            SS_PEN_X = x - 1  # 's' has offset 1
            break
print(f"'silverspaceship.com' pen_x: {SS_PEN_X}")

# ---- Extract character cells using ISLAND-BASED positioning ----
# Instead of cumulative pen_x (which drifts), find each character's actual
# pixel position from islands in the reference image.
print("\n=== Extracting character bitmaps (island-based) ===")

char_bitmaps = {}  # ch -> list of (bitmap_2d, island_start, island_end)

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

def extract_line_islands(text, y_start, x_left, x_right, label=""):
    """Extract character bitmaps using island positions."""
    islands = get_islands(y_start, x_left, x_right)
    non_space_chars = [c for c in text if c != ' ']

    if len(islands) == len(non_space_chars):
        # Perfect 1:1 mapping
        island_idx = 0
        extracted = 0
        for ch in text:
            if ch == ' ':
                continue
            isl_start, isl_end = islands[island_idx]
            # Extract bitmap at island position, full 13px height
            bm = ref_mask[y_start:y_start+FONT_HEIGHT, isl_start:isl_end+1].copy()
            if ch not in char_bitmaps:
                char_bitmaps[ch] = []
            char_bitmaps[ch].append((bm, isl_start, isl_end))
            island_idx += 1
            extracted += 1
        print(f"  {label}: {extracted} chars, {len(islands)} islands (perfect match)")
    elif len(islands) == len(non_space_chars) - 1:
        # One merged island — find which chars merged
        # Strategy: use advance widths to determine split point
        pen_x = x_left
        for x in range(x_left, x_left + 20):
            if np.any(ref_mask[y_start:y_start+FONT_HEIGHT, x]):
                pen_x = x
                break

        # Map islands to chars, detecting the merged pair
        island_idx = 0
        char_list = [(ch, i) for i, ch in enumerate(text) if ch != ' ']
        extracted = 0

        # Compute expected pen_x per non-space char using advances
        positions = []  # (ch, pen_x_expected)
        px = INSTR_PEN_X if x_left > 100 else FW_PEN_X or 0
        for ch in text:
            if ch != ' ':
                positions.append((ch, px))
            px += advances.get(ch, 6)

        # For each island, check if it maps to 1 or 2 chars
        pos_idx = 0
        for isl_start, isl_end in islands:
            ch, exp_px = positions[pos_idx]
            isl_width = isl_end - isl_start + 1

            # Check if this island is too wide (merged two chars)
            adv = advances.get(ch, 6)
            if pos_idx + 1 < len(positions) and isl_width > adv + 2:
                # Merged! Split at the advance boundary
                ch2, exp_px2 = positions[pos_idx + 1]
                split_x = isl_start + adv  # approximate split
                # Find nearest blank or low-density column for split
                bm1 = ref_mask[y_start:y_start+FONT_HEIGHT, isl_start:split_x].copy()
                bm2 = ref_mask[y_start:y_start+FONT_HEIGHT, split_x:isl_end+1].copy()
                if ch not in char_bitmaps:
                    char_bitmaps[ch] = []
                char_bitmaps[ch].append((bm1, isl_start, split_x - 1))
                if ch2 not in char_bitmaps:
                    char_bitmaps[ch2] = []
                char_bitmaps[ch2].append((bm2, split_x, isl_end))
                pos_idx += 2
                extracted += 2
            else:
                bm = ref_mask[y_start:y_start+FONT_HEIGHT, isl_start:isl_end+1].copy()
                if ch not in char_bitmaps:
                    char_bitmaps[ch] = []
                char_bitmaps[ch].append((bm, isl_start, isl_end))
                pos_idx += 1
                extracted += 1

        print(f"  {label}: {extracted} chars, {len(islands)} islands (1 merged)")
    else:
        print(f"  {label}: SKIP — {len(islands)} islands vs {len(non_space_chars)} chars")

# Instruction lines
for i, (text, y) in enumerate(zip(INSTRUCTION_LINES, line_starts[:9])):
    extract_line_islands(text, y, 445, 625, f"Line {i+1} (y={y})")

# Bottom text
if bottom_y is not None:
    extract_line_islands("freeware", bottom_y, 0, 80, "freeware")
    extract_line_islands("silverspaceship.com", bottom_y, 465, 640, "silverspaceship.com")

# ---- Verify consistency ----
print(f"\n=== Consistency check ({len(char_bitmaps)} unique chars) ===")
consistent_bitmaps = {}  # ch -> single canonical 2D array
inconsistent = []

for ch in sorted(char_bitmaps.keys()):
    entries = char_bitmaps[ch]  # list of (bitmap, isl_start, isl_end)
    n = len(entries)

    # All bitmaps should have the same shape (same width)
    # Group by width, take the most common width
    from collections import Counter
    widths = [bm.shape[1] for bm, s, e in entries]
    width_counts = Counter(widths)
    best_width = width_counts.most_common(1)[0][0]

    # Filter to bitmaps with the best width
    same_width = [(bm, s, e) for bm, s, e in entries if bm.shape[1] == best_width]
    diff_width = [(bm, s, e) for bm, s, e in entries if bm.shape[1] != best_width]

    if diff_width:
        print(f"  '{ch}': {n} occ, {len(diff_width)} with different widths "
              f"({[bm.shape[1] for bm, s, e in diff_width]} vs {best_width})")

    bitmaps = [bm for bm, s, e in same_width]

    if len(bitmaps) == 1:
        consistent_bitmaps[ch] = bitmaps[0]
        pixels = int(np.sum(bitmaps[0]))
        print(f"  '{ch}': {n} occ (w={best_width}), {pixels} black pixels")
    else:
        # Check all match
        ref_bm = bitmaps[0]
        mismatches = 0
        for i, bm in enumerate(bitmaps[1:], 1):
            if not np.array_equal(ref_bm, bm):
                mismatches += 1

        if mismatches == 0:
            consistent_bitmaps[ch] = ref_bm
            pixels = int(np.sum(ref_bm))
            print(f"  '{ch}': {len(bitmaps)} occ (w={best_width}), all identical, {pixels} px")
        else:
            # Use majority vote
            stacked = np.stack(bitmaps)
            majority = np.sum(stacked, axis=0) > (len(bitmaps) / 2)
            consistent_bitmaps[ch] = majority
            inconsistent.append(ch)
            pixels = int(np.sum(majority))
            print(f"  '{ch}': {len(bitmaps)} occ (w={best_width}), {mismatches} differ, "
                  f"majority={pixels} px")

if inconsistent:
    print(f"\nWARNING: {len(inconsistent)} chars had inconsistencies: {inconsistent}")
else:
    print(f"\nAll {len(consistent_bitmaps)} extracted chars are perfectly consistent!")

# ---- Load Wine sserife.fon for fallback ----
print("\n=== Loading Wine sserife.fon for fallback glyphs ===")
face = freetype.Face(FON_PATH, 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])

wine_glyphs = {}
for code in range(32, 127):
    ch = chr(code)
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bm = face.glyph.bitmap
    bitmap = np.zeros((bm.rows, bm.width), dtype=bool)
    for by in range(bm.rows):
        for bx in range(bm.width):
            if bm.buffer[by * bm.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                bitmap[by, bx] = True
    wine_glyphs[ch] = {
        'bitmap': bitmap,
        'bearing_x': face.glyph.bitmap_left,
        'bearing_y': face.glyph.bitmap_top,
        'width': bm.width,
        'height': bm.rows,
    }

# ---- Build final glyph set ----
print("\n=== Building final glyph set ===")

# For each ASCII 32-126, determine source and prepare bitmap data
final_glyphs = []  # list of dicts with all glyph info
ref_count = 0
wine_count = 0

for code in range(32, 127):
    ch = chr(code)
    adv = advances.get(ch, 6)

    if ch in consistent_bitmaps and ch != ' ':
        # Use reference-extracted bitmap (island-based: tight bbox)
        island_bm = consistent_bitmaps[ch]
        source = "ref"
        ref_count += 1

        # Island bitmap is the tight bounding box of black pixels.
        # We need to determine bearing_x:
        # - Characters with "offset 0" (t, f, T): first pixel at pen_x → bearing_x = 0
        # - Characters with "offset 1" (all others): first pixel at pen_x+1 → bearing_x = 1
        # The island bitmap starts at the first pixel, so:
        # - offset 0 chars: bearing_x = 0, bitmap = island as-is
        # - offset 1 chars: bearing_x = 1, bitmap = island as-is
        OFFSET_0_CHARS = {'t', 'f', 'T'}
        bearing_x = 0 if ch in OFFSET_0_CHARS else 1

        bitmap_2d = island_bm
        width = bitmap_2d.shape[1]
        height = FONT_HEIGHT
        bearing_y = FONT_ASCENT

        # Ensure height = 13
        if bitmap_2d.shape[0] < FONT_HEIGHT:
            bitmap_2d = np.pad(bitmap_2d, ((0, FONT_HEIGHT - bitmap_2d.shape[0]), (0, 0)))
        elif bitmap_2d.shape[0] > FONT_HEIGHT:
            bitmap_2d = bitmap_2d[:FONT_HEIGHT, :]

    else:
        # Use Wine fallback (including space)
        source = "wine"
        wine_count += 1
        wg = wine_glyphs[ch]
        bitmap_2d = wg['bitmap']
        width = wg['width']
        bearing_x = wg['bearing_x']
        bearing_y = wg['bearing_y']
        height = wg['height']

    pitch = (width + 7) // 8

    # Pack bitmap into 1-bit bytes (MSB = leftmost)
    packed = []
    for row in range(height):
        for byte_idx in range(pitch):
            byte_val = 0
            for bit in range(8):
                col = byte_idx * 8 + bit
                if col < width and row < bitmap_2d.shape[0] and col < bitmap_2d.shape[1]:
                    if bitmap_2d[row, col]:
                        byte_val |= (1 << (7 - bit))
            packed.append(byte_val)

    final_glyphs.append({
        'code': code,
        'char': ch,
        'advance': adv,
        'bearing_x': bearing_x,
        'bearing_y': bearing_y,
        'width': width,
        'height': height,
        'pitch': pitch,
        'packed': packed,
        'source': source,
    })

print(f"  Reference-extracted: {ref_count} glyphs")
print(f"  Wine fallback: {wine_count} glyphs")

# ---- Generate Rust source ----
print(f"\n=== Generating {RUST_OUTPUT} ===")

lines = []
lines.append("/// MS Sans Serif 8pt bitmap font data.")
lines.append("/// Glyph bitmaps extracted from reference screenshot (original Windows game).")
lines.append("/// Fallback glyphs from Wine's sserife.fon (LGPL 2.1) for chars not in screenshot.")
lines.append("/// Advance widths from scripts/final_widths.json (island analysis + offset correction).")
lines.append("/// Generated by scripts/extract_and_generate_glyphs.py.")
lines.append("")
lines.append("/// Per-glyph metrics and bitmap data.")
lines.append("#[derive(Clone, Copy)]")
lines.append("pub struct GlyphData {")
lines.append("    /// Character advance width in pixels")
lines.append("    pub advance: u8,")
lines.append("    /// Horizontal bearing (offset from pen position to left edge of bitmap)")
lines.append("    pub bearing_x: i8,")
lines.append("    /// Vertical bearing (offset from baseline to top edge of bitmap)")
lines.append("    pub bearing_y: i8,")
lines.append("    /// Bitmap width in pixels")
lines.append("    pub width: u8,")
lines.append("    /// Bitmap height in pixels")
lines.append("    pub height: u8,")
lines.append("    /// Bitmap pitch (bytes per row)")
lines.append("    pub pitch: u8,")
lines.append("    /// Offset into BITMAP_DATA where this glyph's rows start")
lines.append("    pub bitmap_offset: u16,")
lines.append("}")
lines.append("")
lines.append(f"/// Font height (tmHeight) = {FONT_HEIGHT}px")
lines.append(f"pub const FONT_HEIGHT: i32 = {FONT_HEIGHT};")
lines.append("")
lines.append(f"/// Font ascent (ascender) = {FONT_ASCENT}px")
lines.append(f"pub const FONT_ASCENT: i32 = {FONT_ASCENT};")
lines.append("")
lines.append(f"/// Line spacing (tmHeight + tmExternalLeading) = {LINE_SPACING}px")
lines.append("/// Source: DrawTextA uses this for line skip")
lines.append(f"pub const LINE_SPACING: i32 = {LINE_SPACING};")
lines.append("")

# Build flat bitmap data array and glyph table
bitmap_data = []
glyph_entries = []

for g in final_glyphs:
    offset = len(bitmap_data)
    bitmap_data.extend(g['packed'])

    ch = g['char']
    if ch == '\\':
        ch_display = "'\\\\'"
    elif ch == "'":
        ch_display = "'\\''"
    else:
        ch_display = f"'{ch}'"

    src_tag = "REF" if g['source'] == "ref" else "FON"

    glyph_entries.append(
        f"    GlyphData {{ advance: {g['advance']:2}, bearing_x: {g['bearing_x']:2}, "
        f"bearing_y: {g['bearing_y']:2}, width: {g['width']:2}, height: {g['height']:2}, "
        f"pitch: {g['pitch']}, bitmap_offset: {offset:4} }}, // {g['code']:3} {ch_display} [{src_tag}]"
    )

lines.append(f"/// Glyph metrics for ASCII 32-126 ({len(final_glyphs)} characters).")
lines.append("/// Index = char_code - 32.")
lines.append("/// [REF] = extracted from reference screenshot, [FON] = Wine sserife.fon fallback.")
lines.append("#[rustfmt::skip]")
lines.append(f"pub const GLYPHS: [GlyphData; {len(final_glyphs)}] = [")
for entry in glyph_entries:
    lines.append(entry)
lines.append("];")
lines.append("")

lines.append("/// Packed 1-bit bitmap data for all glyphs.")
lines.append("/// Each row is `pitch` bytes, MSB = leftmost pixel.")
lines.append("#[rustfmt::skip]")
lines.append(f"pub const BITMAP_DATA: [u8; {len(bitmap_data)}] = [")

for i in range(0, len(bitmap_data), 16):
    chunk = bitmap_data[i:i+16]
    hex_bytes = ", ".join(f"0x{b:02X}" for b in chunk)
    lines.append(f"    {hex_bytes},")

lines.append("];")
lines.append("")

rust_src = "\n".join(lines)
with open(RUST_OUTPUT, "w") as f:
    f.write(rust_src)
print(f"Wrote {RUST_OUTPUT} ({len(rust_src)} bytes, {len(final_glyphs)} glyphs, {len(bitmap_data)} bitmap bytes)")

# ---- Generate debug sprite sheet ----
print(f"\n=== Generating {SPRITE_OUTPUT} ===")
cell_w = 14  # max advance + padding
cell_h = 16
cols = 16
rows_img = (len(final_glyphs) + cols - 1) // cols
img_w = cols * cell_w
img_h = rows_img * cell_h

img = Image.new('RGB', (img_w, img_h), (164, 164, 164))
pixels = img.load()

for idx, g in enumerate(final_glyphs):
    col_idx = idx % cols
    row_idx = idx // cols
    base_x = col_idx * cell_w
    base_y = row_idx * cell_h

    # Draw glyph pixels
    gx = base_x + g['bearing_x']
    gy = base_y + FONT_ASCENT - g['bearing_y']

    color = (0, 0, 0) if g['source'] == "ref" else (0, 0, 200)  # black for ref, blue for wine

    for by in range(g['height']):
        for bx in range(g['width']):
            byte_idx = by * g['pitch'] + (bx >> 3)
            bit_idx = 7 - (bx & 7)
            if byte_idx < len(g['packed']) and (g['packed'][byte_idx] & (1 << bit_idx)):
                px = gx + bx
                py = gy + by
                if 0 <= px < img_w and 0 <= py < img_h:
                    pixels[px, py] = color

img.save(SPRITE_OUTPUT)
print(f"Wrote {SPRITE_OUTPUT} ({img_w}x{img_h})")
print(f"\nBlack = reference-extracted glyphs, Blue = Wine fallback glyphs")
