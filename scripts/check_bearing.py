# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "numpy"]
# ///
"""Check freetype bitmap_left for vgasys.fon and whether bitmaps have blank first columns."""
import freetype
import numpy as np

SYS_FON = "assets/fonts/vgasys.fon"

face = freetype.Face(SYS_FON, 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])

print("char  bm_left  bm_width  first_col_has_content  last_col_has_content")
for code in range(32, 127):
    ch = chr(code)
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    bm = face.glyph.bitmap
    bm_left = face.glyph.bitmap_left

    # Extract bitmap
    raw = np.zeros((bm.rows, bm.width), dtype=bool)
    for by in range(bm.rows):
        for bx in range(bm.width):
            if bm.buffer[by * bm.pitch + (bx >> 3)] & (1 << (7 - (bx & 7))):
                raw[by, bx] = True

    first_col = raw[:, 0].any() if bm.width > 0 else False
    last_col = raw[:, -1].any() if bm.width > 0 else False

    if code >= 33:  # skip space
        print(f"  {ch}    {bm_left:7d}  {bm.width:8d}  {str(first_col):21s}  {str(last_col)}")

# Key question: does freetype's bitmap_left already account for the offset?
# If bm_left=1 and bitmap starts with content, we should use bm_left as bearing_x
# If bm_left=0 and bitmap has blank first column, bearing_x should be 0
print("\n=== Characters where bitmap_left != 0 ===")
for code in range(33, 127):
    ch = chr(code)
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    if face.glyph.bitmap_left != 0:
        print(f"  {ch}: bitmap_left={face.glyph.bitmap_left}")
