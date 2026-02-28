# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py"]
# ///
"""Debug charmap issues with sserife.fon — try direct glyph access."""
import freetype

fon_path = "assets/fonts/sserife.fon"
face = freetype.Face(fon_path, 0)  # Face 0 = 13px
face.select_size(0)

print(f"Num glyphs: {face.num_glyphs}")
print(f"Num charmaps: {face.num_charmaps}")

# Set charmap index 0 explicitly
face.set_charmap(face.charmaps[0])

# Try iterating all char codes
print("\nAll char->glyph mappings via get_first_char/get_next_char:")
count = 0
charcode, glyph_index = face.get_first_char()
while glyph_index != 0 and count < 300:
    face.load_glyph(glyph_index, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    adv = face.glyph.advance.x // 64
    bw = face.glyph.bitmap.width
    ch = chr(charcode) if 32 <= charcode < 127 else f"\\x{charcode:02x}"
    if 32 <= charcode < 200:
        print(f"  code={charcode:3d} ('{ch}') glyph={glyph_index:3d} advance={adv:2d} bitmap_w={bw:2d}")
    charcode, glyph_index = face.get_next_char(charcode, glyph_index)
    count += 1

print(f"\nTotal chars: {count}")

# Also try: maybe the font uses Windows-1252 offset (0x20 = space = glyph 1)
# So charcode 0x20 -> glyph 1, 0x21 -> glyph 2, etc.
print("\n\nDirect glyph index access (glyph 1..95 = ASCII 32..126?):")
for gi in range(1, 96):
    face.load_glyph(gi, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    adv = face.glyph.advance.x // 64
    bw = face.glyph.bitmap.width
    bh = face.glyph.bitmap.rows
    ch = chr(gi + 31) if 32 <= gi + 31 < 127 else '?'
    print(f"  glyph={gi:3d} -> '{ch}' advance={adv:2d} bitmap={bw:2d}x{bh:2d}")
