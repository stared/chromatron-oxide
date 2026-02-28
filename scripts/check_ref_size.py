# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow"]
# ///
"""Check reference image size and bottom text."""
from PIL import Image
import numpy as np

REF = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
img = Image.open(REF)
print(f"Reference size: {img.size} (mode={img.mode})")

arr = np.array(img.convert("RGB"))
print(f"Array shape: {arr.shape}")

# Check bottom area for non-gray pixels by row
print("\n=== Bottom area non-gray rows ===")
for y in range(430, arr.shape[0]):
    gray_count = np.sum(np.all(arr[y, :] == [164, 164, 164], axis=1))
    non_gray = arr.shape[1] - gray_count
    if non_gray > 0:
        # Sample non-gray pixels
        mask = ~np.all(arr[y, :] == [164, 164, 164], axis=1)
        xs = np.where(mask)[0]
        samples = [(int(x), tuple(arr[y, x].tolist())) for x in xs[:5]]
        print(f"  y={y}: {non_gray} non-gray px, x-range=[{xs[0]},{xs[-1]}], samples={samples}")
