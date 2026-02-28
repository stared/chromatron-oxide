# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow", "numpy"]
# ///
"""Find exact alignment between our 640x480 framebuffer and the 638x508 reference screenshot."""
import numpy as np
from PIL import Image

REF = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
OURS = "screenshots/framebuffer_1771431637.png"

ref = np.array(Image.open(REF).convert("RGB"))
ours = np.array(Image.open(OURS).convert("RGB"))

print(f"Reference: {ref.shape[1]}x{ref.shape[0]}")
print(f"Ours:      {ours.shape[1]}x{ours.shape[0]}")

# Strategy: use the grid lines as alignment anchor
# The grid has dark gray lines on the gray background
# Grid starts at pixel (20,30) in our framebuffer, 25px cells, 16x14 grid

# Find a distinctive small patch in our framebuffer
# Use the grid corner area (top-left of grid)
# The grid has specific pixel patterns that should be findable

# Let's use the instruction text since we know its reference position
# Our first text pixel: y=128
# Reference first text pixel: y=157
# dy = 29

# For horizontal, let's check where black pixels start on the first text line
# In ours, first black pixel on y=128 should be at x=450+bearing_x
# In reference, first black pixel on y=157 should be at x_ref

print("\n=== First black pixels on text lines ===")
print("Checking our line 1 (y=128):")
ours_row = np.all(ours[128, :] == [0, 0, 0], axis=1)
if np.any(ours_row):
    first_x = np.argmax(ours_row)
    print(f"  First black at x={first_x}")

print("Checking ref line 1 (y=157):")
ref_row = np.all(ref[157, :] == [0, 0, 0], axis=1)
if np.any(ref_row):
    first_x = np.argmax(ref_row)
    print(f"  First black at x={first_x}")

# Let's also check grid lines
# In our framebuffer, the grid outline starts at x=20, y=30
# It's dark gray (128,128,128) on gray (164,164,164) background
print("\n=== Grid alignment ===")
# Look for the top grid line (y=30 in ours)
# Check ours first
print("Our grid top line (y=30, x=15-25):")
for x in range(15, 30):
    c = tuple(ours[30, x].tolist())
    if c != (164, 164, 164):
        print(f"  x={x}: {c}")

# Now search reference for same pattern
print("\nSearching reference for grid top line around y=55-65:")
for y in range(55, 70):
    for x in range(15, 30):
        c = tuple(ref[y, x].tolist())
        if c == (128, 128, 128):
            print(f"  ref y={y}, x={x}: {c}")
            break

# Template matching: take a 20x20 patch from ours and search in ref
print("\n=== Template matching ===")
# Use a patch from the grid corner
patch = ours[28:38, 18:28]  # 10x10 patch at grid corner
print(f"Patch from ours[28:38, 18:28]:")

best_score = 0
best_pos = None
for dy in range(20, 40):
    for dx in range(-5, 5):
        ry = dy
        rx = dx + 18
        if ry + 10 > ref.shape[0] or rx < 0 or rx + 10 > ref.shape[1]:
            continue
        ref_patch = ref[ry:ry+10, rx:rx+10]
        score = np.sum(patch == ref_patch)
        if score > best_score:
            best_score = score
            best_pos = (dx, dy - 28)
            if score == patch.size:
                break

print(f"Best match: dx={best_pos[0]}, dy={best_pos[1]} (score={best_score}/{patch.size})")

# Try a larger search and use the whole grid area
print("\n=== Full grid area template match ===")
# Take the grid area from ours: y=30-380, x=20-420
# This is 350x400 - too large. Use a smaller distinctive area
# Top of grid: y=30-60, x=20-100
patch_y1, patch_y2 = 30, 60
patch_x1, patch_x2 = 20, 100
patch = ours[patch_y1:patch_y2, patch_x1:patch_x2]

best_score = 0
best_pos = None
for dy in range(-5, 40):
    ry = patch_y1 + dy
    for dx in range(-5, 5):
        rx = patch_x1 + dx
        if ry < 0 or ry + (patch_y2-patch_y1) > ref.shape[0]:
            continue
        if rx < 0 or rx + (patch_x2-patch_x1) > ref.shape[1]:
            continue
        ref_patch = ref[ry:ry+(patch_y2-patch_y1), rx:rx+(patch_x2-patch_x1)]
        score = int(np.sum(np.all(patch == ref_patch, axis=2)))
        if score > best_score:
            best_score = score
            best_pos = (dx, dy)

total = (patch_y2-patch_y1) * (patch_x2-patch_x1)
print(f"Best offset: dx={best_pos[0]}, dy={best_pos[1]} (score={best_score}/{total} = {100*best_score/total:.1f}%)")

# Try with just matching the grayscale grid values
print("\n=== Grayscale-only grid match ===")
best_score = 0
best_pos = None
patch_gray = patch[:,:,0]  # Just R channel (grayscale)
for dy in range(-5, 40):
    ry = patch_y1 + dy
    for dx in range(-5, 5):
        rx = patch_x1 + dx
        if ry < 0 or ry + (patch_y2-patch_y1) > ref.shape[0]:
            continue
        if rx < 0 or rx + (patch_x2-patch_x1) > ref.shape[1]:
            continue
        ref_gray = ref[ry:ry+(patch_y2-patch_y1), rx:rx+(patch_x2-patch_x1), 0]
        # Allow ±1 tolerance
        score = int(np.sum(np.abs(patch_gray.astype(int) - ref_gray.astype(int)) <= 2))
        if score > best_score:
            best_score = score
            best_pos = (dx, dy)

print(f"Best offset: dx={best_pos[0]}, dy={best_pos[1]} (score={best_score}/{total} = {100*best_score/total:.1f}%)")
