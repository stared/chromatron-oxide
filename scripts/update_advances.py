# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Update advance widths in ms_sans_serif.rs from final_widths.json."""
import json
import re

# Load corrected advance widths
with open("scripts/final_widths.json") as f:
    widths = json.load(f)

# Build advance lookup by char code
advances = {}
for ch, w in widths.items():
    advances[ord(ch)] = w

# Read the Rust file
with open("src/ms_sans_serif.rs") as f:
    content = f.read()

# Replace advance values in GlyphData lines
# Pattern: "advance:  X," followed by "// NNN 'c'" at end of line
def replace_advance(m):
    prefix = m.group(1)
    old_advance = int(m.group(2))
    suffix = m.group(3)
    char_code = int(m.group(4))
    new_advance = advances.get(char_code, old_advance)
    return f"{prefix}{new_advance:2d}{suffix}{char_code}"

pattern = r'(GlyphData \{ advance: )(\s*\d+)(,.+//\s+)(\d+)'
new_content = re.sub(pattern, replace_advance, content)

# Verify changes
old_lines = content.split('\n')
new_lines = new_content.split('\n')
changed = 0
for o, n in zip(old_lines, new_lines):
    if o != n:
        changed += 1
        # Extract the char code from the comment
        m = re.search(r'// +(\d+)', n)
        code = int(m.group(1)) if m else 0
        old_adv = re.search(r'advance: +(\d+)', o)
        new_adv = re.search(r'advance: +(\d+)', n)
        print(f"  {code:3d} {repr(chr(code)):>5}: {old_adv.group(1):>2} -> {new_adv.group(1):>2}")

print(f"\nChanged {changed} of 95 glyphs")

with open("src/ms_sans_serif.rs", "w") as f:
    f.write(new_content)

print("Written: src/ms_sans_serif.rs")
