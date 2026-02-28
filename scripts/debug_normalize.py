# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow", "numpy"]
# ///
"""Debug what normalize() does with the reference image."""
import numpy as np
from PIL import Image

REF = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
OURS = "screenshots/framebuffer_1771431637.png"

def find_game_area(arr):
    gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows = np.any(gray, axis=1)
    cols = np.any(gray, axis=0)
    y1 = int(np.argmax(rows))
    y2 = int(arr.shape[0] - np.argmax(rows[::-1]))
    x1 = int(np.argmax(cols))
    x2 = int(arr.shape[1] - np.argmax(cols[::-1]))
    return x1, y1, x2 - x1, y2 - y1

ref = np.array(Image.open(REF).convert("RGB"))
ours = np.array(Image.open(OURS).convert("RGB"))

print(f"Reference: {ref.shape[1]}x{ref.shape[0]}")
x, y, w, h = find_game_area(ref)
print(f"Reference game area: ({x}, {y}) {w}x{h}")

print(f"\nOurs: {ours.shape[1]}x{ours.shape[0]}")
x, y, w, h = find_game_area(ours)
print(f"Ours game area: ({x}, {y}) {w}x{h}")

# Check reference top rows
print("\n=== Reference top rows (y=0-35) ===")
for y in range(0, 35):
    row = ref[y]
    gray_count = np.sum(np.all(np.abs(row.astype(int) - 164) <= 5, axis=1))
    non_gray = ref.shape[1] - gray_count
    if non_gray > 0:
        # Sample first non-gray
        mask = ~np.all(np.abs(row.astype(int) - 164) <= 5, axis=1)
        xs = np.where(mask)[0]
        samples = [(int(x), tuple(row[x].tolist())) for x in xs[:3]]
        print(f"  y={y:3d}: {gray_count} gray, {non_gray} non-gray, samples={samples}")
    else:
        print(f"  y={y:3d}: ALL gray")
