/// Core game state and logic.
/// Source: grid at DAT_004190a0, game state vars throughout 0x417xxx-0x41axxx

use crate::types::*;
use crate::levels::LEVELS;
use crate::beam;

/// The main game state, mirroring the original's global variables.
pub struct Game {
    /// 15×15 game grid
    /// Source: DAT_004190a0, 15×15 × 20 bytes
    pub grid: [[Cell; GRID_SIZE]; GRID_SIZE],

    /// Toolbox pieces (stored in grid rows >= GRID_SIZE conceptually)
    /// Source: DAT_0041a234 area — pieces moved from grid to toolbox
    pub toolbox: Vec<Cell>,

    /// Current level index (0–49)
    /// Source: DAT_00417c70
    pub current_level: usize,

    /// Level data index into the level definitions array
    /// Source: DAT_0041a864
    pub level_data_index: usize,

    /// Game state (not playing / playing)
    /// Source: DAT_0041a800
    pub game_state: GameState,

    /// Win flag for current level
    /// Source: DAT_0041a980
    pub win_flag: bool,

    /// Level completion status (50 levels)
    /// Source: DAT_0041a9a0[64]
    pub level_completed: [bool; NUM_LEVELS],

    /// Level accessibility status
    /// Source: DAT_0041a880[64]
    pub level_accessible: [bool; NUM_LEVELS],

    /// Drag state
    /// Source: DAT_00417c74
    pub drag_state: DragState,

    /// Selected cell coordinates during drag
    /// Source: DAT_0041846c (x), DAT_00418468 (y)
    pub selected_x: i32,
    pub selected_y: i32,

    /// Drag pixel position
    /// Source: DAT_00417c64, DAT_00417c68
    pub drag_pixel_x: i32,
    pub drag_pixel_y: i32,

    /// Click start position (for drag threshold)
    /// Source: DAT_00417050, DAT_00417054
    pub click_start_x: i32,
    pub click_start_y: i32,

    /// Saved grid states per level
    /// Source: DAT_00418ea0[64] — dynamically allocated
    pub saved_states: Vec<Option<Vec<Vec<Cell>>>>,

    /// Cheat flag (L key)
    /// Source: DAT_0041a860
    pub cheat_flag: bool,

    /// Dirty flag — needs repaint
    /// Source: managed via InvalidateRect / DAT_0040b030
    pub dirty: bool,
}

impl Game {
    pub fn new() -> Self {
        let grid = std::array::from_fn(|_| std::array::from_fn(|_| Cell::default()));
        let mut game = Self {
            grid,
            toolbox: Vec::new(),
            current_level: 0,
            level_data_index: 0,
            game_state: GameState::NotPlaying,
            win_flag: false,
            level_completed: [false; NUM_LEVELS],
            level_accessible: [false; NUM_LEVELS],
            drag_state: DragState::Idle,
            selected_x: 0,
            selected_y: 0,
            drag_pixel_x: 0,
            drag_pixel_y: 0,
            click_start_x: 0,
            click_start_y: 0,
            saved_states: (0..NUM_LEVELS).map(|_| None).collect(),
            cheat_flag: false,
            dirty: true,
        };
        game.compute_level_access();
        game.load_level(true);
        game
    }

    /// Load a level from level definitions.
    /// Source: FUN_004024f0 @ 0x4024f0 (load_level) + FUN_004037c0 @ 0x4037c0 (load_level_data)
    pub fn load_level(&mut self, from_saved: bool) {
        let level_idx = self.current_level;
        let data_idx = crate::levels::LEVEL_ORDER[level_idx] as usize;
        self.level_data_index = data_idx;

        if from_saved {
            if let Some(saved) = &self.saved_states[level_idx] {
                // Restore from saved state
                for y in 0..GRID_SIZE {
                    for x in 0..GRID_SIZE {
                        self.grid[y][x] = saved[y][x].clone();
                    }
                }
                self.check_win_condition();
                self.game_state = GameState::Playing;
                self.dirty = true;
                return;
            }
        }

        // Load fresh from level data
        // Source: FUN_004037c0 @ 0x4037c0 — zeros grid, then parses 5-byte piece records
        self.clear_grid();

        if data_idx < LEVELS.len() {
            let level = &LEVELS[data_idx];
            for piece in level.pieces {
                let x = piece.x as usize;
                let y = piece.y as usize;
                if x < GRID_SIZE && y < GRID_SIZE {
                    self.grid[y][x].piece_type = PieceType::from_u8(piece.piece_type);
                    self.grid[y][x].rotation = piece.rotation;
                    self.grid[y][x].color = piece.color;
                }
            }
        }

        // Move moveable pieces to toolbox
        // Source: FUN_004023f0 @ 0x4023f0 (init_toolbox)
        self.init_toolbox();
        self.check_win_condition();
        self.game_state = GameState::Playing;
        self.dirty = true;
    }

    /// Clear the grid
    fn clear_grid(&mut self) {
        for row in &mut self.grid {
            for cell in row {
                *cell = Cell::default();
            }
        }
    }

    /// Move all moveable pieces from grid to toolbox
    /// Source: FUN_004023f0 @ 0x4023f0
    fn init_toolbox(&mut self) {
        self.toolbox.clear();
        for y in 0..GRID_SIZE {
            for x in 0..GRID_SIZE {
                if self.grid[y][x].piece_type.is_moveable() {
                    let mut cell = self.grid[y][x].clone();
                    cell.rotation = 0; // Reset rotation for toolbox
                    self.toolbox.push(cell);
                    self.grid[y][x] = Cell::default();
                }
            }
        }
        // Sort toolbox pieces by type then color (matches original's qsort)
        self.toolbox.sort_by_key(|c| (c.piece_type as u8, c.color));
    }

    /// Save current grid state for this level
    /// Source: FUN_004024b0 @ 0x4024b0
    pub fn save_grid_state(&mut self) {
        let state: Vec<Vec<Cell>> = self.grid.iter()
            .map(|row| row.iter().cloned().collect())
            .collect();
        self.saved_states[self.current_level] = Some(state);
    }

    /// Compute which levels are accessible
    /// Source: FUN_00401910 @ 0x401910 — progressive unlock based on completion
    pub fn compute_level_access(&mut self) {
        // Find highest completed level
        let mut highest = 0;
        for i in (0..NUM_LEVELS).rev() {
            if self.level_completed[i] {
                highest = i;
                break;
            }
        }

        // Unlock count based on thresholds
        // Source: checks at 0x401910: >8→+1, >18→+1, >25→+1, >34→+2
        let mut unlock_count = 1;
        if highest > 8 { unlock_count = 2; }
        if highest > 18 { unlock_count += 1; }
        if highest > 25 { unlock_count += 1; }
        if highest > 34 { unlock_count += 2; }

        for i in 0..NUM_LEVELS {
            if self.level_completed[i] {
                self.level_accessible[i] = true;
            } else if unlock_count > 0 {
                self.level_accessible[i] = true;
                unlock_count -= 1;
            }
        }
    }

    /// Recalculate all beams and check win condition
    /// Source: FUN_00401d10 @ 0x401d10
    pub fn check_win_condition(&mut self) {
        beam::recalculate_beams(&mut self.grid);

        // Check all targets
        // Source: FUN_00401d10 iterates grid looking for type==10 (Target)
        let mut all_satisfied = true;
        for y in 0..GRID_SIZE {
            for x in 0..GRID_SIZE {
                if self.grid[y][x].piece_type == PieceType::Target {
                    if !beam::check_target_satisfied(&self.grid[y][x]) {
                        all_satisfied = false;
                    }
                }
            }
        }

        // Cheat flag override
        // Source: DAT_0041a860 check at 0x401d10
        if self.cheat_flag {
            all_satisfied = true;
            self.cheat_flag = false;
        }

        self.win_flag = all_satisfied;

        // If won and not already completed, mark as completed
        // Source: 0x401d10 checks DAT_0041a800 and DAT_0041a980
        if self.game_state == GameState::Playing && self.win_flag && !self.level_completed[self.current_level] {
            self.level_completed[self.current_level] = true;
            self.save_grid_state();
            self.compute_level_access();
        }
    }

    /// Select and load a level by number (0-indexed)
    /// Source: FUN_00402560 @ 0x402560
    pub fn select_level(&mut self, level: usize) {
        if level >= NUM_LEVELS { return; }
        self.save_grid_state();
        self.current_level = level;
        self.load_level(true);
    }

    /// Advance to next level
    /// Source: FUN_004025e0 @ 0x4025e0
    pub fn next_level(&mut self) {
        self.save_grid_state();
        if self.current_level < NUM_LEVELS - 1 {
            self.current_level += 1;
        }
        self.load_level(true);
    }

    /// Go to previous level
    /// Source: FUN_00402610 @ 0x402610
    pub fn prev_level(&mut self) {
        self.save_grid_state();
        if self.current_level > 0 {
            self.current_level -= 1;
        }
        self.load_level(true);
    }

    /// Reset current level from fresh data
    /// Source: FUN_004024f0(0) @ 0x4024f0 with param_1=0
    pub fn reset_level(&mut self) {
        self.load_level(false);
    }

    /// Recalculate beams and mark dirty for repaint
    /// Source: FUN_00401f50 @ 0x401f50
    pub fn recalc_and_redraw(&mut self) {
        self.check_win_condition();
        self.dirty = true;
    }

    /// Get the cell being dragged (if any).
    pub fn get_dragged_cell(&self) -> Option<&Cell> {
        if self.drag_state != DragState::Dragging {
            return None;
        }
        let sx = self.selected_x as usize;
        if self.selected_y == GRID_SIZE as i32 {
            self.toolbox.get(sx)
        } else {
            let sy = self.selected_y as usize;
            if sx < GRID_SIZE && sy < GRID_SIZE {
                Some(&self.grid[sy][sx])
            } else {
                None
            }
        }
    }

    /// Get instruction text for current level
    pub fn get_instruction_text(&self) -> &str {
        let data_idx = crate::levels::LEVEL_ORDER[self.current_level] as usize;
        if data_idx < LEVELS.len() {
            &LEVELS[data_idx].text
        } else {
            ""
        }
    }
}
