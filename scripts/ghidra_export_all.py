# Ghidra headless post-analysis script
# Exports: decompiled C for all functions, function list, string table, import table
# Usage: analyzeHeadless ... -postScript ghidra_export_all.py <output_dir>

import os
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

args = getScriptArgs()
if len(args) < 1:
    output_dir = "."
else:
    output_dir = args[0]

monitor = ConsoleTaskMonitor()
program = currentProgram
listing = program.getListing()
func_manager = program.getFunctionManager()

# Set up decompiler
decomp = DecompInterface()
decomp.openProgram(program)

prefix = program.getName().replace(".exe", "").replace(".","_")

# 1. Export decompiled C for all functions
print("[*] Decompiling all functions...")
c_path = os.path.join(output_dir, prefix + "_decompiled.c")
with open(c_path, "w") as f:
    f.write("// Ghidra decompiled output for: %s\n" % program.getName())
    f.write("// Analysis date: auto-generated\n\n")

    func = func_manager.getFunctions(True).next()
    count = 0
    while func is not None:
        results = decomp.decompileFunction(func, 60, monitor)
        if results and results.decompileCompleted():
            c_code = results.getDecompiledFunction().getC()
            f.write("// Function: %s @ 0x%s\n" % (func.getName(), func.getEntryPoint()))
            f.write(c_code)
            f.write("\n\n")
        else:
            f.write("// FAILED to decompile: %s @ 0x%s\n\n" % (func.getName(), func.getEntryPoint()))
        count += 1
        try:
            func = func_manager.getFunctions(True).next()
        except StopIteration:
            break
    print("[*] Decompiled %d functions" % count)

# 2. Export function list with addresses and sizes
print("[*] Exporting function list...")
func_path = os.path.join(output_dir, prefix + "_functions.txt")
with open(func_path, "w") as f:
    f.write("%-40s %-12s %-8s\n" % ("Name", "Address", "Size"))
    f.write("-" * 64 + "\n")
    for func in func_manager.getFunctions(True):
        body = func.getBody()
        size = body.getNumAddresses()
        f.write("%-40s 0x%-10s %-8d\n" % (func.getName(), func.getEntryPoint(), size))

# 3. Export string table
print("[*] Exporting strings...")
str_path = os.path.join(output_dir, prefix + "_strings_ghidra.txt")
with open(str_path, "w") as f:
    from ghidra.program.model.data import StringDataType
    data_iter = listing.getDefinedData(True)
    for data in data_iter:
        dt = data.getDataType()
        if "string" in dt.getName().lower():
            val = data.getValue()
            if val:
                f.write("0x%-10s %s\n" % (data.getAddress(), str(val)))

# 4. Export import table
print("[*] Exporting imports...")
imp_path = os.path.join(output_dir, prefix + "_imports.txt")
with open(imp_path, "w") as f:
    sym_table = program.getSymbolTable()
    for sym in sym_table.getExternalSymbols():
        f.write("%-40s %s\n" % (sym.getName(), sym.getParentNamespace()))

decomp.dispose()
print("[*] Export complete. Files in: %s" % output_dir)
