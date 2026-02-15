/// Core data types for Chromatron, derived from decompiled binary.
/// See decompiled/FUNCTION_MAP.md for full reverse engineering notes.

/// Grid dimensions: 15×15 cells
/// Source: grid iteration bounds throughout (e.g., FUN_00401890 @ 0x401890 uses 0xf)
pub const GRID_SIZE: usize = 15;

/// Cell size in pixels (0x18 = 24)
/// Source: FUN_00402d10 @ 0x402d10, coordinate calculation `param * 0x18`
pub const CELL_SIZE: i32 = 24;

/// Window dimensions
/// Source: FUN_00403b30 (WinMain) @ 0x403b30, DAT_00417c60 = 0x280, DAT_00417c5c = 0x1E0
pub const WINDOW_WIDTH: u32 = 640;
pub const WINDOW_HEIGHT: u32 = 480;

/// Grid origin in pixels
/// Source: FUN_00402d10 @ 0x402d10, `iVar1 = param_1 * 0x18 + 0x3c` and `iVar2 = param_2 * 0x18 + 0x1e`
pub const GRID_ORIGIN_X: i32 = 60; // 0x3C
pub const GRID_ORIGIN_Y: i32 = 30; // 0x1E

/// Toolbox origin and cell size
/// Source: FUN_00402d10 @ 0x402d10, toolbox branch: `(param_1 % 6) * 0x1a + 0x1cc`
pub const TOOLBOX_ORIGIN_X: i32 = 460; // 0x1CC
pub const TOOLBOX_ORIGIN_Y: i32 = 20;  // 0x14
pub const TOOLBOX_CELL_SIZE: i32 = 26;  // 0x1A
pub const TOOLBOX_COLS: usize = 6;
pub const TOOLBOX_ROWS: usize = 4;

/// Background color: RGB(164, 164, 164)
/// Source: FUN_00403690 @ 0x403690, fills framebuffer with 0xa4a4a4a4
pub const BG_COLOR: (u8, u8, u8) = (164, 164, 164);

/// Sprite size: 24×24 pixels
/// Source: FUN_00403740 (decompress_sprites) @ 0x403740, decompresses to 0x240 = 576 = 24*24
pub const SPRITE_SIZE: usize = 24;

/// Total number of levels
pub const NUM_LEVELS: usize = 50;

/// Maximum beam propagation iterations
/// Source: FUN_00401620 @ 0x401620, `local_4 = 0x400`
pub const MAX_BEAM_ITERATIONS: usize = 1024;

/// Maximum beams in queue
/// Source: FUN_00401030 @ 0x401030, checks `DAT_0041a984 != 0x20`
pub const MAX_BEAM_QUEUE: usize = 32;

/// Piece types as identified from beam_interact_piece switch (FUN_00401090 @ 0x401090)
/// and is_moveable check (FUN_00402280 @ 0x402280: types 3–9 are moveable)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum PieceType {
    Empty = 0,
    Wall = 1,
    Laser = 2,
    Reflector = 3,   // Mirror, rotatable
    Bender = 4,      // Angled reflector, H/V ↔ diagonal
    Filter = 5,      // Passes only matching color
    Prism = 6,       // Bends R/G/B differently
    Doppler = 7,     // Color shift R→G→B→R
    Splitter = 8,    // Splits + passes through
    Tangler = 9,     // Quantum tangler, entangled pairs
    Target = 10,     // Pinwheel, must receive correct color
    Conduit = 11,    // Passes beam on axis only (H/V)
    Teleporter = 12, // Beam jumps to next teleporter in same direction
}

impl PieceType {
    pub fn from_u8(v: u8) -> Self {
        match v {
            0 => Self::Empty,
            1 => Self::Wall,
            2 => Self::Laser,
            3 => Self::Reflector,
            4 => Self::Bender,
            5 => Self::Filter,
            6 => Self::Prism,
            7 => Self::Doppler,
            8 => Self::Splitter,
            9 => Self::Tangler,
            10 => Self::Target,
            11 => Self::Conduit,
            12 => Self::Teleporter,
            _ => Self::Empty,
        }
    }

    /// Source: FUN_00402280 @ 0x402280 — returns 1 if type is 3–9
    pub fn is_moveable(self) -> bool {
        let v = self as u8;
        v >= 3 && v <= 9
    }
}

/// Color bitmask for beams (additive RGB)
/// Source: beam_interact_piece uses bitmask operations throughout
/// bit 0 = Red (0x1), bit 1 = Green (0x2), bit 2 = Blue (0x4)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Color(pub u8);

impl Color {
    pub const NONE: Color = Color(0);
    pub const RED: Color = Color(1);
    pub const GREEN: Color = Color(2);
    pub const YELLOW: Color = Color(3);  // R+G
    pub const BLUE: Color = Color(4);
    pub const MAGENTA: Color = Color(5); // R+B
    pub const CYAN: Color = Color(6);    // G+B
    pub const WHITE: Color = Color(7);   // R+G+B

    pub fn has_red(self) -> bool { self.0 & 1 != 0 }
    pub fn has_green(self) -> bool { self.0 & 2 != 0 }
    pub fn has_blue(self) -> bool { self.0 & 4 != 0 }
}

/// 8 compass directions
/// Source: direction delta tables at DAT_0040b034/DAT_0040b054
/// dx = [0, 1, 1, 1, 0, -1, -1, -1]
/// dy = [-1, -1, 0, 1, 1, 1, 0, -1]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Direction {
    N = 0,
    NE = 1,
    E = 2,
    SE = 3,
    S = 4,
    SW = 5,
    W = 6,
    NW = 7,
}

impl Direction {
    pub const DX: [i32; 8] = [0, 1, 1, 1, 0, -1, -1, -1];
    pub const DY: [i32; 8] = [-1, -1, 0, 1, 1, 1, 0, -1];

    pub fn from_u8(v: u8) -> Self {
        match v & 7 {
            0 => Self::N,
            1 => Self::NE,
            2 => Self::E,
            3 => Self::SE,
            4 => Self::S,
            5 => Self::SW,
            6 => Self::W,
            7 => Self::NW,
            _ => unreachable!(),
        }
    }

    pub fn dx(self) -> i32 { Self::DX[self as usize] }
    pub fn dy(self) -> i32 { Self::DY[self as usize] }

    /// Rotate direction by N steps (positive = clockwise)
    pub fn rotate(self, steps: i32) -> Self {
        Self::from_u8(((self as i32 + steps) & 7) as u8)
    }

    /// Opposite direction
    pub fn opposite(self) -> Self {
        self.rotate(4)
    }
}

/// A single grid cell (20 bytes in original, at DAT_004190a0)
/// Source: cell layout derived from offsets in beam_interact_piece
/// byte[0]=type, byte[1]=color/subtype, byte[2]=rotation
/// bytes[4-11]=beam data per direction
#[derive(Debug, Clone)]
pub struct Cell {
    pub piece_type: PieceType,
    pub color: u8,     // Piece color/subtype (laser color, filter color, target required color)
    pub rotation: u8,  // Direction/rotation (0–7)
    pub beam_incoming: [u8; 8], // Color bitmask of beams arriving from each direction
    pub beam_outgoing: [u8; 8], // Color bitmask of beams leaving in each direction
}

impl Default for Cell {
    fn default() -> Self {
        Self {
            piece_type: PieceType::Empty,
            color: 0,
            rotation: 0,
            beam_incoming: [0; 8],
            beam_outgoing: [0; 8],
        }
    }
}

/// A beam entry in the propagation queue
/// Source: FUN_00401030 @ 0x401030, 8-byte entries (x, y, dir, color, entangle_id as u32)
#[derive(Debug, Clone)]
pub struct BeamEntry {
    pub x: u8,
    pub y: u8,
    pub dir: u8,
    pub color: u8,
    pub entangle_id: u32,
}

/// Level definition (const-compatible for static level data)
#[derive(Debug, Clone, Copy)]
pub struct LevelPiece {
    pub piece_type: u8,
    pub rotation: u8,
    pub color: u8,
    pub x: u8,
    pub y: u8,
}

#[derive(Debug, Clone)]
pub struct LevelDef {
    pub pieces: &'static [LevelPiece],
    pub text: &'static str,
}

/// Beam line colors (RGB) indexed by color bitmask
/// Source: DAT_0040b0c0, extracted from binary
/// Note: original stores as packed u32, we use (R,G,B) tuples
/// 0=black, 1=red(0xFF0000), 2=green(0x00C800), 3=yellow, 4=blue(0x0000FF), 5=magenta, 6=cyan, 7=white
pub const BEAM_COLORS: [(u8, u8, u8); 8] = [
    (0, 0, 0),       // 0: none/black
    (255, 0, 0),     // 1: red     (original: 0x0000FF in BGR = FF0000 RGB)
    (0, 200, 0),     // 2: green   (original: 0x00C800)
    (255, 200, 0),   // 3: yellow  (R+G)
    (0, 0, 255),     // 4: blue    (original: 0xFF0000 in BGR = 0000FF RGB)
    (255, 0, 255),   // 5: magenta (R+B)
    (0, 200, 255),   // 6: cyan    (G+B)
    (255, 255, 255), // 7: white   (R+G+B)
];

/// Doppler forward color shift: R→G, G→B, B→R
/// Source: DAT_0040b074 extracted = [0, 2, 4, 0, 1, 0, 4, 1]
/// Index by color bitmask, returns shifted color
pub const DOPPLER_FWD: [u8; 8] = [0, 2, 4, 0, 1, 0, 4, 1];

/// Doppler reverse color shift: R→B, G→R, B→G
/// Source: DAT_0040b088 extracted = [0, 4, 1, 0, 2, 0, ?, ?]
/// (entries 6,7 look garbled in extraction — derive from logic)
pub const DOPPLER_REV: [u8; 8] = [0, 4, 1, 0, 2, 0, 2, 4];

/// Mouse action types (from WndProc message mapping)
/// Source: WndProc @ 0x4038d0
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MouseAction {
    Move = 0,
    LeftDown = 1,
    MiddleDown = 2,
    RightDown = 3,
    LeftUp = 4,
    MiddleUp = 5,
    RightUp = 6,
}

/// Drag state
/// Source: DAT_00417c74 values in handle_mouse
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DragState {
    Idle = 0,
    ClickStarted = 1,
    Dragging = 2,
}

/// Game state
/// Source: DAT_0041a800
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GameState {
    NotPlaying = 0,
    Playing = 2,
}
