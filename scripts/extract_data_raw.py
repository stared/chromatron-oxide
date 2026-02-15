"""Extract game data directly from the raw PE binary file.

The PE has 3 sections:
  .text  VA=0x1000  raw=0x400   size=0x9000
  .rdata VA=0xa000  raw=0x9400  size=0x1000
  .data  VA=0xb000  raw=0xa400  size=0x12000 (raw) / 0x10e38 (virtual)

Image base = 0x00400000
To convert VA to file offset: file_offset = VA - section_VA + section_raw_offset

Usage: JAVA_HOME=/opt/homebrew/opt/openjdk@21 uv run scripts/extract_data_raw.py
"""

import os
import json
import struct

binary = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "originals", "chromatron_unpacked.exe"))
output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "decompiled"))

with open(binary, 'rb') as f:
    pe_data = f.read()

print(f"[*] Binary size: {len(pe_data)} bytes")

# Parse PE headers to find section mappings
pe_offset = struct.unpack_from('<I', pe_data, 0x3C)[0]
print(f"[*] PE header at offset 0x{pe_offset:x}")

# COFF header
num_sections = struct.unpack_from('<H', pe_data, pe_offset + 6)[0]
optional_hdr_size = struct.unpack_from('<H', pe_data, pe_offset + 20)[0]
image_base = struct.unpack_from('<I', pe_data, pe_offset + 0x34)[0]
print(f"[*] Image base: 0x{image_base:08x}")
print(f"[*] Sections: {num_sections}")

# Section headers start after optional header
section_offset = pe_offset + 24 + optional_hdr_size
sections = []
for i in range(num_sections):
    off = section_offset + i * 40
    name = pe_data[off:off+8].rstrip(b'\x00').decode('ascii')
    vsize = struct.unpack_from('<I', pe_data, off + 8)[0]
    va = struct.unpack_from('<I', pe_data, off + 12)[0]
    raw_size = struct.unpack_from('<I', pe_data, off + 16)[0]
    raw_ptr = struct.unpack_from('<I', pe_data, off + 20)[0]
    sections.append({'name': name, 'va': va, 'vsize': vsize, 'raw_ptr': raw_ptr, 'raw_size': raw_size})
    print(f"    {name}: VA=0x{va:x} vsize=0x{vsize:x} raw=0x{raw_ptr:x} rawsize=0x{raw_size:x}")

def va_to_offset(va_addr):
    """Convert virtual address to file offset."""
    rva = va_addr - image_base
    for s in sections:
        if s['va'] <= rva < s['va'] + s['raw_size']:
            return rva - s['va'] + s['raw_ptr']
    raise ValueError(f"VA 0x{va_addr:08x} (RVA 0x{rva:x}) not in any section")

def read_bytes_at(va_addr, length):
    off = va_to_offset(va_addr)
    return pe_data[off:off+length]

def read_int32(va_addr):
    return struct.unpack('<i', read_bytes_at(va_addr, 4))[0]

def read_uint32(va_addr):
    return struct.unpack('<I', read_bytes_at(va_addr, 4))[0]

data = {}

# 1. Direction delta tables
print("\n[*] Extracting direction tables...")
dx = [read_int32(0x0040b034 + i*4) for i in range(8)]
dy = [read_int32(0x0040b054 + i*4) for i in range(8)]
data['direction_dx'] = dx
data['direction_dy'] = dy
print(f"    dx = {dx}")
print(f"    dy = {dy}")

# 2. Doppler color shift tables
print("[*] Extracting doppler tables...")
doppler_fwd = [read_bytes_at(0x0040b074 + i*4, 1)[0] for i in range(8)]
doppler_rev = [read_bytes_at(0x0040b088 + i*4, 1)[0] for i in range(8)]
data['doppler_fwd'] = doppler_fwd
data['doppler_rev'] = doppler_rev
print(f"    fwd = {doppler_fwd}")
print(f"    rev = {doppler_rev}")

# 3. Beam color table
print("[*] Extracting beam colors...")
beam_colors = [read_uint32(0x0040b0c0 + i*4) for i in range(8)]
data['beam_colors_hex'] = [f"0x{c:06x}" for c in beam_colors]
data['beam_colors'] = beam_colors
print(f"    beam_colors = {[f'0x{c:06x}' for c in beam_colors]}")

# 4. Save permutation table
print("[*] Extracting save permutation...")
save_perm = list(read_bytes_at(0x0040b09c, 32))
data['save_permutation'] = save_perm
print(f"    save_perm = {save_perm}")

# 5. Level order
print("[*] Extracting level order...")
level_order = list(read_bytes_at(0x0040b168, 50))
data['level_order'] = level_order
print(f"    level_order = {level_order}")

# 6. Palette (256 × 3 RGB at 0x415934)
print("[*] Extracting palette...")
palette_raw = read_bytes_at(0x00415934, 256 * 3)
palette = []
for i in range(256):
    r = palette_raw[i*3]
    g = palette_raw[i*3 + 1]
    b = palette_raw[i*3 + 2]
    palette.append([r, g, b])
data['palette'] = palette
# Print first few non-zero entries
for i, (r, g, b) in enumerate(palette[:20]):
    if r or g or b:
        print(f"    palette[{i}] = ({r}, {g}, {b})")

# 7. Sprite data
print("[*] Extracting sprite data...")
sprite_count = read_int32(0x00415c34)
print(f"    sprite_count = {sprite_count}")
data['sprite_count'] = sprite_count

sprite_ptrs = [read_uint32(0x00415734 + i*4) for i in range(sprite_count)]
print(f"    first few sprite ptrs: {[f'0x{p:08x}' for p in sprite_ptrs[:5]]}")

sprites_rle = []
for i, ptr in enumerate(sprite_ptrs):
    rle_data = []
    offset = 0
    decoded_size = 0
    while decoded_size < 0x240:  # 24*24 = 576 bytes
        b = read_bytes_at(ptr + offset, 1)[0]
        offset += 1
        if b < 0xC1:
            rle_data.append(b)
            decoded_size += 1
        else:
            run_len = b - 0xC0
            val = read_bytes_at(ptr + offset, 1)[0]
            offset += 1
            rle_data.append(b)
            rle_data.append(val)
            decoded_size += run_len
    sprites_rle.append(rle_data)

data['sprites_rle'] = sprites_rle
print(f"    Extracted {len(sprites_rle)} sprites")

# 8. Level data
print("[*] Extracting level data...")
max_data_idx = max(level_order) + 1
print(f"    {max_data_idx} unique level data entries")

level_grid_ptrs = [read_uint32(0x0040e65c + i*4) for i in range(max_data_idx)]
level_text_ptrs = [read_uint32(0x0040e758 + i*4) for i in range(max_data_idx)]

levels = []
for idx in range(max_data_idx):
    grid_ptr = level_grid_ptrs[idx]
    text_ptr = level_text_ptrs[idx]

    # Read instruction text (skip null pointers)
    text = ""
    if text_ptr != 0:
        try:
            text_bytes = []
            for j in range(512):
                b = read_bytes_at(text_ptr + j, 1)[0]
                if b == 0:
                    break
                text_bytes.append(b)
            text = bytes(text_bytes).decode('ascii', errors='replace')
        except (ValueError, IndexError):
            text = ""

    # Read grid data: 5-byte records until type==0
    pieces = []
    if grid_ptr != 0:
        try:
            offset = 0
            for _ in range(225):  # max 15*15 pieces
                rec = read_bytes_at(grid_ptr + offset, 5)
                piece_type = rec[0]
                if piece_type == 0:
                    break
                pieces.append({
                    'type': piece_type,
                    'rotation': rec[1],
                    'color': rec[2],
                    'x': rec[3],
                    'y': rec[4]
                })
                offset += 5
        except (ValueError, IndexError):
            pass

    levels.append({
        'index': idx,
        'text': text,
        'pieces': pieces
    })
    if idx < 5 or (pieces and idx < 10):
        print(f"    Level data[{idx}]: {len(pieces)} pieces, text='{text[:50]}'")
        for p in pieces[:3]:
            print(f"      type={p['type']} rot={p['rotation']} color={p['color']} pos=({p['x']},{p['y']})")

data['levels'] = levels

# Write JSON
output_path = os.path.join(output_dir, "extracted_data.json")
with open(output_path, 'w') as f:
    json.dump(data, f, indent=2)
print(f"\n[*] All data written to {output_path}")
print(f"[*] Summary: {len(palette)} palette, {len(sprites_rle)} sprites, {len(levels)} levels")
