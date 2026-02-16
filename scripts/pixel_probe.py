"""Probe specific pixels in the Rust screenshot and reference to diagnose rendering issues.

Usage: uv run scripts/pixel_probe.py <rust_screenshot> <reference_screenshot>
"""
import sys
import numpy as np
from PIL import Image

def load_and_crop(path, label):
    """Load image, detect content area, crop and resize to 640x480."""
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    print(f"\n{label}: {path}")
    print(f"  Raw size: {img.size}")

    BG_COLOR = np.array([164, 164, 164])
    dist = np.abs(arr.astype(np.int16) - BG_COLOR.astype(np.int16)).sum(axis=2)
    bg_mask = dist < 30

    rows = np.any(bg_mask, axis=1)
    cols = np.any(bg_mask, axis=0)

    if rows.any() and cols.any():
        y_min = int(np.argmax(rows))
        y_max = int(arr.shape[0] - np.argmax(rows[::-1]))
        x_min = int(np.argmax(cols))
        x_max = int(arr.shape[1] - np.argmax(cols[::-1]))
        print(f"  Content rect: ({x_min},{y_min}) to ({x_max},{y_max}) = {x_max-x_min}x{y_max-y_min}")
    else:
        x_min, y_min = 0, 0
        x_max, y_max = arr.shape[1], arr.shape[0]
        print(f"  No gray background found, using full image")

    cropped = img.crop((x_min, y_min, x_max, y_max))
    cw, ch = cropped.size
    if cw != 640 or ch != 480:
        print(f"  Resizing from {cw}x{ch} to 640x480")
        cropped = cropped.resize((640, 480), Image.NEAREST)  # NEAREST to avoid interpolation artifacts

    return np.array(cropped)

def main():
    if len(sys.argv) < 3:
        print("Usage: uv run scripts/pixel_probe.py <rust> <reference>")
        sys.exit(1)

    rust = load_and_crop(sys.argv[1], "Rust")
    ref = load_and_crop(sys.argv[2], "Reference")

    # Probe key locations (all in 640x480 game coordinates)
    probes = [
        ("Background (10, 10)", 10, 10),
        ("Background (300, 460)", 300, 460),
        ("Grid center (200, 200)", 200, 200),  # Should be gray bg
        ("Grid origin area (60, 30)", 60, 30),  # Cell (0,0) center
        ("Near laser (84, 222)", 84, 222),       # Approx laser position on level 1
        ("Beam area (120, 222)", 120, 222),       # Should be beam area
        ("Toolbox area (460, 20)", 460, 20),     # Toolbox start
        ("Level num row1 (10, 410)", 10, 410),   # Level numbers
        ("Bottom text (50, 460)", 50, 460),       # "freeware" area
    ]

    print(f"\n{'Location':<30s} {'Rust RGB':<20s} {'Ref RGB':<20s} {'Diff'}")
    print("=" * 85)
    for name, x, y in probes:
        if x < 640 and y < 480:
            rp = tuple(rust[y, x])
            fp = tuple(ref[y, x])
            d = tuple(abs(int(a) - int(b)) for a, b in zip(rp, fp))
            print(f"{name:<30s} {str(rp):<20s} {str(fp):<20s} {d}")

    # Check a horizontal line across the grid area to see if grid lines exist in reference
    print(f"\n=== Horizontal scan at y=200 (mid-grid), x=48..108 ===")
    print(f"{'x':>4s}  {'Rust':<15s} {'Ref':<15s} {'RefNote'}")
    for x in range(48, 109):
        rp = tuple(rust[200, x])
        fp = tuple(ref[200, x])
        note = ""
        if fp == (164, 164, 164):
            note = "BG"
        elif abs(fp[0] - 164) < 20 and abs(fp[1] - 164) < 20 and abs(fp[2] - 164) < 20:
            note = f"near-BG"
        else:
            note = f"NON-BG"
        print(f"{x:4d}  {str(rp):<15s} {str(fp):<15s} {note}")

    # Vertical scan to check grid structure
    print(f"\n=== Vertical scan at x=200, y=18..78 ===")
    print(f"{'y':>4s}  {'Rust':<15s} {'Ref':<15s} {'RefNote'}")
    for y in range(18, 79):
        rp = tuple(rust[y, x])
        fp = tuple(ref[y, 200])
        note = ""
        if fp == (164, 164, 164):
            note = "BG"
        elif abs(fp[0] - 164) < 20 and abs(fp[1] - 164) < 20 and abs(fp[2] - 164) < 20:
            note = f"near-BG ({fp[0]},{fp[1]},{fp[2]})"
        else:
            note = f"NON-BG"
        print(f"{y:4d}  {str(rp):<15s} {str(fp):<15s} {note}")

    # Check background color consistency in Rust version
    print(f"\n=== Rust background color samples ===")
    bg_samples = [(5,5), (300,5), (5,470), (300,200), (420, 300)]
    for x, y in bg_samples:
        rp = tuple(rust[y, x])
        print(f"  ({x},{y}): {rp}")

    # Check reference background color consistency
    print(f"\n=== Reference background color samples ===")
    for x, y in bg_samples:
        fp = tuple(ref[y, x])
        print(f"  ({x},{y}): {fp}")

if __name__ == "__main__":
    main()
