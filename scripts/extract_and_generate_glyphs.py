# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""Extract pixel-perfect glyph bitmaps from multiple reference screenshots.

Processes all 4 level screenshots to maximize reference glyph coverage.
Characters not in any screenshot fall back to Wine's sserife.fon (boldened
to match reference weight).

Output: src/ms_sans_serif.rs (bitmap font data) + debug sprite sheet.
"""
import numpy as np
from PIL import Image
import freetype
import json

# ---- Configuration ----
FON_PATH = "assets/fonts/sserife.fon"
WIDTHS_PATH = "scripts/final_widths.json"
RUST_OUTPUT = "src/ms_sans_serif.rs"
SPRITE_OUTPUT = "scripts/extracted_glyphs.png"

FONT_HEIGHT = 13
FONT_ASCENT = 11
LINE_SPACING = 16
INSTR_RECT_WIDTH = 170  # 620 - 450

# Characters where first pixel starts at pen_x (offset 0)
# All others start at pen_x + 1 (offset 1)
OFFSET_0_CHARS = {'t', 'f', 'T'}

SCREENSHOTS = [
    {
        'path': "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png",
        'label': "Level 1",
        'instruction': "Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel.",
        'extra': [],
    },
    {
        'path': "screenshots/15688195-chromatron-windows-level-2-level-completed.png",
        'label': "Level 2 (won)",
        'instruction': "Click on a level or press spacebar for next.",
        'extra': [
            # "You win!" at rect (170, 385)
            {"text": "You win!", "x_search": (165, 195), "y_search": (380, 400)},
            # "(won)" at rect (350, 385)
            {"text": "(won)", "x_search": (345, 365), "y_search": (380, 400)},
        ],
    },
    {
        'path': "screenshots/15688228-chromatron-windows-level-3-rgb-to-cmy-conversion.png",
        'label': "Level 3",
        'instruction': "Some pinwheels require multiple lasers to light them up. You get magenta from red and blue. Yellow is formed by green plus red. Combining green and blue yields a color known variously as cyan, teal, or aqua.",
        'extra': [],
    },
    {
        'path': "screenshots/15870999-chromatron-windows-level-4-introduction-of-splitter.png",
        'label': "Level 4",
        'instruction': "If a laser hits a SPLITTER at the correct angle, it bounces off at an angle and also goes straight through. If it hits head on, it just goes through.",
        'extra': [],
    },
]

# ---- Load advance widths ----
print("Loading advance widths...")
with open(WIDTHS_PATH) as f:
    advances = json.load(f)


# ---- Utility functions ----

def normalize(path):
    """Load screenshot, crop to game area, place on 640x480 gray canvas."""
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows, cols = np.any(gray, axis=1), np.any(gray, axis=0)
    if not rows.any() or not cols.any():
        result = np.full((480, 640, 3), 164, dtype=np.uint8)
        ph, pw = min(arr.shape[0], 480), min(arr.shape[1], 640)
        result[:ph, :pw] = arr[:ph, :pw]
        return result
    y1 = int(np.argmax(rows))
    y2 = int(arr.shape[0] - np.argmax(rows[::-1]))
    x1 = int(np.argmax(cols))
    x2 = int(arr.shape[1] - np.argmax(cols[::-1]))
    cropped = arr[y1:y2, x1:x2]
    ch, cw = cropped.shape[:2]
    # Handle Retina 2x
    if abs(cw - 1280) < 20 and abs(ch - 960) < 20:
        cropped = np.array(Image.fromarray(cropped).resize((640, 480), Image.BOX))
        ch, cw = cropped.shape[:2]
    result = np.full((480, 640, 3), 164, dtype=np.uint8)
    ph, pw = min(ch, 480), min(cw, 640)
    result[:ph, :pw] = cropped[:ph, :pw]
    return result


def word_wrap(text, max_width):
    """Break text into lines matching Win32 DT_WORDBREAK behavior."""
    words = text.split(' ')
    lines = []
    current = ""
    width = 0
    space_w = advances.get(' ', 3)

    for word in words:
        word_w = sum(advances.get(ch, 6) for ch in word)
        if current:
            test_w = width + space_w + word_w
            if test_w > max_width:
                lines.append(current)
                current = word
                width = word_w
            else:
                current += " " + word
                width = test_w
        else:
            current = word
            width = word_w

    if current:
        lines.append(current)
    return lines


def get_islands(mask, y_start, x_left, x_right, height=13):
    """Find contiguous columns with black pixels in a strip."""
    strip = mask[y_start:y_start+height, x_left:x_right]
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


def detect_text_y_starts(mask, x_left, x_right, y_min, y_max):
    """Find y-starts of text lines by scanning row profile."""
    row_profile = np.sum(mask[:, x_left:x_right], axis=1)
    line_starts = []
    in_text = False
    for y in range(y_min, y_max):
        if row_profile[y] > 0 and not in_text:
            line_starts.append(y)
            in_text = True
        elif row_profile[y] == 0 and in_text:
            in_text = False
    return line_starts


def extract_line_islands(mask, text, y_start, x_left, x_right, label=""):
    """Extract character bitmaps using island positions. Returns list of (ch, bitmap_2d)."""
    islands = get_islands(mask, y_start, x_left, x_right)
    non_space_chars = [c for c in text if c != ' ']
    results = []

    if len(islands) == len(non_space_chars):
        # Perfect 1:1 mapping
        island_idx = 0
        for ch in text:
            if ch == ' ':
                continue
            isl_start, isl_end = islands[island_idx]
            bm = mask[y_start:y_start+FONT_HEIGHT, isl_start:isl_end+1].copy()
            results.append((ch, bm))
            island_idx += 1
        print(f"    {label}: {len(results)} chars, {len(islands)} islands (perfect)")

    elif len(islands) == len(non_space_chars) - 1:
        # One merged island — split using advance widths
        # Compute expected positions for splitting
        pen_x_start = x_left
        for x in range(x_left, x_left + 20):
            if np.any(mask[y_start:y_start+FONT_HEIGHT, x]):
                pen_x_start = x
                break

        positions = []
        px = pen_x_start
        first_ch = non_space_chars[0]
        if first_ch in OFFSET_0_CHARS:
            pass  # pen_x = first pixel
        else:
            px -= 1  # offset 1: pen_x = first_pixel - 1

        for ch in text:
            if ch != ' ':
                positions.append((ch, px))
            px += advances.get(ch, 6)

        island_idx = 0
        pos_idx = 0
        for isl_start, isl_end in islands:
            if pos_idx >= len(positions):
                break
            ch, exp_px = positions[pos_idx]
            isl_width = isl_end - isl_start + 1
            adv = advances.get(ch, 6)

            # Check if merged (island too wide for single char)
            if pos_idx + 1 < len(positions) and isl_width > adv + 2:
                ch2, exp_px2 = positions[pos_idx + 1]
                split_x = isl_start + adv
                bm1 = mask[y_start:y_start+FONT_HEIGHT, isl_start:split_x].copy()
                bm2 = mask[y_start:y_start+FONT_HEIGHT, split_x:isl_end+1].copy()
                results.append((ch, bm1))
                results.append((ch2, bm2))
                pos_idx += 2
            else:
                bm = mask[y_start:y_start+FONT_HEIGHT, isl_start:isl_end+1].copy()
                results.append((ch, bm))
                pos_idx += 1

        print(f"    {label}: {len(results)} chars, {len(islands)} islands (1 merged)")

    elif abs(len(islands) - len(non_space_chars)) <= 2:
        # Close but not exact — might have 2 merges. Try advance-based splitting.
        pen_x_start = x_left
        for x in range(x_left, x_left + 20):
            if np.any(mask[y_start:y_start+FONT_HEIGHT, x]):
                pen_x_start = x
                break

        positions = []
        px = pen_x_start
        first_ch = non_space_chars[0]
        if first_ch not in OFFSET_0_CHARS:
            px -= 1

        for ch in text:
            if ch != ' ':
                positions.append((ch, px))
            px += advances.get(ch, 6)

        island_idx = 0
        pos_idx = 0
        for isl_start, isl_end in islands:
            if pos_idx >= len(positions):
                break
            ch, exp_px = positions[pos_idx]
            isl_width = isl_end - isl_start + 1
            adv = advances.get(ch, 6)

            remaining_chars = len(positions) - pos_idx
            remaining_islands = len(islands) - island_idx

            if remaining_chars > remaining_islands and isl_width > adv + 2:
                # Need to split this island for multiple chars
                chars_in_island = remaining_chars - remaining_islands + 1
                cx = isl_start
                for ci in range(chars_in_island):
                    if pos_idx + ci >= len(positions):
                        break
                    cch, _ = positions[pos_idx + ci]
                    cadv = advances.get(cch, 6)
                    cx_end = min(cx + cadv, isl_end + 1)
                    if ci == chars_in_island - 1:
                        cx_end = isl_end + 1  # last char gets remaining
                    bm = mask[y_start:y_start+FONT_HEIGHT, cx:cx_end].copy()
                    results.append((cch, bm))
                    cx = cx_end
                pos_idx += chars_in_island
            else:
                bm = mask[y_start:y_start+FONT_HEIGHT, isl_start:isl_end+1].copy()
                results.append((ch, bm))
                pos_idx += 1

            island_idx += 1

        print(f"    {label}: {len(results)} chars, {len(islands)} islands ({len(non_space_chars)} expected)")
    else:
        print(f"    {label}: SKIP — {len(islands)} islands vs {len(non_space_chars)} chars")

    return results


def embolden_bitmap(bitmap_2d):
    """Add weight by smearing right by 1 pixel (within existing dimensions)."""
    if bitmap_2d.size == 0 or bitmap_2d.shape[1] == 0:
        return bitmap_2d
    result = bitmap_2d.copy()
    result[:, 1:] |= bitmap_2d[:, :-1]  # right-smear
    return result


# ---- Process all screenshots ----
print("\n=== Processing screenshots ===")
all_char_bitmaps = {}  # ch -> list of bitmap_2d

for ss in SCREENSHOTS:
    print(f"\n--- {ss['label']} ---")
    print(f"  Loading: {ss['path']}")

    ref = normalize(ss['path'])
    mask = np.all(ref < 50, axis=2)  # True where black

    # Compute instruction text line breaks
    instr_lines = word_wrap(ss['instruction'], INSTR_RECT_WIDTH)
    print(f"  Instruction lines ({len(instr_lines)}):")
    for i, line in enumerate(instr_lines):
        w = sum(advances.get(ch, 6) for ch in line)
        print(f"    {i+1}: \"{line}\" ({w}px)")

    # Detect instruction text y-positions
    y_starts = detect_text_y_starts(mask, 448, 622, 115, 300)
    print(f"  Detected y-starts: {y_starts}")

    if len(y_starts) < len(instr_lines):
        print(f"  WARNING: Expected {len(instr_lines)} lines, found {len(y_starts)} y-starts")
        # Try wider scan
        y_starts = detect_text_y_starts(mask, 440, 630, 110, 310)
        print(f"  Wider scan y-starts: {y_starts}")

    # Extract instruction text
    for i, line in enumerate(instr_lines):
        if i >= len(y_starts):
            print(f"    Line {i+1}: SKIP (no y-start)")
            continue
        y = y_starts[i]
        results = extract_line_islands(mask, line, y, 445, 625,
                                       f"Line {i+1} (y={y})")
        for ch, bm in results:
            if ch not in all_char_bitmaps:
                all_char_bitmaps[ch] = []
            all_char_bitmaps[ch].append(bm)

    # Detect and extract bottom text
    bottom_y = None
    for y in range(448, 465):
        if np.sum(mask[y, :60]) > 0:
            bottom_y = y
            break
    print(f"  Bottom text y-start: {bottom_y}")

    if bottom_y:
        # "freeware"
        results = extract_line_islands(mask, "freeware", bottom_y, 0, 80, "freeware")
        for ch, bm in results:
            if ch not in all_char_bitmaps:
                all_char_bitmaps[ch] = []
            all_char_bitmaps[ch].append(bm)

        # "silverspaceship.com"
        results = extract_line_islands(mask, "silverspaceship.com", bottom_y, 465, 640,
                                       "silverspaceship.com")
        for ch, bm in results:
            if ch not in all_char_bitmaps:
                all_char_bitmaps[ch] = []
            all_char_bitmaps[ch].append(bm)

    # Extra text (e.g., "You win!", "(won)")
    for extra in ss.get('extra', []):
        text = extra['text']
        x_lo, x_hi = extra['x_search']
        y_lo, y_hi = extra['y_search']

        # Find actual y-start
        extra_y = None
        for y in range(y_lo, y_hi):
            if np.sum(mask[y, x_lo:x_hi+50]) > 0:
                extra_y = y
                break

        if extra_y:
            print(f"  Extra \"{text}\" at y={extra_y}")
            results = extract_line_islands(mask, text, extra_y, x_lo-5, x_hi+100,
                                           f"\"{text}\"")
            for ch, bm in results:
                if ch not in all_char_bitmaps:
                    all_char_bitmaps[ch] = []
                all_char_bitmaps[ch].append(bm)
        else:
            print(f"  Extra \"{text}\": not found in y=[{y_lo},{y_hi}]")


# ---- Verify consistency across all screenshots ----
print(f"\n=== Consistency check ({len(all_char_bitmaps)} unique chars) ===")
from collections import Counter

consistent_bitmaps = {}  # ch -> single canonical 2D array
inconsistent = []

for ch in sorted(all_char_bitmaps.keys()):
    entries = all_char_bitmaps[ch]
    n = len(entries)

    # Group by width, take the most common width
    widths = [bm.shape[1] for bm in entries]
    width_counts = Counter(widths)
    best_width = width_counts.most_common(1)[0][0]

    same_width = [bm for bm in entries if bm.shape[1] == best_width]
    diff_count = sum(1 for bm in entries if bm.shape[1] != best_width)

    if diff_count:
        print(f"  '{ch}': {n} occ, {diff_count} with different widths "
              f"({[bm.shape[1] for bm in entries if bm.shape[1] != best_width]} vs {best_width})")

    bitmaps = same_width

    if len(bitmaps) == 1:
        consistent_bitmaps[ch] = bitmaps[0]
        pixels = int(np.sum(bitmaps[0]))
        print(f"  '{ch}': {n} occ (w={best_width}), {pixels} black px")
    else:
        ref_bm = bitmaps[0]
        mismatches = sum(1 for bm in bitmaps[1:] if not np.array_equal(ref_bm, bm))

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
                  f"majority={pixels} px **INCONSISTENT**")

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


# ---- Embolden Wine fallback glyphs to match reference weight ----
print("\n=== Emboldening Wine fallback glyphs ===")

# Compare weight for chars we have both REF and Wine versions
weight_ratios = []
for ch in consistent_bitmaps:
    if ch in wine_glyphs:
        ref_px = int(np.sum(consistent_bitmaps[ch]))
        wine_px = int(np.sum(wine_glyphs[ch]['bitmap']))
        if wine_px > 0:
            ratio = ref_px / wine_px
            weight_ratios.append((ch, ref_px, wine_px, ratio))

if weight_ratios:
    avg_ratio = np.mean([r[3] for r in weight_ratios])
    print(f"  Weight comparison (REF vs Wine) for {len(weight_ratios)} chars:")
    print(f"  Average ratio: {avg_ratio:.2f}x (REF has {avg_ratio:.0%} of Wine's pixels? no...)")
    # Show a few examples
    for ch, ref_px, wine_px, ratio in sorted(weight_ratios, key=lambda x: -x[3])[:5]:
        print(f"    '{ch}': REF={ref_px} Wine={wine_px} ratio={ratio:.2f}")
    for ch, ref_px, wine_px, ratio in sorted(weight_ratios, key=lambda x: x[3])[:5]:
        print(f"    '{ch}': REF={ref_px} Wine={wine_px} ratio={ratio:.2f}")

# Apply boldening to all Wine glyphs
for ch, wg in wine_glyphs.items():
    wg['bitmap_original'] = wg['bitmap'].copy()
    wg['bitmap'] = embolden_bitmap(wg['bitmap'])

# Check emboldened weight vs reference
if weight_ratios:
    bold_ratios = []
    for ch in consistent_bitmaps:
        if ch in wine_glyphs:
            ref_px = int(np.sum(consistent_bitmaps[ch]))
            bold_px = int(np.sum(wine_glyphs[ch]['bitmap']))
            if bold_px > 0:
                ratio = ref_px / bold_px
                bold_ratios.append((ch, ref_px, bold_px, ratio))
    if bold_ratios:
        avg_bold = np.mean([r[3] for r in bold_ratios])
        print(f"\n  After emboldening:")
        print(f"  Average ratio REF/boldened: {avg_bold:.2f}x")
        for ch, ref_px, bold_px, ratio in sorted(bold_ratios, key=lambda x: abs(x[3]-1))[:5]:
            print(f"    '{ch}': REF={ref_px} bold={bold_px} ratio={ratio:.2f}")


# ---- Build final glyph set ----
print("\n=== Building final glyph set ===")

final_glyphs = []
ref_count = 0
bold_count = 0

for code in range(32, 127):
    ch = chr(code)
    adv = advances.get(ch, 6)

    if ch in consistent_bitmaps and ch != ' ':
        # Use reference-extracted bitmap
        source = "ref"
        ref_count += 1

        bitmap_2d = consistent_bitmaps[ch]
        bearing_x = 0 if ch in OFFSET_0_CHARS else 1
        bearing_y = FONT_ASCENT
        width = bitmap_2d.shape[1]
        height = FONT_HEIGHT

        # Ensure height = 13
        if bitmap_2d.shape[0] < FONT_HEIGHT:
            bitmap_2d = np.pad(bitmap_2d, ((0, FONT_HEIGHT - bitmap_2d.shape[0]), (0, 0)))
        elif bitmap_2d.shape[0] > FONT_HEIGHT:
            bitmap_2d = bitmap_2d[:FONT_HEIGHT, :]

    else:
        # Use emboldened Wine fallback
        source = "bold"
        bold_count += 1
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
print(f"  Emboldened Wine fallback: {bold_count} glyphs")

# List which chars are REF vs BOLD
ref_chars = [g['char'] for g in final_glyphs if g['source'] == 'ref']
bold_chars = [g['char'] for g in final_glyphs if g['source'] == 'bold']
print(f"\n  REF chars ({len(ref_chars)}): {''.join(ref_chars)}")
print(f"  BOLD chars ({len(bold_chars)}): {''.join(bold_chars)}")


# ---- Generate Rust source ----
print(f"\n=== Generating {RUST_OUTPUT} ===")

lines = []
lines.append("/// MS Sans Serif 8pt bitmap font data.")
lines.append("/// Glyph bitmaps extracted from reference screenshots (original Windows game).")
lines.append("/// Fallback glyphs from Wine's sserife.fon (LGPL 2.1), emboldened to match reference weight.")
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

    src_tag = "REF" if g['source'] == "ref" else "BOLD"

    glyph_entries.append(
        f"    GlyphData {{ advance: {g['advance']:2}, bearing_x: {g['bearing_x']:2}, "
        f"bearing_y: {g['bearing_y']:2}, width: {g['width']:2}, height: {g['height']:2}, "
        f"pitch: {g['pitch']}, bitmap_offset: {offset:4} }}, // {g['code']:3} {ch_display} [{src_tag}]"
    )

lines.append(f"/// Glyph metrics for ASCII 32-126 ({len(final_glyphs)} characters).")
lines.append("/// Index = char_code - 32.")
lines.append("/// [REF] = extracted from reference screenshot, [BOLD] = emboldened Wine sserife.fon.")
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
cell_w = 14
cell_h = 16
cols = 16
rows_img = (len(final_glyphs) + cols - 1) // cols
img_w = cols * cell_w
img_h = rows_img * cell_h

img = Image.new('RGB', (img_w, img_h), (164, 164, 164))
pixels_img = img.load()

for idx, g in enumerate(final_glyphs):
    col_idx = idx % cols
    row_idx = idx // cols
    base_x = col_idx * cell_w
    base_y = row_idx * cell_h

    gx = base_x + g['bearing_x']
    gy = base_y + FONT_ASCENT - g['bearing_y']

    # black for ref, dark green for boldened wine
    color = (0, 0, 0) if g['source'] == "ref" else (0, 100, 0)

    for by in range(g['height']):
        for bx in range(g['width']):
            byte_idx = by * g['pitch'] + (bx >> 3)
            bit_idx = 7 - (bx & 7)
            if byte_idx < len(g['packed']) and (g['packed'][byte_idx] & (1 << bit_idx)):
                px = gx + bx
                py = gy + by
                if 0 <= px < img_w and 0 <= py < img_h:
                    pixels_img[px, py] = color

img.save(SPRITE_OUTPUT)
print(f"Wrote {SPRITE_OUTPUT} ({img_w}x{img_h})")
print(f"\nBlack = reference-extracted, Dark green = emboldened Wine fallback")
