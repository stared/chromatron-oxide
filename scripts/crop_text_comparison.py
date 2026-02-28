# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""
Crop instruction text from both reference and our framebuffer using
near-black pixel detection (same method as crop_reference_text.py).
Produces a 3-panel comparison: Reference | Ours | Diff overlay.
"""

import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

PROJECT = Path(__file__).resolve().parent.parent
BLACK_THRESHOLD = 40
MIN_BLACK_PER_ROW = 4
GAP_THRESHOLD = 20

# Reference: full window capture (638×508) with title bar
# Our framebuffer: raw 640×480 client area (no title bar)
# The instruction text rect in client coords: (450, 125, 620, 475) = 170×350
# But the reference image has a title bar offset, so we detect text bounds in each.

# Client-area instruction rect (same for both, but pixel coords differ in reference)
RECT_W = 170

def find_text_in_image(img_arr, panel_x, panel_y, panel_w, panel_h):
    """Find the text block within a panel region using near-black pixel detection."""
    panel = img_arr[panel_y:panel_y+panel_h, panel_x:panel_x+panel_w]
    gray = np.min(panel, axis=2)
    black_count = np.sum(gray < BLACK_THRESHOLD, axis=1)
    text_mask = black_count >= MIN_BLACK_PER_ROW
    text_rows = np.where(text_mask)[0]

    if len(text_rows) == 0:
        return panel, 0, panel_h

    # First block only (skip level numbers)
    gaps = np.diff(text_rows)
    split_points = np.where(gaps > GAP_THRESHOLD)[0]
    if len(split_points) > 0:
        text_rows = text_rows[:split_points[0] + 1]

    first, last = int(text_rows[0]), int(text_rows[-1])
    margin = 2
    crop_top = max(0, first - margin)
    crop_bottom = min(panel_h, last + margin + 1)
    return panel[crop_top:crop_bottom], crop_top, crop_bottom


def main():
    if len(sys.argv) < 3:
        print("Usage: uv run scripts/crop_text_comparison.py <our_framebuffer.png> <reference.png> [output.png]")
        sys.exit(1)

    ours_path = Path(sys.argv[1])
    ref_path = Path(sys.argv[2])
    out_path = Path(sys.argv[3]) if len(sys.argv) > 3 else PROJECT / "screenshots" / "text_only_comparison.png"

    ours_full = np.array(Image.open(ours_path))
    ref_full = np.array(Image.open(ref_path))
    print(f"Our framebuffer: {ours_full.shape[1]}×{ours_full.shape[0]}")
    print(f"Reference image: {ref_full.shape[1]}×{ref_full.shape[0]}")

    # Our framebuffer: direct client area, instruction rect at (450, 125)
    ours_text, ours_top, ours_bot = find_text_in_image(ours_full, 450, 125, RECT_W, 350)
    print(f"Our text: rows {ours_top}..{ours_bot} of panel (height={ours_text.shape[0]})")

    # Reference: has title bar. Search a larger vertical range to find the text.
    # The title bar is ~25-30px. So instruction rect top in image coords ≈ 125+25=150.
    # Search from y=100 to y=500 in the reference to be safe.
    ref_text, ref_top, ref_bot = find_text_in_image(ref_full, 450, 100, RECT_W, 400)
    print(f"Ref text: rows {ref_top}..{ref_bot} of search area (height={ref_text.shape[0]})")

    # Make both same height
    h = max(ours_text.shape[0], ref_text.shape[0])
    w = RECT_W

    def pad(arr, target_h):
        if arr.shape[0] >= target_h:
            return arr[:target_h]
        padded = np.full((target_h, arr.shape[1], 3), 164, dtype=np.uint8)
        padded[:arr.shape[0]] = arr
        return padded

    ref_text = pad(ref_text, h)
    ours_text = pad(ours_text, h)

    # Diff
    diff_mask = np.any(ref_text != ours_text, axis=2)
    diff_overlay = ours_text.copy()
    diff_overlay[diff_mask] = [255, 0, 255]

    # Stats
    total = h * w
    identical = int(np.sum(~diff_mask))
    print(f"\nText comparison: {identical}/{total} identical ({100*identical/total:.1f}%)")

    # Build 3-panel image
    gap = 4
    canvas = Image.new("RGB", (w * 3 + gap * 2, h + 22), (42, 42, 42))
    canvas.paste(Image.fromarray(ref_text), (0, 22))
    canvas.paste(Image.fromarray(ours_text), (w + gap, 22))
    canvas.paste(Image.fromarray(diff_overlay), (w * 2 + gap * 2, 22))

    draw = ImageDraw.Draw(canvas)
    draw.text((2, 2), "REFERENCE", fill=(200, 200, 200))
    draw.text((w + gap + 2, 2), "OURS (W95FA 11px)", fill=(200, 200, 200))
    draw.text((w * 2 + gap * 2 + 2, 2), "DIFF (magenta)", fill=(255, 0, 255))

    canvas.save(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
