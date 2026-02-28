# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow"]
# ///
"""Analyze the reference screenshot to understand coordinate mapping."""
from PIL import Image

ref_path = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
img = Image.open(ref_path)
pixels = img.load()
w, h = img.size

print(f"Reference image: {w}x{h}")

# The game renders at 640x480. The screenshot is 638x508.
# Difference: 638-640=-2 in width, 508-480=+28 in height
# This suggests the screenshot includes the window title bar (about 28px)
# and has a 1px border on each side (hence -2px width)

# Find the game's gray background (0xA4A4A4 = 164,164,164)
# Scan to find the content area boundaries
# Look for the transition from non-gray to gray at the top

# Find top-left corner of the game content
for y in range(0, 50):
    r, g, b = pixels[5, y][:3]
    if abs(r-164) < 5 and abs(g-164) < 5 and abs(b-164) < 5:
        print(f"Gray background starts at y={y} (x=5)")
        break

# Find left border
for x in range(0, 20):
    r, g, b = pixels[x, 40][:3]
    if abs(r-164) < 5 and abs(g-164) < 5 and abs(b-164) < 5:
        print(f"Gray background starts at x={x} (y=40)")
        break

# Find the grid's top-left corner (first non-gray pixel in grid area)
# Grid cells start at pixel (48, 18) in framebuffer (60-12, 30-12)
# Look for the distinctive grid color
print("\nLooking for grid boundaries:")
# The grid background tile has palette color that's slightly different from the bg gray
# Let's find horizontal lines where the grid begins
for y in range(10, 50):
    # Check if there's a grid cell at the expected position
    for x in range(40, 70):
        if x < w and y < h:
            r, g, b = pixels[x, y][:3]
            # Grid cell colors are darker than the bg gray
            if abs(r-164) > 10 or abs(g-164) > 10 or abs(b-164) > 10:
                # Found non-background pixel
                if r < 164:  # darker = grid
                    print(f"  Grid pixel found at ({x}, {y}): RGB({r},{g},{b})")
                    break
    else:
        continue
    break

# Also check bottom-right extent
print("\nBottom-right content:")
for y in range(h-5, h-1):
    for x in range(w-5, w-1):
        r, g, b = pixels[x, y][:3]
        print(f"  ({x},{y}): RGB({r},{g},{b})")

# Let's look at the "freeware" text position more carefully
# In our framebuffer, "freeware" is drawn at (0, 450)
# With an offset, it should be at (offset_x, offset_y + 450)
print("\nLooking for 'freeware' - scanning rows y=455-475, x=0-70:")
for y in range(455, 475):
    first_black = None
    last_black = None
    for x in range(0, 70):
        if x < w and y < h:
            r, g, b = pixels[x, y][:3]
            if r < 50 and g < 50 and b < 50:
                if first_black is None:
                    first_black = x
                last_black = x
    if first_black is not None:
        print(f"  y={y}: first_black={first_black}, last_black={last_black}")

# And "silverspaceship.com" at (470, 450)
print("\nLooking for 'silverspaceship.com' - scanning y=455-475, x=460-640:")
for y in range(455, 475):
    first_black = None
    last_black = None
    for x in range(460, min(640, w)):
        if x < w and y < h:
            r, g, b = pixels[x, y][:3]
            if r < 50 and g < 50 and b < 50:
                if first_black is None:
                    first_black = x
                last_black = x
    if first_black is not None:
        print(f"  y={y}: first_black={first_black}, last_black={last_black}")
