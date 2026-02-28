# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py"]
# ///
"""Measure text widths from sserife.fon to debug word-wrap differences."""
import freetype

FON_PATH = "assets/fonts/sserife.fon"
face = freetype.Face(FON_PATH, 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])

def measure_text(text):
    """Sum of advance widths for a string."""
    total = 0
    for ch in text:
        face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
        total += face.glyph.advance.x >> 6
    return total

# Level 1 instruction text
text = "Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel."

rect_width = 170  # 620 - 450

# Simulate word wrapping like DrawTextA (DT_WORDBREAK)
words = text.split()
line = ""
lines = []
for word in words:
    test = f"{line} {word}" if line else word
    w = measure_text(test)
    if line and w > rect_width:
        lines.append((line, measure_text(line)))
        line = word
    else:
        line = test
if line:
    lines.append((line, measure_text(line)))

print(f"Rect width: {rect_width}")
print(f"Lines ({len(lines)}):")
for i, (line, w) in enumerate(lines):
    print(f"  {i+1}. [{w:3d}px] '{line}'")

# Also show individual key word widths
print("\nKey word widths:")
for word in ["Drag", "the", "REFLECTOR", "in", "the", "toolbox", "above", "onto"]:
    print(f"  '{word}' = {measure_text(word)}px")

# Also check: maybe the original uses a different measurement
# In Win32 DrawTextA, text width comes from GetTextExtentPoint32
# which includes the overhang (tmOverhang) for italic fonts
# For bitmap fonts, tmOverhang = 0, so it's just sum of character widths
print(f"\n'Drag the REFLECTOR in' = {measure_text('Drag the REFLECTOR in')}px")
print(f"'Drag the REFLECTOR in the' = {measure_text('Drag the REFLECTOR in the')}px")
print(f"'the toolbox above onto' = {measure_text('the toolbox above onto')}px")
print(f"'the toolbox above onto the' = {measure_text('the toolbox above onto the')}px")

# Check space width
print(f"\nspace advance = {measure_text(' ')}px")
