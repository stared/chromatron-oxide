"""Decompile the WndProc at 0x004038d0 which Ghidra missed as a function.

Usage: JAVA_HOME=/opt/homebrew/opt/openjdk@21 uv run scripts/ghidra_decompile_wndproc.py
"""

import os
import sys

ghidra_dir = os.environ.get("GHIDRA_INSTALL_DIR", "/opt/homebrew/Cellar/ghidra/12.0/libexec")
os.environ["GHIDRA_INSTALL_DIR"] = ghidra_dir

import pyghidra
pyghidra.start()

from ghidra.app.decompiler import DecompInterface  # type: ignore
from ghidra.util.task import ConsoleTaskMonitor  # type: ignore
from ghidra.program.model.address import AddressFactory  # type: ignore

binary = os.path.join(os.path.dirname(__file__), "..", "originals", "chromatron_unpacked.exe")
output = os.path.join(os.path.dirname(__file__), "..", "decompiled", "wndproc_decompiled.c")

print(f"[*] Opening {binary}")
with pyghidra.open_program(os.path.abspath(binary)) as flat_api:
    program = flat_api.getCurrentProgram()
    func_manager = program.getFunctionManager()
    addr_factory = program.getAddressFactory()
    listing = program.getListing()
    monitor = ConsoleTaskMonitor()

    decomp = DecompInterface()
    decomp.openProgram(program)

    # Try to create a function at 0x004038d0 if it doesn't exist
    wndproc_addr = addr_factory.getDefaultAddressSpace().getAddress(0x004038d0)
    func = func_manager.getFunctionAt(wndproc_addr)
    if func is None:
        print("[*] Creating function at 0x004038d0...")
        from ghidra.app.cmd.function import CreateFunctionCmd  # type: ignore
        cmd = CreateFunctionCmd(wndproc_addr)
        cmd.applyTo(program)
        func = func_manager.getFunctionAt(wndproc_addr)

    if func is None:
        print("[!] Could not create function at 0x004038d0")
        # Try disassembling first
        from ghidra.app.cmd.disassemble import DisassembleCommand  # type: ignore
        from ghidra.program.model.address import AddressSet  # type: ignore
        dis_cmd = DisassembleCommand(wndproc_addr, None, True)
        dis_cmd.applyTo(program)
        cmd = CreateFunctionCmd(wndproc_addr)
        cmd.applyTo(program)
        func = func_manager.getFunctionAt(wndproc_addr)

    if func is not None:
        print(f"[*] Decompiling {func.getName()} at {func.getEntryPoint()}")
        results = decomp.decompileFunction(func, 120, monitor)
        if results and results.decompileCompleted():
            c_code = results.getDecompiledFunction().getC()
            with open(output, "w") as f:
                f.write(f"// WndProc decompiled from 0x004038d0\n")
                f.write(f"// Function: {func.getName()} size={func.getBody().getNumAddresses()}\n\n")
                f.write(c_code)
            print(f"[*] Written to {output}")
            print(f"[*] Function size: {func.getBody().getNumAddresses()} bytes")
        else:
            print("[!] Decompilation failed")
            if results:
                print(f"    Error: {results.getErrorMessage()}")
    else:
        print("[!] Failed to create function")

    decomp.dispose()
