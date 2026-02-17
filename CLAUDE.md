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

## Screenshots & Visual Verification
- **Reference screenshots**: `screenshots/15883305-*.png` (Win32 originals, levels 1-4)
- **Rust recomp snapshots**: `screenshots/rust-recomp_*.png` (named with date + suffix)
- **F12 framebuffer dumps**: `screenshots/framebuffer_*.bmp` (exact 640×480 internal render)

### Capture workflow
1. Launch game: `cargo run --release &` then `sleep 4`
2. Capture window: `uv run scripts/take_screenshot.py "suffix"` (macOS Quartz, handles Retina)
3. Or press **F12** in-game for exact framebuffer BMP, then convert: `uv run scripts/bmp_to_png.py screenshots/framebuffer_*.bmp`

### Comparison
- `uv run scripts/compare.py <ours> <reference> [output]` — 2-panel [Reference | Ours + magenta diff], regional stats to stdout

### Reference filenames
- Level 1: `15883305-chromatron-windows-level-1-directly-starts-after-launching-the-g.png`
- Level 2: `15688195-chromatron-windows-level-2-level-completed.png`
- Level 3: `15688228-chromatron-windows-level-3-rgb-to-cmy-conversion.png`
- Level 4: `15870999-chromatron-windows-level-4-introduction-of-splitter.png`
