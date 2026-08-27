/// Beam tracing engine — the core physics of Chromatron.
/// Source: FUN_00401030–FUN_004018e0

use crate::types::*;

/// A beam being propagated through the grid.
#[derive(Clone)]
struct Beam {
    x: i32,
    y: i32,
    dir: u8,
    color: u8,
    entangle_id: u32,
}

/// Clear all beam data in the grid (incoming and outgoing).
/// Source: FUN_00401860 @ 0x401860 — zeros bytes[3-11] in each cell
pub fn clear_beams(grid: &mut [[Cell; GRID_SIZE]; GRID_SIZE]) {
    for row in grid.iter_mut() {
        for cell in row.iter_mut() {
            cell.beam_incoming = [0; 8];
            cell.beam_outgoing = [0; 8];
        }
    }
}

/// Check if a target cell is satisfied (all required colors present).
/// Source: FUN_004018e0 @ 0x4018e0
/// ORs all 8 incoming beam bytes, compares to required color (cell.color)
pub fn check_target_satisfied(cell: &Cell) -> bool {
    let mut received: u8 = 0;
    for i in 0..8 {
        received |= cell.beam_incoming[i];
    }
    received == cell.color
}

/// Recalculate all beams: clear then emit from all lasers.
/// Source: FUN_004018d0 @ 0x4018d0
pub fn recalculate_beams(grid: &mut [[Cell; GRID_SIZE]; GRID_SIZE]) {
    clear_beams(grid);
    emit_from_lasers(grid);
}

/// Scan grid for lasers and trace beams from each.
/// Source: FUN_00401890 @ 0x401890 — iterates grid, calls trace for type==2
fn emit_from_lasers(grid: &mut [[Cell; GRID_SIZE]; GRID_SIZE]) {
    for y in 0..GRID_SIZE {
        for x in 0..GRID_SIZE {
            if grid[y][x].piece_type == PieceType::Laser {
                let dir = grid[y][x].rotation;
                let color = grid[y][x].color;
                trace_beams(grid, x as i32, y as i32, dir, color, 0);
            }
        }
    }
}

/// Main beam propagation loop (BFS with double-buffered queues).
/// Source: FUN_00401620 @ 0x401620
///
/// The algorithm uses two queues that swap each iteration:
/// 1. Start with initial beam in queue A
/// 2. For each beam in queue A: advance one step, interact with piece at new cell
/// 3. New beams go into queue B
/// 4. Swap A and B, repeat until empty or max iterations (1024)
fn trace_beams(
    grid: &mut [[Cell; GRID_SIZE]; GRID_SIZE],
    start_x: i32,
    start_y: i32,
    start_dir: u8,
    start_color: u8,
    start_entangle: u32,
) {
    let mut queue_a: Vec<Beam> = vec![Beam {
        x: start_x,
        y: start_y,
        dir: start_dir,
        color: start_color,
        entangle_id: start_entangle,
    }];
    let mut queue_b: Vec<Beam> = Vec::new();
    let mut entangle_counter: u32 = 1;

    for _iteration in 0..MAX_BEAM_ITERATIONS {
        if queue_a.is_empty() {
            break;
        }
        queue_b.clear();

        for beam in &queue_a {
            // Source: `(&DAT_004190ac)[cell * 0x14 + dir] |= color` — the outgoing
            // mark is written when the beam is *dequeued*, at the cell it leaves
            // from, so the seed beam marks the laser cell and beams dropped by the
            // 32-entry queue cap are never marked.
            grid[beam.y as usize][beam.x as usize].beam_outgoing[beam.dir as usize & 7] |= beam.color;

            let dx = Direction::DX[beam.dir as usize & 7];
            let dy = Direction::DY[beam.dir as usize & 7];
            let nx = beam.x + dx;
            let ny = beam.y + dy;

            if nx < 0 || nx >= GRID_SIZE as i32 || ny < 0 || ny >= GRID_SIZE as i32 {
                continue;
            }

            // Interact with piece at this cell
            // (beam_outgoing is set inside interact_piece via emit_beam)
            interact_piece(
                grid, &mut queue_b, &mut entangle_counter,
                nx, ny, beam.dir, beam.color, beam.entangle_id,
            );
        }

        // Handle doppler entanglement resolution for new beams
        // Source: FUN_00401620 inner loop at ~0x401700 — checks type==7 (Doppler)
        // and adjusts entangled beam colors
        resolve_entanglement(&mut queue_b, grid);

        std::mem::swap(&mut queue_a, &mut queue_b);
    }
}

/// Beam-piece interaction — the giant switch on piece type.
/// Source: FUN_00401090 @ 0x401090
///
/// This is the core of Chromatron's physics. Each piece type handles
/// incoming beams differently.
fn interact_piece(
    grid: &mut [[Cell; GRID_SIZE]; GRID_SIZE],
    queue: &mut Vec<Beam>,
    entangle_counter: &mut u32,
    x: i32,
    y: i32,
    dir: u8,
    color: u8,
    entangle_id: u32,
) {
    let ux = x as usize;
    let uy = y as usize;
    let cell_type = grid[uy][ux].piece_type;
    let cell_rot = grid[uy][ux].rotation;
    let cell_color = grid[uy][ux].color;

    // Mark incoming beam
    grid[uy][ux].beam_incoming[dir as usize & 7] |= color;

    // Relative direction: how the beam approaches relative to piece's orientation
    // Source: `uVar4 = param_3 - (uint)bVar7 & 7` in FUN_00401090
    let rel_dir = (dir.wrapping_sub(cell_rot)) & 7;

    match cell_type {
        PieceType::Empty => {
            // Beam passes through empty cell
            emit_beam(grid, queue, x, y, dir, color, entangle_id);
        }
        PieceType::Wall => {
            // Wall blocks the beam — do nothing
        }
        PieceType::Laser => {
            // Laser also blocks (beam hits the emitter)
        }
        PieceType::Reflector => {
            // Source: case 3 in FUN_00401090
            // Reflects beam: relative dir 1→rot-1, 2→rot-2, 3→rot-3
            match rel_dir {
                1 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(1)) & 7, color, entangle_id),
                2 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(2)) & 7, color, entangle_id),
                3 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(3)) & 7, color, entangle_id),
                _ => {} // Other angles: beam blocked
            }
        }
        PieceType::Bender => {
            // Source: case 4 in FUN_00401090
            // Angled reflector: 0→rot-1, 1→rot-2, 2→rot-3, 3→rot-4
            match rel_dir {
                0 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(1)) & 7, color, entangle_id),
                1 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(2)) & 7, color, entangle_id),
                2 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(3)) & 7, color, entangle_id),
                3 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(4)) & 7, color, entangle_id),
                _ => {} // Blocked
            }
        }
        PieceType::Filter => {
            // Source: case 5 in FUN_00401090
            // Only passes through matching color on directions 2 and 6 (along axis)
            if (rel_dir == 2 || rel_dir == 6) && (cell_color & color) != 0 {
                emit_beam(grid, queue, x, y, dir, cell_color & color, entangle_id);
            }
        }
        PieceType::Prism => {
            // Source: case 6 in FUN_00401090
            // Bends R/G/B differently based on relative direction
            // Blue (bit 2):
            if color & 4 != 0 {
                let out_dir = match rel_dir {
                    1 => Some((cell_rot.wrapping_add(1)) & 7),
                    2 => Some((cell_rot.wrapping_add(2)) & 7),
                    5 => Some((cell_rot.wrapping_sub(3)) & 7),
                    6 => Some((cell_rot.wrapping_sub(2)) & 7),
                    _ => None,
                };
                if let Some(d) = out_dir {
                    emit_beam(grid, queue, x, y, d, 4, entangle_id);
                }
            }
            // Green (bit 1):
            if color & 2 != 0 {
                let out_dir = match rel_dir {
                    0 => Some((cell_rot.wrapping_add(1)) & 7),
                    2 => Some((cell_rot.wrapping_add(3)) & 7),
                    5 => Some((cell_rot.wrapping_sub(4)) & 7),
                    7 => Some((cell_rot.wrapping_sub(2)) & 7),
                    _ => None,
                };
                if let Some(d) = out_dir {
                    emit_beam(grid, queue, x, y, d, 2, entangle_id);
                }
            }
            // Red (bit 0):
            if color & 1 != 0 {
                match rel_dir {
                    0 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(2)) & 7, 1, entangle_id),
                    2 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(4)) & 7, 1, entangle_id),
                    5 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_add(3)) & 7, 1, entangle_id),
                    7 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_add(1)) & 7, 1, entangle_id),
                    _ => {}
                }
            }
        }
        PieceType::Doppler => {
            // Source: case 7 in FUN_00401090
            // Only relative angles 2 and 6 pass; every other angle is absorbed.
            if rel_dir == 2 {
                // Source: `if (param_4 & 4) uVar4 = 2; if (param_4 & 2) uVar4 |= 1;
                //          if (param_4 & 1) uVar4 |= 4;`  → R→G, G→B, B→R (forward)
                // Same mapping as DOPPLER_REL2 (DAT_0040b088).
                let mut new_color: u8 = 0;
                if color & 4 != 0 { new_color |= 2; } // R→G
                if color & 2 != 0 { new_color |= 1; } // G→B
                if color & 1 != 0 { new_color |= 4; } // B→R
                if entangle_id != 0 {
                    // Source: `if (param_5 != 0) uVar4 = param_4;`
                    // Entangled beams keep their colour here; the shift is applied
                    // afterwards by resolve_entanglement, to both halves of the pair.
                    new_color = color;
                }
                emit_beam(grid, queue, x, y, dir, new_color, entangle_id);
            } else if rel_dir == 6 {
                // Source: `bVar7 = (param_4 & 4) != 0; if (param_4 & 2) bVar7 |= 4;
                //          if (param_4 & 1) bVar7 |= 2;`  → R→B, B→G, G→R (backwards)
                // Same mapping as DOPPLER_REL6 (DAT_0040b074).
                let mut new_color: u8 = 0;
                if color & 4 != 0 { new_color |= 1; } // R→B
                if color & 2 != 0 { new_color |= 4; } // G→R
                if color & 1 != 0 { new_color |= 2; } // B→G
                if entangle_id != 0 {
                    new_color = color;
                }
                emit_beam(grid, queue, x, y, dir, new_color, entangle_id);
            }
            // Other directions: blocked
        }
        PieceType::Splitter => {
            // Source: case 8 in FUN_00401090
            // Source: `if ((uVar4 != 0) && (uVar4 != 4)) { ... }`
            // Head-on along the splitter's axis (rel 0 / 4): the beam is absorbed,
            // nothing is emitted at all.
            if rel_dir == 0 || rel_dir == 4 {
                return;
            }

            // Source: `if ((uVar4 != 2) && (uVar4 != 6)) param_5 = 0;`
            // Only the perpendicular crossing keeps entanglement; a diagonal hit
            // collapses the wave function on both output beams.
            let eid = if rel_dir == 2 || rel_dir == 6 { entangle_id } else { 0 };
            emit_beam(grid, queue, x, y, dir, color, eid); // Straight through

            // Split at diagonal approaches (the reflected copy is never entangled)
            match rel_dir {
                1 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(1)) & 7, color, 0),
                3 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(3)) & 7, color, 0),
                5 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_add(3)) & 7, color, 0),
                7 => emit_beam(grid, queue, x, y, (cell_rot.wrapping_add(1)) & 7, color, 0),
                _ => {}
            }
        }
        PieceType::Tangler => {
            // Source: case 9 in FUN_00401090
            // Takes beam on one side (rel_dir==2), outputs entangled pair in both directions
            if rel_dir == 2 {
                // Split each color component into separate entangled pairs
                let mut bit = 1u8;
                while bit < 5 {
                    if color & bit != 0 {
                        let eid = *entangle_counter;
                        emit_beam(grid, queue, x, y, cell_rot & 7, bit, eid);
                        emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(4)) & 7, bit, eid);
                        *entangle_counter += 1;
                    }
                    bit *= 2;
                }
            }
            // Other directions: blocked (tangler only accepts from one side)
        }
        PieceType::Target => {
            // Source: case 0xa in FUN_00401090
            // Target just passes beam through (absorbs and marks)
            emit_beam(grid, queue, x, y, dir, color, entangle_id);
        }
        PieceType::Conduit => {
            // Source: case 0xb in FUN_00401090
            // Only passes beam on axis-aligned directions (0 and 4 = N and S, relative)
            if rel_dir == 0 || rel_dir == 4 {
                emit_beam(grid, queue, x, y, dir, color, entangle_id);
            }
        }
        PieceType::Teleporter => {
            // Source: case 0xc in FUN_00401090
            // Beam jumps to next teleporter in same direction
            let dx = Direction::DX[dir as usize & 7];
            let dy = Direction::DY[dir as usize & 7];
            let mut tx = x + dx;
            let mut ty = y + dy;
            while tx >= 0 && tx < GRID_SIZE as i32 && ty >= 0 && ty < GRID_SIZE as i32 {
                if grid[ty as usize][tx as usize].piece_type == PieceType::Teleporter {
                    // Found next teleporter — emit beam from there
                    emit_beam(grid, queue, tx, ty, dir, color, entangle_id);
                    break;
                }
                tx += dx;
                ty += dy;
            }
            // If no teleporter found, beam disappears
        }
    }
}

/// Append a beam to the next-step queue.
/// Source: FUN_00401030 @ 0x401030 — a plain bounded push; the queue silently
/// drops everything past 32 entries (`if (DAT_0041a984 != 0x20)`). The outgoing
/// beam mark is *not* written here — it happens on dequeue in trace_beams.
fn emit_beam(
    _grid: &mut [[Cell; GRID_SIZE]; GRID_SIZE],
    queue: &mut Vec<Beam>,
    x: i32, y: i32, dir: u8, color: u8, entangle_id: u32,
) {
    let d = dir & 7;
    if queue.len() < MAX_BEAM_QUEUE {
        queue.push(Beam { x, y, dir: d, color, entangle_id });
    }
}

/// Resolve entanglement for beams standing on a doppler.
/// Source: second inner loop of FUN_00401620 @ ~0x401700, run after every
/// propagation step over the freshly filled queue.
///
/// For each beam `i` that sits on a doppler and carries an entanglement id,
/// *every* beam in the queue sharing that id — beam `i` included — gets a
/// colour shift. Beam `i` itself takes the shift for the angle it crossed at;
/// its entangled partners take the opposite one. This is what makes the
/// quantum tangler work: dopplering one half of a pair shifts the other half
/// backwards, even though that half never touched a doppler.
///
/// Source: `if ((iVar10 == iVar9) == ((cVar3 - cVar2 & 7U) == 2))
///              bVar4 = (&DAT_0040b088)[color * 4];
///          else bVar4 = (&DAT_0040b074)[color * 4];`
/// where cVar2 is the doppler's rotation and cVar3 is beam i's direction.
fn resolve_entanglement(queue: &mut Vec<Beam>, grid: &[[Cell; GRID_SIZE]; GRID_SIZE]) {
    let len = queue.len();
    for i in 0..len {
        let eid = queue[i].entangle_id;
        // Source: `*(int *)(puVar11 + iVar10 * 8 + 4) != 0` plus the x/y < 0xf bounds check
        if eid == 0 {
            continue;
        }
        let (bx, by, bdir) = (queue[i].x, queue[i].y, queue[i].dir);
        if bx < 0 || bx >= GRID_SIZE as i32 || by < 0 || by >= GRID_SIZE as i32 {
            continue;
        }
        let cell = &grid[by as usize][bx as usize];
        // Source: `(&DAT_004190a0)[iVar9] == '\a'` — piece type 7
        if cell.piece_type != PieceType::Doppler {
            continue;
        }
        // Source: `(cVar3 - cVar2 & 7U) == 2`
        let at_rel2 = (bdir.wrapping_sub(cell.rotation) & 7) == 2;

        for j in 0..len {
            if queue[j].entangle_id != eid {
                continue;
            }
            let c = queue[j].color as usize & 7;
            queue[j].color = if (i == j) == at_rel2 {
                DOPPLER_REL2[c]
            } else {
                DOPPLER_REL6[c]
            };
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::levels::{LEVELS, LEVEL_ORDER};

    /// Build a grid with every piece of a level placed exactly where the level
    /// data puts it. The shipped piece positions ARE the intended solution:
    /// on load, `init_toolbox` (FUN_004023f0) lifts the moveable types 3..9 out
    /// of the grid and into the toolbox, leaving the player to put them back.
    fn grid_from_level(data_idx: usize) -> [[Cell; GRID_SIZE]; GRID_SIZE] {
        let mut grid: [[Cell; GRID_SIZE]; GRID_SIZE] = Default::default();
        for p in LEVELS[data_idx].pieces {
            grid[p.y as usize][p.x as usize].piece_type = PieceType::from_u8(p.piece_type);
            grid[p.y as usize][p.x as usize].rotation = p.rotation;
            grid[p.y as usize][p.x as usize].color = p.color;
        }
        grid
    }

    fn unsatisfied_targets(data_idx: usize) -> Vec<(usize, usize, u8, u8)> {
        let mut grid = grid_from_level(data_idx);
        recalculate_beams(&mut grid);
        let mut bad = Vec::new();
        for y in 0..GRID_SIZE {
            for x in 0..GRID_SIZE {
                let cell = &grid[y][x];
                if cell.piece_type == PieceType::Target && !check_target_satisfied(cell) {
                    let got = cell.beam_incoming.iter().fold(0u8, |a, b| a | b);
                    bad.push((x, y, cell.color, got));
                }
            }
        }
        bad
    }

    /// Game level 26 is the quantum tangler tutorial (level data index 36).
    /// A blue beam enters the tangler at (7,8). Its west half runs backwards
    /// through the doppler at (6,8) and turns green (lighting the green pinwheel
    /// at (4,10)); that must drag its entangled east partner the other way, to
    /// red, for the red pinwheel at (10,4). The blue pinwheel at (7,7) is lit by
    /// the laser beam on its way into the tangler.
    #[test]
    fn tangler_tutorial_level_is_solved_by_its_own_layout() {
        assert_eq!(LEVEL_ORDER[25], 36);
        assert_eq!(unsatisfied_targets(36), vec![]);
    }

    /// Game level 16 (level data index 32) is the one shipped layout that does
    /// not light every pinwheel: the blue laser leaves the bender at (11,3)
    /// heading south-east and runs off the board, so the red pinwheel at (9,7)
    /// stays dark and the reflector at (12,2) is never touched. The level uses
    /// only lasers, walls, reflectors and benders — no doppler, splitter or
    /// tangler — so this is a property of the stored layout, not of the beam
    /// engine. The level is still solvable by hand from the toolbox.
    const LAYOUT_IS_NOT_A_SOLUTION: [u8; 1] = [32];

    /// Every playable level's shipped layout is the level designer's solution:
    /// on load, `init_toolbox` lifts the moveable pieces off the board, and the
    /// player has to put them back. So tracing the layout as stored must light
    /// every pinwheel.
    #[test]
    fn all_levels_are_solved_by_their_own_layout() {
        let mut failures = Vec::new();
        for (n, &data_idx) in LEVEL_ORDER.iter().enumerate() {
            if LAYOUT_IS_NOT_A_SOLUTION.contains(&data_idx) {
                continue;
            }
            let bad = unsatisfied_targets(data_idx as usize);
            if !bad.is_empty() {
                failures.push(format!("level {} (data {}): {:?}", n + 1, data_idx, bad));
            }
        }
        assert!(failures.is_empty(), "unsolved levels:\n{}", failures.join("\n"));
    }
}

