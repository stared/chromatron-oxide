# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""Inspect a chroma.dat save file."""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "chroma.dat"
data = open(path, "rb").read()
print(f"File: {path} ({len(data)} bytes)")

# Magic
magic = data[0:4]
print(f"Magic: {magic!r} ({'OK' if magic == b'CHR\x01' else 'BAD'})")

# Current level
current = data[4]
print(f"Current level: {current}")

# Level completed bitfield (7 bytes = 56 bits, 50 used)
completed = []
for i in range(50):
    byte_idx = 5 + i // 8
    bit_idx = i % 8
    if data[byte_idx] & (1 << bit_idx):
        completed.append(i)
print(f"Completed levels ({len(completed)}): {completed}")

# Num saved levels
num_saved = data[12]
print(f"Saved level states: {num_saved}")

pos = 13
for s in range(num_saved):
    level_idx = data[pos]
    pos += 1
    # Skip grid (675 bytes)
    pos += 675
    tb_count = data[pos]
    pos += 1
    # Skip toolbox
    pos += tb_count * 3
    print(f"  Level {level_idx}: toolbox={tb_count} pieces")

print(f"Bytes consumed: {pos}/{len(data)}")
