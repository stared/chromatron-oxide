# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py"]
# ///
"""Survey advance widths from all available font sources.

For each font, extract advance widths for ASCII 32-126.
Prints a comparison table so we can see which source matches
the original Windows MS Sans Serif character widths.
"""
import freetype
import json
from pathlib import Path

FONTS = {
    "sserife.fon": {"path": "assets/fonts/sserife.fon", "face_idx": 0, "size": None, "is_fon": True},
    "ms_sans_serif.ttf@11": {"path": "assets/fonts/ms_sans_serif.ttf", "face_idx": 0, "size": 11, "is_fon": False},
    "ms_sans_serif.ttf@13": {"path": "assets/fonts/ms_sans_serif.ttf", "face_idx": 0, "size": 13, "is_fon": False},
    "ms_sans_serif.ttf@8pt96": {"path": "assets/fonts/ms_sans_serif.ttf", "face_idx": 0, "size_pt": 8, "dpi": 96, "is_fon": False},
    "Geneva.ttf@13": {"path": "assets/fonts/Geneva.ttf", "face_idx": 0, "size": 13, "is_fon": False},
    "W95font.otf@11": {"path": "assets/fonts/W95font.otf", "face_idx": 0, "size": 11, "is_fon": False},
    "W95font.otf@13": {"path": "assets/fonts/W95font.otf", "face_idx": 0, "size": 13, "is_fon": False},
    "W95font.otf@8pt96": {"path": "assets/fonts/W95font.otf", "face_idx": 0, "size_pt": 8, "dpi": 96, "is_fon": False},
}

# Also try loading ms_sans_serif.ttf faces 1+ if they exist
try:
    face_test = freetype.Face("assets/fonts/ms_sans_serif.ttf", 1)
    FONTS["ms_sans_serif.ttf:1@13"] = {"path": "assets/fonts/ms_sans_serif.ttf", "face_idx": 1, "size": 13, "is_fon": False}
except Exception:
    pass

results = {}

for name, cfg in FONTS.items():
    path = cfg["path"]
    if not Path(path).exists():
        print(f"SKIP {name}: file not found")
        continue
    try:
        face = freetype.Face(path, cfg["face_idx"])

        if cfg["is_fon"]:
            face.select_size(0)
        elif "size_pt" in cfg:
            face.set_char_size(cfg["size_pt"] * 64, 0, cfg["dpi"], 0)
        else:
            face.set_pixel_sizes(0, cfg["size"])

        # Set charmap
        if face.num_charmaps > 0:
            face.set_charmap(face.charmaps[0])

        widths = {}
        for code in range(32, 127):
            ch = chr(code)
            face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
            adv = face.glyph.advance.x >> 6
            widths[ch] = adv

        results[name] = widths
        total = sum(widths.values())
        space_w = widths.get(' ', '?')
        print(f"OK   {name:30s}: space={space_w}, total_advance={total}, height={face.size.height >> 6}")

    except Exception as e:
        print(f"FAIL {name}: {e}")

# Print comparison table for key characters
key_chars = list(" !\"().,-:;ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
font_names = list(results.keys())

print("\n=== Advance Width Comparison Table ===\n")
header = f"{'Char':>5}"
for fn in font_names:
    short = fn[:12]
    header += f" {short:>12}"
print(header)
print("-" * len(header))

for ch in key_chars:
    row = f"  {repr(ch):>3}"
    for fn in font_names:
        w = results[fn].get(ch, '?')
        row += f" {w:>12}"
    print(row)

# Print specific text widths for verification
print("\n=== Text Width Comparison ===\n")
test_strings = [
    "freeware",
    "silverspaceship.com",
    "Drag the REFLECTOR in",
    "the toolbox above onto",
    "the board and place it in",
    "front of the laser beam.",
    "Click on it to rotate it.",
    "Position the mirror so that",
    "the laser beam is",
    "reflected into the",
    "pinwheel.",
    "Drag the REFLECTOR in the",  # what our font wraps as line 1
    "You win!",
    "(won)",
]

header = f"{'Text':>35}"
for fn in font_names:
    short = fn[:12]
    header += f" {short:>12}"
print(header)
print("-" * len(header))

for text in test_strings:
    row = f"{text:>35}"
    for fn in font_names:
        w = sum(results[fn].get(ch, 6) for ch in text)
        row += f" {w:>12}"
    print(row)

# Word-wrap simulation with each font
print("\n=== Word-Wrap Simulation (rect_width=170) ===\n")
instruction = "Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel."

for fn in font_names:
    widths = results[fn]
    def measure(text):
        return sum(widths.get(ch, 6) for ch in text)

    words = instruction.split()
    line = ""
    lines = []
    for word in words:
        test = f"{line} {word}" if line else word
        if line and measure(test) > 170:
            lines.append(line)
            line = word
        else:
            line = test
    if line:
        lines.append(line)

    print(f"{fn} ({len(lines)} lines):")
    for i, ln in enumerate(lines):
        print(f"  {i+1}. [{measure(ln):3d}px] {ln}")
    print()

# Save all results as JSON for use by other scripts
output = {name: {ch: w for ch, w in widths.items()} for name, widths in results.items()}
with open("scripts/font_widths.json", "w") as f:
    json.dump(output, f, indent=2)
print("Saved: scripts/font_widths.json")
