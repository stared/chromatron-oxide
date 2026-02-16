"""Convert a BMP file to PNG for viewing."""
import sys
from PIL import Image

bmp_path = sys.argv[1]
png_path = bmp_path.replace(".bmp", ".png")
Image.open(bmp_path).save(png_path)
print(f"Converted: {png_path}")
