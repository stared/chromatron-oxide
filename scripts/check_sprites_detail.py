"""Check sprite 0 and empty cell rendering. Also check palette entries 0-16."""
import json
import os

data_path = os.path.join(os.path.dirname(__file__), "..", "decompiled", "extracted_data.json")
with open(data_path) as f:
    data = json.load(f)

palette = data["palette"]
sprites_rle = data["sprites_rle"]

# Check palette entries 0-20 (raw BGR from binary)
print("Palette entries 0-20 (as stored in binary = BGR):")
for i in range(min(21, len(palette))):
    bgr = palette[i]
    print(f"  [{i:3d}]: BGR({bgr[0]:3d},{bgr[1]:3d},{bgr[2]:3d}) → RGB({bgr[2]:3d},{bgr[1]:3d},{bgr[0]:3d})")

# Check palette entries near 0x5C (92)
print(f"\nPalette entries near RGB(92,92,92):")
for i in range(256):
    bgr = palette[i]
    r, g, b = bgr[2], bgr[1], bgr[0]  # BGR→RGB
    if abs(r - 92) < 10 and abs(g - 92) < 10 and abs(b - 92) < 10:
        print(f"  [{i:3d}]: RGB({r:3d},{g:3d},{b:3d})")

# Check palette entries near 0xA4 (164)
print(f"\nPalette entries near RGB(164,164,164):")
for i in range(256):
    bgr = palette[i]
    r, g, b = bgr[2], bgr[1], bgr[0]
    if abs(r - 164) < 10 and abs(g - 164) < 10 and abs(b - 164) < 10:
        print(f"  [{i:3d}]: RGB({r:3d},{g:3d},{b:3d})")

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

# Check sprite 0 - what is it?
print(f"\nSprite 0 (first sprite):")
if len(sprites_rle) > 0:
    pixels = decompress(sprites_rle[0])
    from collections import Counter
    c = Counter(pixels)
    print(f"  Pixel value counts: {dict(sorted(c.items()))}")
    # Show as ASCII art
    for y in range(24):
        row = ""
        for x in range(24):
            p = pixels[y * 24 + x]
            if p < 14:
                row += "."
            else:
                row += f"{p:x}"[-1]
            row = ""
        for x in range(24):
            p = pixels[y * 24 + x]
            if p == 0:
                row += " "
            elif p < 14:
                row += "."
            else:
                row += "#"
        if y < 12:
            print(f"  {row}")

# Check sprite 1 (Wall)
print(f"\nSprite 1 (Wall):")
if len(sprites_rle) > 1:
    pixels = decompress(sprites_rle[1])
    c = Counter(pixels)
    print(f"  Pixel value counts: {dict(sorted(c.items()))}")
    for y in range(24):
        row = ""
        for x in range(24):
            p = pixels[y * 24 + x]
            if p == 0:
                row += " "
            elif p < 14:
                row += "."
            else:
                row += "#"
        if y < 12:
            print(f"  {row}")

# What palette index draws as (92,92,92)?
print(f"\n\nLooking for palette index that gives RGB(92,92,92)...")
for i in range(256):
    bgr = palette[i]
    r, g, b = bgr[2], bgr[1], bgr[0]
    if r == 92 and g == 92 and b == 92:
        print(f"  FOUND: palette[{i}] = RGB(92,92,92)")

# Check if sprites use palette indices 0-13 (transparent range) a lot
print(f"\nTransparent range (0-13) in first 5 sprites:")
for si in range(min(5, len(sprites_rle))):
    pixels = decompress(sprites_rle[si])
    trans = sum(1 for p in pixels if p < 14)
    print(f"  Sprite {si}: {trans}/576 transparent ({100*trans/576:.0f}%)")
    c = Counter(p for p in pixels if p < 14)
    print(f"    Transparent values: {dict(sorted(c.items()))}")
