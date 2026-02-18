# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""
Final advance width table, verified by manual tracing through REFLECTOR
and all 9 instruction text lines.

Key insight: some characters have "offset 0" (bitmap first pixel at pen_x)
while most have "offset 1" (first pixel at pen_x + 1). The raw fp_diff
measurements need correction: when current char has offset=0 or next char
has offset=0, the measurement is off by 1.

Offset=0 characters (confirmed from reference): t, f, T
All others: offset=1

Corrected advance = raw_fp_diff - offset(next) + offset(current)
"""
import freetype
import numpy as np
from PIL import Image
import json
from collections import Counter

# ---- Reference data ----
# These advances were traced through the reference screenshot
# using island positions and correcting for character offsets.

# Measured characters (from instruction text + bottom text):
MEASURED = {
    ' ': 4,   # 17/22 observations via word gap analysis
    '.': 4,   # from silverspaceship.com: .→c = fp_diff 4
    'C': 9,   # from Click: C→l=9, REFLECTOR: C→T=8(corrected: 9)
    'D': 10,  # from Drag: D→r=10
    'E': 9,   # from REFLECTOR: E→F=9
    'F': 8,   # from REFLECTOR: F→L=8
    'L': 8,   # from REFLECTOR: L→E=8
    'O': 10,  # from REFLECTOR: traced O→R=10
    'P': 9,   # from Position: P→o=9
    'R': 10,  # from REFLECTOR: R→E=10, R+sp=14-4=10
    'T': 8,   # from REFLECTOR: T→O=9, corrected for T offset=0: 8
    'a': 8,   # 11/13 observations (7s corrected to 8 before t/f)
    'b': 8,   # 5/5 observations
    'c': 7,   # 4/4 observations (all from c→non-t/f context)
    'd': 8,   # estimated from pattern (fon=6, +2)
    'e': 8,   # 9/10 observations (7 corrected to 8 before t/f)
    'f': 4,   # raw=5, corrected for f offset=0: 4
    'g': 8,   # from Drag: g+sp+t = 11, advance(g)=11-4-(-1)=8
    'h': 8,   # 9/9 observations
    'i': 4,   # 9/13 observations=4 (3s corrected to 4 before t)
    'k': 8,   # estimated (fon=6, +2; not directly measured)
    'l': 4,   # 6/7 observations (3 corrected to 4 before t)
    'm': 12,  # 2/2 observations
    'n': 8,   # corrected: 7s become 8 (before t, offset=0)
    'o': 8,   # 10/14 observations (7s corrected to 8 before t/f)
    'p': 8,   # 4/4 observations (no correction needed)
    'r': 5,   # 9/9 observations (all from r→offset=1 contexts)
    's': 8,   # 7/7 observations
    't': 4,   # raw=5, corrected for t offset=0: 4
    'u': 8,   # estimated (fon=6, +2)
    'v': 9,   # 1 observation
    'w': 11,  # 2/2 observations (from pinwheel, freeware)
    'x': 7,   # estimated (fon=5, +2)
}

# Verify: all instruction line breaks must be correct
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

# ---- Verify line breaks ----
print("=== Line break verification ===\n")
lines = word_wrap(INSTRUCTION, 170, MEASURED)
all_match = True
for i, line in enumerate(lines):
    w = measure_text(line, MEASURED)
    expected = EXPECTED_LINES[i] if i < len(EXPECTED_LINES) else "???"
    match = "✓" if line == expected else "✗"
    if line != expected: all_match = False
    if i + 1 < len(EXPECTED_LINES):
        next_word = EXPECTED_LINES[i + 1].split()[0]
        overflow = f"{expected} {next_word}"
        ow = measure_text(overflow, MEASURED)
        print(f"  {i+1}. {match} [{w:3d}px] '{line}' (overflow+'{next_word}'={ow})")
    else:
        print(f"  {i+1}. {match} [{w:3d}px] '{line}' (last)")

if all_match:
    print("\n ALL 9 LINES MATCH EXPECTED! ")
else:
    print("\n MISMATCH! Need adjustment.")

# Key widths
print(f"\nKey metrics:")
print(f"  'freeware': {measure_text('freeware', MEASURED)}px")
print(f"  'silverspaceship.com': {measure_text('silverspaceship.com', MEASURED)}px")

# ---- Build full ASCII table ----
# Load sserife.fon for reference
face = freetype.Face("assets/fonts/sserife.fon", 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])
fon_advance = {}
for code in range(32, 127):
    ch = chr(code)
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    fon_advance[ch] = face.glyph.advance.x >> 6

# For unmeasured characters, use fon + 2 (the dominant pattern)
full_widths = {}
for code in range(32, 127):
    ch = chr(code)
    if ch in MEASURED:
        full_widths[ch] = MEASURED[ch]
    else:
        full_widths[ch] = fon_advance[ch] + 2

print(f"\n\n=== Full advance width table ===\n")
print(f"{'Code':>4} {'Char':>6} {'FON':>4} {'New':>4} {'Delta':>6}")
for code in range(32, 127):
    ch = chr(code)
    fon = fon_advance[ch]
    new = full_widths[ch]
    delta = new - fon
    ch_d = repr(ch) if ch != ' ' else "'SP'"
    measured = "M" if ch in MEASURED else "E"  # M=measured, E=estimated
    print(f"  {code:3d} {ch_d:>5}: {fon:3d} → {new:3d}  ({'+' if delta >= 0 else ''}{delta}) [{measured}]")

# ---- Pixel comparison ----
print("\n\n=== Pixel comparison with reference ===\n")

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

# Load sserife.fon glyphs
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
                   'bearing_y': face.glyph.bitmap_top}

FONT_ASCENT = 11

def render_text_at(mask, text, x, y, widths):
    pen_x = x
    for ch in text:
        g = glyphs.get(ch)
        if g:
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

# Render with corrected y positions (128 not 125, 453 not 450)
# But the Rust code uses y=125 and y=450. Let me check both.
for y_instr, y_bottom, label in [(125, 450, "Rust positions (125, 450)"),
                                   (128, 453, "Reference positions (128, 453)")]:
    our = np.zeros((480, 640), dtype=bool)
    cy = y_instr
    for line_text in EXPECTED_LINES:
        if cy + 16 > 475: break
        render_text_at(our, line_text, 450, cy, full_widths)
        cy += 16
    render_text_at(our, "freeware", 0, y_bottom, full_widths)
    render_text_at(our, "silverspaceship.com", 470, y_bottom, full_widths)

    # Score
    instr_region = (120, 300, 448, 622)
    bottom_region = (446, 475, 0, 640)

    y1, y2, x1, x2 = instr_region
    o, r = our[y1:y2, x1:x2], ref_mask[y1:y2, x1:x2]
    agree_instr = np.sum(o == r) / r.size
    tp = np.sum(o & r)
    fp = np.sum(o & ~r)
    fn = np.sum(~o & r)
    f1_instr = 2*tp / (2*tp + fp + fn) if (2*tp + fp + fn) > 0 else 0

    y1, y2, x1, x2 = bottom_region
    o, r = our[y1:y2, x1:x2], ref_mask[y1:y2, x1:x2]
    agree_bottom = np.sum(o == r) / r.size

    overall = np.sum(our == ref_mask) / ref_mask.size

    print(f"{label}:")
    print(f"  Instruction agree: {agree_instr:.4f}, F1: {f1_instr:.4f}")
    print(f"  Bottom agree: {agree_bottom:.4f}")
    print(f"  Overall agree: {overall:.6f}")
    print()

# Save final widths
with open("scripts/final_widths.json", "w") as f:
    json.dump(full_widths, f, indent=2)
print("Saved: scripts/final_widths.json")

# Also save as Rust-friendly format
print("\n=== Rust advance array ===\n")
print("// Advance widths for ASCII 32-126 (matching original MS Sans Serif 8pt)")
print("const ADVANCES: [u8; 95] = [")
advances = []
for code in range(32, 127):
    ch = chr(code)
    advances.append(full_widths.get(ch, fon_advance.get(ch, 6) + 2))
# Print in groups of 16
for i in range(0, len(advances), 16):
    chunk = advances[i:i+16]
    print(f"    {', '.join(f'{a:2d}' for a in chunk)},")
print("];")
