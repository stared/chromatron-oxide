# Chromatron

Pixel-perfect recompilation of **Chromatron** (laser puzzle game) in Rust, reverse-engineered from the original Win32 binary.

Read the full story: [Chromatron Recompiled](https://quesma.com/blog/chromatron-recompiled/)

## Build & Run

```bash
cargo run --release
```

Requires Rust. No external dependencies beyond what Cargo fetches (winit + softbuffer).

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

## Credits

Original game by Sean Barrett / [Silver Spaceship Software](http://silverspaceship.com/).

This recompilation is shared for educational purposes. No copyright is claimed over the original game logic or assets.
