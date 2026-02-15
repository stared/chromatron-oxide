# Chromatron Recompilation Project

## Core Rules
- All temporary files go inside this project directory (never /tmp or external paths). Use `scripts/` for temp scripts, `decompiled/` for analysis artifacts.
- Use `uv run script.py` for Python, never `python3` directly.
- Use `fd` not `find`, `rg` not `grep`.
- Commit at every meaningful stage to track the de/recompilation process.

## Project Structure
- `originals/` - Original binaries (Win32 .exe, Mac PPC .sit/.app)
- `screenshots/` - Reference screenshots from original game
- `scripts/` - Helper/analysis scripts (Ghidra, extraction, etc.)
- `decompiled/` - Raw Ghidra output + annotated analysis
- `src/` - C + SDL2 rewrite source code
- `web/` - WASM build output
- `ghidra/` - Ghidra project files (gitignored)

## Key Constraint
Every game mechanic, rendering detail, and data structure MUST be traced to the decompiled binary. Nothing invented or assumed.
