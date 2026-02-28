# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""Compare original Microsoft sserife.fon (96 DPI) vs reference glyphs."""
import numpy as np
from PIL import Image
import freetype

MS_FON = "assets/fonts/sserife_microsoft.fon"
WINE_FON = "assets/fonts/sserife.fon"
REF_PATH = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"

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

ref = normalize(REF_PATH)
ref_mask = np.all(ref < 50, axis=2)

# Extract reference glyphs
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
Y_STARTS = [128, 144, 160, 176, 192, 208, 224, 240, 256]

def get_islands(mask, y_start, x_left, x_right, height=13):
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

ref_glyphs = {}
for line_text, y in zip(LINES, Y_STARTS):
    islands = get_islands(ref_mask, y, 445, 625)
    non_space = [c for c in line_text if c != ' ']
    if len(islands) == len(non_space):
        for ch, (s, e) in zip(non_space, islands):
            bm = ref_mask[y:y+13, s:e+1]
            if ch not in ref_glyphs:
                ref_glyphs[ch] = bm

print(f"Reference glyphs: {len(ref_glyphs)}")

def load_fon_glyph(face, ch):
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bm = face.glyph.bitmap
    bitmap = np.zeros((bm.rows, bm.width), dtype=bool)
    for by in range(bm.rows):
        for bx in range(bm.width):
            if bm.buffer[by * bm.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                bitmap[by, bx] = True
    return bitmap, face.glyph.bitmap_left, face.glyph.bitmap_top, face.glyph.advance.x // 64

def compare_bitmaps(a, b):
    h = max(a.shape[0], b.shape[0])
    w = max(a.shape[1], b.shape[1])
    pa = np.zeros((h, w), dtype=bool)
    pb = np.zeros((h, w), dtype=bool)
    pa[:a.shape[0], :a.shape[1]] = a
    pb[:b.shape[0], :b.shape[1]] = b
    return np.array_equal(pa, pb), int(np.sum(pa != pb))

# Enumerate faces/sizes in MS font
print("\n=== Microsoft sserife.fon (96 DPI) ===")
ms = freetype.Face(MS_FON, 0)
print(f"  Num faces: {ms.num_faces}")
for fi in range(ms.num_faces):
    f = freetype.Face(MS_FON, fi)
    sizes = [(s.height, s.y_ppem // 64) for s in f.available_sizes]
    print(f"  Face {fi}: sizes={sizes}, family='{f.family_name}'")

# Compare each face/size
print("\n=== Comparison against reference ===")
best_face = -1
best_matches = 0
best_diff = 99999

for fi in range(ms.num_faces):
    f = freetype.Face(MS_FON, fi)
    for si, sz in enumerate(f.available_sizes):
        f.select_size(si)
        f.set_charmap(f.charmaps[0])

        matches = 0
        total_diff = 0
        for ch in sorted(ref_glyphs.keys()):
            bm, bx, by, adv = load_fon_glyph(f, ch)
            exact, diff = compare_bitmaps(ref_glyphs[ch], bm)
            if exact:
                matches += 1
            total_diff += diff

        print(f"  Face {fi}, h={sz.height}px ppem={sz.y_ppem//64}: "
              f"{matches}/{len(ref_glyphs)} exact, total_diff={total_diff}")

        if matches > best_matches or (matches == best_matches and total_diff < best_diff):
            best_face = fi
            best_matches = matches
            best_diff = total_diff
            best_si = si

# Detailed comparison for best face
print(f"\n=== Best: Face {best_face} ({best_matches} exact) ===")
f = freetype.Face(MS_FON, best_face)
f.select_size(best_si)
f.set_charmap(f.charmaps[0])

print(f"\nChar  REF_px  MS_px   Wine_px  ref_w ms_w  match")
print("-" * 60)

wine = freetype.Face(WINE_FON, 0)
wine.select_size(0)
wine.set_charmap(wine.charmaps[0])

for ch in sorted(ref_glyphs.keys()):
    ref_bm = ref_glyphs[ch]
    ms_bm, ms_bx, ms_by, ms_adv = load_fon_glyph(f, ch)
    w_bm, w_bx, w_by, w_adv = load_fon_glyph(wine, ch)

    exact, diff = compare_bitmaps(ref_bm, ms_bm)
    ref_px = int(np.sum(ref_bm))
    ms_px = int(np.sum(ms_bm))
    w_px = int(np.sum(w_bm))

    tag = "EXACT" if exact else f"diff={diff}"
    print(f"  {ch}    {ref_px:3d}    {ms_px:3d}     {w_px:3d}     "
          f"{ref_bm.shape[1]:2d}   {ms_bm.shape[1]:2d}    {tag}")

# Also show advance widths
print(f"\n=== Advance widths ===")
print(f"Char  MS_adv  Wine_adv")
for code in range(32, 127):
    ch = chr(code)
    ms_bm, ms_bx, ms_by, ms_adv = load_fon_glyph(f, ch)
    w_bm, w_bx, w_by, w_adv = load_fon_glyph(wine, ch)
    if ms_adv != w_adv:
        print(f"  {code:3d} '{ch}': ms={ms_adv}  wine={w_adv}")
