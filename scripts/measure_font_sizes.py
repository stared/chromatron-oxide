# /// script
# requires-python = ">=3.13"
# dependencies = ["pillow"]
# ///
"""Measure font metrics at various sizes to find the best match for the original.

The original Win32 SYSTEM_FONT (MS Sans Serif 8pt) at 96 DPI has:
- Line height: 13px (11px ascent + 2px descent/leading)
- Approximate widths: 'M' ~9px, 'i' ~2px, space ~3px
- The instruction text "Drag the REFLECTOR in" fits in a ~190px wide rect
"""
import sys
from PIL import ImageFont

font_path = sys.argv[1] if len(sys.argv) > 1 else "assets/fonts/W95font.otf"
print(f"Font: {font_path}")
print(f"{'Size':>4}  {'Height':>6}  {'Ascent':>6}  {'Descent':>7}  {'M':>4}  {'i':>4}  {'sp':>4}  {'Drag the REFLECTOR in':>22}")
print("-" * 80)

for size in range(7, 16):
    try:
        font = ImageFont.truetype(font_path, size)
        ascent, descent = font.getmetrics()
        height = ascent + descent
        m_w = font.getlength("M")
        i_w = font.getlength("i")
        sp_w = font.getlength(" ")
        test_w = font.getlength("Drag the REFLECTOR in")
        print(f"{size:>4}  {height:>6}  {ascent:>6}  {descent:>7}  {m_w:>4.0f}  {i_w:>4.0f}  {sp_w:>4.0f}  {test_w:>22.0f}")
    except Exception as e:
        print(f"{size:>4}  ERROR: {e}")

# Also measure ms_sans_serif.ttf and Geneva for comparison
print()
for other_font in ["assets/fonts/ms_sans_serif.ttf", "assets/fonts/Geneva.ttf"]:
    try:
        print(f"\nFont: {other_font}")
        print(f"{'Size':>4}  {'Height':>6}  {'Ascent':>6}  {'Descent':>7}  {'M':>4}  {'i':>4}  {'sp':>4}  {'Drag the REFLECTOR in':>22}")
        print("-" * 80)
        for size in range(7, 16):
            font = ImageFont.truetype(other_font, size)
            ascent, descent = font.getmetrics()
            height = ascent + descent
            m_w = font.getlength("M")
            i_w = font.getlength("i")
            sp_w = font.getlength(" ")
            test_w = font.getlength("Drag the REFLECTOR in")
            print(f"{size:>4}  {height:>6}  {ascent:>6}  {descent:>7}  {m_w:>4.0f}  {i_w:>4.0f}  {sp_w:>4.0f}  {test_w:>22.0f}")
    except Exception as e:
        print(f"  ERROR: {e}")
