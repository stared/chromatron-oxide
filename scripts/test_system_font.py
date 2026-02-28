# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "Pillow", "numpy"]
# ///
"""Test Windows System font (vgasys.fon) vs reference glyphs."""
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

def compare(a, b):
    h, w = max(a.shape[0], b.shape[0]), max(a.shape[1], b.shape[1])
    pa, pb = np.zeros((h, w), dtype=bool), np.zeros((h, w), dtype=bool)
    pa[:a.shape[0], :a.shape[1]] = a
    pb[:b.shape[0], :b.shape[1]] = b
    return np.array_equal(pa, pb), int(np.sum(pa != pb))

def show(name, bm):
    print(f"  {name} ({bm.shape[1]}x{bm.shape[0]}, {int(np.sum(bm))}px):")
    for r in range(bm.shape[0]):
        print(f"    {''.join('#' if bm[r,c] else '.' for c in range(bm.shape[1]))}")

# Load System font
print("\n=== System font (vgasys.fon) ===")
f = freetype.Face(SYS_FON, 0)
print(f"Num faces: {f.num_faces}")
for fi in range(f.num_faces):
    face = freetype.Face(SYS_FON, fi)
    sizes = [(s.height, s.y_ppem//64) for s in face.available_sizes]
    print(f"  Face {fi}: sizes={sizes}, family='{face.family_name}', style='{face.style_name}'")

# Test each face
for fi in range(f.num_faces):
    face = freetype.Face(SYS_FON, fi)
    for si, sz in enumerate(face.available_sizes):
        face.select_size(si)
        face.set_charmap(face.charmaps[0])

        matches = 0
        total_diff = 0
        for ch in sorted(ref_glyphs.keys()):
            bm, bx, by, adv = load_glyph(face, ch)
            ex, diff = compare(ref_glyphs[ch], bm)
            if ex: matches += 1
            total_diff += diff

        print(f"\n  Face {fi}, h={sz.height}px: {matches}/{len(ref_glyphs)} exact, total_diff={total_diff}")

        # Show details
        print(f"  Char  REF   sys   ref_w sys_w  adv  match")
        print(f"  " + "-" * 55)
        for ch in sorted(ref_glyphs.keys()):
            ref_bm = ref_glyphs[ch]
            sys_bm, bx, by, adv = load_glyph(face, ch)
            ex, diff = compare(ref_bm, sys_bm)
            tag = "EXACT!" if ex else f"diff={diff}"
            print(f"    {ch}  {int(np.sum(ref_bm)):3d}   {int(np.sum(sys_bm)):3d}   "
                  f"{ref_bm.shape[1]:2d}    {sys_bm.shape[1]:2d}     {adv:2d}   {tag}")

        # Visual comparison
        for ch in ['e', 'a', 'R']:
            if ch in ref_glyphs:
                print(f"\n  === '{ch}' ===")
                show("Reference", ref_glyphs[ch])
                sys_bm, _, _, _ = load_glyph(face, ch)
                show("System", sys_bm)
