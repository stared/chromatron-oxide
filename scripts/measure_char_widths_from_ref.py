# /// script
# requires-python = ">=3.13"
# dependencies = ["Pillow", "numpy"]
# ///
"""
Determine the actual MS Sans Serif 8pt character advance widths by analyzing
known text strings in the reference screenshot.

Known text strings and their positions:
- "freeware" at (0, 450) -> 55px wide in reference
- "silverspaceship.com" at (470, 450) -> 133px wide in reference
- Instruction text lines with known content

From the reference instruction text for Level 1:
"Drag the REFLECTOR in the toolbox above onto the board and place it in
front of the laser beam. Click on it to rotate it. Position the mirror
so that the laser beam is reflected into the pinwheel."

Reference line widths (from normalized coords, text starts at ~451):
Line 1: "Drag the REFLECTOR in" -> 154px (x=451-604)
Line 3: "the toolbox above onto" -> 147px (x=450-596)
Line 4: "the board and place it in" -> 155px (x=450-604)
Line 5: "front of the laser beam." -> 149px (x=450-598)
Line 6: "Click on it to rotate it." -> 134px (x=451-584)
Line 7: "Position the" -> 167px? No that's too wide...

Actually wait, let me reconsider the line content.
"""
import numpy as np
from PIL import Image

# First figure out exactly what text is on each line using word-wrap analysis
# The rect is 170px wide (620-450)

# From the reference, the text lines have these widths:
# Line 1: 154px
# Line 2: 6px  (just "j" descender or artifact?)
# Line 3: 147px
# Line 4: 155px
# Line 5: 149px
# Line 6: 134px
# Line 7: 167px
# Line 8: 112px
# Line 9: 106px
# Line 10: 60px

# The instruction text:
text = "Drag the REFLECTOR in the toolbox above onto the board and place it in front of the laser beam. Click on it to rotate it. Position the mirror so that the laser beam is reflected into the pinwheel."

# If we assume the rect_width is 170, let's figure out what character widths
# would produce the known line breaks. The reference shows 9 real text lines.

# From the comparison image, the reference lines are:
# 1: "Drag the REFLECTOR in"
# 2: "the toolbox above onto"
# 3: "the board and place it in"
# 4: "front of the laser beam."
# 5: "Click on it to rotate it."
# 6: "Position the"
# 7: "mirror so that"
# 8: "the laser beam is"
# 9: "reflected into the"
# 10: "pinwheel."

# Wait, that's 10 lines. Let me recount from reference image.
# Line 1: 154px -> could be "Drag the REFLECTOR in" (21 chars + spaces)
# Line 2: 6px -> too small, probably JPEG artifact from above
# Line 3-10: actual text lines

# Let me reconsider: the compare image showed 9 lines of text in the reference.
# Let me count again from the line analysis:
# Line 1: y=128, 154px  -> first text line
# Line 2: y=139, 6px    -> this is just 2px tall, likely an artifact of "j" descender
# Lines 3-10 follow at 16px spacing

# So skipping line 2 (artifact), lines at y=128, 144, 160, 176, 192, 208, 224, 240, 256
# That's 9 lines with 16px spacing (128, 144=128+16, 160=144+16, etc.)

# The instruction text word-wrapped should be:
lines_text = [
    "Drag the REFLECTOR in",           # line 1: 154px
    "the toolbox above onto",           # line 2: 147px
    "the board and place it in",        # line 3: 155px
    "front of the laser beam.",         # line 4: 149px
    "Click on it to rotate it.",        # line 5: 134px
    "Position the mirror so that",      # line 6: 167px
    "the laser beam is",                # line 7: 112px
    "reflected into the",               # line 8: 106px
    "pinwheel.",                         # line 9: 60px
]

ref_widths = [154, 147, 155, 149, 134, 167, 112, 106, 60]

# Let me solve for character widths.
# For MS Sans Serif 8pt, I know from Windows documentation:
# Space = 4px (this is key!)
# Most lowercase = 6px, some = 4-5px
# Most uppercase = 8px, some = 6-7px

# Let me try standard MS Sans Serif 8pt widths
# These are from the actual Windows font (not Wine's version)
win_widths = {
    ' ': 4,  # tmBreakChar width = 4
    'a': 6, 'b': 6, 'c': 5, 'd': 6, 'e': 6, 'f': 4, 'g': 6, 'h': 6,
    'i': 2, 'j': 4, 'k': 6, 'l': 2, 'm': 8, 'n': 6, 'o': 6, 'p': 6,
    'q': 6, 'r': 4, 's': 5, 't': 4, 'u': 6, 'v': 6, 'w': 8, 'x': 6,
    'y': 6, 'z': 5,
    'A': 8, 'B': 8, 'C': 7, 'D': 8, 'E': 7, 'F': 6, 'G': 8, 'H': 8,
    'I': 4, 'J': 5, 'K': 8, 'L': 6, 'M': 10, 'N': 8, 'O': 8, 'P': 8,
    'Q': 8, 'R': 8, 'S': 7, 'T': 8, 'U': 8, 'V': 8, 'W': 12, 'X': 8,
    'Y': 8, 'Z': 8,
    '.': 4, ',': 4, '!': 4, '?': 6, '-': 4, '(': 4, ')': 4, '@': 12,
    ':': 4, ';': 4, '"': 5, "'": 2, '/': 6, '\\': 6,
    '0': 6, '1': 6, '2': 6, '3': 6, '4': 6, '5': 6, '6': 6, '7': 6, '8': 6, '9': 6,
}

def measure(text, widths):
    return sum(widths.get(ch, 6) for ch in text)

print("Testing Windows MS Sans Serif widths:")
for text, ref_w in zip(lines_text, ref_widths):
    w = measure(text, win_widths)
    print(f"  '{text}' -> {w}px (ref: {ref_w}px, diff: {w-ref_w:+d})")

# Check other known strings
print(f"\n'freeware' = {measure('freeware', win_widths)}px (ref: 55px)")
print(f"'silverspaceship.com' = {measure('silverspaceship.com', win_widths)}px (ref: 133px)")

# Now check: would "Drag the REFLECTOR in the" fit in 170px?
print(f"\n'Drag the REFLECTOR in the' = {measure('Drag the REFLECTOR in the', win_widths)}px (rect: 170px)")
print(f"'Drag the REFLECTOR in' = {measure('Drag the REFLECTOR in', win_widths)}px")

# Try a few adjustments to get closer
# What if the space width is 3?
print("\n--- With space=3 ---")
widths3 = dict(win_widths)
widths3[' '] = 3
for text, ref_w in zip(lines_text, ref_widths):
    w = measure(text, widths3)
    print(f"  '{text}' -> {w}px (ref: {ref_w}px, diff: {w-ref_w:+d})")
