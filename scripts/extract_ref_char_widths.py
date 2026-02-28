# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow", "numpy"]
# ///
"""
Extract character widths from the reference screenshot by analyzing known text.
Uses the normalized (640x480) version of the reference.
"""
import numpy as np
from PIL import Image

# First, normalize the reference just like compare.py does
GAME_SIZE = (640, 480)

def find_game_area(arr):
    gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows = np.any(gray, axis=1)
    cols = np.any(gray, axis=0)
    if not rows.any() or not cols.any():
        return 0, 0, arr.shape[1], arr.shape[0]
    y1 = int(np.argmax(rows))
    y2 = int(arr.shape[0] - np.argmax(rows[::-1]))
    x1 = int(np.argmax(cols))
    x2 = int(arr.shape[1] - np.argmax(cols[::-1]))
    return x1, y1, x2 - x1, y2 - y1

def normalize(path):
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    x, y, w, h = find_game_area(arr)
    cropped = arr[y:y+h, x:x+w]
    ch, cw = cropped.shape[:2]
    if abs(cw - 1280) < 20 and abs(ch - 960) < 20:
        cropped = np.array(Image.fromarray(cropped).resize(GAME_SIZE, Image.BOX))
        ch, cw = cropped.shape[:2]
    result = np.full((480, 640, 3), 164, dtype=np.uint8)
    ph, pw = min(ch, 480), min(cw, 640)
    result[:ph, :pw] = cropped[:ph, :pw]
    return result

ref_path = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
ref = normalize(ref_path)
print(f"Normalized reference: {ref.shape}")

# Now analyze the text areas
# Text is black (near 0,0,0) on gray (164,164,164) background
is_text = np.all(ref < 50, axis=2)

# Find text lines in instruction area (450, 125) to (620, 350)
print("\n=== Instruction text lines ===")
for y in range(125, 350):
    row = is_text[y, 450:620]
    if row.any():
        first = int(np.argmax(row))
        last = int(len(row) - 1 - np.argmax(row[::-1]))
        total = int(row.sum())
        if total > 3:  # skip noise
            print(f"  y={y}: x={450+first}-{450+last} ({total} black px)")

print("\n=== Bottom text ===")
# "freeware" at (0, 450) and "silverspaceship.com" at (470, 450)
for y in range(448, 480):
    row = is_text[y, :]
    if row.any():
        positions = np.where(row)[0]
        # Split into groups (freeware vs silverspaceship.com)
        gaps = np.where(np.diff(positions) > 20)[0]
        groups = np.split(positions, gaps + 1)
        parts = []
        for g in groups:
            if len(g) > 2:
                parts.append(f"x={g[0]}-{g[-1]}({len(g)}px)")
        if parts:
            print(f"  y={y}: {', '.join(parts)}")

# Now measure "freeware" width by looking at the leftmost extent
print("\n=== 'freeware' precise bounds ===")
freeware_min_x = 640
freeware_max_x = 0
freeware_min_y = 480
freeware_max_y = 0
for y in range(448, 475):
    for x in range(0, 80):
        if is_text[y, x]:
            freeware_min_x = min(freeware_min_x, x)
            freeware_max_x = max(freeware_max_x, x)
            freeware_min_y = min(freeware_min_y, y)
            freeware_max_y = max(freeware_max_y, y)

print(f"  Bounds: ({freeware_min_x},{freeware_min_y})-({freeware_max_x},{freeware_max_y})")
print(f"  Width: {freeware_max_x - freeware_min_x + 1}px, Height: {freeware_max_y - freeware_min_y + 1}px")

# "silverspaceship.com" bounds
print("\n=== 'silverspaceship.com' precise bounds ===")
ss_min_x = 640
ss_max_x = 0
ss_min_y = 480
ss_max_y = 0
for y in range(448, 475):
    for x in range(450, 640):
        if is_text[y, x]:
            ss_min_x = min(ss_min_x, x)
            ss_max_x = max(ss_max_x, x)
            ss_min_y = min(ss_min_y, y)
            ss_max_y = max(ss_max_y, y)

print(f"  Bounds: ({ss_min_x},{ss_min_y})-({ss_max_x},{ss_max_y})")
print(f"  Width: {ss_max_x - ss_min_x + 1}px, Height: {ss_max_y - ss_min_y + 1}px")

# Instruction text: line-by-line analysis
print("\n=== Instruction text line bounds ===")
# Group rows into lines
in_line = False
line_start = 0
text_lines = []
for y in range(125, 350):
    row = is_text[y, 450:620]
    has_text = row.sum() > 3
    if has_text and not in_line:
        in_line = True
        line_start = y
    elif not has_text and in_line:
        in_line = False
        text_lines.append((line_start, y))
if in_line:
    text_lines.append((line_start, 350))

for i, (y1, y2) in enumerate(text_lines):
    # Find the precise x bounds
    min_x = 620
    max_x = 450
    for y in range(y1, y2):
        for x in range(450, 620):
            if is_text[y, x]:
                min_x = min(min_x, x)
                max_x = max(max_x, x)
    text_w = max_x - min_x + 1
    # Line spacing
    next_y = text_lines[i+1][0] if i+1 < len(text_lines) else y2 + 3
    spacing = next_y - y1
    print(f"  Line {i+1}: y={y1:3d}-{y2:3d} ({y2-y1:2d}px), x={min_x}-{max_x} ({text_w:3d}px), spacing={spacing}px")
