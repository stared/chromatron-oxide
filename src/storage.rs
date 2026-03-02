/// Persistent game state saving/loading.
/// Desktop: writes `chroma.dat` file via std::fs.
/// WASM: base64-encodes to localStorage under key "chromatron_save".
///
/// Binary format:
///   4 bytes   magic b"CHR\x01"
///   1 byte    current_level
///   7 bytes   level_completed bitfield (50 bits, LE)
///   1 byte    num_saved_levels
///   Per saved level (repeated num_saved_levels times):
///     1 byte    level_index
///     675 bytes grid: 15×15 cells × 3 bytes (piece_type, color, rotation)
///     1 byte    toolbox_count
///     N×3 bytes toolbox cells (piece_type, color, rotation)

use crate::game::{Game, SavedLevelState};
use crate::types::*;

const MAGIC: &[u8; 4] = b"CHR\x01";

/// Data recovered from a save file.
pub struct SaveData {
    pub current_level: usize,
    pub level_completed: [bool; NUM_LEVELS],
    pub saved_states: Vec<Option<SavedLevelState>>,
}

/// Serialize the game state to a binary blob.
pub fn serialize(game: &Game) -> Vec<u8> {
    let mut buf = Vec::with_capacity(4096);

    // Magic
    buf.extend_from_slice(MAGIC);

    // Current level
    buf.push(game.current_level as u8);

    // Level completed bitfield (7 bytes = 56 bits, we use 50)
    let mut bitfield = [0u8; 7];
    for i in 0..NUM_LEVELS {
        if game.level_completed[i] {
            bitfield[i / 8] |= 1 << (i % 8);
        }
    }
    buf.extend_from_slice(&bitfield);

    // Count saved levels
    let saved_count = game.saved_states.iter().filter(|s| s.is_some()).count() as u8;
    buf.push(saved_count);

    // Per saved level
    for (idx, state) in game.saved_states.iter().enumerate() {
        let Some(saved) = state else { continue };

        buf.push(idx as u8);

        // Grid: 15×15 × 3 bytes
        for row in &saved.grid {
            for cell in row {
                buf.push(cell.piece_type as u8);
                buf.push(cell.color);
                buf.push(cell.rotation);
            }
        }

        // Toolbox
        let tb_count = saved.toolbox.len().min(24) as u8;
        buf.push(tb_count);
        for i in 0..tb_count as usize {
            buf.push(saved.toolbox[i].piece_type as u8);
            buf.push(saved.toolbox[i].color);
            buf.push(saved.toolbox[i].rotation);
        }
    }

    buf
}

/// Deserialize a binary blob into SaveData. Returns None on any error.
pub fn deserialize(data: &[u8]) -> Option<SaveData> {
    // Check magic
    if data.len() < 13 { return None; } // 4 + 1 + 7 + 1
    if &data[0..4] != MAGIC { return None; }
    let mut pos = 4;

    // Current level
    let current_level = data[pos] as usize;
    if current_level >= NUM_LEVELS { return None; }
    pos += 1;

    // Level completed bitfield
    let mut level_completed = [false; NUM_LEVELS];
    for i in 0..NUM_LEVELS {
        if data[pos + i / 8] & (1 << (i % 8)) != 0 {
            level_completed[i] = true;
        }
    }
    pos += 7;

    // Num saved levels
    let num_saved = data[pos] as usize;
    pos += 1;

    let mut saved_states: Vec<Option<SavedLevelState>> = (0..NUM_LEVELS).map(|_| None).collect();

    for _ in 0..num_saved {
        if pos >= data.len() { return None; }
        let level_idx = data[pos] as usize;
        pos += 1;
        if level_idx >= NUM_LEVELS { return None; }

        // Grid: 15×15 × 3 bytes = 675
        if pos + 675 > data.len() { return None; }
        let mut grid: Vec<Vec<Cell>> = Vec::with_capacity(GRID_SIZE);
        for _y in 0..GRID_SIZE {
            let mut row = Vec::with_capacity(GRID_SIZE);
            for _x in 0..GRID_SIZE {
                row.push(Cell {
                    piece_type: PieceType::from_u8(data[pos]),
                    color: data[pos + 1],
                    rotation: data[pos + 2],
                    ..Cell::default()
                });
                pos += 3;
            }
            grid.push(row);
        }

        // Toolbox count
        if pos >= data.len() { return None; }
        let tb_count = data[pos] as usize;
        pos += 1;
        if tb_count > 24 { return None; }
        if pos + tb_count * 3 > data.len() { return None; }

        let mut toolbox = Vec::with_capacity(tb_count);
        for _ in 0..tb_count {
            toolbox.push(Cell {
                piece_type: PieceType::from_u8(data[pos]),
                color: data[pos + 1],
                rotation: data[pos + 2],
                ..Cell::default()
            });
            pos += 3;
        }

        saved_states[level_idx] = Some(SavedLevelState { grid, toolbox });
    }

    Some(SaveData {
        current_level,
        level_completed,
        saved_states,
    })
}

// ---------------------------------------------------------------------------
// Platform: native (not wasm32)
// ---------------------------------------------------------------------------

#[cfg(not(target_arch = "wasm32"))]
const SAVE_FILE: &str = "chroma.dat";

#[cfg(not(target_arch = "wasm32"))]
pub fn save_game(game: &Game) -> bool {
    let data = serialize(game);
    match std::fs::write(SAVE_FILE, &data) {
        Ok(_) => {
            eprintln!("Game saved ({} bytes)", data.len());
            true
        }
        Err(e) => {
            eprintln!("Failed to save game: {}", e);
            false
        }
    }
}

#[cfg(not(target_arch = "wasm32"))]
pub fn load_game() -> Option<SaveData> {
    match std::fs::read(SAVE_FILE) {
        Ok(data) => {
            let result = deserialize(&data);
            if result.is_some() {
                eprintln!("Game loaded from {}", SAVE_FILE);
            } else {
                eprintln!("Save file corrupt, starting fresh");
            }
            result
        }
        Err(_) => {
            eprintln!("No save file found, starting fresh");
            None
        }
    }
}

// ---------------------------------------------------------------------------
// Platform: wasm32
// ---------------------------------------------------------------------------

#[cfg(target_arch = "wasm32")]
const STORAGE_KEY: &str = "chromatron_save";

#[cfg(target_arch = "wasm32")]
pub fn save_game(game: &Game) -> bool {
    let data = serialize(game);
    let encoded = base64_encode(&data);

    let Ok(Some(storage)) = web_sys::window()
        .expect("no window")
        .local_storage()
    else {
        log::warn!("localStorage not available");
        return false;
    };

    match storage.set_item(STORAGE_KEY, &encoded) {
        Ok(_) => {
            log::info!("Game saved ({} bytes, {} b64 chars)", data.len(), encoded.len());
            true
        }
        Err(_) => {
            log::warn!("Failed to write to localStorage");
            false
        }
    }
}

#[cfg(target_arch = "wasm32")]
pub fn load_game() -> Option<SaveData> {
    let storage = web_sys::window()?.local_storage().ok()??;
    let encoded = storage.get_item(STORAGE_KEY).ok()??;
    let data = base64_decode(&encoded)?;
    let result = deserialize(&data);
    if result.is_some() {
        log::info!("Game loaded from localStorage");
    } else {
        log::warn!("Save data corrupt, starting fresh");
    }
    result
}

// ---------------------------------------------------------------------------
// Minimal base64 encode/decode (no external dependency)
// ---------------------------------------------------------------------------

#[cfg(target_arch = "wasm32")]
const B64_CHARS: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

#[cfg(target_arch = "wasm32")]
fn base64_encode(input: &[u8]) -> String {
    let mut out = String::with_capacity((input.len() + 2) / 3 * 4);
    for chunk in input.chunks(3) {
        let b0 = chunk[0] as u32;
        let b1 = if chunk.len() > 1 { chunk[1] as u32 } else { 0 };
        let b2 = if chunk.len() > 2 { chunk[2] as u32 } else { 0 };
        let triple = (b0 << 16) | (b1 << 8) | b2;

        out.push(B64_CHARS[((triple >> 18) & 0x3F) as usize] as char);
        out.push(B64_CHARS[((triple >> 12) & 0x3F) as usize] as char);
        if chunk.len() > 1 {
            out.push(B64_CHARS[((triple >> 6) & 0x3F) as usize] as char);
        } else {
            out.push('=');
        }
        if chunk.len() > 2 {
            out.push(B64_CHARS[(triple & 0x3F) as usize] as char);
        } else {
            out.push('=');
        }
    }
    out
}

#[cfg(target_arch = "wasm32")]
fn base64_decode(input: &str) -> Option<Vec<u8>> {
    let input = input.as_bytes();
    if input.len() % 4 != 0 { return None; }

    let decode_char = |c: u8| -> Option<u8> {
        match c {
            b'A'..=b'Z' => Some(c - b'A'),
            b'a'..=b'z' => Some(c - b'a' + 26),
            b'0'..=b'9' => Some(c - b'0' + 52),
            b'+' => Some(62),
            b'/' => Some(63),
            b'=' => Some(0),
            _ => None,
        }
    };

    let mut out = Vec::with_capacity(input.len() / 4 * 3);
    for chunk in input.chunks(4) {
        let a = decode_char(chunk[0])?;
        let b = decode_char(chunk[1])?;
        let c = decode_char(chunk[2])?;
        let d = decode_char(chunk[3])?;
        let triple = (a as u32) << 18 | (b as u32) << 12 | (c as u32) << 6 | (d as u32);

        out.push((triple >> 16) as u8);
        if chunk[2] != b'=' {
            out.push((triple >> 8) as u8);
        }
        if chunk[3] != b'=' {
            out.push(triple as u8);
        }
    }
    Some(out)
}
