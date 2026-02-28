# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py"]
# ///
"""Test if FreeType can load sserife.fon and inspect its properties."""
import freetype

fon_path = "assets/fonts/sserife.fon"
print(f"Loading: {fon_path}")

face = freetype.Face(fon_path)
print(f"Family name: {face.family_name}")
print(f"Style name: {face.style_name}")
print(f"Num faces: {face.num_faces}")
print(f"Num glyphs: {face.num_glyphs}")
print(f"Num fixed sizes: {face.num_fixed_sizes}")
print(f"Is scalable: {face.is_scalable}")
print(f"Has fixed sizes: {face.has_fixed_sizes}")

if face.has_fixed_sizes:
    print("\nAvailable bitmap strikes:")
    for i, size in enumerate(face.available_sizes):
        print(f"  Strike {i}: width={size.width}, height={size.height}, "
              f"size={size.size/64:.1f}pt, x_ppem={size.x_ppem/64:.1f}, y_ppem={size.y_ppem/64:.1f}")

# Try each face index
for face_idx in range(face.num_faces):
    f = freetype.Face(fon_path, face_idx)
    print(f"\nFace {face_idx}: family={f.family_name}, style={f.style_name}")
    if f.has_fixed_sizes:
        for i, size in enumerate(f.available_sizes):
            print(f"  Strike {i}: height={size.height}, y_ppem={size.y_ppem/64:.1f}")
    # Try setting pixel size and measuring some chars
    try:
        if f.has_fixed_sizes:
            f.select_size(0)
        else:
            f.set_pixel_sizes(0, 13)

        test_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "
        widths = {}
        for ch in test_chars:
            f.load_char(ch, freetype.FT_LOAD_DEFAULT)
            widths[ch] = f.glyph.advance.x // 64

        print(f"  Char widths: M={widths.get('M')}, i={widths.get('i')}, "
              f"space={widths.get(' ')}, a={widths.get('a')}, W={widths.get('W')}")

        # Measure key text
        test_text = "Drag the REFLECTOR in"
        total_w = sum(widths.get(c, 0) for c in test_text)
        print(f"  '{test_text}' width = {total_w}px")

    except Exception as e:
        print(f"  Error measuring: {e}")
