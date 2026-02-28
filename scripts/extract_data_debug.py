"""Debug: check memory layout and find actual data addresses.

Usage: JAVA_HOME=/opt/homebrew/opt/openjdk@21 uv run scripts/extract_data_debug.py
"""

import os

ghidra_dir = os.environ.get("GHIDRA_INSTALL_DIR", "/opt/homebrew/Cellar/ghidra/12.0/libexec")
os.environ["GHIDRA_INSTALL_DIR"] = ghidra_dir

import pyghidra
pyghidra.start()

binary = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "originals", "chromatron_unpacked.exe"))

print(f"[*] Opening {binary}")
with pyghidra.open_program(binary) as flat_api:
    program = flat_api.getCurrentProgram()
    mem = program.getMemory()
    addr_space = program.getAddressFactory().getDefaultAddressSpace()

    # List all memory blocks
    print("\n[*] Memory blocks:")
    for block in mem.getBlocks():
        print(f"    {block.getName()}: start={block.getStart()} end={block.getEnd()} size={block.getSize()} init={block.isInitialized()}")

    # Try reading from .rdata section where our data should be
    def try_read(addr, label):
        try:
            a = addr_space.getAddress(addr)
            buf = bytearray(16)
            mem.getBytes(a, buf)
            print(f"    {label} @ 0x{addr:08x}: {list(buf)}")
            return True
        except Exception as e:
            print(f"    {label} @ 0x{addr:08x}: FAILED - {e}")
            return False

    print("\n[*] Probing key addresses:")
    # These are the addresses from the decompiled code
    try_read(0x0040b034, "direction_dx")
    try_read(0x0040b054, "direction_dy")
    try_read(0x0040b074, "doppler_fwd")
    try_read(0x0040b088, "doppler_rev")
    try_read(0x0040b09c, "save_perm")
    try_read(0x0040b0c0, "beam_colors")
    try_read(0x0040b168, "level_order")
    try_read(0x00415734, "sprite_ptrs")
    try_read(0x00415934, "palette")
    try_read(0x00415c34, "sprite_count")
    try_read(0x0040e65c, "level_grid_ptrs")
    try_read(0x0040e758, "level_text_ptrs")

    # Check the .rdata start
    try_read(0x0040a000, ".rdata start")
    try_read(0x00410000, "possible .data start")
