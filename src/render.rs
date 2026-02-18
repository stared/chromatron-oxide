/// Rendering engine — SDL2-based port of the original GDI rendering.
/// Source: FUN_00403690 (render_board), FUN_004032f0 (render_frame), FUN_00402c20 (blit_sprite)

use sdl2::pixels::Color as SdlColor;
use sdl2::render::Canvas;
use sdl2::video::Window;

use crate::bitmap_font::BitmapFont;
use crate::game::Game;
use crate::levels::PALETTE;
use crate::types::*;

/// Decompress a single RLE sprite to 24×24 indexed pixels.
/// Source: FUN_00403740 @ 0x403740
/// Format: byte < 0xC1 → literal; byte >= 0xC1 → run of (byte - 0xC0) copies of next byte
pub fn decompress_sprite(rle: &[u8]) -> Vec<u8> {
    let mut result = Vec::with_capacity(SPRITE_SIZE * SPRITE_SIZE);
    let mut i = 0;
    while result.len() < SPRITE_SIZE * SPRITE_SIZE && i < rle.len() {
        let b = rle[i];
        i += 1;
        if b < 0xC1 {
            result.push(b);
        } else {
            let count = (b - 0xC0) as usize;
            if i < rle.len() {
                let val = rle[i];
                i += 1;
                for _ in 0..count {
                    if result.len() < SPRITE_SIZE * SPRITE_SIZE {
                        result.push(val);
                    }
                }
            }
        }
    }
    result
}

/// Get sprite index for a piece.
/// Source: FUN_00401dc0 @ 0x401dc0 (get_sprite_index)
/// NOTE: Empty cells return 0 (grid background tile), NOT -1/None!
pub fn get_sprite_index(cell: &Cell) -> Option<usize> {
    let rot = cell.rotation as usize;
    let rot_mod4 = rot & 3;
    match cell.piece_type {
        PieceType::Empty => Some(0),  // Sprite 0 = grid background tile
        PieceType::Wall => Some(1),
        PieceType::Laser => {
            match cell.color {
                1 => Some(rot + 0x58), // Red
                2 => Some(rot + 0x48), // Green
                4 => Some(rot + 0x38), // Blue
                7 => Some(rot + 0x68), // White
                _ => None,
            }
        }
        PieceType::Reflector => Some(rot + 0x20),
        PieceType::Bender => Some(rot + 0x30),
        PieceType::Filter => {
            match cell.color {
                1 => Some(rot_mod4 + 0x08), // Red filter
                2 => Some(rot_mod4 + 0x70), // Green filter
                4 => Some(rot_mod4 + 0x60), // Blue filter
                _ => None,
            }
        }
        PieceType::Prism => Some(rot + 0x18),
        PieceType::Doppler => Some(rot + 0x40),
        PieceType::Splitter => Some(rot_mod4 + 0x28),
        PieceType::Tangler => Some(rot + 0x50),
        PieceType::Target => {
            let base = match cell.color {
                0 => 0x0c,  // Black target
                1 => 0x06,  // Red
                2 => 0x04,  // Green
                3 => 0x12,  // Yellow
                4 => 0x02,  // Blue
                5 => 0x14,  // Magenta
                6 => 0x10,  // Cyan
                7 => 0x16,  // White
                _ => return None,
            };
            let mut received: u8 = 0;
            for i in 0..8 {
                received |= cell.beam_incoming[i];
            }
            let lit = received == cell.color;
            Some(base + if lit { 1 } else { 0 })
        }
        PieceType::Conduit => Some(rot_mod4 + 0x2c),
        PieceType::Teleporter => Some(0x0e),
    }
}

/// Draw the entire game frame.
/// Source: FUN_004032f0 (render_frame) + FUN_00403690 (render_board)
pub fn render(canvas: &mut Canvas<Window>, game: &Game, sprites: &[Vec<u8>],
              font: &BitmapFont) {
    // Step 1: Fill background with gray (0xA4 per channel)
    // Source: FUN_00403690 fills framebuffer with 0xa4
    canvas.set_draw_color(SdlColor::RGB(BG_COLOR.0, BG_COLOR.1, BG_COLOR.2));
    canvas.clear();

    // Step 2: Draw all cells on main grid (first pass, threshold=0)
    // Source: FUN_00403690 first loop, calls FUN_00402d10(col, row, 0)
    // threshold=0 means ALL pixels are drawn, including grid background (sprite 0)
    for row in 0..GRID_SIZE {
        for col in 0..GRID_SIZE {
            draw_cell(canvas, &game.grid[row][col], col, row, sprites, 0);
        }
    }

    // Step 3: Draw beams, then redraw pieces over beams with threshold=0x10
    // Source: FUN_00403690 second loop
    // threshold=0x10 means only pixels >= 16 are drawn (piece graphics only, no background)
    for row in 0..GRID_SIZE {
        for col in 0..GRID_SIZE {
            let has_beams = draw_beams_at_cell(canvas, &game.grid[row][col], col, row);
            if has_beams {
                // Redraw piece without background so beams show through
                // Source: FUN_00402d10(col, row, 0x10) when beams present
                draw_cell(canvas, &game.grid[row][col], col, row, sprites, 0x10);
            }
        }
    }

    // Step 4: Draw toolbox cells (24 cells at row 0xF, threshold=0)
    // Source: FUN_00403690 third loop, FUN_00402d10(col, 0xF, 0) for col 0..23
    // NOTE: Original draws all 24 slots, including empty ones (draws grid bg tile)
    for i in 0..(TOOLBOX_COLS * TOOLBOX_ROWS) {
        // Toolbox position: (col%6)*26+460, (col/6)*26+20
        // Source: FUN_00402d10 toolbox branch
        let display_col = i % TOOLBOX_COLS;
        let display_row = i / TOOLBOX_COLS;
        let cx = (display_col as i32) * TOOLBOX_CELL_SIZE + TOOLBOX_ORIGIN_X;
        let cy = (display_row as i32) * TOOLBOX_CELL_SIZE + TOOLBOX_ORIGIN_Y;
        if i < game.toolbox.len() {
            draw_sprite_at(canvas, &game.toolbox[i], cx, cy, sprites, 0);
        } else {
            // Empty toolbox slot: draw grid background tile (sprite 0)
            let empty = Cell::default();
            draw_sprite_at(canvas, &empty, cx, cy, sprites, 0);
        }
    }

    // Draw dragged piece at cursor position
    // Source: FUN_00403650 (draw_drag_overlay)
    if let Some(dragged) = game.get_dragged_cell() {
        draw_sprite_at(canvas, dragged, game.drag_pixel_x, game.drag_pixel_y, sprites, 0);
    }

    // Step 5: Draw level selector (if game_mode == 2)
    // Source: FUN_00403690 calls FUN_00403240 when DAT_0041a800 == 2
    if game.game_state == GameState::Playing {
        draw_level_numbers(canvas, game, sprites);
    }

    // Text overlays — drawn AFTER framebuffer blit in original (FUN_004032f0)
    // Source: FUN_00403e50 calls with (text, left, top, right, bottom)
    // Flags: 0x810 = DT_WORDBREAK | DT_NOPREFIX — LEFT-aligned (no DT_CENTER)

    // Status text: "You win!" or "(won)"
    if game.win_flag {
        // Source: FUN_00403e50("You win!", 0x14a, 0x181, 0x190, 0x1a4)
        // rect: left=330, top=385, right=400, bottom=420
        draw_text_in_rect(canvas, font, "You win!", 330, 385, 400, 420);
    } else if game.level_completed[game.current_level] {
        // Source: FUN_00403e50("(won)", 0x15e, 0x181, 0x190, 0x1a4)
        // rect: left=350, top=385, right=400, bottom=420
        draw_text_in_rect(canvas, font, "(won)", 350, 385, 400, 420);
    }

    // Instruction/help text or "Click on a level..."
    // Source: rect (left=0x1c2(450), top=0x7d(125), right=0x26c(620), bottom=0x1db(475))
    if game.game_state == GameState::Playing && game.win_flag {
        draw_text_wrapped_in_rect(canvas, font, "Click on a level or press spacebar for next.",
                                  450, 128, 620, 475);
    } else {
        let text = game.get_instruction_text();
        if !text.is_empty() {
            draw_text_wrapped_in_rect(canvas, font, text, 450, 128, 620, 475);
        }
    }

    // "freeware" label
    // Source: FUN_00403e50("freeware", 0, 0x1c2, 0x64, 0x1e0)
    // rect: left=0, top=450, right=100, bottom=480
    draw_text_in_rect(canvas, font, "freeware", 0, 453, 100, 480);

    // "more levels @" — shown for levels > 39 on even levels or level 49
    // Source: conditional on level>39 && (level%2==0 || level==49)
    // rect: left=350, top=450, right=465, bottom=480
    if game.current_level > 39 && (game.current_level % 2 == 0 || game.current_level == 49) {
        draw_text_in_rect(canvas, font, "more levels @", 350, 453, 465, 480);
    }

    // URL "silverspaceship.com"
    // Source: FUN_00403e50(decoded_url, 0x1d6, 0x1c2, 0x280, 0x1e0)
    // rect: left=470, top=450, right=640, bottom=480
    draw_text_in_rect(canvas, font, "silverspaceship.com", 470, 453, 640, 480);

    // NOTE: canvas.present() is called by the caller after optional framebuffer save
}

/// Draw a piece sprite centered at (cx, cy) with given transparency threshold.
/// Source: FUN_00402be0 @ 0x402be0
/// Calls blit_sprite at (cx-12, cy-12) with palette_offset=0 always.
/// The threshold parameter controls which sprite pixels are drawn:
///   threshold=0: draw ALL pixels (grid background + piece)
///   threshold=0x10: draw only pixels >= 16 (piece graphics only)
fn draw_sprite_at(canvas: &mut Canvas<Window>, cell: &Cell, cx: i32, cy: i32,
                  sprites: &[Vec<u8>], transparency_threshold: usize) {
    let Some(idx) = get_sprite_index(cell) else { return };
    blit_sprite(canvas, sprites, idx,
                cx - SPRITE_SIZE as i32 / 2, cy - SPRITE_SIZE as i32 / 2,
                SPRITE_SIZE, SPRITE_SIZE, SPRITE_SIZE,
                transparency_threshold, 0);
}

/// Draw a cell on the main grid.
/// Source: FUN_00402d10 @ 0x402d10
/// Main grid: center at (col*24+60, row*24+30)
fn draw_cell(canvas: &mut Canvas<Window>, cell: &Cell, col: usize, row: usize,
             sprites: &[Vec<u8>], transparency_threshold: usize) {
    // Source: iVar1 = col * 0x18 + 0x3c, iVar2 = row * 0x18 + 0x1e
    // These are the sprite CENTER coordinates
    let cx = GRID_ORIGIN_X + (col as i32) * CELL_SIZE;
    let cy = GRID_ORIGIN_Y + (row as i32) * CELL_SIZE;
    draw_sprite_at(canvas, cell, cx, cy, sprites, transparency_threshold);
}

/// Blit a sprite region to the canvas.
/// Source: FUN_00402c20 @ 0x402c20 (blit_sprite)
///
/// Parameters match the original:
///   param_7 = transparency_threshold: skip pixels with palette index < threshold
///   param_8 = palette_offset: added to pixel palette index for color lookup
fn blit_sprite(
    canvas: &mut Canvas<Window>, sprites: &[Vec<u8>],
    sprite_idx: usize, dst_x: i32, dst_y: i32,
    draw_w: usize, draw_h: usize, src_stride: usize,
    transparency_threshold: usize, palette_offset: usize,
) {
    if sprite_idx >= sprites.len() { return; }
    let sprite = &sprites[sprite_idx];

    for sy in 0..draw_h {
        for sx in 0..draw_w {
            let pixel_idx = sy * src_stride + sx;
            if pixel_idx >= sprite.len() { continue; }
            let raw_pal = sprite[pixel_idx] as usize;
            // Source: `if (param_7 <= (int)(uint)*(byte *)(iVar3 + param_3))`
            if raw_pal < transparency_threshold {
                continue;
            }
            let pal_idx = (raw_pal + palette_offset) & 0xFF;
            let (r, g, b) = PALETTE[pal_idx];
            canvas.set_draw_color(SdlColor::RGB(r, g, b));
            canvas.draw_point((dst_x + sx as i32, dst_y + sy as i32)).ok();
        }
    }
}

/// Draw beam lines at a cell. Returns true if any beams were drawn.
/// Source: FUN_00402dc0 @ 0x402dc0
///
/// For each of 8 directions, combines beam_incoming[(d+4)&7] and beam_outgoing[d]
/// via bitwise OR to get the total beam color, then draws a single line from cell
/// center to 13px in that direction.
fn draw_beams_at_cell(canvas: &mut Canvas<Window>, cell: &Cell, col: usize, row: usize) -> bool {
    // Cell center coordinates
    // Source: iVar3 = col*0x18+0x3c, iVar4 = row*0x18+0x1e
    let cx = GRID_ORIGIN_X + (col as i32) * CELL_SIZE;
    let cy = GRID_ORIGIN_Y + (row as i32) * CELL_SIZE;
    let extent: i32 = CELL_SIZE / 2 + 1; // 13 pixels

    let mut any_beams = false;

    for d in 0..8usize {
        let opp = (d + 4) & 7;
        // Source: beam_incoming[(direction-4)&7] | beam_outgoing[direction]
        // (direction-4)&7 == (direction+4)&7 since -4 ≡ 4 mod 8
        let color = cell.beam_incoming[opp] | cell.beam_outgoing[d];
        if color == 0 {
            continue;
        }
        any_beams = true;

        let (r, g, b) = BEAM_COLORS[color as usize & 7];
        canvas.set_draw_color(SdlColor::RGB(r, g, b));
        let ex = cx + Direction::DX[d] * extent;
        let ey = cy + Direction::DY[d] * extent;
        canvas.draw_line((cx, cy), (ex, ey)).ok();
    }

    any_beams
}

/// Digit sprite indices: sprites 118-127 correspond to digits '0'-'9'.
/// Source: DAT_00418238 = digit_sprite_ptrs[10], offset 0x1D8 from sprite_data_ptrs
const DIGIT_SPRITE_BASE: usize = 118;

/// Digit sprite rendering constants.
/// Source: FUN_004031a0 @ 0x4031a0 (draw_number_string)
const DIGIT_W: usize = 12;
const DIGIT_H: usize = 12;
const DIGIT_ADVANCE: i32 = 8;
const DIGIT_SPACE_ADVANCE: i32 = 4;

/// Draw level numbers at the bottom of the screen using sprite-based digits.
/// Source: FUN_00403240 @ 0x403240 (draw_level_selector)
fn draw_level_numbers(canvas: &mut Canvas<Window>, game: &Game, sprites: &[Vec<u8>]) {
    // Two rows of 25, starting at (10, 0x19a) with 0x14 (20px) spacing
    // Source: `(iVar1 % 0x19) * 0x14 + 10` and `(iVar1 / 0x19) * 0x14 + 0x19a`
    for i in 0..NUM_LEVELS {
        let col = i % 25;
        let row = i / 25;
        let x = (col as i32) * 20 + 10;
        let y = (row as i32) * 20 + 410; // 0x19a = 410

        // Palette offset based on level status
        // Source: FUN_00403200 @ 0x403200 (get_level_display_color)
        let palette_offset: usize = if i == game.current_level {
            0x00  // Current level: default palette (white/gray)
        } else if game.level_completed[i] {
            0x48  // Completed: blue tint
        } else if game.level_accessible[i] {
            0x30  // Accessible: green tint
        } else {
            0x10  // Inaccessible: red tint
        };

        // Format as 2-digit number with leading space
        let num_str = format!("{:2}", i + 1);
        let mut cx = x;
        for ch in num_str.chars() {
            if ch >= '0' && ch <= '9' {
                let digit = (ch as usize) - ('0' as usize);
                // Source: FUN_004031a0 calls blit_sprite with threshold=0x0E, palette_offset=color
                blit_sprite(canvas, sprites, DIGIT_SPRITE_BASE + digit,
                           cx, y, DIGIT_W, DIGIT_H, SPRITE_SIZE, 0x0E, palette_offset);
                cx += DIGIT_ADVANCE;
            } else {
                cx += DIGIT_SPACE_ADVANCE;
            }
        }
    }
}

/// Measure text width using bitmap font advance widths.
/// Source: matches original GDI character metrics exactly (same bitmap font data).
fn measure_text(font: &BitmapFont, text: &str) -> i32 {
    font.measure_text(text)
}

/// Draw text at (x, y) using bitmap font (1-bit black glyphs, no anti-aliasing).
/// Source: DrawTextA with SetBkColor(0xA4A4A4), SetTextColor(0x000000).
/// Bitmap font rendering = pixel-perfect match for original GDI bitmap font.
fn draw_text_at(canvas: &mut Canvas<Window>, font: &BitmapFont,
                text: &str, x: i32, y: i32) {
    font.draw_text(canvas, text, x, y);
}

/// Draw text LEFT-aligned within a rectangle (single line).
/// Source: FUN_00403e50 → DrawTextA with flags 0x810 (DT_WORDBREAK | DT_NOPREFIX).
/// DT_CENTER (0x01) is NOT set — text is left-aligned.
fn draw_text_in_rect(canvas: &mut Canvas<Window>, font: &BitmapFont,
                     text: &str, left: i32, top: i32, _right: i32, _bottom: i32) {
    draw_text_at(canvas, font, text, left, top);
}

/// Draw text LEFT-aligned with word-wrap within a rectangle.
/// Source: FUN_00403e50 → DrawTextA with flags 0x810 (DT_WORDBREAK | DT_NOPREFIX).
fn draw_text_wrapped_in_rect(canvas: &mut Canvas<Window>, font: &BitmapFont,
                              text: &str, left: i32, top: i32, right: i32, bottom: i32) {
    let rect_width = right - left;
    // Source: DrawTextA uses tmHeight + tmExternalLeading for line spacing
    // MS Sans Serif 8pt: tmHeight=13, tmExternalLeading=3 → line spacing=16
    // W95FA's internal metrics don't include the external leading, so we hard-code 16
    // to match the original Win32 rendering exactly.
    // Verified: reference screenshot shows text lines at y intervals of exactly 16px
    let line_height = 16;

    // Word-wrap: measure each word and break lines when width exceeds rect
    let mut cy = top;
    let words: Vec<&str> = text.split_whitespace().collect();
    let mut line = String::new();

    for word in words {
        let test = if line.is_empty() {
            word.to_string()
        } else {
            format!("{} {}", line, word)
        };
        if !line.is_empty() && measure_text(font, &test) > rect_width {
            // Flush current line left-aligned
            draw_text_at(canvas, font, &line, left, cy);
            cy += line_height;
            line.clear();
            if cy + line_height > bottom { break; }
        }
        if !line.is_empty() { line.push(' '); }
        line.push_str(word);
    }
    if !line.is_empty() && cy + line_height <= bottom {
        draw_text_at(canvas, font, &line, left, cy);
    }
}
