# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""Find exact alignment of System font glyphs to match reference 13px cell."""
import numpy as np
from PIL import Image
import freetype

SYS_FON = "assets/fonts/vgasys.fon"
REF_PATH = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"

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

ref = normalize(REF_PATH)
ref_mask = np.all(ref < 50, axis=2)

LINES = [
    "Drag the REFLECTOR in", "the toolbox above onto",
    "the board and place it in", "front of the laser beam.",
    "Click on it to rotate it.", "Position the mirror so that",
    "the laser beam is", "reflected into the", "pinwheel.",
]
Y_STARTS = [128, 144, 160, 176, 192, 208, 224, 240, 256]

def get_islands(mask, y_start, x_left, x_right):
    strip = mask[y_start:y_start+13, x_left:x_right]
    col_profile = np.sum(strip, axis=0)
    islands, in_island, start = [], False, 0
    for i in range(len(col_profile)):
        if col_profile[i] > 0:
            if not in_island: start = i; in_island = True
        else:
            if in_island: islands.append((x_left+start, x_left+i-1)); in_island = False
    if in_island: islands.append((x_left+start, x_left+len(col_profile)-1))
    return islands

ref_glyphs = {}
for text, y in zip(LINES, Y_STARTS):
    islands = get_islands(ref_mask, y, 445, 625)
    non_space = [c for c in text if c != ' ']
    if len(islands) == len(non_space):
        for ch, (s, e) in zip(non_space, islands):
            if ch not in ref_glyphs:
                ref_glyphs[ch] = ref_mask[y:y+13, s:e+1]

print(f"Reference glyphs: {len(ref_glyphs)}")

def load_glyph(face, ch):
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bm = face.glyph.bitmap
    bitmap = np.zeros((bm.rows, bm.width), dtype=bool)
    for by in range(bm.rows):
        for bx in range(bm.width):
            if bm.buffer[by * bm.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                bitmap[by, bx] = True
    return bitmap, face.glyph.bitmap_left, face.glyph.bitmap_top, face.glyph.advance.x // 64

# Load System font
face = freetype.Face(SYS_FON, 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])

# For each reference glyph, try all y-offsets and x-offsets to find exact match
print("\n=== Finding alignment for each glyph ===")

def compare_at_offset(ref_bm, sys_bm, dy, dx):
    """Compare ref (13xW) against sys (16xW2) with offset (dy, dx)."""
    matches = 0
    total = 0
    for ry in range(ref_bm.shape[0]):
        sy = ry + dy
        for rx in range(ref_bm.shape[1]):
            sx = rx + dx
            total += 1
            ref_val = ref_bm[ry, rx]
            sys_val = sys_bm[sy, sx] if 0 <= sy < sys_bm.shape[0] and 0 <= sx < sys_bm.shape[1] else False
            if ref_val == sys_val:
                matches += 1
    return total - matches  # return number of differences

best_offsets = {}
for ch in sorted(ref_glyphs.keys()):
    ref_bm = ref_glyphs[ch]
    sys_bm, bx, by, adv = load_glyph(face, ch)

    best_dy, best_dx, best_diff = 0, 0, 9999
    for dy in range(-2, 8):
        for dx in range(-3, 5):
            diff = compare_at_offset(ref_bm, sys_bm, dy, dx)
            if diff < best_diff:
                best_dy, best_dx, best_diff = dy, dx, diff

    best_offsets[ch] = (best_dy, best_dx, best_diff)
    tag = "PERFECT!" if best_diff == 0 else f"diff={best_diff}"
    print(f"  '{ch}': best offset dy={best_dy}, dx={best_dx}  {tag}  "
          f"(ref {ref_bm.shape[1]}x{ref_bm.shape[0]}, sys {sys_bm.shape[1]}x{sys_bm.shape[0]}, "
          f"bearing_x={bx}, bearing_y={by})")

# Summary
dys = [v[0] for v in best_offsets.values() if v[2] == 0]
dxs = [v[1] for v in best_offsets.values() if v[2] == 0]
perfect = sum(1 for v in best_offsets.values() if v[2] == 0)
print(f"\nPerfect matches: {perfect}/{len(ref_glyphs)}")
if dys:
    from collections import Counter
    print(f"dy values (perfect only): {Counter(dys)}")
    print(f"dx values (perfect only): {Counter(dxs)}")

# Show advance widths
print(f"\n=== System font advance widths ===")
import json
with open("scripts/final_widths.json") as f:
    our_advances = json.load(f)

print("Char  sys_adv  our_adv  match")
mismatches = 0
for code in range(32, 127):
    ch = chr(code)
    _, _, _, sys_adv = load_glyph(face, ch)
    our_adv = our_advances.get(ch, 0)
    if sys_adv != our_adv:
        print(f"  {code:3d} '{ch}': sys={sys_adv}  our={our_adv}  MISMATCH")
        mismatches += 1

print(f"\n{mismatches} advance width mismatches out of 95")
