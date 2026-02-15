/// Input handling — mouse and keyboard.
/// Source: FUN_00401f70 (handle_mouse), FUN_00402a80 (handle_keypress), WndProc @ 0x4038d0

use crate::game::Game;
use crate::types::*;

/// Convert pixel coordinates to grid cell, or identify which UI region was clicked.
/// Source: FUN_00401f70 @ 0x401f70, coordinate conversion logic
///
/// Returns: (grid_x, grid_y) where grid_y < 15 = main grid,
/// grid_y == 15 = toolbox, grid_y == -2 = level number area
pub fn pixel_to_grid(px: i32, py: i32) -> (i32, i32) {
    // Main grid: origin (60, 30), cell size 24
    // Source: `iVar2 = param_2 / 0x18 + -2` and `iVar4 = (param_3 + 0x1e) / 0x18 + -2`
    let gx = (px - GRID_ORIGIN_X + CELL_SIZE) / CELL_SIZE - 1;
    let gy = (py - GRID_ORIGIN_Y + CELL_SIZE) / CELL_SIZE - 1;

    if gx >= 0 && gx < GRID_SIZE as i32 && gy >= 0 && gy < GRID_SIZE as i32 {
        return (gx, gy);
    }

    // Toolbox: origin (460, 20), cell size 26, 6×4
    // Source: `iVar2 = (param_2 + -0x1a6) / 0x1a + -1`
    let tx = (px - TOOLBOX_ORIGIN_X + TOOLBOX_CELL_SIZE) / TOOLBOX_CELL_SIZE - 1;
    let ty = (py - TOOLBOX_ORIGIN_Y + TOOLBOX_CELL_SIZE) / TOOLBOX_CELL_SIZE - 1;
    if tx >= 0 && tx < TOOLBOX_COLS as i32 && ty >= 0 && ty < TOOLBOX_ROWS as i32 {
        return (tx + ty * TOOLBOX_COLS as i32, GRID_SIZE as i32); // toolbox index, row=15
    }

    // Level numbers: two rows at bottom
    // Source: `iVar2 = (param_2 + 10) / 0x14 + -1` and `iVar1 = (param_3 + -0x186) / 0x14 + -1`
    let lx = (px + 10) / 20 - 1;
    let ly = (py - 390) / 20 - 1;
    if lx >= 0 && lx < 25 && ly >= 0 && ly < 2 {
        let level = lx + ly * 25;
        return (level, -2); // level index, row=-2 indicates level number
    }

    (-1, -1) // Not in any clickable area
}

/// Handle mouse input.
/// Source: FUN_00401f70 @ 0x401f70
pub fn handle_mouse(game: &mut Game, action: MouseAction, px: i32, py: i32) {
    let (gx, gy) = pixel_to_grid(px, py);

    if game.game_state != GameState::Playing {
        // Not playing — only allow clicking level numbers
        if gy == -2 && gx >= 0 && gx < NUM_LEVELS as i32 {
            if matches!(action, MouseAction::LeftDown | MouseAction::LeftUp) {
                game.select_level(gx as usize);
            }
        }
        return;
    }

    match action {
        MouseAction::Move => {
            if game.drag_state == DragState::ClickStarted {
                // Check drag threshold (2px)
                // Source: checks abs(DAT_00417050 - param_2) < 2
                let dx = (game.click_start_x - px).abs();
                let dy = (game.click_start_y - py).abs();
                if dx >= 2 || dy >= 2 {
                    // Start actual drag
                    start_drag(game);
                }
            }
            if game.drag_state == DragState::Dragging {
                game.drag_pixel_x = px;
                game.drag_pixel_y = py;
                game.dirty = true;
            }
        }
        MouseAction::LeftDown => {
            if gx < 0 || gy < 0 { return; }

            if gy < GRID_SIZE as i32 {
                // Clicked on main grid
                let cell_type = game.grid[gy as usize][gx as usize].piece_type;
                if cell_type.is_moveable() {
                    game.selected_x = gx;
                    game.selected_y = gy;
                    game.click_start_x = px;
                    game.click_start_y = py;
                    game.drag_state = DragState::ClickStarted;
                }
            } else if gy == GRID_SIZE as i32 {
                // Clicked on toolbox
                // Source: FUN_00401f70 handles toolbox at row >= 0xf
                let idx = gx as usize;
                if idx < game.toolbox.len() {
                    game.selected_x = gx;
                    game.selected_y = gy;
                    game.click_start_x = px;
                    game.click_start_y = py;
                    game.drag_state = DragState::ClickStarted;
                }
            }
        }
        MouseAction::LeftUp => {
            if game.drag_state == DragState::Dragging {
                // Drop piece
                drop_piece(game, gx, gy);
            } else if game.drag_state == DragState::ClickStarted {
                // Click without drag = rotate piece (clockwise)
                // Source: FUN_00401f70 param_1==4 branch, `(&DAT_004190a2)[iVar4] = (&DAT_004190a2)[iVar4] - 1 & 7`
                if game.selected_y == GRID_SIZE as i32 {
                    // Rotate toolbox piece
                    let idx = game.selected_x as usize;
                    if idx < game.toolbox.len() {
                        game.toolbox[idx].rotation = game.toolbox[idx].rotation.wrapping_sub(1) & 7;
                        game.dirty = true;
                    }
                } else if game.selected_y >= 0 && game.selected_y < GRID_SIZE as i32
                    && game.selected_x >= 0 && game.selected_x < GRID_SIZE as i32 {
                    let cell = &mut game.grid[game.selected_y as usize][game.selected_x as usize];
                    if cell.piece_type.is_moveable() {
                        cell.rotation = cell.rotation.wrapping_sub(1) & 7;
                        game.recalc_and_redraw();
                    }
                }
                game.drag_state = DragState::Idle;
            } else if gy == -2 && gx >= 0 && gx < NUM_LEVELS as i32 {
                // Clicked on level number
                if game.level_accessible[gx as usize] {
                    game.select_level(gx as usize);
                }
            }
            game.drag_state = DragState::Idle;
        }
        MouseAction::RightUp => {
            // Right-click = rotate opposite direction
            // Source: FUN_00401f70 param_1==6 branch, `rotation + 1 & 7`
            if game.drag_state != DragState::Idle { return; }
            if gy == GRID_SIZE as i32 && gx >= 0 {
                // Rotate toolbox piece
                let idx = gx as usize;
                if idx < game.toolbox.len() {
                    game.toolbox[idx].rotation = (game.toolbox[idx].rotation + 1) & 7;
                    game.dirty = true;
                }
            } else if gy >= 0 && gy < GRID_SIZE as i32 && gx >= 0 && gx < GRID_SIZE as i32 {
                let cell = &mut game.grid[gy as usize][gx as usize];
                if cell.piece_type.is_moveable() {
                    cell.rotation = (cell.rotation + 1) & 7;
                    game.recalc_and_redraw();
                }
            }
        }
        _ => {}
    }
}

/// Start dragging a piece from the grid or toolbox.
/// Source: FUN_004022a0 @ 0x4022a0
fn start_drag(game: &mut Game) {
    let sx = game.selected_x as usize;
    let sy = game.selected_y;

    if sy == GRID_SIZE as i32 {
        // From toolbox
        if sx < game.toolbox.len() {
            game.drag_state = DragState::Dragging;
            game.drag_pixel_x = game.click_start_x;
            game.drag_pixel_y = game.click_start_y;
            game.dirty = true;
        } else {
            game.drag_state = DragState::Idle;
        }
    } else {
        let syu = sy as usize;
        if sx < GRID_SIZE && syu < GRID_SIZE && game.grid[syu][sx].piece_type.is_moveable() {
            game.drag_state = DragState::Dragging;
            game.drag_pixel_x = game.click_start_x;
            game.drag_pixel_y = game.click_start_y;
            game.dirty = true;
        } else {
            game.drag_state = DragState::Idle;
        }
    }
}

/// Drop a piece at the target grid location.
/// Source: FUN_00402350 @ 0x402350
fn drop_piece(game: &mut Game, target_x: i32, target_y: i32) {
    let sx = game.selected_x as usize;
    let sy = game.selected_y;
    let from_toolbox = sy == GRID_SIZE as i32;

    if target_x >= 0 && target_x < GRID_SIZE as i32
        && target_y >= 0 && target_y < GRID_SIZE as i32
    {
        let tx = target_x as usize;
        let ty = target_y as usize;
        if game.grid[ty][tx].piece_type == PieceType::Empty {
            if from_toolbox {
                // Move piece from toolbox to grid
                if sx < game.toolbox.len() {
                    game.grid[ty][tx] = game.toolbox.remove(sx);
                }
            } else {
                // Move piece within grid
                let syu = sy as usize;
                if syu < GRID_SIZE && sx < GRID_SIZE {
                    game.grid[ty][tx] = game.grid[syu][sx].clone();
                    game.grid[syu][sx] = Cell::default();
                }
            }
        }
    }
    // If dropped outside valid area, piece stays where it was

    game.recalc_and_redraw();
    game.drag_state = DragState::Idle;
}

/// Handle keyboard input.
/// Source: FUN_00402a80 @ 0x402a80
/// Key codes: 0x03=Ctrl+C, 0x16=Ctrl+V, 0x1b=ESC, 0x20=Space, 0x2b=+, 0x2d=-,
///            0x3d==, 0x4c=L, 0x72=R
pub fn handle_keypress(game: &mut Game, keycode: u32) -> bool {
    match keycode {
        0x1b => return true, // ESC = quit
        0x20 | 0x2b | 0x3d => {
            // Space, +, = → next level (if next is accessible)
            if game.current_level + 1 < NUM_LEVELS && game.level_accessible[game.current_level + 1] {
                game.next_level();
            }
        }
        0x2d => {
            // - → previous level
            game.prev_level();
        }
        0x72 => {
            // R → reset level
            game.reset_level();
        }
        0x4c => {
            // L → cheat (force win)
            game.cheat_flag = true;
            game.check_win_condition();
            game.dirty = true;
        }
        // Ctrl+C and Ctrl+V would go here — clipboard not yet implemented
        _ => {}
    }
    false // Don't quit
}
