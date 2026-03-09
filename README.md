# Chromatron

Pixel-perfect recompilation of **Chromatron** (laser puzzle game) in Rust, reverse-engineered from the original Win32 binary.

Read the full story: [Chromatron Recompiled](https://quesma.com/blog/chromatron-recompiled/)

## Build & Run

```bash
cargo run --release
```

Requires Rust. No external dependencies beyond what Cargo fetches (winit + softbuffer).

## Project Structure

- `src/` — Rust recompilation (winit + softbuffer). Each function references its decompiled origin.
- `decompiled/` — Ghidra decompiled C code (Win32 + Mac PPC), function maps, string tables.
- `originals/` — Original game binaries (Win32 .exe, Mac PPC .sit). See [Unpacking Originals](#unpacking-originals).
- `scripts/` — Code generators, data extraction, visual comparison tools.
- `web/` — WASM build (Trunk).
- `assets/fonts/` — vgasys.fon (Windows System font used by the original).
- `screenshots/` — Reference screenshots from the original Win32 game.

## How to Play

- **Drag** pieces from the toolbox onto the grid
- **Click** a placed piece to rotate it
- **Right-click** to rotate the other way
- Guide laser beams into matching-color pinwheel targets
- All targets must be lit with the correct color to win

## Keys

- **Space / + / =** --- next level
- **-** --- previous level
- **R** --- reset level
- **Ctrl+C** --- copy solution
- **Ctrl+V** --- paste solution
- **ESC** --- quit

## Unpacking Originals

The repo stores only the original compressed binaries. Scripts in `scripts/` expect the unpacked versions — regenerate them with:

```bash
# Win32: decompress UPX-packed exe (needed by extract_data.py, generate_levels_rs.py, etc.)
cp originals/chromatron.exe originals/chromatron_unpacked.exe
upx -d originals/chromatron_unpacked.exe

# Mac PPC: extract StuffIt archive
unar -o originals/ originals/chromatron.sit
```

Requires [UPX](https://upx.github.io/) and [unar](https://theunarchiver.com/command-line).

## Credits

Original game by Sean Barrett / [Silver Spaceship Software](http://silverspaceship.com/).

This recompilation is shared for educational purposes. No copyright is claimed over the original game logic or assets.
