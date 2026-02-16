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
            // Color shift: forward (rel_dir==2) or reverse (rel_dir==6)
            // Source: DOPPLER_FWD[1]=2,FWD[2]=4,FWD[4]=1 → R→G, G→B, B→R
            // Source: DOPPLER_REV[1]=4,REV[2]=1,REV[4]=2 → R→B, G→R, B→G
            if rel_dir == 2 {
                // Forward: R→G, G→B, B→R
                let mut new_color: u8 = 0;
                if color & 1 != 0 { new_color |= 2; } // R→G
                if color & 2 != 0 { new_color |= 4; } // G→B
                if color & 4 != 0 { new_color |= 1; } // B→R
                if entangle_id != 0 {
                    new_color = color; // Entangled beams pass through unchanged initially
                }
                emit_beam(grid, queue, x, y, dir, new_color, entangle_id);
            } else if rel_dir == 6 {
                // Reverse: R→B, G→R, B→G
                let mut new_color: u8 = 0;
                if color & 1 != 0 { new_color |= 4; } // R→B
                if color & 2 != 0 { new_color |= 1; } // G→R
                if color & 4 != 0 { new_color |= 2; } // B→G
                if entangle_id != 0 {
                    new_color = color;
                }
                emit_beam(grid, queue, x, y, dir, new_color, entangle_id);
            }
            // Other directions: blocked
        }
        PieceType::Splitter => {
            // Source: case 8 in FUN_00401090
            // Beam passes through + splits at angles 1,3,5,7 (diagonal approach)
            // Head-on (0,4) or perpendicular (2,6): just passes through
            let passes_through = rel_dir == 0 || rel_dir == 4 || rel_dir == 2 || rel_dir == 6;
            if passes_through {
                // Collapse entanglement when going through splitter
                let eid = if rel_dir == 2 || rel_dir == 6 { entangle_id } else { 0 };
                emit_beam(grid, queue, x, y, dir, color, eid);
            }

            // Split at diagonal approaches
            match rel_dir {
                1 => {
                    emit_beam(grid, queue, x, y, dir, color, 0); // Through
                    emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(1)) & 7, color, 0); // Reflect
                }
                3 => {
                    emit_beam(grid, queue, x, y, dir, color, 0);
                    emit_beam(grid, queue, x, y, (cell_rot.wrapping_sub(3)) & 7, color, 0);
                }
                5 => {
                    emit_beam(grid, queue, x, y, dir, color, 0);
                    emit_beam(grid, queue, x, y, (cell_rot.wrapping_add(3)) & 7, color, 0);
                }
                7 => {
                    emit_beam(grid, queue, x, y, dir, color, 0);
                    emit_beam(grid, queue, x, y, (cell_rot.wrapping_add(1)) & 7, color, 0);
                }
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

/// Add a beam to the queue AND mark outgoing direction on the cell for rendering.
/// This ensures beams visually originate from cell centers at the correct output angle.
fn emit_beam(
    grid: &mut [[Cell; GRID_SIZE]; GRID_SIZE],
    queue: &mut Vec<Beam>,
    x: i32, y: i32, dir: u8, color: u8, entangle_id: u32,
) {
    let d = dir & 7;
    grid[y as usize][x as usize].beam_outgoing[d as usize] |= color;
    if queue.len() < MAX_BEAM_QUEUE {
        queue.push(Beam { x, y, dir: d, color, entangle_id });
    }
}

/// Resolve entanglement for beams going through dopplers.
/// Source: inner loop in FUN_00401620 @ ~0x401700
/// When entangled beams go through dopplers, the shift on one beam
/// causes the opposite shift on its partner.
fn resolve_entanglement(queue: &mut Vec<Beam>, grid: &[[Cell; GRID_SIZE]; GRID_SIZE]) {
    // Find pairs of entangled beams passing through dopplers
    let len = queue.len();
    for i in 0..len {
        for j in 0..len {
            if queue[i].entangle_id != 0 && queue[i].entangle_id == queue[j].entangle_id {
                let iy = queue[i].y as usize;
                let ix = queue[i].x as usize;
                if iy < GRID_SIZE && ix < GRID_SIZE {
                    let cell = &grid[iy][ix];
                    if cell.piece_type == PieceType::Doppler {
                        let rel_i = (queue[i].dir.wrapping_sub(cell.rotation)) & 7;
                        let rel_j = (queue[j].dir.wrapping_sub(cell.rotation)) & 7;
                        // If one beam goes forward and the other is this beam,
                        // apply opposite doppler to partner
                        if i == j {
                            if (rel_i.wrapping_sub(cell.rotation) & 7) == 2 {
                                queue[i].color = DOPPLER_FWD[queue[i].color as usize & 7];
                            }
                        } else {
                            // Partner gets opposite shift
                            if (rel_i == 2) == (rel_j == 2) {
                                // Same direction — use forward
                                queue[j].color = DOPPLER_FWD[queue[j].color as usize & 7];
                            } else {
                                // Opposite — use reverse
                                queue[j].color = DOPPLER_REV[queue[j].color as usize & 7];
                            }
                        }
                    }
                }
            }
        }
    }
}
