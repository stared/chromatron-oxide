# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow", "numpy"]
# ///
"""Check bottom text area in reference - what colors are there?"""
import numpy as np
from PIL import Image
from collections import Counter

REF = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
ref = np.array(Image.open(REF).convert("RGB"))

# Bottom area
print("=== Unique colors in bottom area (y=440-480, x=0-640) ===")
bottom = ref[440:480, :, :]
colors = Counter()
for y in range(bottom.shape[0]):
    for x in range(bottom.shape[1]):
        c = tuple(bottom[y, x])
        colors[c] += 1

for color, count in colors.most_common(10):
    print(f"  RGB{color}: {count} px")

# Check if there's any non-background color
print("\n=== Non-gray pixels in bottom area ===")
gray = np.all(ref[440:480] == [164, 164, 164], axis=2)
non_gray = ~gray
for y in range(40):
    n = int(np.sum(non_gray[y]))
    if n > 0:
        # Find which colors
        row = ref[440+y]
        non_gray_pixels = []
        for x in range(640):
            if not np.array_equal(row[x], [164, 164, 164]):
                non_gray_pixels.append((x, tuple(row[x])))
        colors_in_row = Counter(c for _, c in non_gray_pixels)
        print(f"  y={440+y}: {n} non-gray px, colors={dict(colors_in_row.most_common(5))}, x-range=[{non_gray_pixels[0][0]},{non_gray_pixels[-1][0]}]")
