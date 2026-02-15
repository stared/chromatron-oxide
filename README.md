# Chromatron

Pixel-perfect recompilation of **Chromatron** (laser puzzle game by Sean Barrett / Silver Spaceship Software) in Rust + SDL2.

Reverse engineered from the original Win32 and Mac PPC binaries.

## Build & Run

```bash
cargo run --release
```

## How to play

- **Drag** pieces from the toolbox onto the grid
- **Click** a placed piece to rotate it
- **Right-click** to rotate the other way
- Guide laser beams into matching-color pinwheel targets
- All targets must be lit with the correct color to win

## Keys

- **Space / + / =** — next level
- **-** — previous level
- **R** — reset level
- **Ctrl+C** — copy solution
- **Ctrl+V** — paste solution
- **ESC** — quit
