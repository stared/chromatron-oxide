# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow", "numpy"]
# ///
"""Check if the reference image normalization introduces scaling."""
import numpy as np
from PIL import Image

ref_path = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
img = Image.open(ref_path).convert("RGB")
arr = np.array(img)
print(f"Raw reference: {arr.shape[1]}x{arr.shape[0]}")

# Find gray area
gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
rows = np.any(gray, axis=1)
cols = np.any(gray, axis=0)
y1 = int(np.argmax(rows))
y2 = int(arr.shape[0] - np.argmax(rows[::-1]))
x1 = int(np.argmax(cols))
x2 = int(arr.shape[1] - np.argmax(cols[::-1]))
cw = x2 - x1
ch = y2 - y1

print(f"Gray area: ({x1},{y1}) to ({x2},{y2}) = {cw}x{ch}")
print(f"Game target: 640x480")
print(f"Scale factor: {cw/640:.4f}x{ch/480:.4f}")

# So the cropped gray area is NOT 640x480. It gets placed without scaling
# onto a 640x480 canvas. This means coordinates in the normalized image
# are 1:1 with the cropped content.

# But if the gray area is only ~632x~450, the content starts at (x1,y1) in the original
# and gets placed at (0,0) in the 640x480 canvas.
# So pixel (0,0) in the normalized image = pixel (x1,y1) in the raw reference.

# In the raw reference:
# "freeware" should be at (x1 + 0, y1 + 450) in raw coords
# Let's check

print(f"\nExpected 'freeware' in raw: ({x1}, {y1 + 450})")
is_text = np.all(arr < 50, axis=2)
# Find first black pixel near "freeware" position
for dy in range(-5, 10):
    y = y1 + 450 + dy
    if y < 0 or y >= arr.shape[0]:
        continue
    for x in range(x1, x1 + 80):
        if x < arr.shape[1] and is_text[y, x]:
            print(f"  Black pixel at raw ({x},{y}) = normalized ({x-x1},{y-y1})")
            break
    else:
        continue
    break

# Let's look at the grid cell size to calibrate
# In the game, grid cells are 24x24 pixels, starting at (48,18) top-left corner
# So grid line at x=48, 72, 96, ... and y=18, 42, 66, ...
# Let's check the actual grid positions in the reference

# The grid background tiles have a specific dark edge. Let's look for the
# leftmost column of the grid.
print("\nGrid left edge detection (looking for dark vertical line):")
for x in range(x1 + 40, x1 + 60):
    if x < arr.shape[1]:
        col = arr[y1 + 18: y1 + 400, x, :]
        # Check if this column has consistently dark pixels (grid edge)
        dark_count = np.sum(np.all(col < 100, axis=1))
        if dark_count > 100:
            print(f"  x={x} (normalized {x-x1}): {dark_count} dark pixels")

# Measure distance between grid lines to verify 24px cell size
print("\nLooking for grid cell boundaries (horizontal lines at known y positions):")
for test_y in [y1+18, y1+42, y1+66, y1+90]:
    if test_y < arr.shape[0]:
        row = arr[test_y, x1+48:x1+432, :]
        # Count dark pixels (grid line)
        dark = np.all(row < 100, axis=1)
        dark_count = int(dark.sum())
        first = int(np.argmax(dark)) if dark.any() else -1
        print(f"  y={test_y} (normalized {test_y-y1}): {dark_count} dark pixels, first at x={first+48}")

# Let's now measure the actual pixel distance for known game elements
# Grid goes from x=48 to x=48+16*24=432 (16 columns)
# That's 384 pixels = 16*24

# Let's measure the actual grid width in the raw reference
print("\n\nMeasuring actual grid pixel width:")
# Look at a row in the middle of the grid
grid_row_y = y1 + 200
if grid_row_y < arr.shape[0]:
    row = arr[grid_row_y, :, :]
    # Find first and last dark pixel (grid area)
    is_dark = np.all(row < 120, axis=1)
    if is_dark.any():
        dark_positions = np.where(is_dark)[0]
        # Filter to grid area (roughly x1+30 to x1+450)
        grid_dark = dark_positions[(dark_positions > x1+30) & (dark_positions < x1+450)]
        if len(grid_dark) > 0:
            grid_left = int(grid_dark[0])
            grid_right = int(grid_dark[-1])
            grid_width = grid_right - grid_left + 1
            print(f"  Grid extends from x={grid_left} to x={grid_right} (width={grid_width}px)")
            print(f"  Expected: 384px (16*24). Actual scale: {grid_width/384:.4f}")
