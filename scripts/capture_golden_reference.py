# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""Convert a 640x480 BMP framebuffer to raw u32 golden reference (0x00RRGGBB format).

Usage: uv run scripts/capture_golden_reference.py <input.bmp> [output.bin]

Output defaults to tests/golden_reference.bin
"""
import sys
import struct
from pathlib import Path
from PIL import Image

def main():
    if len(sys.argv) < 2:
        print("Usage: uv run scripts/capture_golden_reference.py <input.bmp> [output.bin]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("tests/golden_reference.bin")

    img = Image.open(input_path).convert("RGB")
    assert img.size == (640, 480), f"Expected 640x480, got {img.size}"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to 0x00RRGGBB u32 format (little-endian)
    pixels = img.load()
    with open(output_path, "wb") as f:
        for y in range(480):
            for x in range(640):
                r, g, b = pixels[x, y]
                val = (r << 16) | (g << 8) | b
                f.write(struct.pack("<I", val))

    size = output_path.stat().st_size
    print(f"Written {size} bytes to {output_path}")
    assert size == 640 * 480 * 4, f"Expected {640*480*4}, got {size}"
    print("Golden reference captured successfully.")

if __name__ == "__main__":
    main()
