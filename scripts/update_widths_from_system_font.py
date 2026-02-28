# /// script
# requires-python = ">=3.13"
# dependencies = ["freetype-py", "numpy"]
# ///
"""Replace final_widths.json with native advance widths from vgasys.fon.

Also verifies that line breaks match for all 4 level texts.
"""
import json
import freetype

SYS_FON = "assets/fonts/vgasys.fon"
WIDTHS_PATH = "scripts/final_widths.json"

# Load current widths for comparison
with open(WIDTHS_PATH) as f:
    old_advances = json.load(f)

# Load System font native advances
face = freetype.Face(SYS_FON, 0)
face.select_size(0)
face.set_charmap(face.charmaps[0])

new_advances = {}
for code in range(32, 127):
    ch = chr(code)
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    adv = face.glyph.advance.x // 64
    new_advances[ch] = adv

# Compare
print("=== Advance width changes ===")
changes = 0
for code in range(32, 127):
    ch = chr(code)
    old = old_advances.get(ch, 0)
    new = new_advances[ch]
    if old != new:
        print(f"  {code:3d} '{ch}': {old} -> {new} ({'+' if new > old else ''}{new - old})")
        changes += 1
print(f"\n{changes} changes out of 95")

# Word wrap function
def word_wrap(text, max_width, advances):
    words = text.split(' ')
    lines = []
    current = ""
    width = 0
    space_w = advances.get(' ', 4)
    for word in words:
        word_w = sum(advances.get(ch, 8) for ch in word)
        if current:
            test_w = width + space_w + word_w
            if test_w > max_width:
                lines.append(current)
                current = word
                width = word_w
            else:
                current += " " + word
                width = test_w
        else:
            current = word
            width = word_w
    if current:
        lines.append(current)
    return lines

# Verify line breaks for all level texts
RECT_WIDTH = 170
TEXTS = {
    "Level 1": "Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel.",
    "Level 2 (won)": "Click on a level or press spacebar for next.",
    "Level 3": "Some pinwheels require multiple lasers to light them up. You get magenta from red and blue. Yellow is formed by green plus red. Combining green and blue yields a color known variously as cyan, teal, or aqua.",
    "Level 4": "If a laser hits a SPLITTER at the correct angle, it bounces off at an angle and also goes straight through. If it hits head on, it just goes through.",
}

print("\n=== Line break verification ===")
all_match = True
for name, text in TEXTS.items():
    old_lines = word_wrap(text, RECT_WIDTH, old_advances)
    new_lines = word_wrap(text, RECT_WIDTH, new_advances)

    match = old_lines == new_lines
    if not match:
        all_match = False
        print(f"\n  {name}: MISMATCH!")
        print(f"    Old ({len(old_lines)} lines):")
        for i, line in enumerate(old_lines):
            w = sum(old_advances.get(ch, 0) for ch in line)
            print(f"      {i+1}: \"{line}\" ({w}px)")
        print(f"    New ({len(new_lines)} lines):")
        for i, line in enumerate(new_lines):
            w = sum(new_advances.get(ch, 0) for ch in line)
            print(f"      {i+1}: \"{line}\" ({w}px)")
    else:
        print(f"  {name}: OK ({len(new_lines)} lines)")
        for i, line in enumerate(new_lines):
            w = sum(new_advances.get(ch, 0) for ch in line)
            print(f"    {i+1}: \"{line}\" ({w}px)")

if all_match:
    print("\nAll line breaks match! Safe to update.")
else:
    print("\nWARNING: Some line breaks changed!")

# Write new widths
with open(WIDTHS_PATH, 'w') as f:
    json.dump(new_advances, f, indent=2, ensure_ascii=False)
print(f"\nWrote {WIDTHS_PATH}")
