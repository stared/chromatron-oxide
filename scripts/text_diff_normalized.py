# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow", "numpy"]
# ///
"""Compare instruction text after proper normalization (same as compare.py)."""
import numpy as np
from PIL import Image

GAME_SIZE = (640, 480)

def find_game_area(arr):
    gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows = np.any(gray, axis=1)
    cols = np.any(gray, axis=0)
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

REF = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
OURS = "screenshots/framebuffer_1771431637.png"

ref = normalize(REF)
ours = normalize(OURS)

# Instruction text region
x1, x2 = 440, 630
y1, y2 = 120, 310

ref_crop = ref[y1:y2, x1:x2]
ours_crop = ours[y1:y2, x1:x2]

# Check first text pixel in each
print("=== First black pixels per line (normalized) ===")
for y in range(y2 - y1):
    abs_y = y + y1
    ref_row_black = np.all(ref_crop[y] == [0,0,0], axis=1)
    ours_row_black = np.all(ours_crop[y] == [0,0,0], axis=1)
    ref_n = int(np.sum(ref_row_black))
    ours_n = int(np.sum(ours_row_black))
    if ref_n > 0 or ours_n > 0:
        ref_first_x = int(np.argmax(ref_row_black)) + x1 if ref_n > 0 else -1
        ours_first_x = int(np.argmax(ours_row_black)) + x1 if ours_n > 0 else -1
        match = "MATCH" if ref_n == ours_n and np.array_equal(ref_row_black, ours_row_black) else ""
        xdiff = f"dx={ours_first_x - ref_first_x}" if ref_n > 0 and ours_n > 0 else ""
        if not match:
            print(f"  y={abs_y}: ref={ref_n:3d}@x={ref_first_x}  ours={ours_n:3d}@x={ours_first_x}  {xdiff}")

# Per-line summary
print("\n=== Per text line summary ===")
line_starts = [128, 144, 160, 176, 192, 208, 224, 240, 256]
for ls in line_starts:
    total_match = 0
    total_px = 0
    for dy in range(13):
        y = ls + dy - y1
        if y < 0 or y >= y2 - y1:
            continue
        match = np.all(ref_crop[y] == ours_crop[y], axis=1)
        total_match += int(np.sum(match))
        total_px += ref_crop.shape[1]
    pct = 100 * total_match / max(total_px, 1)
    print(f"  Line at y={ls}: {pct:.1f}% identical")

# Build diff overlay
ref_black = np.all(ref_crop == [0,0,0], axis=2)
ours_black = np.all(ours_crop == [0,0,0], axis=2)
missing = ref_black & ~ours_black
extra = ours_black & ~ref_black

print(f"\n=== Totals ===")
print(f"Missing (in ref, not ours): {np.sum(missing)} px")
print(f"Extra (in ours, not ref): {np.sum(extra)} px")
print(f"Matching black pixels: {np.sum(ref_black & ours_black)} px")

# Save zoomed diff
scale = 3
h, w = ref_crop.shape[:2]
overlay = ours_crop.copy()
overlay[missing] = [255, 0, 255]  # magenta
overlay[extra] = [0, 255, 255]    # cyan

canvas = Image.new("RGB", (w * 3 * scale + 20, h * scale + 30), (40, 40, 40))
from PIL import ImageDraw
draw = ImageDraw.Draw(canvas)
labels = ["REFERENCE", "OURS", "DIFF"]
for i, label in enumerate(labels):
    draw.text((i * (w * scale + 10) + 5, 2), label, fill=(200, 200, 200))

for i, img_arr in enumerate([ref_crop, ours_crop, overlay]):
    pil = Image.fromarray(img_arr)
    pil = pil.resize((w * scale, h * scale), Image.NEAREST)
    canvas.paste(pil, (i * (w * scale + 10), 20))

canvas.save("screenshots/text_diff_normalized.png")
print("\nSaved: screenshots/text_diff_normalized.png")
