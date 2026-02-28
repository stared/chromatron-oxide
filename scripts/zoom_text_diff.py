# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow", "numpy"]
# ///
"""Zoom into instruction text area and show detailed diff."""
import numpy as np
from PIL import Image

REF = "screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png"
OURS = "screenshots/framebuffer_1771431637.png"
OUT = "screenshots/text_diff_zoom.png"

ref = np.array(Image.open(REF).convert("RGB"))
ours = np.array(Image.open(OURS).convert("RGB"))

# Instruction text region: x=[450,620], y=[128,280]
# Also bottom text: y=[450,465]
x1, x2 = 440, 630
y1, y2 = 120, 285

ref_crop = ref[y1:y2, x1:x2]
ours_crop = ours[y1:y2, x1:x2]

# Build diff image: reference, ours, overlay
diff_mask = np.any(ref_crop != ours_crop, axis=2)
n_diff = np.sum(diff_mask)
total = diff_mask.size
print(f"Instruction text area: {total - n_diff}/{total} identical ({100*(1-n_diff/total):.1f}%)")
print(f"Different pixels: {n_diff}")

# Create overlay: ours with magenta for ref-only pixels, cyan for ours-only pixels
overlay = ours_crop.copy()
ref_black = np.all(ref_crop == [0,0,0], axis=2)
ours_black = np.all(ours_crop == [0,0,0], axis=2)
# Pixels black in ref but not in ours = magenta (we're missing these)
missing = ref_black & ~ours_black
overlay[missing] = [255, 0, 255]
# Pixels black in ours but not in ref = cyan (we have extra)
extra = ours_black & ~ref_black
overlay[extra] = [0, 255, 255]

print(f"Missing pixels (in ref, not ours): {np.sum(missing)}")
print(f"Extra pixels (in ours, not ref): {np.sum(extra)}")

# Scale up 3x for visibility
scale = 3
h, w = ref_crop.shape[:2]
canvas = Image.new("RGB", (w * 3 * scale + 20, h * scale + 40), (40, 40, 40))

# Labels
from PIL import ImageDraw
draw = ImageDraw.Draw(canvas)
labels = ["REFERENCE", "OURS", "DIFF (magenta=missing, cyan=extra)"]
for i, label in enumerate(labels):
    draw.text((i * (w * scale + 10) + 5, 5), label, fill=(200, 200, 200))

for i, img_arr in enumerate([ref_crop, ours_crop, overlay]):
    pil = Image.fromarray(img_arr)
    pil = pil.resize((w * scale, h * scale), Image.NEAREST)
    canvas.paste(pil, (i * (w * scale + 10), 25))

canvas.save(OUT)
print(f"Saved: {OUT}")

# Per-row analysis
print("\n=== Per-row diff (y relative to crop) ===")
for y in range(h):
    row_missing = np.sum(missing[y])
    row_extra = np.sum(extra[y])
    if row_missing > 0 or row_extra > 0:
        abs_y = y + y1
        print(f"  y={abs_y:3d} (rel {y:3d}): missing={row_missing:3d} extra={row_extra:3d}")
