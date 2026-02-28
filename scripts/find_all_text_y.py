# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow", "numpy"]
# ///
"""Find ALL text y-positions in reference screenshot."""
import numpy as np
from PIL import Image

REF = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
ref = np.array(Image.open(REF).convert("RGB"))
black = np.all(ref == [0, 0, 0], axis=2)

print("=== Instruction text area (x=450-620) ===")
for y in range(100, 310):
    n = int(np.sum(black[y, 450:620]))
    if n > 0:
        print(f"  y={y}: {n} black px")

print("\n=== Bottom text area (x=0-640, y=430-480) ===")
for y in range(430, 480):
    n = int(np.sum(black[y, :640]))
    if n > 0:
        print(f"  y={y}: {n} black px")

print("\n=== Level number area (x=0-350, y=0-30) ===")
# Level numbers are red, not black, so skip

# Also check the "won" text area
print("\n=== Won text area (x=300-450, y=370-420) ===")
for y in range(370, 420):
    n = int(np.sum(black[y, 300:450]))
    if n > 0:
        print(f"  y={y}: {n} black px")
