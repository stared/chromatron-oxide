"""Probe grid area pixels to check alignment between Rust and reference.
Uses exact 2x downscale for Retina without content-rect detection."""
import sys
import numpy as np
from PIL import Image

def load_rust(path):
    """Load Rust screenshot - find exact game area by looking for gray background boundaries."""
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    print(f"Rust: {path}")
    print(f"  Raw size: {img.size}")

    # For Retina, the game area is 1280x960 (640×480 at 2x)
    # Find the game content by looking for the background color at known positions
    # The gray background (164,164,164) should be at the very corners of the game area

    # Try to find a large block of gray ~164
    h, w = arr.shape[:2]

    # Search for the top-left corner of the game content
    # Look for a transition from non-gray to gray starting from top-left
    # Actually, for macOS screencapture -l, the window capture includes the title bar
    # and window shadow. Let's find the content area more precisely.

    # Strategy: find rows/cols where the gray pixel count jumps
    gray_mask = np.all(np.abs(arr.astype(int) - 164) <= 2, axis=2)

    # Find first row with significant gray
    row_gray = gray_mask.sum(axis=1)
    col_gray = gray_mask.sum(axis=0)

    # First and last rows with >50% gray content
    threshold = w * 0.3
    gray_rows = np.where(row_gray > threshold)[0]
    gray_cols = np.where(col_gray > h * 0.1)[0]

    if len(gray_rows) > 0 and len(gray_cols) > 0:
        y_start = gray_rows[0]
        y_end = gray_rows[-1] + 1
        x_start = gray_cols[0]
        x_end = gray_cols[-1] + 1
        print(f"  Gray area: x=[{x_start},{x_end}] y=[{y_start},{y_end}] = {x_end-x_start}x{y_end-y_start}")

        # Check if this is 2x (Retina)
        crop_w = x_end - x_start
        crop_h = y_end - y_start
        cropped = img.crop((x_start, y_start, x_end, y_end))

        if crop_w > 900 and crop_h > 700:
            # Retina 2x - downsample with box filter for exact 2x
            target_w = crop_w // 2
            target_h = crop_h // 2
            print(f"  2x downscale: {crop_w}x{crop_h} → {target_w}x{target_h}")
            cropped = cropped.resize((target_w, target_h), Image.BOX)
            # Then crop/pad to 640x480
            arr_cropped = np.array(cropped)
            if arr_cropped.shape[0] > 480:
                arr_cropped = arr_cropped[:480, :, :]
            if arr_cropped.shape[1] > 640:
                arr_cropped = arr_cropped[:, :640, :]
            return arr_cropped

        return np.array(cropped)

    print("  WARN: gray area not found, using full image")
    return arr

def load_ref(path):
    """Load reference screenshot."""
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    print(f"Ref: {path}")
    print(f"  Raw size: {img.size}")

    # Find content area
    gray_mask = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    h, w = arr.shape[:2]
    row_gray = gray_mask.sum(axis=1)
    col_gray = gray_mask.sum(axis=0)
    threshold = w * 0.1
    gray_rows = np.where(row_gray > threshold)[0]
    gray_cols = np.where(col_gray > h * 0.05)[0]

    if len(gray_rows) > 0 and len(gray_cols) > 0:
        y_start = gray_rows[0]
        y_end = gray_rows[-1] + 1
        x_start = gray_cols[0]
        x_end = gray_cols[-1] + 1
        print(f"  Content area: x=[{x_start},{x_end}] y=[{y_start},{y_end}] = {x_end-x_start}x{y_end-y_start}")
        cropped = img.crop((x_start, y_start, x_end, y_end))
        arr_c = np.array(cropped)
        # Pad or crop to 640x480
        result = np.full((480, 640, 3), 164, dtype=np.uint8)
        h2, w2 = arr_c.shape[:2]
        result[:min(h2,480), :min(w2,640)] = arr_c[:min(h2,480), :min(w2,640)]
        return result

    return arr

def main():
    if len(sys.argv) < 3:
        print("Usage: uv run scripts/pixel_probe2.py <rust> <reference>")
        sys.exit(1)

    rust = load_rust(sys.argv[1])
    ref = load_ref(sys.argv[2])

    print(f"\nRust shape: {rust.shape}")
    print(f"Ref shape:  {ref.shape}")

    # Ensure same size
    h = min(rust.shape[0], ref.shape[0], 480)
    w = min(rust.shape[1], ref.shape[1], 640)
    rust = rust[:h, :w]
    ref = ref[:h, :w]

    # Sample grid background at known empty cell positions
    # Grid cell centers: (col*24+60, row*24+30) for col,row in 0..14
    # Empty cells for level 1 are most of the grid
    print(f"\n=== Grid cell center pixels (should be grid bg = ~(92,92,92)) ===")
    for row in [0, 5, 10, 14]:
        for col in [0, 5, 10, 14]:
            x = col * 24 + 60
            y = row * 24 + 30
            if x < w and y < h:
                rp = tuple(int(v) for v in rust[y, x])
                fp = tuple(int(v) for v in ref[y, x])
                d = max(abs(rp[i]-fp[i]) for i in range(3))
                print(f"  Cell({col:2d},{row:2d}) ({x:3d},{y:3d}): rust={rp} ref={fp} maxdiff={d}")

    # Sample grid line positions (between cells)
    # Cell borders at (col*24+48, row*24+18) which is at sprite pixel boundary
    print(f"\n=== Grid line pixels (between cells) ===")
    for row in [0, 5, 10]:
        for col in [0, 5, 10]:
            # Left edge of cell (col+1) = (col+1)*24+48 = col*24+72
            x = col * 24 + 48
            y = row * 24 + 18
            if x < w and y < h:
                rp = tuple(int(v) for v in rust[y, x])
                fp = tuple(int(v) for v in ref[y, x])
                d = max(abs(rp[i]-fp[i]) for i in range(3))
                print(f"  Border({col:2d},{row:2d}) ({x:3d},{y:3d}): rust={rp} ref={fp} maxdiff={d}")

    # Compare identical pixel count per region
    diff = np.abs(rust.astype(int) - ref.astype(int))

    # Main grid interior (avoiding edges)
    grid_x1, grid_y1 = 48, 18
    grid_x2, grid_y2 = min(48 + 15*24, w), min(18 + 15*24, h)
    grid_diff = diff[grid_y1:grid_y2, grid_x1:grid_x2]
    grid_identical = int(np.all(grid_diff == 0, axis=2).sum())
    grid_total = (grid_y2-grid_y1) * (grid_x2-grid_x1)
    print(f"\n=== Grid interior ({grid_x1},{grid_y1}) to ({grid_x2},{grid_y2}) ===")
    print(f"  Identical: {grid_identical}/{grid_total} ({100*grid_identical/max(grid_total,1):.1f}%)")
    print(f"  Mean diff: {grid_diff.mean():.2f}")

    # Outer background
    bg_diff = diff[:18, :48]
    bg_identical = int(np.all(bg_diff == 0, axis=2).sum())
    bg_total = 18 * 48
    print(f"\n=== Outer background (0,0) to (48,18) ===")
    print(f"  Identical: {bg_identical}/{bg_total} ({100*bg_identical/max(bg_total,1):.1f}%)")
    if bg_total > 0:
        print(f"  Rust[0,0]={tuple(int(v) for v in rust[0,0])} Ref[0,0]={tuple(int(v) for v in ref[0,0])}")

if __name__ == "__main__":
    main()
