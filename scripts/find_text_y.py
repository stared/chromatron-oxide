# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow", "numpy"]
# ///
"""Find exact y-positions of text lines in reference vs our render."""
import numpy as np
from PIL import Image

REF = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
OURS = "screenshots/framebuffer_1771431637.png"

ref = np.array(Image.open(REF).convert("RGB"))
ours = np.array(Image.open(OURS).convert("RGB"))

# Instruction text x-range
x1, x2 = 450, 620

print("=== Row-by-row black pixel count (instruction text area x=450-620) ===")
print(f"{'y':>4s}  {'ref':>4s}  {'ours':>4s}  {'match':>5s}")
for y in range(100, 300):
    ref_row = np.all(ref[y, x1:x2] == [0, 0, 0], axis=1)
    ours_row = np.all(ours[y, x1:x2] == [0, 0, 0], axis=1)
    ref_n = int(np.sum(ref_row))
    ours_n = int(np.sum(ours_row))
    if ref_n > 0 or ours_n > 0:
        match = "YES" if ref_n == ours_n and np.array_equal(ref_row, ours_row) else ""
        print(f"{y:4d}  {ref_n:4d}  {ours_n:4d}  {match}")

# Also check bottom text
print("\n=== Bottom text area (y=440-475) ===")
for y in range(440, 475):
    ref_row = np.all(ref[y, :640] == [0, 0, 0], axis=1)
    ours_row = np.all(ours[y, :640] == [0, 0, 0], axis=1)
    ref_n = int(np.sum(ref_row))
    ours_n = int(np.sum(ours_row))
    if ref_n > 0 or ours_n > 0:
        match = "YES" if ref_n == ours_n and np.array_equal(ref_row, ours_row) else ""
        print(f"{y:4d}  {ref_n:4d}  {ours_n:4d}  {match}")
