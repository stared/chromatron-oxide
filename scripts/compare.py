"""Compare our screenshot against the original reference.
Outputs a 2-panel image: [Reference | Ours with diff pixels in magenta]
Plus per-region statistics to stdout.

Handles Retina 2x, window chrome cropping, and different input sizes.

Usage: uv run scripts/compare.py <ours> <reference> [output]
"""
import sys
import numpy as np
from PIL import Image

GAME_SIZE = (640, 480)


def find_game_area(arr):
    """Find game content by gray background (164,164,164 ±5)."""
    gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows = np.any(gray, axis=1)
    cols = np.any(gray, axis=0)
    if not rows.any() or not cols.any():
        return 0, 0, arr.shape[1], arr.shape[0]
    y1 = int(np.argmax(rows))
    y2 = int(arr.shape[0] - np.argmax(rows[::-1]))
    x1 = int(np.argmax(cols))
    x2 = int(arr.shape[1] - np.argmax(cols[::-1]))
    return x1, y1, x2 - x1, y2 - y1


def normalize(path):
    """Load image, crop to game area, place on 640x480 gray canvas.
    No scaling unless Retina 2x (exact halving via BOX)."""
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    x, y, w, h = find_game_area(arr)
    cropped = arr[y:y+h, x:x+w]
    ch, cw = cropped.shape[:2]
    # Retina 2x: exact half via averaging
    if abs(cw - 1280) < 20 and abs(ch - 960) < 20:
        cropped = np.array(Image.fromarray(cropped).resize(GAME_SIZE, Image.BOX))
        ch, cw = cropped.shape[:2]
    # Place on 640x480 gray canvas (no interpolation scaling)
    result = np.full((480, 640, 3), 164, dtype=np.uint8)
    ph, pw = min(ch, 480), min(cw, 640)
    result[:ph, :pw] = cropped[:ph, :pw]
    return result


def main():
    ours_path = sys.argv[1]
    ref_path = sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) > 3 else "screenshots/comparison.png"

    ours = normalize(ours_path)
    ref = normalize(ref_path)

    diff = np.abs(ours.astype(np.int16) - ref.astype(np.int16))
    differs = ~np.all(diff == 0, axis=2)  # bool mask: True where pixels differ
    total = GAME_SIZE[0] * GAME_SIZE[1]
    identical = int((~differs).sum())

    print(f"=== Pixel Diff ===")
    print(f"Total: {total:,}  Identical: {identical:,} ({100*identical/total:.1f}%)  "
          f"Different: {total-identical:,} ({100*(total-identical)/total:.1f}%)")

    regions = {
        "Grid area":        (48, 18, 408, 378),
        "Toolbox":          (448, 8, 608, 112),
        "Instruction text": (450, 125, 620, 350),
        "Level numbers":    (0, 400, 520, 450),
        "Bottom text":      (0, 450, 640, 480),
    }
    print(f"\n=== Regional ===")
    for name, (x1, y1, x2, y2) in regions.items():
        rd = differs[y1:y2, x1:x2]
        rt = rd.size
        ri = int((~rd).sum())
        print(f"  {name:<20s}: {100*ri/max(rt,1):5.1f}% identical")

    # Build output: [Reference | Ours with magenta diff overlay]
    overlay = ours.copy()
    overlay[differs] = [255, 0, 255]  # magenta

    panel = np.concatenate([ref, overlay], axis=1)
    Image.fromarray(panel).save(out_path)
    print(f"\nSaved: {out_path}")
    print(f"Layout: [Reference | Ours + magenta diff]")


if __name__ == "__main__":
    main()
