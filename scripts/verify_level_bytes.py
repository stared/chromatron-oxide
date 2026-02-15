"""Verify raw 5-byte level piece records from binary.
Check if rotation and color fields are swapped in extraction.
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
    raise ValueError(f"VA 0x{va_addr:08x} not mapped")

def read_bytes(va, n):
    off = va_to_offset(va)
    return pe_data[off:off+n]

def read_u32(va):
    return struct.unpack('<I', read_bytes(va, 4))[0]

# Level order
level_order = list(read_bytes(0x0040b168, 50))
print(f"Level order[0] = {level_order[0]}  (game level 1 → data index {level_order[0]})")

# Read level data pointer for data index 1
grid_ptr = read_u32(0x0040e65c + level_order[0] * 4)
print(f"Grid data pointer: 0x{grid_ptr:08x}")

# Read raw 5-byte records
print(f"\nRaw 5-byte records for level 1 (data index {level_order[0]}):")
print(f"{'byte0':>6} {'byte1':>6} {'byte2':>6} {'byte3':>6} {'byte4':>6}  (interpretation)")
for i in range(10):
    rec = read_bytes(grid_ptr + i * 5, 5)
    if rec[0] == 0:
        print(f"  {rec[0]:5d} -- end sentinel --")
        break
    piece_names = {1:'Wall', 2:'Laser', 3:'Reflector', 4:'Bender', 5:'Filter',
                   6:'Prism', 7:'Doppler', 8:'Splitter', 9:'Tangler',
                   10:'Target', 11:'Conduit', 12:'Teleporter'}
    name = piece_names.get(rec[0], f'Unknown({rec[0]})')
    print(f"  {rec[0]:5d} {rec[1]:5d} {rec[2]:5d} {rec[3]:5d} {rec[4]:5d}  "
          f"type={name}  if [t,rot,col,x,y]: rot={rec[1]} col={rec[2]} at ({rec[3]},{rec[4]})"
          f"  if [t,col,rot,x,y]: col={rec[1]} rot={rec[2]} at ({rec[3]},{rec[4]})")

# Also check beam_colors to confirm
print(f"\nBeam color table (u32 at 0x0040b0c0):")
for i in range(8):
    val = read_u32(0x0040b0c0 + i * 4)
    r = val & 0xFF
    g = (val >> 8) & 0xFF
    b = (val >> 16) & 0xFF
    print(f"  [{i}] = 0x{val:06x}  → COLORREF(R={r},G={g},B={b})")
