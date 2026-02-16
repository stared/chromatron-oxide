"""Check what the digit sprites (indices 118-127) look like and verify palette offset coloring."""
import json
import os

data_path = os.path.join(os.path.dirname(__file__), "..", "decompiled", "extracted_data.json")
with open(data_path) as f:
    data = json.load(f)

palette = data["palette"]
sprites_rle = data["sprites_rle"]

def decompress(rle):
    pixels = []
    i = 0
    while len(pixels) < 576 and i < len(rle):
        b = rle[i]
        i += 1
        if b < 0xC1:
            pixels.append(b)
        else:
            count = b - 0xC0
            val = rle[i]
            i += 1
            pixels.extend([val] * count)
    return pixels[:576]

# Check sprites 118-127 (digit 0-9)
print("Digit sprites (indices 118-127):")
print("=" * 60)
for digit in range(10):
    idx = 118 + digit
    if idx >= len(sprites_rle):
        print(f"  Sprite {idx}: OUT OF RANGE (only {len(sprites_rle)} sprites)")
        continue

    pixels = decompress(sprites_rle[idx])

    # Show the 12x12 top-left corner as ASCII art
    print(f"\nDigit {digit} (sprite {idx}):")
    from collections import Counter
    used = Counter(pixels[:576])

    # Show 12x12 grid
    for y in range(12):
        row = ""
        for x in range(12):
            p = pixels[y * 24 + x]
            if p < 14:
                row += "."
            else:
                row += "#"
        print(f"  {row}")

    # Show palette indices used in 12x12 area
    area_pixels = []
    for y in range(12):
        for x in range(12):
            area_pixels.append(pixels[y * 24 + x])
    area_used = Counter(area_pixels)
    print(f"  Palette indices: {dict(sorted(area_used.items()))}")

# Check palette offset effect
print("\n\nPalette offset coloring for digit 1:")
idx = 119
pixels = decompress(sprites_rle[idx])
# Get the non-transparent pixel values
vis_pixels = set()
for y in range(12):
    for x in range(12):
        p = pixels[y * 24 + x]
        if p >= 14:
            vis_pixels.add(p)

print(f"  Visible pixel values: {sorted(vis_pixels)}")
for offset_name, offset in [("Default (white)", 0), ("Red", 0x10), ("Green", 0x30), ("Blue", 0x48)]:
    print(f"  {offset_name} (offset={offset:#x}):")
    for p in sorted(vis_pixels):
        pal_idx = (p + offset) % 256
        if pal_idx < len(palette):
            r, g, b = palette[pal_idx]
            print(f"    pal[{p}+{offset}={pal_idx}] = ({r},{g},{b})")
