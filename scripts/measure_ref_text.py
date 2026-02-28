# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow"]
# ///
"""Measure actual text pixel widths from reference screenshot."""
from PIL import Image

ref_path = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
img = Image.open(ref_path)
pixels = img.load()
w, h = img.size

print(f"Reference image: {w}x{h}")

# The instruction text area: left=450, top=125, right=620, bottom=475
# But the reference image may be slightly offset. Let's scan for text.
# Text is black (0,0,0) on gray (164,164,164) background.

# Scan the text area for black pixels row by row
text_left = 450
text_right = 620
text_top = 125
text_bottom = 300  # enough for the instruction text

# Adjust for reference image offset (it may be slightly different from our 640x480)
# The reference is 638x508, so there might be a border
# Let's find where the grid starts to determine offset
# Grid starts at (60-12, 30-12) = (48, 18) in our framebuffer

# Find the text lines by scanning for rows with black pixels
print("\nScanning for text rows in instruction area:")
text_rows = []
in_text = False
text_start = 0
for y in range(text_top, text_bottom):
    has_black = False
    for x in range(text_left, min(text_right, w)):
        r, g, b = pixels[x, y][:3]
        if r < 50 and g < 50 and b < 50:
            has_black = True
            break
    if has_black and not in_text:
        in_text = True
        text_start = y
    elif not has_black and in_text:
        in_text = False
        text_rows.append((text_start, y))
if in_text:
    text_rows.append((text_start, text_bottom))

for i, (y1, y2) in enumerate(text_rows):
    # Find leftmost and rightmost black pixel in this text band
    min_x = w
    max_x = 0
    for y in range(y1, y2):
        for x in range(text_left, min(text_right, w)):
            r, g, b = pixels[x, y][:3]
            if r < 50 and g < 50 and b < 50:
                min_x = min(min_x, x)
                max_x = max(max_x, x)
    text_w = max_x - min_x + 1 if max_x >= min_x else 0
    print(f"  Line {i+1}: y={y1}-{y2} ({y2-y1}px tall), x={min_x}-{max_x} (width={text_w}px)")

# Also measure the bottom text lines
print("\nScanning bottom text:")
for y in range(440, min(480, h)):
    has_black = False
    for x in range(0, min(640, w)):
        r, g, b = pixels[x, y][:3]
        if r < 50 and g < 50 and b < 50:
            has_black = True
            break
    if has_black and not in_text:
        in_text = True
        text_start = y
    elif not has_black and in_text:
        in_text = False
        # Find extent
        min_x = w
        max_x = 0
        for yy in range(text_start, y):
            for x in range(0, min(640, w)):
                r, g, b = pixels[x, yy][:3]
                if r < 50 and g < 50 and b < 50:
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)
        print(f"  y={text_start}-{y}: x={min_x}-{max_x}")
