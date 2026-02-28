# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py"]
# ///
"""Test sserife.fon loading with proper bitmap font handling."""
import freetype

fon_path = "assets/fonts/sserife.fon"

# Face 0 has height=13 which is what we want
for face_idx in range(3):
    face = freetype.Face(fon_path, face_idx)
    print(f"\n=== Face {face_idx} ===")
    print(f"Family: {face.family_name}, Style: {face.style_name}")
    print(f"Fixed sizes: {face.num_fixed_sizes}")
    if face.has_fixed_sizes:
        for i, size in enumerate(face.available_sizes):
            print(f"  Strike {i}: height={size.height}, y_ppem={size.y_ppem/64:.1f}")

    # Select the bitmap strike properly
    face.select_size(0)
    print(f"Height after select_size(0): {face.size.height/64:.1f}")
    print(f"Ascender: {face.size.ascender/64:.1f}, Descender: {face.size.descender/64:.1f}")

    # Use FT_LOAD_TARGET_MONO for bitmap fonts
    test_chars = "MiWwabcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    widths = {}
    for ch in test_chars:
        face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
        adv = face.glyph.advance.x // 64
        bw = face.glyph.bitmap.width
        widths[ch] = (adv, bw)

    print(f"\nChar widths (advance, bitmap_width):")
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz 0123456789":
        if ch in widths:
            adv, bw = widths[ch]
            print(f"  '{ch}': advance={adv}, bitmap_w={bw}")

    # Measure "Drag the REFLECTOR in"
    test = "Drag the REFLECTOR in"
    total = sum(widths.get(c, (0,0))[0] for c in test)
    print(f"\n  '{test}' total advance = {total}px")
