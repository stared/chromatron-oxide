# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow", "numpy"]
# ///
"""Compare text widths between our framebuffer and the reference."""
import numpy as np
from PIL import Image

GAME_SIZE = (640, 480)

def find_game_area(arr):
    gray = np.all(np.abs(arr.astype(int) - 164) <= 5, axis=2)
    rows = np.any(gray, axis=1)
    cols = np.any(gray, axis=0)
    if not rows.any() or not cols.any():
        return 0, 0, arr.shape[1], arr.shape[0]
    y1 = int(np.argmax(rows))
    y2 = int(arr.shape[0] - np.argmax(rows[::-1]))
    x1 = int(np.argmax(cols))
    x2 = int(arr.shape[1] - np.argmax(cols[::-1]))
    return x1, y1, x2 - x1, y2 - y1

def normalize(path):
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    x, y, w, h = find_game_area(arr)
    print(f"  {path}: raw={arr.shape[1]}x{arr.shape[0]}, gray=({x},{y})+{w}x{h}")
    cropped = arr[y:y+h, x:x+w]
    ch, cw = cropped.shape[:2]
    if abs(cw - 1280) < 20 and abs(ch - 960) < 20:
        cropped = np.array(Image.fromarray(cropped).resize(GAME_SIZE, Image.BOX))
        ch, cw = cropped.shape[:2]
    result = np.full((480, 640, 3), 164, dtype=np.uint8)
    ph, pw = min(ch, 480), min(cw, 640)
    result[:ph, :pw] = cropped[:ph, :pw]
    return result

ours = normalize("screenshots/framebuffer_1771418725.png")
ref = normalize("screenshots/15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png")

ours_text = np.all(ours < 50, axis=2)
ref_text = np.all(ref < 50, axis=2)

# Compare "freeware"
print("\n=== 'freeware' ===")
for name, img_text in [("Ours", ours_text), ("Ref", ref_text)]:
    for y in range(448, 470):
        row = img_text[y, 0:80]
        if row.any():
            positions = np.where(row)[0]
            print(f"  {name} y={y}: x={positions[0]}-{positions[-1]} ({len(positions)} px)")

# Compare "silverspaceship.com"
print("\n=== 'silverspaceship.com' ===")
for name, img_text in [("Ours", ours_text), ("Ref", ref_text)]:
    for y in range(448, 470):
        row = img_text[y, 460:640]
        if row.any():
            positions = np.where(row)[0] + 460
            print(f"  {name} y={y}: x={positions[0]}-{positions[-1]} ({len(positions)} px)")

# Compare instruction text first line
print("\n=== Instruction text (line by line) ===")
for name, img_text in [("Ours", ours_text), ("Ref", ref_text)]:
    print(f"\n{name}:")
    in_line = False
    line_start = 0
    line_num = 0
    for y in range(125, 300):
        row = img_text[y, 450:620]
        has_text = row.sum() > 3
        if has_text and not in_line:
            in_line = True
            line_start = y
        elif not has_text and in_line:
            in_line = False
            line_num += 1
            # Find bounds
            min_x = 620
            max_x = 450
            for yy in range(line_start, y):
                row = img_text[yy, 450:620]
                if row.any():
                    pos = np.where(row)[0] + 450
                    min_x = min(min_x, pos[0])
                    max_x = max(max_x, pos[-1])
            print(f"  Line {line_num}: y={line_start}-{y}, x={min_x}-{max_x} ({max_x-min_x+1}px)")
    if in_line:
        line_num += 1
        min_x = 620
        max_x = 450
        for yy in range(line_start, 300):
            row = img_text[yy, 450:620]
            if row.any():
                pos = np.where(row)[0] + 450
                min_x = min(min_x, pos[0])
                max_x = max(max_x, pos[-1])
        print(f"  Line {line_num}: y={line_start}-{300}, x={min_x}-{max_x} ({max_x-min_x+1}px)")
