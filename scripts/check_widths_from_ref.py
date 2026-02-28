# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow"]
# ///
"""
Measure character widths from the reference screenshot by analyzing
the known text "freeware" and "silverspaceship.com" at the bottom.
"""
from PIL import Image
import sys

ref_path = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
img = Image.open(ref_path)
pixels = img.load()
w, h = img.size

# The reference has a window border. Let's figure out the exact offset.
# In our 640x480 framebuffer, "freeware" is at (0, 450).
# In the reference, the window content area is offset by the border.

# Find the exact extent of "freeware" text
# Look for black pixels in the bottom-left area
print("Scanning for 'freeware' text:")
for y in range(450, min(480, h)):
    row_pixels = []
    for x in range(0, 200):
        r, g, b = pixels[x, y][:3]
        if r < 50 and g < 50 and b < 50:
            row_pixels.append(x)
    if row_pixels:
        print(f"  y={y}: x={min(row_pixels)}-{max(row_pixels)} ({len(row_pixels)} black pixels)")

print("\nScanning for 'silverspaceship.com' text:")
for y in range(450, min(480, h)):
    row_pixels = []
    for x in range(450, min(640, w)):
        r, g, b = pixels[x, y][:3]
        if r < 50 and g < 50 and b < 50:
            row_pixels.append(x)
    if row_pixels:
        print(f"  y={y}: x={min(row_pixels)}-{max(row_pixels)} ({len(row_pixels)} black pixels)")

# Now extract the instruction text area more precisely
# Find each line's text content and horizontal extent
print("\n\nInstruction text lines (detailed):")
text_area_left = 440
text_area_right = min(625, w)

# First, find all rows with text
text_rows = []
for y in range(140, 310):
    has_black = False
    for x in range(text_area_left, text_area_right):
        if x < w:
            r, g, b = pixels[x, y][:3]
            if r < 50 and g < 50 and b < 50:
                has_black = True
                break
    text_rows.append((y, has_black))

# Group into text lines (consecutive rows with black pixels)
lines = []
line_start = None
for y, has_black in text_rows:
    if has_black and line_start is None:
        line_start = y
    elif not has_black and line_start is not None:
        lines.append((line_start, y))
        line_start = None
if line_start is not None:
    lines.append((line_start, text_rows[-1][0] + 1))

# For each line, find the horizontal extent
for i, (y1, y2) in enumerate(lines):
    min_x = w
    max_x = 0
    for y in range(y1, y2):
        for x in range(text_area_left, text_area_right):
            if x < w:
                r, g, b = pixels[x, y][:3]
                if r < 50 and g < 50 and b < 50:
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)
    text_width = max_x - min_x + 1
    print(f"  Line {i+1}: y={y1:3d}-{y2:3d} ({y2-y1:2d}px), x={min_x}-{max_x} ({text_width:3d}px text width)")

# Now figure out the window border offset
# "freeware" should start at x=0 in framebuffer coords
# Let's find where it actually starts
print("\n\nLooking for exact border offset:")
for y in range(455, 475):
    for x in range(0, 30):
        if x < w:
            r, g, b = pixels[x, y][:3]
            if r < 50 and g < 50 and b < 50:
                print(f"  First black pixel at ({x}, {y})")
                break
    else:
        continue
    break
