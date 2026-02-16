"""Exact pixel diff between raw 640x480 framebuffer and reference.
For the reference, crops to content area without any scaling.

Usage: uv run scripts/exact_diff.py <framebuffer_png> <reference_png> [output]
"""
import sys
import numpy as np
from PIL import Image

def load_framebuffer(path):
    """Load our exact 640x480 framebuffer."""
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    assert arr.shape == (480, 640, 3), f"Expected 640x480, got {img.size}"
    return arr

def load_reference(path):
    """Load reference, find game content, crop to exactly 640x480.
    Pad with gray if smaller, crop if larger."""
    img = Image.open(path).convert("RGB")
    arr = np.array(img)

    # Find gray background area
    gray_mask = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows = np.any(gray_mask, axis=1)
    cols = np.any(gray_mask, axis=0)

    if rows.any() and cols.any():
        y1 = int(np.argmax(rows))
        y2 = int(arr.shape[0] - np.argmax(rows[::-1]))
        x1 = int(np.argmax(cols))
        x2 = int(arr.shape[1] - np.argmax(cols[::-1]))
    else:
        y1, x1 = 0, 0
        y2, x2 = arr.shape[0], arr.shape[1]

    print(f"Reference content: ({x1},{y1}) to ({x2},{y2}) = {x2-x1}x{y2-y1}")
    cropped = arr[y1:y2, x1:x2]

    # Place into 640x480 canvas (gray background)
    result = np.full((480, 640, 3), 164, dtype=np.uint8)
    h, w = cropped.shape[:2]
    ph, pw = min(h, 480), min(w, 640)
    result[:ph, :pw] = cropped[:ph, :pw]
    return result

def main():
    fb_path = sys.argv[1]
    ref_path = sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) > 3 else "screenshots/exact_diff.png"

    fb = load_framebuffer(fb_path)
    ref = load_reference(ref_path)

    diff = np.abs(fb.astype(np.int16) - ref.astype(np.int16))
    total = 640 * 480

    identical = int(np.all(diff == 0, axis=2).sum())
    near = int(np.all(diff <= 3, axis=2).sum())
    print(f"\n=== Exact Pixel Diff (no scaling) ===")
    print(f"Total pixels:     {total:,}")
    print(f"Identical:        {identical:,} ({100*identical/total:.1f}%)")
    print(f"Near-identical:   {near:,} ({100*near/total:.1f}%)")
    print(f"Different:        {total-near:,} ({100*(total-near)/total:.1f}%)")
    print(f"Max diff:         {diff.max()}")
    print(f"Mean diff:        {diff.mean():.2f}")

    # Regional
    regions = {
        "Grid area (48-408, 18-378)": (48, 18, 408, 378),
        "Grid interior (60-396, 30-366)": (60, 30, 396, 366),
        "Toolbox (448-608, 8-112)": (448, 8, 608, 112),
        "Instruction text (450-620, 125-350)": (450, 125, 620, 350),
        "Level numbers (0-520, 400-450)": (0, 400, 520, 450),
        "Bottom text (0-640, 450-480)": (0, 450, 640, 480),
        "Outer BG (0-48, 0-18)": (0, 0, 48, 18),
    }
    print(f"\n=== Regional Analysis ===")
    for name, (x1, y1, x2, y2) in regions.items():
        rd = diff[y1:y2, x1:x2]
        rt = (y2-y1) * (x2-x1)
        ri = int(np.all(rd == 0, axis=2).sum())
        print(f"  {name:<42s}: {100*ri/max(rt,1):5.1f}% identical, mean={rd.mean():.1f}")

    # Generate comparison image
    diff_amp = np.clip(diff * 4, 0, 255).astype(np.uint8)
    dm = np.sqrt((diff.astype(float)**2).sum(axis=2))
    heatmap = np.zeros((480, 640, 3), dtype=np.uint8)
    heatmap[:,:,1] = np.where(dm == 0, 128, 0)
    heatmap[:,:,0] = np.clip(dm * 4, 0, 255).astype(np.uint8)

    top = np.concatenate([ref, fb], axis=1)
    bot = np.concatenate([diff_amp, heatmap], axis=1)
    panel = np.concatenate([top, bot], axis=0)
    Image.fromarray(panel).save(out_path)
    print(f"\nDiff image saved: {out_path}")
    print(f"Layout: [ref|rust] / [diff×4|heatmap]")

if __name__ == "__main__":
    main()
