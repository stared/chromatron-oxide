"""Create a superimposed (blended) comparison of Rust vs reference screenshots.
Outputs: side-by-side, 50% blend overlay, and checkerboard interleave.

Usage: uv run scripts/superimpose.py <rust> <reference> <output>
"""
import sys
import numpy as np
from PIL import Image

def find_game_area(arr, bg_val=164, tolerance=5):
    """Find game content by gray background."""
    gray = np.all(np.abs(arr.astype(int) - bg_val) <= tolerance, axis=2)
    rows = np.any(gray, axis=1)
    cols = np.any(gray, axis=0)
    if not rows.any() or not cols.any():
        return 0, 0, arr.shape[1], arr.shape[0]
    y1 = int(np.argmax(rows))
    y2 = int(arr.shape[0] - np.argmax(rows[::-1]))
    x1 = int(np.argmax(cols))
    x2 = int(arr.shape[1] - np.argmax(cols[::-1]))
    return x1, y1, x2 - x1, y2 - y1

def normalize_to_640x480(img):
    arr = np.array(img.convert("RGB"))
    x, y, w, h = find_game_area(arr)
    cropped = img.crop((x, y, x + w, y + h))
    cw, ch = cropped.size
    # Use NEAREST for Retina 2x (exact half), BOX otherwise
    if abs(cw - 1280) < 20 and abs(ch - 960) < 20:
        cropped = cropped.resize((640, 480), Image.BOX)
    elif (cw, ch) != (640, 480):
        cropped = cropped.resize((640, 480), Image.LANCZOS)
    return np.array(cropped, dtype=np.uint8)

def main():
    rust_path, ref_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    rust = normalize_to_640x480(Image.open(rust_path).convert("RGB"))
    ref = normalize_to_640x480(Image.open(ref_path).convert("RGB"))

    # Ensure same shape
    h = min(rust.shape[0], ref.shape[0])
    w = min(rust.shape[1], ref.shape[1])
    rust = rust[:h, :w]
    ref = ref[:h, :w]

    # 1. Side by side
    side = np.concatenate([ref, rust], axis=1)

    # 2. 50% alpha blend
    blend = ((ref.astype(np.float32) + rust.astype(np.float32)) / 2).astype(np.uint8)

    # 3. Checkerboard (8px blocks)
    checker = np.copy(ref)
    block = 8
    for by in range(0, h, block):
        for bx in range(0, w, block):
            if ((by // block) + (bx // block)) % 2 == 0:
                checker[by:by+block, bx:bx+block] = rust[by:by+block, bx:bx+block]

    # 4. Diff amplified
    diff = np.abs(rust.astype(np.int16) - ref.astype(np.int16))
    diff_amp = np.clip(diff * 4, 0, 255).astype(np.uint8)

    # Compose: 2x2 grid
    # [side-by-side (2w × h)]
    # [blend | checker]
    # [diff×4 | (label)]
    row2 = np.concatenate([blend, checker], axis=1)
    row3 = np.concatenate([diff_amp, np.full_like(diff_amp, 128)], axis=1)

    # Make side same width as row2
    panel = np.concatenate([side, row2, row3], axis=0)
    Image.fromarray(panel).save(out_path)
    print(f"Saved: {out_path}")
    print(f"Layout: row1=[ref|rust], row2=[50% blend|checkerboard], row3=[diff×4|gray]")
    print(f"Size: {panel.shape[1]}x{panel.shape[0]}")

if __name__ == "__main__":
    main()
