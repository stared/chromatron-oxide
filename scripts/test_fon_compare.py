# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""Compare Wine sserife.fon vs original Microsoft sseriff.fon vs reference glyphs."""
import numpy as np
from PIL import Image
import freetype

WINE_FON = "assets/fonts/sserife.fon"
ORIG_FON = "assets/fonts/sseriff.fon"
REF_PATH = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"

FONT_HEIGHT = 13

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

# Extract reference glyphs from level 1
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

print(f"Reference glyphs extracted: {len(ref_glyphs)}")

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

# Load fonts
print("\n=== Wine sserife.fon (96 DPI) ===")
wine = freetype.Face(WINE_FON, 0)
wine.select_size(0)
wine.set_charmap(wine.charmaps[0])

print(f"  Num faces: {wine.num_faces}")
print(f"  Available sizes: {[s.height for s in wine.available_sizes]}")

print("\n=== Original Microsoft sseriff.fon (120 DPI) ===")
orig = freetype.Face(ORIG_FON, 0)
print(f"  Num faces: {orig.num_faces}")

# Try each face index in the .fon file
for face_idx in range(orig.num_faces):
    f = freetype.Face(ORIG_FON, face_idx)
    sizes = [(s.height, s.width, s.x_ppem, s.y_ppem) for s in f.available_sizes]
    print(f"  Face {face_idx}: sizes={sizes}, family='{f.family_name}', style='{f.style_name}'")

# Now try each face/size combo and compare against reference
print("\n=== Comparing each face/size against reference ===")
for face_idx in range(orig.num_faces):
    f = freetype.Face(ORIG_FON, face_idx)
    for size_idx, sz in enumerate(f.available_sizes):
        f.select_size(size_idx)
        f.set_charmap(f.charmaps[0])

        matches = 0
        total_diff = 0
        total_compared = 0

        for ch in sorted(ref_glyphs.keys()):
            bm, bx, by, adv = load_fon_glyph(f, ch)
            ref_bm = ref_glyphs[ch]
            exact, diff = compare_bitmaps(ref_bm, bm)
            if exact:
                matches += 1
            total_diff += diff
            total_compared += 1

        print(f"  Face {face_idx}, size {sz.height}px (y_ppem={sz.y_ppem//64}): "
              f"{matches}/{total_compared} exact, total_diff={total_diff} px")

        # Show per-char details for best candidates
        if matches > 5:
            print(f"    Per-char details:")
            for ch in sorted(ref_glyphs.keys()):
                bm, bx, by, adv = load_fon_glyph(f, ch)
                ref_bm = ref_glyphs[ch]
                exact, diff = compare_bitmaps(ref_bm, bm)
                ref_px = int(np.sum(ref_bm))
                fon_px = int(np.sum(bm))
                tag = "EXACT" if exact else f"diff={diff}"
                print(f"      '{ch}': ref={ref_px:3d}px fon={fon_px:3d}px "
                      f"ref_w={ref_bm.shape[1]} fon_w={bm.shape[1]} {tag}")
