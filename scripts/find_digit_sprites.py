"""Find the digit sprite pointer array in the binary.
The decompiled code references digit_sprite_ptrs[10] for rendering level numbers.
"""
import struct, os

binary = os.path.join(os.path.dirname(__file__), "..", "originals", "chromatron_unpacked.exe")
with open(binary, 'rb') as f:
    pe_data = f.read()

pe_offset = struct.unpack_from('<I', pe_data, 0x3C)[0]
image_base = struct.unpack_from('<I', pe_data, pe_offset + 0x34)[0]
num_sections = struct.unpack_from('<H', pe_data, pe_offset + 6)[0]
optional_hdr_size = struct.unpack_from('<H', pe_data, pe_offset + 20)[0]
section_offset = pe_offset + 24 + optional_hdr_size
sections = []
for i in range(num_sections):
    off = section_offset + i * 40
    va = struct.unpack_from('<I', pe_data, off + 12)[0]
    raw_ptr = struct.unpack_from('<I', pe_data, off + 20)[0]
    raw_size = struct.unpack_from('<I', pe_data, off + 16)[0]
    sections.append({'va': va, 'raw_ptr': raw_ptr, 'raw_size': raw_size})

def va_to_offset(va_addr):
    rva = va_addr - image_base
    for s in sections:
        if s['va'] <= rva < s['va'] + s['raw_size']:
            return rva - s['va'] + s['raw_ptr']
    return None

def read_u32(va):
    off = va_to_offset(va)
    if off is None:
        return None
    return struct.unpack('<I', pe_data[off:off+4])[0]

# The decompiled code references draw_number_string at 0x004031a0
# which uses digit sprite pointers. Let's search around the sprite pointer area.
# Sprite pointers are at 0x00415734. The digit sprites might be nearby.

# Check the function at 0x004031a0 for references to data addresses
# by reading the decompiled C
decomp_path = os.path.join(os.path.dirname(__file__), "..", "decompiled", "chromatron_unpacked_decompiled.c")
with open(decomp_path) as f:
    decomp = f.read()

# Find the function around 0x4031a0
idx = decomp.find("004031")
if idx >= 0:
    # Print 40 lines of context
    start = max(0, decomp.rfind('\n', 0, idx))
    end = decomp.find('\n', idx)
    for _ in range(40):
        next_end = decomp.find('\n', end + 1)
        if next_end < 0:
            break
        end = next_end
    print("Decompiled code around 0x4031a0:")
    print(decomp[start:end])
    print()

# Also search for DAT_00415 references that might be digit ptrs
# The sprite_count is at 0x00415c34, sprite ptrs at 0x00415734
# Digit pointers might be at a nearby address
for search_addr_str in ["004157", "00415c", "0040b1", "0040b2"]:
    for match_start in range(len(decomp)):
        match_start = decomp.find(f"DAT_{search_addr_str}", match_start)
        if match_start < 0:
            break
        # Print some context
        line_start = decomp.rfind('\n', 0, match_start) + 1
        line_end = decomp.find('\n', match_start)
        line = decomp[line_start:line_end].strip()
        if "digit" in line.lower() or "number" in line.lower() or "num" in line.lower():
            print(f"Found: {line}")
        match_start = line_end
