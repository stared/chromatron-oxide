# /// script
# requires-python = ">=3.13"
# dependencies = ["pillow", "numpy"]
# ///
"""Extract text regions from framebuffer and reference, create comparison."""
import sys
import numpy as np
from PIL import Image

GAME_SIZE = (640, 480)

def load_and_normalize(path):
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    # If already 640x480, return as-is
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
    fb = load_and_normalize(sys.argv[1])  # ours
    ref = load_and_normalize(sys.argv[2])  # reference
    out_path = sys.argv[3]

    # Text regions to extract (x1, y1, x2, y2, label)
    regions = [
        (440, 115, 630, 360, "Instruction text"),
        (0, 440, 640, 480, "Bottom bar (freeware + URL)"),
    ]

    panels = []
    for x1, y1, x2, y2, label in regions:
        ref_crop = ref[y1:y2, x1:x2]
        fb_crop = fb[y1:y2, x1:x2]

        # Diff: magenta where different
        diff = np.abs(fb_crop.astype(np.int16) - ref_crop.astype(np.int16))
        differs = ~np.all(diff == 0, axis=2)
        overlay = fb_crop.copy()
        overlay[differs] = [255, 0, 255]

        # Scale up 3x for visibility
        scale = 3
        h, w = ref_crop.shape[:2]
        ref_big = np.repeat(np.repeat(ref_crop, scale, axis=0), scale, axis=1)
        fb_big = np.repeat(np.repeat(fb_crop, scale, axis=0), scale, axis=1)
        overlay_big = np.repeat(np.repeat(overlay, scale, axis=0), scale, axis=1)

        # Label bar
        row = np.concatenate([ref_big, fb_big, overlay_big], axis=1)
        panels.append(row)

        # Add 6px gray separator
        sep = np.full((6, row.shape[1], 3), 200, dtype=np.uint8)
        panels.append(sep)

    # Remove trailing separator
    if panels:
        panels.pop()

    # Pad all rows to same width
    max_w = max(p.shape[1] for p in panels)
    padded = []
    for p in panels:
        if p.shape[1] < max_w:
            pad = np.full((p.shape[0], max_w - p.shape[1], 3), 164, dtype=np.uint8)
            p = np.concatenate([p, pad], axis=1)
        padded.append(p)
    panels = padded

    final = np.concatenate(panels, axis=0)
    Image.fromarray(final).save(out_path)
    print(f"Saved: {out_path} ({final.shape[1]}x{final.shape[0]})")
    print("Layout per row: [Reference 3x | Ours 3x | Ours+magenta diff 3x]")
    print("Row 1: Instruction text (440-630, 115-360)")
    print("Row 2: Bottom bar (0-640, 440-480)")

if __name__ == "__main__":
    main()
