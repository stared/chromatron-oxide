/// Rendering engine — SDL2-based port of the original GDI rendering.
/// Source: FUN_00403690 (render_grid), FUN_004032f0 (render_all), FUN_00402c20 (blit_sprite)

use sdl2::pixels::Color as SdlColor;
use sdl2::rect::Rect;
use sdl2::render::Canvas;
use sdl2::video::Window;

use crate::font;
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
pub fn get_sprite_index(cell: &Cell) -> Option<usize> {
    let rot = cell.rotation as usize;
    let rot_mod4 = rot & 3;
    match cell.piece_type {
        PieceType::Empty => None,
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
            // Target sprite depends on color and whether satisfied
            // Source: case 10 in get_sprite_index, complex mapping
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
            // Check if target is satisfied (lit up)
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
/// Source: FUN_004032f0 (render_all) + FUN_00403690 (render_grid)
pub fn render(canvas: &mut Canvas<Window>, game: &Game, sprites: &[Vec<u8>]) {
    // Fill background with gray
    // Source: FUN_00403690 fills framebuffer with 0xa4
    canvas.set_draw_color(SdlColor::RGB(BG_COLOR.0, BG_COLOR.1, BG_COLOR.2));
    canvas.clear();

    // Draw grid lines (subtle lighter lines)
    canvas.set_draw_color(SdlColor::RGB(180, 180, 180));
    for i in 0..=GRID_SIZE {
        let x = GRID_ORIGIN_X + (i as i32) * CELL_SIZE;
        let y = GRID_ORIGIN_Y + (i as i32) * CELL_SIZE;
        canvas.draw_line(
            (GRID_ORIGIN_X, y as i32),
            (GRID_ORIGIN_X + GRID_SIZE as i32 * CELL_SIZE, y as i32),
        ).ok();
        canvas.draw_line(
            (x as i32, GRID_ORIGIN_Y),
            (x as i32, GRID_ORIGIN_Y + GRID_SIZE as i32 * CELL_SIZE),
        ).ok();
    }

    // Draw all pieces on main grid
    // Source: FUN_00403690 first loop, calls FUN_00402d10 for each cell
    for y in 0..GRID_SIZE {
        for x in 0..GRID_SIZE {
            draw_piece_on_grid(canvas, &game.grid[y][x], x, y, sprites);
        }
    }

    // Draw beam lines
    // Source: FUN_00403690 second loop, calls FUN_00402dc0
    for y in 0..GRID_SIZE {
        for x in 0..GRID_SIZE {
            draw_beams_at_cell(canvas, &game.grid[y][x], x, y);
        }
    }

    // Draw toolbox background
    // Source: darker gray area for toolbox
    canvas.set_draw_color(SdlColor::RGB(140, 140, 140));
    for row in 0..TOOLBOX_ROWS {
        for col in 0..TOOLBOX_COLS {
            let tx = TOOLBOX_ORIGIN_X + (col as i32) * TOOLBOX_CELL_SIZE;
            let ty = TOOLBOX_ORIGIN_Y + (row as i32) * TOOLBOX_CELL_SIZE;
            canvas.fill_rect(Rect::new(tx, ty, TOOLBOX_CELL_SIZE as u32, TOOLBOX_CELL_SIZE as u32)).ok();
        }
    }

    // Draw toolbox grid lines
    canvas.set_draw_color(SdlColor::RGB(120, 120, 120));
    for i in 0..=TOOLBOX_COLS {
        let x = TOOLBOX_ORIGIN_X + (i as i32) * TOOLBOX_CELL_SIZE;
        canvas.draw_line(
            (x, TOOLBOX_ORIGIN_Y),
            (x, TOOLBOX_ORIGIN_Y + TOOLBOX_ROWS as i32 * TOOLBOX_CELL_SIZE),
        ).ok();
    }
    for i in 0..=TOOLBOX_ROWS {
        let y = TOOLBOX_ORIGIN_Y + (i as i32) * TOOLBOX_CELL_SIZE;
        canvas.draw_line(
            (TOOLBOX_ORIGIN_X, y),
            (TOOLBOX_ORIGIN_X + TOOLBOX_COLS as i32 * TOOLBOX_CELL_SIZE, y),
        ).ok();
    }

    // Draw toolbox pieces
    // Source: FUN_00403690 third loop draws pieces at row >= 0xf
    for (i, cell) in game.toolbox.iter().enumerate() {
        let col = i % TOOLBOX_COLS;
        let row = i / TOOLBOX_COLS;
        if row < TOOLBOX_ROWS {
            let tx = TOOLBOX_ORIGIN_X + (col as i32) * TOOLBOX_CELL_SIZE + TOOLBOX_CELL_SIZE / 2;
            let ty = TOOLBOX_ORIGIN_Y + (row as i32) * TOOLBOX_CELL_SIZE + TOOLBOX_CELL_SIZE / 2;
            draw_sprite_at(canvas, cell, tx, ty, sprites);
        }
    }

    // Draw dragged piece at cursor position
    // Source: FUN_004032f0 draws selected piece at mouse pos during drag
    if let Some(dragged) = game.get_dragged_cell() {
        draw_sprite_at(canvas, dragged, game.drag_pixel_x, game.drag_pixel_y, sprites);
    }

    // Draw level numbers at bottom
    // Source: FUN_00403240 @ 0x403240
    draw_level_numbers(canvas, game);

    // Draw status text
    // Source: FUN_004032f0 @ 0x4032f0
    if game.win_flag {
        draw_text_simple(canvas, "You win!", 330, 385);
    } else if game.level_completed[game.current_level] {
        draw_text_simple(canvas, "(completed)", 320, 375);
    }

    // Draw instruction text
    let text = game.get_instruction_text();
    if !text.is_empty() {
        draw_wrapped_text(canvas, text, TOOLBOX_ORIGIN_X, 130, 170);
    }

    // Draw "Click on a level or press spacebar for next."
    if game.game_state == GameState::Playing {
        if game.win_flag {
            draw_text_simple(canvas, "Click on a level or press spacebar for next.", 125, 450);
        }
    }

    // Draw "freeware" and "silverspaceship.com"
    draw_text_simple(canvas, "freeware", 0, 450);
    draw_text_simple(canvas, "silverspaceship.com", 470, 450);

    canvas.present();
}

/// Draw a piece on the main grid.
/// Source: FUN_00402d10 @ 0x402d10
fn draw_piece_on_grid(canvas: &mut Canvas<Window>, cell: &Cell, x: usize, y: usize, sprites: &[Vec<u8>]) {
    if cell.piece_type == PieceType::Empty {
        return;
    }
    let px = GRID_ORIGIN_X + (x as i32) * CELL_SIZE;
    let py = GRID_ORIGIN_Y + (y as i32) * CELL_SIZE;
    draw_sprite_at(canvas, cell, px + CELL_SIZE / 2, py + CELL_SIZE / 2, sprites);
}

/// Draw a sprite centered at (cx, cy) using palette lookup.
/// Source: FUN_00402c20 @ 0x402c20 (blit_sprite)
fn draw_sprite_at(canvas: &mut Canvas<Window>, cell: &Cell, cx: i32, cy: i32, sprites: &[Vec<u8>]) {
    let Some(idx) = get_sprite_index(cell) else { return };
    if idx >= sprites.len() { return; }
    let sprite = &sprites[idx];
    let half = SPRITE_SIZE as i32 / 2;

    for sy in 0..SPRITE_SIZE {
        for sx in 0..SPRITE_SIZE {
            let pixel_idx = sy * SPRITE_SIZE + sx;
            if pixel_idx >= sprite.len() { continue; }
            let pal_idx = sprite[pixel_idx] as usize;
            // Transparency: skip palette indices below threshold (0x0E = 14)
            // Source: FUN_00402c20 param_7 threshold check: `if (param_7 <= pixel_value)`
            if pal_idx < 14 {
                continue;
            }
            let (r, g, b) = PALETTE[pal_idx];
            canvas.set_draw_color(SdlColor::RGB(r, g, b));
            canvas.draw_point((cx - half + sx as i32, cy - half + sy as i32)).ok();
        }
    }
}

/// Draw beam lines at a cell.
/// Source: FUN_00402dc0 @ 0x402dc0
///
/// Each beam has two segments per cell: from center toward the entry point
/// (where the beam came from) and from center toward the exit point.
fn draw_beams_at_cell(canvas: &mut Canvas<Window>, cell: &Cell, x: usize, y: usize) {
    let cx = GRID_ORIGIN_X + (x as i32) * CELL_SIZE + CELL_SIZE / 2;
    let cy = GRID_ORIGIN_Y + (y as i32) * CELL_SIZE + CELL_SIZE / 2;
    let half = CELL_SIZE / 2 + 1;

    for dir in 0..8u8 {
        let d = dir as usize & 7;
        let opp = ((dir + 4) & 7) as usize;

        // Outgoing: draw from center toward exit direction
        if cell.beam_outgoing[d] != 0 {
            let (r, g, b) = BEAM_COLORS[cell.beam_outgoing[d] as usize & 7];
            canvas.set_draw_color(SdlColor::RGB(r, g, b));
            let ex = cx + Direction::DX[d] * half;
            let ey = cy + Direction::DY[d] * half;
            canvas.draw_line((cx, cy), (ex, ey)).ok();
        }

        // Incoming: beam traveling in direction `dir` entered this cell,
        // so it came from the opposite side — draw from center toward entry point
        if cell.beam_incoming[d] != 0 {
            let (r, g, b) = BEAM_COLORS[cell.beam_incoming[d] as usize & 7];
            canvas.set_draw_color(SdlColor::RGB(r, g, b));
            let ex = cx + Direction::DX[opp] * half;
            let ey = cy + Direction::DY[opp] * half;
            canvas.draw_line((cx, cy), (ex, ey)).ok();
        }
    }
}

/// Draw level numbers at the bottom of the screen.
/// Source: FUN_00403240 @ 0x403240
fn draw_level_numbers(canvas: &mut Canvas<Window>, game: &Game) {
    // Two rows of 25, starting at (10, 410) with 20px spacing
    // Source: `(iVar1 % 0x19) * 0x14 + 10` and `(iVar1 / 0x19) * 0x14 + 0x19a`
    for i in 0..NUM_LEVELS {
        let col = i % 25;
        let row = i / 25;
        let x = (col as i32) * 20 + 10;
        let y = (row as i32) * 20 + 410;

        // Color based on level status
        // Source: FUN_00403200 @ 0x403200
        let color = if i == game.current_level {
            SdlColor::RGB(255, 255, 255) // Current level: white
        } else if game.level_completed[i] {
            SdlColor::RGB(84, 84, 252)   // Completed: blue
        } else if game.level_accessible[i] {
            SdlColor::RGB(0, 200, 0)     // Accessible: green
        } else {
            SdlColor::RGB(168, 0, 0)     // Inaccessible: red
        };

        // Render level number using bitmap font
        canvas.set_draw_color(color);
        let num_str = format!("{}", i + 1);
        let mut cx = x;
        for ch in num_str.chars() {
            if let Some(glyph) = font::get_char(ch) {
                for row in 0..7 {
                    let bits = glyph[row];
                    for col in 0..5 {
                        if bits & (0x10 >> col) != 0 {
                            canvas.draw_point((cx + col, y + row as i32)).ok();
                        }
                    }
                }
            }
            cx += font::CHAR_W;
        }
    }
}

/// Draw text using the embedded bitmap font.
/// Source: replaces DrawTextA from original Win32 GDI rendering (FUN_00403e50)
fn draw_text_simple(canvas: &mut Canvas<Window>, text: &str, x: i32, y: i32) {
    canvas.set_draw_color(SdlColor::RGB(0, 0, 0));
    let mut cx = x;
    for ch in text.chars() {
        if let Some(glyph) = font::get_char(ch) {
            for row in 0..7 {
                let bits = glyph[row];
                for col in 0..5 {
                    if bits & (0x10 >> col) != 0 {
                        canvas.draw_point((cx + col, y + row as i32)).ok();
                    }
                }
            }
        }
        cx += font::CHAR_W;
    }
}

/// Draw wrapped text in a bounding box.
/// Source: replaces DrawTextA with DT_WORDBREAK flag
fn draw_wrapped_text(canvas: &mut Canvas<Window>, text: &str, x: i32, y: i32, max_width: i32) {
    let chars_per_line = (max_width / font::CHAR_W) as usize;

    let mut cy = y;
    let words: Vec<&str> = text.split_whitespace().collect();
    let mut line = String::new();

    for word in words {
        if !line.is_empty() && line.len() + 1 + word.len() > chars_per_line {
            draw_text_simple(canvas, &line, x, cy);
            cy += font::CHAR_H;
            line.clear();
        }
        if !line.is_empty() { line.push(' '); }
        line.push_str(word);
    }
    if !line.is_empty() {
        draw_text_simple(canvas, &line, x, cy);
    }
}
