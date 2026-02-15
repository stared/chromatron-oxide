# Chromatron Recompilation Project

## Core Rules
- All temporary files go inside this project directory (never /tmp or external paths). Use `scripts/` for temp scripts, `decompiled/` for analysis artifacts.
- **Python**: Always use `uv run script.py` or `uv run` with inline script metadata. NEVER use `python3` directly, `python -c`, or inline heredoc/PYEOF Python. Always write script files first (even for one-off tasks), then run with `uv`.
- Use `fd` not `find`, `rg` not `grep`.
- Commit at every meaningful stage to track the de/recompilation process.

## Language & Stack
- **Rust + SDL2** (sdl2 crate) for the rewrite, NOT C.
- Every Rust function/struct should have comments referencing the specific decompiled source (function name, address, or file:line) it was derived from.
- Use `cargo` for building. Makefile wraps cargo for convenience targets (native, wasm, run, serve).
- **Python tooling**: `uv` for all Python needs (scripts, packages). `pyproject.toml` for dependencies.

## Project Structure
- `originals/` - Original binaries (Win32 .exe, Mac PPC .sit/.app)
- `screenshots/` - Reference screenshots from original game
- `scripts/` - Helper/analysis scripts (Ghidra, extraction, etc.)
- `decompiled/` - Raw Ghidra output + annotated analysis
- `src/` - Rust source code (SDL2-based rewrite)
- `web/` - WASM build output
- `ghidra/` - Ghidra project files (gitignored)

## Key Constraint
Every game mechanic, rendering detail, and data structure MUST be traced to the decompiled binary. Nothing invented or assumed. Rust code comments must cite the decompiled origin.
