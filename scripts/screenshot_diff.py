"""Compare a Rust recompilation screenshot against the original reference.
Uses numpy to compute per-pixel difference and generates a visual diff image.

Handles:
- macOS Retina 2x screenshots (downscales to 1x)
- Window chrome cropping (finds game content by gray background color)
- Different-sized reference screenshots

Usage: uv run scripts/screenshot_diff.py <rust_screenshot> <reference_screenshot> [output_diff]
"""
import sys
import os
import numpy as np
from PIL import Image

# Game background color: RGB(164, 164, 164)
BG_COLOR = np.array([164, 164, 164], dtype=np.uint8)
GAME_SIZE = (640, 480)


def find_content_rect(img_arr: np.ndarray, bg_color: np.ndarray, tolerance: int = 10) -> tuple[int, int, int, int]:
    """Find the bounding box of the game content area by looking for the gray background.
    Returns (x, y, w, h)."""
    # Find pixels close to the background color
    dist = np.abs(img_arr.astype(np.int16) - bg_color.astype(np.int16)).sum(axis=2)
    bg_mask = dist < tolerance * 3  # tolerance per channel * 3 channels

    # Find the bounding box of background pixels
    rows = np.any(bg_mask, axis=1)
    cols = np.any(bg_mask, axis=0)

    if not rows.any() or not cols.any():
        # Fallback: use entire image
        return (0, 0, img_arr.shape[1], img_arr.shape[0])

    y_min = np.argmax(rows)
    y_max = img_arr.shape[0] - np.argmax(rows[::-1])
    x_min = np.argmax(cols)
    x_max = img_arr.shape[1] - np.argmax(cols[::-1])

    return (int(x_min), int(y_min), int(x_max - x_min), int(y_max - y_min))


def crop_to_game_area(img: Image.Image) -> Image.Image:
    """Crop image to just the 640x480 game content area."""
    arr = np.array(img)
    x, y, w, h = find_content_rect(arr, BG_COLOR)
    print(f"  Content rect: ({x},{y}) {w}x{h}")

    # Crop to content
    cropped = img.crop((x, y, x + w, y + h))

    # If it's approximately 2x the game size (Retina), downscale
    cw, ch = cropped.size
    if cw > GAME_SIZE[0] * 1.5 and ch > GAME_SIZE[1] * 1.5:
        print(f"  Retina detected ({cw}x{ch}), downscaling to {GAME_SIZE[0]}x{GAME_SIZE[1]}")
        cropped = cropped.resize(GAME_SIZE, Image.LANCZOS)
    elif (cw, ch) != GAME_SIZE:
        print(f"  Resizing from {cw}x{ch} to {GAME_SIZE[0]}x{GAME_SIZE[1]}")
        cropped = cropped.resize(GAME_SIZE, Image.LANCZOS)

    return cropped


def compare_screenshots(rust_path: str, ref_path: str, diff_path: str | None = None):
    print(f"Loading Rust screenshot: {rust_path}")
    rust_img = Image.open(rust_path).convert("RGB")
    print(f"  Raw size: {rust_img.size}")
    rust_img = crop_to_game_area(rust_img)

    print(f"Loading reference screenshot: {ref_path}")
    ref_img = Image.open(ref_path).convert("RGB")
    print(f"  Raw size: {ref_img.size}")
    ref_img = crop_to_game_area(ref_img)

    print(f"\nComparing at: {rust_img.size[0]}x{rust_img.size[1]}")

    rust_arr = np.array(rust_img, dtype=np.int16)
    ref_arr = np.array(ref_img, dtype=np.int16)

    # Per-pixel absolute difference
    diff = np.abs(rust_arr - ref_arr)

    # Statistics
    total_pixels = rust_arr.shape[0] * rust_arr.shape[1]
    identical_pixels = int(np.all(diff == 0, axis=2).sum())
    near_identical = int(np.all(diff <= 5, axis=2).sum())  # within 5 per channel
    pct_identical = 100.0 * identical_pixels / total_pixels
    pct_near = 100.0 * near_identical / total_pixels

    print(f"\n=== Pixel Diff Statistics ===")
    print(f"Total pixels:     {total_pixels:,}")
    print(f"Identical (exact): {identical_pixels:,} ({pct_identical:.1f}%)")
    print(f"Near-identical (±5): {near_identical:,} ({pct_near:.1f}%)")
    print(f"Different pixels:  {total_pixels - near_identical:,} ({100-pct_near:.1f}%)")
    print(f"Max channel diff:  {diff.max()}")
    print(f"Mean channel diff: {diff.mean():.2f}")

    # Per-channel breakdown
    for ch, name in enumerate(["Red", "Green", "Blue"]):
        ch_diff = diff[:, :, ch]
        print(f"  {name}: max={ch_diff.max()}, mean={ch_diff.mean():.2f}, "
              f"median={np.median(ch_diff):.0f}")

    # Generate diff image
    if diff_path is None:
        base = os.path.splitext(rust_path)[0]
        diff_path = f"{base}_diff.png"

    # Diff amplified 4x for visibility
    diff_amplified = np.clip(diff * 4, 0, 255).astype(np.uint8)

    # Heatmap: green=identical, red=different
    diff_magnitude = np.sqrt((diff.astype(np.float64) ** 2).sum(axis=2))
    heatmap = np.zeros_like(rust_arr, dtype=np.uint8)
    heatmap[:, :, 1] = np.where(diff_magnitude == 0, 128, 0)
    heatmap[:, :, 0] = np.clip(diff_magnitude * 4, 0, 255).astype(np.uint8)

    # 2x2 grid: ref|rust / diff|heatmap
    h, w = ref_arr.shape[:2]
    top = np.concatenate([ref_arr.astype(np.uint8), rust_arr.astype(np.uint8)], axis=1)
    bot = np.concatenate([diff_amplified, heatmap], axis=1)
    panel = np.concatenate([top, bot], axis=0)
    Image.fromarray(panel).save(diff_path)
    print(f"\nDiff image saved to: {diff_path}")
    print("Layout: [reference | rust] / [diff×4 | heatmap]")

    # Regional hotspots (game areas)
    regions = {
        "Main grid":    (60, 30, 360, 360),
        "Toolbox":      (460, 20, 156, 104),
        "Level nums":   (0, 400, 520, 50),
        "Instruction":  (460, 130, 170, 200),
        "Bottom text":  (0, 440, 640, 40),
    }
    print(f"\n=== Regional Analysis ===")
    for name, (rx, ry, rw, rh) in regions.items():
        rx2 = min(rx + rw, w)
        ry2 = min(ry + rh, h)
        region_diff = diff[ry:ry2, rx:rx2]
        region_mag = diff_magnitude[ry:ry2, rx:rx2]
        region_total = (ry2 - ry) * (rx2 - rx)
        region_identical = int(np.all(region_diff == 0, axis=2).sum())
        pct = 100.0 * region_identical / max(region_total, 1)
        print(f"  {name:15s}: {pct:5.1f}% identical, mean_diff={region_mag.mean():.1f}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: uv run scripts/screenshot_diff.py <rust_screenshot> <reference> [output_diff]")
        sys.exit(1)

    rust_path = sys.argv[1]
    ref_path = sys.argv[2]
    diff_path = sys.argv[3] if len(sys.argv) > 3 else None
    compare_screenshots(rust_path, ref_path, diff_path)
