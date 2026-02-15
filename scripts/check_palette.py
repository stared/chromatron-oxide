"""Check palette entries around the transparency threshold (index 14)."""
import json, os

data_path = os.path.join(os.path.dirname(__file__), "..", "decompiled", "extracted_data.json")
with open(data_path) as f:
    data = json.load(f)

palette = data["palette"]
print("Palette entries around transparency threshold (14):")
for i in range(20):
    r, g, b = palette[i]
    mark = " <-- threshold" if i == 14 else ""
    print(f"  [{i:3d}] = ({r:3d}, {g:3d}, {b:3d}){mark}")

print(f"\nFirst non-black entry: ", end="")
for i, (r, g, b) in enumerate(palette):
    if r or g or b:
        print(f"[{i}] = ({r}, {g}, {b})")
        break

# Check what sprite 0x3A (58, blue laser east) uses
sprite_rle = data["sprites_rle"][58]
# Decompress
pixels = []
i = 0
while len(pixels) < 576 and i < len(sprite_rle):
    b = sprite_rle[i]
    i += 1
    if b < 0xC1:
        pixels.append(b)
    else:
        count = b - 0xC0
        val = sprite_rle[i]
        i += 1
        pixels.extend([val] * count)

# Count palette indices used
from collections import Counter
counts = Counter(pixels[:576])
print(f"\nSprite 58 (blue laser east) palette index usage:")
for idx, cnt in sorted(counts.items()):
    r, g, b = palette[idx]
    vis = "TRANSPARENT" if idx < 14 else "visible"
    print(f"  pal[{idx:3d}] ({r:3d},{g:3d},{b:3d}) × {cnt:3d}  {vis}")
