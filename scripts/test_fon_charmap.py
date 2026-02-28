# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py"]
# ///
"""Debug charmap and encoding issues with sserife.fon."""
import freetype

fon_path = "assets/fonts/sserife.fon"
face = freetype.Face(fon_path, 0)  # Face 0 = 13px
face.select_size(0)

print(f"Num charmaps: {face.num_charmaps}")
for i in range(face.num_charmaps):
    cm = face.charmaps[i]
    print(f"  Charmap {i}: platform={cm.platform_id}, encoding={cm.encoding_id}, "
          f"encoding_name={cm.encoding_name}")

# Try setting charmap explicitly
print(f"\nCurrent charmap: encoding_name={face.charmap.encoding_name if face.charmap else 'None'}")

# Try loading by char code directly
print("\nLoading by char_index (glyph index):")
for code in [32, 33, 65, 66, 67, 77, 105]:  # space ! A B C M i
    idx = face.get_char_index(code)
    face.load_glyph(idx, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    adv = face.glyph.advance.x // 64
    bw = face.glyph.bitmap.width
    bh = face.glyph.bitmap.rows
    print(f"  char_code={code} ('{chr(code)}') -> glyph_idx={idx}, advance={adv}, bitmap={bw}x{bh}")

# Also try iterating through all glyphs
print("\nAll char->glyph mappings:")
charcode, glyph_index = face.get_first_char()
while glyph_index != 0:
    face.load_glyph(glyph_index, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    adv = face.glyph.advance.x // 64
    bw = face.glyph.bitmap.width
    ch = chr(charcode) if 32 <= charcode < 127 else f"\\x{charcode:02x}"
    print(f"  code={charcode:3d} ('{ch}') glyph={glyph_index:3d} advance={adv} bitmap_w={bw}")
    charcode, glyph_index = face.get_next_char(charcode, glyph_index)
