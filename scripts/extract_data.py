"""Extract game data (palette, direction tables, beam colors, doppler tables, level data, sprites)
from the unpacked Win32 binary using PyGhidra.

Usage: JAVA_HOME=/opt/homebrew/opt/openjdk@21 uv run scripts/extract_data.py
"""

import os
import json
import struct

ghidra_dir = os.environ.get("GHIDRA_INSTALL_DIR", "/opt/homebrew/Cellar/ghidra/12.0/libexec")
os.environ["GHIDRA_INSTALL_DIR"] = ghidra_dir

import pyghidra
pyghidra.start()

binary = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "originals", "chromatron_unpacked.exe"))
output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "decompiled"))

print(f"[*] Opening {binary}")
with pyghidra.open_program(binary) as flat_api:
    program = flat_api.getCurrentProgram()
    mem = program.getMemory()
    addr_space = program.getAddressFactory().getDefaultAddressSpace()

    def read_bytes(addr, length):
        """Read bytes from program memory at given address."""
        a = addr_space.getAddress(addr)
        buf = bytearray(length)
        mem.getBytes(a, buf)
        return bytes(buf)

    def read_int32(addr):
        """Read a little-endian 32-bit int."""
        b = read_bytes(addr, 4)
        return struct.unpack('<i', b)[0]

    def read_uint32(addr):
        """Read a little-endian 32-bit unsigned int."""
        b = read_bytes(addr, 4)
        return struct.unpack('<I', b)[0]

    data = {}

    # 1. Direction delta tables (8 directions: N, NE, E, SE, S, SW, W, NW)
    # DAT_0040b034 = dx[8], DAT_0040b054 = dy[8]  (each is int32 × 8)
    print("[*] Extracting direction tables...")
    dx = [read_int32(0x0040b034 + i*4) for i in range(8)]
    dy = [read_int32(0x0040b054 + i*4) for i in range(8)]
    data['direction_dx'] = dx
    data['direction_dy'] = dy
    print(f"    dx = {dx}")
    print(f"    dy = {dy}")

    # 2. Doppler color shift tables
    # DAT_0040b074 = doppler_fwd[8], DAT_0040b088 = doppler_rev[8]
    print("[*] Extracting doppler tables...")
    doppler_fwd = list(read_bytes(0x0040b074, 20))  # 5 entries × 4 bytes
    doppler_rev = list(read_bytes(0x0040b088, 20))
    data['doppler_fwd_raw'] = doppler_fwd
    data['doppler_rev_raw'] = doppler_rev
    # These are indexed by color value (1-7), extract just the mapping
    doppler_fwd_map = [read_bytes(0x0040b074 + i*4, 1)[0] for i in range(8)]
    doppler_rev_map = [read_bytes(0x0040b088 + i*4, 1)[0] for i in range(8)]
    data['doppler_fwd'] = doppler_fwd_map
    data['doppler_rev'] = doppler_rev_map
    print(f"    fwd = {doppler_fwd_map}")
    print(f"    rev = {doppler_rev_map}")

    # 3. Beam color table (RGB values indexed by color bitmask 0-7)
    # DAT_0040b0c0 = beam_colors[8] (each is uint32, RGB packed)
    print("[*] Extracting beam colors...")
    beam_colors = [read_uint32(0x0040b0c0 + i*4) for i in range(8)]
    data['beam_colors'] = [f"0x{c:06x}" for c in beam_colors]
    print(f"    beam_colors = {[f'0x{c:06x}' for c in beam_colors]}")

    # 4. Save permutation table
    # DAT_0040b09c = 32 bytes
    print("[*] Extracting save permutation table...")
    save_perm = list(read_bytes(0x0040b09c, 32))
    data['save_permutation'] = save_perm
    print(f"    save_perm = {save_perm}")

    # 5. Level order mapping (level_number → data_index)
    # DAT_0040b168 = 50 bytes
    print("[*] Extracting level order...")
    level_order = list(read_bytes(0x0040b168, 50))
    data['level_order'] = level_order
    print(f"    level_order = {level_order}")

    # 6. Palette data (256 × 3 bytes RGB at DAT_00415934)
    print("[*] Extracting palette...")
    palette_raw = read_bytes(0x00415934, 256 * 3)
    palette = []
    for i in range(256):
        r = palette_raw[i*3]
        g = palette_raw[i*3 + 1]
        b = palette_raw[i*3 + 2]
        palette.append([r, g, b])
    data['palette'] = palette

    # 7. Sprite pointer table and count
    # DAT_00415c34 = sprite count
    # PTR_DAT_00415734 = array of pointers to RLE-compressed sprite data
    print("[*] Extracting sprite data...")
    sprite_count = read_int32(0x00415c34)
    print(f"    sprite_count = {sprite_count}")
    data['sprite_count'] = sprite_count

    sprite_ptrs = []
    for i in range(sprite_count):
        ptr = read_uint32(0x00415734 + i*4)
        sprite_ptrs.append(ptr)

    # Extract raw RLE sprite data for each sprite
    # Each decompresses to 24*24 = 576 bytes (0x240)
    sprites_rle = []
    for i, ptr in enumerate(sprite_ptrs):
        # Read enough data for RLE - sprites are small, 576 bytes max uncompressed
        # RLE encoding: byte < 0xC1 = literal, byte >= 0xC1 = run of (byte-0xC0) × next_byte
        rle_data = []
        offset = 0
        decoded_size = 0
        while decoded_size < 0x240:
            b = read_bytes(ptr + offset, 1)[0]
            offset += 1
            if b < 0xC1:
                rle_data.append(b)
                decoded_size += 1
            else:
                run_len = b - 0xC0
                val = read_bytes(ptr + offset, 1)[0]
                offset += 1
                rle_data.append(b)
                rle_data.append(val)
                decoded_size += run_len
        sprites_rle.append(rle_data)

    data['sprites_rle'] = sprites_rle
    print(f"    Extracted {len(sprites_rle)} sprites")

    # 8. Level grid data and instruction text
    # DAT_0040e65c = level_grid_ptrs[N], DAT_0040e758 = level_text_ptrs[N]
    # Number of unique level data indices
    max_data_idx = max(level_order) + 1
    print(f"[*] Extracting level data ({max_data_idx} unique levels)...")

    levels = []
    for idx in range(max_data_idx):
        grid_ptr = read_uint32(0x0040e65c + idx * 4)
        text_ptr = read_uint32(0x0040e758 + idx * 4)

        # Read instruction text (null-terminated string)
        text_bytes = []
        for j in range(512):
            b = read_bytes(text_ptr + j, 1)[0]
            if b == 0:
                break
            text_bytes.append(b)
        text = bytes(text_bytes).decode('ascii', errors='replace')

        # Read grid data: sequence of 5-byte records (type, rotation, color, x, y)
        # terminated by type==0
        pieces = []
        offset = 0
        while True:
            rec = read_bytes(grid_ptr + offset, 5)
            piece_type = rec[0]
            if piece_type == 0:
                break
            rotation = rec[1]
            color = rec[2]
            x = rec[3]
            y = rec[4]
            pieces.append({
                'type': piece_type,
                'rotation': rotation,
                'color': color,
                'x': x,
                'y': y
            })
            offset += 5

        levels.append({
            'text': text,
            'pieces': pieces
        })
        if idx < 5:
            print(f"    Level {idx}: {len(pieces)} pieces, text='{text[:60]}...'")

    data['levels'] = levels

    # Write all extracted data to JSON
    output_path = os.path.join(output_dir, "extracted_data.json")
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n[*] All data written to {output_path}")
    print(f"[*] Summary: {len(palette)} palette entries, {len(sprites_rle)} sprites, {len(levels)} levels")
