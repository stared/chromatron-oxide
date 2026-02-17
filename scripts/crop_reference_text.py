# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""
Crop instruction text regions from Windows reference screenshots.

Uses numpy to count near-black pixels per row to find exact text boundaries.
- Text is black on gray → near-black pixels present
- Toolbox icons are medium-dark gray (~102) → NOT near-black
- Level numbers are colored but also near-black → separated by large gap
We take only the FIRST contiguous block of text rows (instruction text),
ignoring the level numbers below.
"""

from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

PROJECT = Path(__file__).resolve().parent.parent
OUTDIR = PROJECT / "font_lab"

# Instruction text rect from render.rs: (left=450, top=125, right=620, bottom=475)
LEFT, TOP, RIGHT, BOTTOM = 450, 125, 620, 475

# Reference screenshots with instruction text visible
REFS = {
    "level1": {
        "file": "15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png",
        "text": "Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel.",
    },
    "level3_colors": {
        "file": "15688228-chromatron-windows-level-3-rgb-to-cmy-conversion.png",
        "text": "Some pinwheels require multiple lasers to light them up. You get magenta from red and blue. Yellow is formed by green plus red. Combining green and blue yields a color known variously as cyan, teal, or aqua.",
    },
    "level4_splitter": {
        "file": "15870999-chromatron-windows-level-4-introduction-of-splitter.png",
        "text": "If a laser hits a SPLITTER at the correct angle, it bounces off at an angle and also goes straight through. If it hits head on, it just goes through.",
    },
}

BLACK_THRESHOLD = 40   # pixels darker than this are "near-black" (text)
MIN_BLACK_PER_ROW = 4  # ignore rows with fewer (stray artifacts / mouse cursor)
GAP_THRESHOLD = 20     # rows of silence that separate text blocks


def find_text_block(panel_arr: np.ndarray) -> tuple[int, int]:
    """Find the first contiguous block of rows containing black text.

    Returns (first_row, last_row) of the instruction text, excluding
    level numbers at the bottom which are separated by a large gap.
    """
    gray = np.min(panel_arr, axis=2)  # min channel — true black has all channels near 0
    black_count = np.sum(gray < BLACK_THRESHOLD, axis=1)  # per-row count

    # Only consider rows with enough near-black pixels (filters stray artifacts)
    text_mask = black_count >= MIN_BLACK_PER_ROW
    text_rows = np.where(text_mask)[0]

    if len(text_rows) == 0:
        print("  WARNING: No text rows detected!")
        return 0, panel_arr.shape[0]

    # Split into contiguous blocks separated by gaps > GAP_THRESHOLD
    gaps = np.diff(text_rows)
    split_points = np.where(gaps > GAP_THRESHOLD)[0]

    if len(split_points) > 0:
        # Take only the first block (instruction text)
        first_block_end = split_points[0]
        block_rows = text_rows[:first_block_end + 1]
        print(f"  Found {len(split_points) + 1} text blocks, taking first one")
        print(f"  Block 1: rows {text_rows[0]}..{text_rows[first_block_end]} (instruction text)")
        for i, sp in enumerate(split_points):
            next_start = sp + 1
            next_end = split_points[i + 1] if i + 1 < len(split_points) else len(text_rows) - 1
            print(f"  Block {i+2}: rows {text_rows[next_start]}..{text_rows[next_end]} (skipped — level numbers)")
    else:
        block_rows = text_rows
        print(f"  Single text block: rows {text_rows[0]}..{text_rows[-1]}")

    return int(block_rows[0]), int(block_rows[-1])


def crop_text_region(ref_key: str, ref_info: dict) -> None:
    filepath = PROJECT / "screenshots" / ref_info["file"]
    if not filepath.exists():
        print(f"SKIP {ref_key}: {filepath.name} not found")
        return

    print(f"\n{'='*60}")
    print(f"Processing: {ref_key}")

    img = Image.open(filepath)
    panel = img.crop((LEFT, TOP, RIGHT, BOTTOM))
    panel_arr = np.array(panel)
    print(f"  Panel: ({LEFT},{TOP})→({RIGHT},{BOTTOM}) = {panel.size}")

    first_text, last_text = find_text_block(panel_arr)
    print(f"  Text bounds: row {first_text} (y={TOP+first_text}) → row {last_text} (y={TOP+last_text})")

    # Small margin around text
    margin = 2
    crop_top = max(0, first_text - margin)
    crop_bottom = min(panel_arr.shape[0], last_text + margin + 1)

    text_crop = panel.crop((0, crop_top, panel.width, crop_bottom))
    print(f"  Crop: rows {crop_top}..{crop_bottom} → {text_crop.size[0]}×{text_crop.size[1]}px")

    out_path = OUTDIR / f"reference_crop_{ref_key}.png"
    text_crop.save(out_path)
    print(f"  → {out_path.name}")

    # Debug image: full panel with red crop lines
    debug = panel.copy()
    draw = ImageDraw.Draw(debug)
    draw.line([(0, crop_top), (panel.width - 1, crop_top)], fill="red", width=1)
    draw.line([(0, crop_bottom), (panel.width - 1, crop_bottom)], fill="red", width=1)
    debug_path = OUTDIR / f"reference_debug_{ref_key}.png"
    debug.save(debug_path)
    print(f"  → {debug_path.name} (debug)")


if __name__ == "__main__":
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for key, info in REFS.items():
        crop_text_region(key, info)
    print("\nDone!")
