# /// script
# requires-python = ">=3.13"
# dependencies = ["pillow", "numpy"]
# ///
"""Create a 3-column comparison: Reference | Geneva (old) | MS Sans Serif (current).
Zoomed 3x on text regions only, with labels."""
import sys
import numpy as np
from PIL import Image, ImageDraw

GAME_SIZE = (640, 480)

def load_and_normalize(path):
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    if arr.shape[:2] == (480, 640):
        return arr
    # Find gray background, crop, place on 640x480 canvas
    gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows = np.any(gray, axis=1)
    cols = np.any(gray, axis=0)
    if rows.any() and cols.any():
        y1 = int(np.argmax(rows)); y2 = int(arr.shape[0] - np.argmax(rows[::-1]))
        x1 = int(np.argmax(cols)); x2 = int(arr.shape[1] - np.argmax(cols[::-1]))
        cropped = arr[y1:y2, x1:x2]
    else:
        cropped = arr
    result = np.full((480, 640, 3), 164, dtype=np.uint8)
    h, w = cropped.shape[:2]
    ph, pw = min(h, 480), min(w, 640)
    result[:ph, :pw] = cropped[:ph, :pw]
    return result

def main():
    if len(sys.argv) < 4:
        print("Usage: uv run scripts/font_comparison.py <reference> <geneva_screenshot> <ms_sans_screenshot> [output]")
        sys.exit(1)

    ref = load_and_normalize(sys.argv[1])
    geneva = load_and_normalize(sys.argv[2])
    ms_sans = load_and_normalize(sys.argv[3])
    out_path = sys.argv[4] if len(sys.argv) > 4 else "screenshots/font_comparison.png"

    # Text regions
    regions = [
        (440, 115, 630, 360, "Instruction text"),
        (0, 440, 640, 480, "Bottom bar"),
    ]

    scale = 3
    panels = []

    for x1, y1, x2, y2, label in regions:
        ref_crop = ref[y1:y2, x1:x2]
        gen_crop = geneva[y1:y2, x1:x2]
        ms_crop = ms_sans[y1:y2, x1:x2]

        # Scale up
        ref_big = np.repeat(np.repeat(ref_crop, scale, axis=0), scale, axis=1)
        gen_big = np.repeat(np.repeat(gen_crop, scale, axis=0), scale, axis=1)
        ms_big = np.repeat(np.repeat(ms_crop, scale, axis=0), scale, axis=1)

        # 3px white separator
        sep_col = np.full((ref_big.shape[0], 3, 3), 255, dtype=np.uint8)

        row = np.concatenate([ref_big, sep_col, gen_big, sep_col, ms_big], axis=1)
        panels.append(row)

        # 6px gray separator between regions
        sep = np.full((6, row.shape[1], 3), 200, dtype=np.uint8)
        panels.append(sep)

    if panels:
        panels.pop()

    # Pad to same width
    max_w = max(p.shape[1] for p in panels)
    padded = []
    for p in panels:
        if p.shape[1] < max_w:
            pad = np.full((p.shape[0], max_w - p.shape[1], 3), 164, dtype=np.uint8)
            p = np.concatenate([p, pad], axis=1)
        padded.append(p)

    final = np.concatenate(padded, axis=0)

    # Add label header
    header_h = 30
    header = np.full((header_h, final.shape[1], 3), 240, dtype=np.uint8)
    final_with_header = np.concatenate([header, final], axis=0)

    img = Image.fromarray(final_with_header)
    draw = ImageDraw.Draw(img)
    col_w = (final.shape[1] - 6) // 3  # approx column width
    draw.text((col_w // 2 - 30, 5), "REFERENCE", fill=(0, 0, 0))
    draw.text((col_w + 3 + col_w // 2 - 20, 5), "GENEVA", fill=(0, 0, 200))
    draw.text((2 * col_w + 6 + col_w // 2 - 40, 5), "MS SANS SERIF", fill=(200, 0, 0))

    img.save(out_path)
    print(f"Saved: {out_path} ({img.width}x{img.height})")
    print("Columns: Reference | Geneva (old, fontdue) | MS Sans Serif (current, sdl2_ttf)")

if __name__ == "__main__":
    main()
