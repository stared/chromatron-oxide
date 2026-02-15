# Chromatron Win32 Binary - Comprehensive Annotated Function Map

Decompiled from `chromatron_unpacked.exe` (Ghidra). Cross-referenced with Mac PPC binary `chromatron1`.

All game logic lives in 0x00401000 -- 0x00403EB0. CRT/stdlib starts at 0x00403F35 (_malloc).

---

## Data Structures

### Grid / Board

- **DAT_004190a0** = `grid[15][15]` -- the main game board. Each cell is **0x14 (20) bytes**.
  - Total size: 15 * 15 * 20 = 4500 bytes (0x1194), spans `0x004190a0` to `0x0041a234`.
- **Cell layout** (20 bytes per cell):
  - `[+0x00]` (DAT_004190a0) = **piece type** (byte)
  - `[+0x01]` (DAT_004190a1) = **color/subtype** (byte) -- for lasers: beam color; for filters: color mask; for targets: required color
  - `[+0x02]` (DAT_004190a2) = **rotation/direction** (byte, 0-7 for 8 compass directions)
  - `[+0x03]` (DAT_004190a3) = unused/padding
  - `[+0x04..+0x0B]` (DAT_004190a4) = **beam_incoming[8]** -- bitmask of beam colors arriving FROM each of 8 directions (first buffer)
  - `[+0x0C..+0x13]` (DAT_004190ac) = **beam_outgoing[8]** -- bitmask of beam colors passing THROUGH in each of 8 directions (second buffer / accumulated)

### Piece Types (byte at offset +0x00)

| Value | Piece         | Description                                                   |
|-------|---------------|---------------------------------------------------------------|
| 0     | Empty         | No piece                                                      |
| 1     | Wall          | Blocks beams                                                  |
| 2     | Laser         | Emits a beam; subtype=color (1=red, 2=green, 4=blue, 7=white) |
| 3     | Reflector     | Mirror that reflects beams at angles 1-3 relative to facing   |
| 4     | Bender        | Angled reflector; bends H/V to diagonals and vice versa       |
| 5     | Filter        | Only passes light matching its color mask                     |
| 6     | Prism         | Refracts R/G/B differently on its long face                   |
| 7     | Doppler       | Shifts colors: R->G->B->R (forward) or R->B->G->R (backward) |
| 8     | Splitter      | Passes beam through and splits at 45-degree angles            |
| 9     | Tangler       | Quantum tangler: outputs entangled beam pair in opposite dirs |
| 10    | Target/Pinwheel | Must be lit with correct color to win                       |
| 11    | Conduit       | Only passes beams in cardinal (H/V) directions                |
| 12    | Teleporter    | Beam jumps to next teleporter in same direction               |

### Color Bitmask

| Bit | Color |
|-----|-------|
| 1   | Red   |
| 2   | Green |
| 4   | Blue  |
| 3   | Yellow (Red+Green) |
| 5   | Magenta (Red+Blue) |
| 6   | Cyan (Green+Blue) |
| 7   | White (Red+Green+Blue) |

### 8 Directions (index 0-7)

| Index | Direction    | dx (DAT_0040b034) | dy (DAT_0040b054) |
|-------|-------------|--------------------|--------------------|
| 0     | East (+x)   | +1                 | 0                  |
| 1     | SE          | +1                 | +1                 |
| 2     | South (+y)  | 0                  | +1                 |
| 3     | SW          | -1                 | +1                 |
| 4     | West (-x)   | -1                 | 0                  |
| 5     | NW          | -1                 | -1                 |
| 6     | North (-y)  | 0                  | -1                 |
| 7     | NE          | +1                 | -1                 |

### Beam Queue Entry (8 bytes)

Used internally by the beam tracing engine. Stored in double-buffered arrays at DAT_00418ca0 / DAT_00418da0.

| Offset | Field           |
|--------|-----------------|
| +0     | x (byte)        |
| +1     | y (byte)        |
| +2     | direction (byte)|
| +3     | color (byte)    |
| +4     | entanglement_id (uint32) -- 0 = not entangled |

### Global State Variables

| Address         | Name                    | Type   | Description                                                  |
|-----------------|-------------------------|--------|--------------------------------------------------------------|
| DAT_0040b030    | dirty_flag              | int    | Set to 1 when screen needs repaint                           |
| DAT_0040b034    | dx_table[8]             | int[8] | X deltas for each of 8 directions                            |
| DAT_0040b054    | dy_table[8]             | int[8] | Y deltas for each of 8 directions                            |
| DAT_0040b074    | doppler_forward[8]      | byte[8]| Color shift table: forward through doppler                   |
| DAT_0040b088    | doppler_backward[8]     | byte[8]| Color shift table: backward through doppler                  |
| DAT_0040b09c    | save_permutation[32]    | byte[32]| Permutation table for save file scrambling                  |
| DAT_0040b0bc    | dragged_sprite_index    | int    | Sprite index of piece being dragged; -1 = none               |
| DAT_0040b0c0    | beam_color_table[8]     | uint[8]| RGB color values for beam rendering, indexed by color mask   |
| DAT_0040b0e0    | url_xor_encoded[N]      | byte[] | XOR-encoded URL/credit string                                |
| DAT_0040b168    | level_order_table[50]   | byte[50]| Maps sequential level index to internal level data index    |
| DAT_00417050    | mouse_down_x            | int    | Mouse X at button-down (for drag threshold detection)        |
| DAT_00417054    | mouse_down_y            | int    | Mouse Y at button-down                                       |
| DAT_00417058    | drag_sprite_backup[32*32]| byte[]| Backup of framebuffer under dragged sprite                   |
| DAT_00417c58    | framebuffer_ptr         | void*  | Pointer to 640x480x24bpp framebuffer (0xe1000 bytes)         |
| DAT_00417c5c    | screen_height           | int    | 480 (0x1e0)                                                  |
| DAT_00417c60    | screen_width            | int    | 640 (0x280)                                                  |
| DAT_00417c64    | drag_draw_x             | int    | Current pixel X of piece being dragged                       |
| DAT_00417c68    | drag_draw_y             | int    | Current pixel Y of piece being dragged                       |
| DAT_00417c6c    | entanglement_counter    | int    | Auto-incrementing ID for quantum entanglement pairs          |
| DAT_00417c70    | current_level_index     | int    | Index into level_order_table (0-49)                          |
| DAT_00417c74    | drag_state              | int    | 0=idle, 1=mouse-down-on-piece, 2=actively-dragging           |
| DAT_00417c78    | drag_piece_backup[20]   | byte[20]| Copy of the cell data being dragged                         |
| DAT_00417c90    | bitmapinfo_header       | BITMAPINFOHEADER | For SetDIBitsToDevice                            |
| DAT_00417cb8    | clipboard_buffer[256]   | char[] | Paste buffer for level codes                                 |
| DAT_00418050    | hwnd                    | HWND   | Main window handle                                           |
| DAT_0041804c    | hdc                     | HDC    | Device context for painting                                  |
| DAT_00418054    | hInstance               | HINSTANCE | Application instance                                      |
| DAT_00418060    | sprite_data_ptrs[N]     | void*[]| Array of pointers to decompressed sprite bitmaps             |
| DAT_00418238    | digit_sprite_ptrs[10]   | void*[]| Sprite pointers for digits 0-9                               |
| DAT_00418460    | drag_last_y             | int    | Previous Y position of dragged piece (for erasing)           |
| DAT_00418464    | drag_last_x             | int    | Previous X position of dragged piece (for erasing)           |
| DAT_00418468    | selected_grid_row       | int    | Grid row of selected/clicked cell                            |
| DAT_0041846c    | selected_grid_col       | int    | Grid column of selected/clicked cell                         |
| DAT_00418480    | help_text_buffer[?]     | char[] | Current level's help/instruction text                        |
| DAT_00418c80    | beam_queue_read_ptr     | void*  | Pointer to current-read beam queue buffer                    |
| DAT_00418ca0    | beam_queue_A            | byte[] | First beam queue buffer (8 bytes x 32 entries)               |
| DAT_00418da0    | beam_queue_B            | byte[] | Second beam queue buffer                                     |
| DAT_00418ea0    | saved_grids[64]         | void*[]| Pointers to saved level state grids (0x1644 bytes each)      |
| DAT_0041a234    | toolbox_area[N]         | byte[] | Toolbox: pieces removed from grid, stored here               |
| DAT_0041a6e4    | game_initialized        | int    | Set to 1 after initial level load                            |
| DAT_0041a700    | version_string_area     | char[] | Area used for version/info display text                      |
| DAT_0041a800    | game_mode               | int    | 0=title/intro, 2=playing                                     |
| DAT_0041a804    | beam_queue_write_ptr    | void*  | Pointer to current-write beam queue buffer                   |
| DAT_0041a808    | beam_queue_read_count   | int    | Number of entries in read queue (alias for swap tracking)     |
| DAT_0041a820    | url_string[64]          | char[] | XOR-decoded URL string (from DAT_0040b0e0)                   |
| DAT_0041a860    | cheat_skip_flag         | int    | Set to 1 by 'L' key to force level completion                |
| DAT_0041a864    | level_data_index        | uint   | Index into level data tables (internal level ID)             |
| DAT_0041a880    | level_accessible[64]    | int[64]| 1 if level is unlocked/accessible, 0 otherwise               |
| DAT_0041a980    | all_targets_satisfied   | int    | 1 if all pinwheels lit correctly, 0 otherwise                |
| DAT_0041a984    | beam_queue_write_count  | int    | Number of entries written to write queue                      |
| DAT_0041a9a0    | level_completed[64]     | int[64]| 1 if level has been beaten, 0 otherwise                      |
| DAT_0041aa9c    | level_completed_last    | int    | Last entry in level_completed array                          |
| DAT_0040e65c    | level_piece_data_ptrs[N]| char*[]| Pointers to encoded level piece layouts                      |
| DAT_0040e758    | level_help_text_ptrs[N] | char*[]| Pointers to level help/instruction strings                   |
| PTR_DAT_00415734| sprite_compressed_ptrs[]| byte*[]| Pointers to RLE-compressed sprite data                       |
| DAT_00415c34    | sprite_count            | int    | Number of sprites to decompress                              |
| DAT_00415934    | palette[256*3]          | byte[] | Color palette: 3 bytes (B,G,R) per palette index            |
| DAT_004166a0    | bitmapinfo_needs_init   | int    | Flag: if set, initialize BITMAPINFOHEADER before blit        |
| DAT_00416698    | window_client_width     | int    | Window client width (640)                                    |
| DAT_0041669c    | window_client_height    | int    | Window client height (480)                                   |

### Rendering Constants

| Value  | Meaning                              |
|--------|--------------------------------------|
| 0x18   | 24 pixels per grid cell              |
| 0x1a   | 26 pixels per toolbox cell           |
| 0x14   | 20 pixels per level-selector cell    |
| 0x280  | 640 pixels screen width              |
| 0x1e0  | 480 pixels screen height             |
| 0x3c   | Grid left offset: col * 24 + 60      |
| 0x1e   | Grid top offset: row * 24 + 30       |
| 0x1cc  | Toolbox area left offset: 460        |
| 0x14   | Toolbox area top offset: 20          |
| 0x19a  | Level selector area top: 410         |
| 0xa4   | Background gray value (164/255)      |

---

## Function Map (Game Logic: 0x00401000 -- 0x00403eb0)

### Beam Tracing Engine

#### FUN_00401000 -- `mark_dirty_rect`
- **Address:** 0x00401000
- **Category:** rendering
- **Signature:** `void (int x, int y, int width, int height)`
- **Description:** Sets the global dirty flag (`DAT_0040b030 = 1`) and calls `invalidate_rect_region` (FUN_00403860) to schedule a repaint of the specified rectangle.
- **Parameters:** x, y = top-left corner in pixels; width, height = rectangle dimensions.
- **Mac PPC equivalent:** FUN_000034b8 (sets DAT_00008040=1, calls FUN_00002c40 -> InvalWindowRect)

#### FUN_00401030 -- `add_beam_to_queue`
- **Address:** 0x00401030
- **Category:** beam_tracing
- **Signature:** `void (byte x, byte y, byte direction, byte color, uint entanglement_id)`
- **Description:** Appends a beam entry to the write queue. Maximum 32 entries (0x20). Each entry is 8 bytes: {x, y, dir, color, entangle_id}. The write pointer is `DAT_0041a804`, and the count is `DAT_0041a984`.
- **Mac PPC equivalent:** FUN_000034ec

#### FUN_00401090 -- `process_beam_at_cell`
- **Address:** 0x00401090
- **Category:** beam_tracing
- **Signature:** `void (int x, int y, int direction, uint color, uint entanglement_id)`
- **Description:** The core beam-interaction dispatcher. Computes the cell index `(x + y*15) * 20`, reads the piece type, and switches on it:
  - **Case 0 (empty):** Beam passes through; adds to queue in same direction.
  - **Case 3 (reflector):** Computes relative angle `uVar4 = (direction - rotation) & 7`. Reflects at relative angles 1, 2, or 3 (mirror-like deflection). Output direction is `(rotation - relative_angle) & 7`. Beams hitting at other angles are absorbed.
  - **Case 4 (bender):** Reflects beams at relative angles 0-3 (bends horizontal/vertical to diagonal and vice versa). Output direction computed as `(rotation - (relative_angle + 1)) & 7` for each case.
  - **Case 5 (filter):** Only passes beam if relative angle is 2 or 6 (head-on) AND beam color matches filter color mask. Output color = intersection of beam and filter colors.
  - **Case 6 (prism):** Separates white light. Each color component (B=4, G=2, R=1) refracts at a different angle depending on entry angle. Only processes the blue (4), green (2), or red (1) component of the beam separately. Each component exits at a different direction relative to the prism's facing.
  - **Case 7 (doppler):** At relative angle 2 (forward): swaps R<->B (bit 1 becomes bit 2, bit 2 becomes bit 1, bit 4 stays or becomes bit 4). At relative angle 6 (backward): opposite swap (bit 4 becomes bit 1, bit 1 becomes bit 4, bit 2 stays). If entangled (`param_5 != 0`), color shift is suppressed (passes unchanged).
  - **Case 8 (splitter):** At diagonal angles relative to facing (1,3,5,7): passes beam straight through AND splits it at a reflected angle. The straight-through beam preserves entanglement; the reflected copy has entanglement set to 0 (wave function collapse). At head-on/cardinal relative angles (0,2,4,6): passes straight through preserving entanglement.
  - **Case 9 (tangler):** At relative angle 2: for each color bit present in the beam, outputs two entangled beams in opposite directions (rotation and rotation+4), each assigned a new unique entanglement_id (from DAT_00417c6c, auto-incremented).
  - **Case 10 (target/pinwheel):** Beam color is recorded in the cell's beam data (OR'd in). Then the beam is re-added to queue at same position and direction (pass-through for rendering / multi-hit tracking).
  - **Case 0xB (conduit):** Only passes beam at relative angles 0 or 4 (i.e., aligned with conduit's axis). Other angles are blocked.
  - **Case 0xC (teleporter):** Steps along beam direction searching for the next cell with type==0xC. If found, beam arrives there (treated as target arrival / case 10 jump). If no teleporter found (exits grid), beam is absorbed.
- **Key data:** `DAT_004190a0` (grid), `DAT_004190a2` (rotation), `DAT_004190a4` (beam incoming), `DAT_004190ac` (beam outgoing), `DAT_0040b034/0040b054` (direction deltas), `DAT_0040b074/0040b088` (doppler color tables).
- **Mac PPC equivalent:** FUN_00003568

#### FUN_00401620 -- `trace_all_beams`
- **Address:** 0x00401620
- **Category:** beam_tracing
- **Signature:** `void (byte start_x, byte start_y, byte direction, byte color)`
- **Description:** The main beam propagation loop. Uses double-buffered queues (DAT_00418ca0 and DAT_00418da0). Starts by adding the initial beam to the queue, then iterates up to 0x400 (1024) times:
  1. Swaps read/write queue pointers.
  2. For each beam in the read queue: advances position by direction delta, records color in the cell's beam_outgoing array (OR'd in), then calls `process_beam_at_cell` to handle interactions.
  3. After processing all beams, performs the **doppler entanglement pass**: for any beam entry where the cell is type 7 (doppler) and the beam has a non-zero entanglement_id, finds all beams sharing that ID. Applies forward or backward color shift from the doppler tables (DAT_0040b074 / DAT_0040b088), choosing direction based on whether the entry is the "same" beam or its entangled "partner" (determined by comparing beam direction relative to doppler rotation).
  4. Repeats until no new beams are generated or iteration limit is reached.
- **Initializes:** `DAT_00417c6c = 1` (entanglement counter reset), `DAT_0041a984 = 0` (write count reset).
- **Mac PPC equivalent:** FUN_00003a58

#### FUN_00401860 -- `clear_beam_data`
- **Address:** 0x00401860
- **Category:** beam_tracing
- **Signature:** `void (void)`
- **Description:** Zeros out the beam data fields (bytes +4 through +19, covering both beam_incoming[8] and beam_outgoing[8]) for every cell in the 15x15 grid. Iterates through grid addresses from DAT_004190ac up to 0x41a240 (covering grid + some toolbox area).
- **Mac PPC equivalent:** FUN_00003d60

#### FUN_00401890 -- `emit_from_all_lasers`
- **Address:** 0x00401890
- **Category:** beam_tracing
- **Signature:** `void (void)`
- **Description:** Scans the entire 15x15 grid. For each cell where `type == 2` (laser), calls `trace_all_beams(x, y, rotation, color)` to emit the laser's beam.
- **Mac PPC equivalent:** FUN_00003e1c

#### FUN_004018d0 -- `recalculate_beams`
- **Address:** 0x004018d0
- **Category:** beam_tracing
- **Signature:** `void (void)`
- **Description:** Convenience wrapper: calls `clear_beam_data()` then `emit_from_all_lasers()`. Used whenever the board state changes and beams need to be recomputed.
- **Mac PPC equivalent:** FUN_00003ea4

#### FUN_004018e0 -- `check_target_satisfied`
- **Address:** 0x004018e0
- **Category:** win_condition
- **Signature:** `bool (int cell_ptr)`
- **Description:** For a single target/pinwheel cell, ORs together all 8 beam_incoming bytes (offsets +4 through +11) to compute the total color hitting the target. Returns `true` if this combined color equals the target's required color (byte at offset +1). The target must be hit by exactly the right mix of colors -- no more, no less.
- **Mac PPC equivalent:** FUN_00003ecc

### Level Management and Save/Load

#### FUN_00401910 -- `compute_level_accessibility`
- **Address:** 0x00401910
- **Category:** level_data
- **Signature:** `void (void)`
- **Description:** Determines which levels are unlocked. First marks the full screen dirty (640x480). Then finds the highest completed level index by scanning `level_completed[]` (DAT_0041a9a0, at DAT_0041aa9c) backward from index 63. Based on the highest completed level, computes how many "free passes" (unlock credits) to distribute:
  - Starts with 1 credit
  - If highest > 8: +1 credit (total 2)
  - If highest > 18: +1 (total 3)
  - If highest > 25: +1 (total 4)
  - If highest > 34: +2 (total 6)
  Then iterates through all 64 level slots. Already-completed levels are always accessible. For uncompleted levels, each consumes one credit until credits run out. Results stored in `DAT_0041a880[]` (level_accessible).
- **Mac PPC equivalent:** FUN_00004050

#### FUN_004019a0 -- `load_save_file`
- **Address:** 0x004019a0
- **Category:** save_load
- **Signature:** `void (void)`
- **Description:** Opens "chroma.dat" for reading (via fopen at FUN_004040b1; the filename is embedded with XOR obfuscation at `s_q_<S>>chroma_dat_0040b0ee + 6`). Reads a 32-byte scrambled bitfield. For each of the 64 levels, decodes 4 scrambled bit positions (via `save_bit_address` and `save_hash`) to verify completion status. If the hash check passes, marks `level_completed[i] = 1`. After the completion data, reads optional saved level states: reads a 1-byte level index, then reads 0x11d (285) entries of 3 bytes each (= type, color, rotation for each of 285 cells covering the 15x19 extended grid = 0x1644 bytes). Allocates 0x1644 bytes per saved level and stores pointers in `DAT_00418ea0[]`. On read failure, frees the partial buffer. Finally calls `compute_level_accessibility()`.
- **Uses:** FUN_004040b1 (fopen), FUN_00403fa9 (fread), FUN_00401b40, FUN_00401b70, FUN_00401bd0, FUN_00403eb0 (fclose).

#### FUN_00401b40 -- `save_bit_address`
- **Address:** 0x00401b40
- **Category:** save_load
- **Signature:** `int (uint level_index, int bit_index)`
- **Description:** Computes the scrambled bit position in the save file for a given level and bit index. Calls `save_permute` with `(level_index & 0x1F) + bit_index * 0x20`, then adds `(level_index >> 5) * 0x80` to the result. This partitions the 256-bit save space into 2 halves for levels 0-31 and 32-63.
- **Mac PPC equivalent:** Part of FUN_00004138

#### FUN_00401b70 -- `save_permute`
- **Address:** 0x00401b70
- **Category:** save_load
- **Signature:** `uint (int index)`
- **Description:** Looks up a position in the save file permutation table (DAT_0040b09c). The 256-bit save space is divided into 4 blocks of 64 positions, each permuted differently:
  - index 0-31: direct lookup from table
  - index 32-63: lookup at `(index + 13) & 0x1F` with offset 0x60
  - index 64-95: lookup at `(index - 12) & 0x1F` with offset 0x20
  - index 96-127: lookup at `(index + 5) & 0x1F` with offset 0x40

#### FUN_00401bd0 -- `save_hash`
- **Address:** 0x00401bd0
- **Category:** save_load
- **Signature:** `int (int level_index)`
- **Description:** Computes a hash/checksum for a level index used to verify save data integrity. Formula: `((level_index * 0x909 >> 4) + level_index * 0x909) % 15 + 1`. Returns a value 1-15, used as a multi-bit pattern for redundant verification. The bits of this value must all be present in the save data at the computed positions for the level to be marked complete.

#### FUN_00401c00 -- `write_save_file`
- **Address:** 0x00401c00
- **Category:** save_load
- **Signature:** `void (void)`
- **Description:** Opens "chroma.dat" for writing. Encodes the `level_completed[]` array into a 32-byte scrambled bitfield using the same permutation and hash scheme as the reader. Then iterates `DAT_00418ea0[]`: for each non-null pointer, writes a 1-byte level index followed by 0x11d entries of 3 bytes each (cell type/color/rotation). Closes the file.
- **Uses:** FUN_004040b1 (fopen), FUN_004040c4 (fwrite), FUN_00403eb0 (fclose), FUN_00401bd0 (hash), FUN_00401b40 (bit address).

### Win Condition and Level Transition

#### FUN_00401d10 -- `check_win_condition`
- **Address:** 0x00401d10
- **Category:** win_condition
- **Signature:** `void (void)`
- **Description:** The main win-check routine. First calls `recalculate_beams()`. Sets `all_targets_satisfied = 1`. Scans every cell in the grid (15x15, with an extra loop factor of 8 due to decompiler artifacts -- effectively checks each cell once): for each cell of type 10 (target/pinwheel, `'\n'` = 0x0A), calls `check_target_satisfied`. If any target fails, sets `all_targets_satisfied = 0`. Handles the cheat flag: if `DAT_0041a860` (cheat_skip_flag) was set, forces `all_targets_satisfied = 1` and clears the flag. If the game is active (`DAT_0041a800 != 0`), the level was won, and it hasn't been marked complete yet: marks `level_completed[current_level] = 1`, saves the grid state (`save_current_grid`), writes the save file (`write_save_file`), and recomputes level accessibility (`compute_level_accessibility`).
- **Mac PPC equivalent:** FUN_00004494

#### FUN_00401dc0 -- `get_piece_sprite_index`
- **Address:** 0x00401dc0
- **Category:** rendering
- **Signature:** `int (byte* cell_ptr)`
- **Description:** Maps a piece's type, color/subtype, and rotation to a sprite index (into the sprite_data_ptrs array). Returns -1 for invalid/unknown combinations. Key sprite index ranges:
  - 0: empty, 1: wall
  - 2-7: target base sprites by subtype (0=black->0xC, 1=red->6, 2=green->4, 3=yellow->0x12, 4=blue->2, 5=magenta->0x14, 6=cyan->0x10, 7=white->0x16); adds +1 if target is currently satisfied
  - 8-11: red filter (rotation & 3)
  - 0x0E: teleporter
  - 0x18-0x1F: prism (by full rotation 0-7)
  - 0x20-0x27: reflector (by rotation)
  - 0x28-0x2B: splitter (by rotation & 3)
  - 0x2C-0x2F: conduit (by rotation & 3)
  - 0x30-0x37: bender (by rotation)
  - 0x38-0x3F: blue laser (by rotation)
  - 0x40-0x47: doppler (by rotation)
  - 0x48-0x4F: green laser (by rotation)
  - 0x50-0x57: tangler (by rotation)
  - 0x58-0x5F: red laser (by rotation)
  - 0x60-0x63: blue filter (rotation & 3)
  - 0x68-0x6F: white laser (by rotation)
  - 0x70-0x73: green filter (rotation & 3)
- For targets (type 10): also performs inline satisfaction check (ORs beam data, compares with required color) to decide between unlit/lit sprite variant.
- **Mac PPC equivalent:** FUN_000045d4

#### FUN_00401f50 -- `recalculate_and_redraw_all`
- **Address:** 0x00401f50
- **Category:** win_condition
- **Signature:** `void (void)`
- **Description:** Convenience wrapper. Calls `check_win_condition()` then `mark_dirty_rect(0, 0, 640, 480)` to repaint the entire screen.
- **Mac PPC equivalent:** FUN_00004f14

### Input Handling

#### FUN_00401f70 -- `handle_mouse_input`
- **Address:** 0x00401f70
- **Category:** input
- **Signature:** `void (int event_type, int pixel_x, int pixel_y)`
- **Description:** The main mouse event dispatcher. Converts pixel coordinates to grid coordinates using three hit-test regions:
  - **Grid area:** `col = pixel_x / 24 - 2`, `row = (pixel_y + 30) / 24 - 2`. Valid if 0 <= col,row < 15. Region code = row (0-14).
  - **Toolbox area:** `col = (pixel_x - 422) / 26 - 1`, `row = (pixel_y + 18) / 26 - 1`. Valid if 0 <= col < 6, 0 <= row < 4. Region code = 0x0F (15). Linear index = `col + row * 6`.
  - **Level selector area:** `col = (pixel_x + 10) / 20 - 1`, `row = (pixel_y - 390) / 20 - 1`. Valid if 0 <= col < 25, 0 <= row < 2. Region code = -2. Linear index = `col + row * 25`.
  - Otherwise region = -1 (outside all areas).

  **Event types** (derived from Win32 messages via mouse_event_adapter):
  - `0` = mouse move (WM_MOUSEMOVE)
  - `1` = left button down (WM_LBUTTONDOWN)
  - `4` = left button up (WM_LBUTTONUP)
  - `6` = right button up (WM_RBUTTONUP)

  **In title/intro mode** (`DAT_0041a800 == 0`): Left-click (1) or left-release (4) on a grid cell stores selected_grid_row/col.

  **In play mode:**
  - **Mouse move (0):** If drag_state is 0, ignores. If drag_state is 1 (mouse-down pending), checks if mouse has moved more than 1 pixel from click point (using absolute value); if so, initiates actual drag by calling `start_drag()`. If drag_state is 2 (actively dragging), invalidates old drag position (60x60 rect), updates drag position, invalidates new position (25x25 rect).
  - **Left-button-down (1):** On a grid cell, checks if the piece is moveable (`is_moveable_piece`). If so, records click position and sets drag_state=1 (pending).
  - **Left-button-up (4):** If region < 0 and drag_state == 2: calls `drop_piece(-1, -1)` to cancel/return piece. If region == -2 (level selector) and level is accessible: calls `select_level(index)`. On a grid cell: if drag_state == 2, calls `drop_piece(col, row)`. If drag_state != 2 and piece is moveable: rotates piece clockwise (`rotation = (rotation - 1) & 7`) and recalculates.
  - **Right-button-up (6):** If drag_state == 0 and on a moveable piece: rotates counter-clockwise (`rotation = (rotation + 1) & 7`) and recalculates.

- **Mac PPC equivalent:** FUN_000050d4 (with Carbon event parameter extraction via FUN_000032ec)

#### FUN_004038a0 -- `mouse_event_adapter`
- **Address:** 0x004038a0
- **Category:** input
- **Signature:** `void (int event_type, WPARAM wParam, LPARAM lParam)`
- **Description:** Thin wrapper that extracts mouse coordinates from LPARAM (low 16 bits = x, high 16 bits = y as signed shorts) and calls `handle_mouse_input`. Called from the WndProc for mouse messages.

### Piece Manipulation

#### FUN_00402280 -- `is_moveable_piece`
- **Address:** 0x00402280
- **Category:** piece_behavior
- **Signature:** `int (int piece_type)`
- **Description:** Returns 1 if the piece type is 3 through 9 inclusive (reflector, bender, filter, prism, doppler, splitter, tangler). These are the pieces the player can drag and rotate. Returns 0 for all other types (empty, wall, laser, target, conduit, teleporter).
- **Mac PPC equivalent:** FUN_000034d8

#### FUN_004022a0 -- `start_drag`
- **Address:** 0x004022a0
- **Category:** input
- **Signature:** `void (void)`
- **Description:** Initiates dragging of the piece at `(selected_grid_col, selected_grid_row)`. Verifies the piece is moveable. Sets drag_state to 2 (actively dragging). Computes the pixel center of the cell: `x = col * 24 + 60`, `y = row * 24 + 30`. Looks up the sprite index via `get_piece_sprite_index` and stores it in `DAT_0040b0bc` (dragged_sprite_index). Records pixel position for drag overlay rendering. If the piece is not moveable, resets drag_state to 0.

#### FUN_00402350 -- `drop_piece`
- **Address:** 0x00402350
- **Category:** input
- **Signature:** `void (int dest_col, int dest_row)`
- **Description:** Places the dragged piece at the destination grid cell. If dest_col >= 0 AND dest_row >= 0 AND the destination cell is empty (type 0): copies the full 20-byte cell data from the source (selected_grid_col/row) to destination, then clears the source cell's type to 0. If the destination is invalid or occupied, the piece stays where it was (the source cell is not modified). Always calls `recalculate_and_redraw_all()`. Resets drag_state to 0 and dragged_sprite_index to -1 (0xFFFFFFFF).

#### FUN_004023e0 -- `noop_stub`
- **Address:** 0x004023e0
- **Category:** utility
- **Signature:** `void (void)`
- **Description:** Empty function (just returns). Likely a stripped/placeholder function. Called from `load_level` when no saved grid state exists (the "initialize fresh" path, which is actually handled by `parse_level_data` before this is reached; this function was probably intended for additional initialization that was removed).

#### FUN_004023f0 -- `init_level_from_toolbox`
- **Address:** 0x004023f0
- **Category:** level_data
- **Signature:** `void (void)`
- **Description:** Moves all moveable pieces from the main 15x15 grid into the toolbox area (DAT_0041a234). Iterates through the grid; for each moveable piece (types 3-9), finds the next empty slot in the toolbox, copies the 20-byte cell data there, resets the rotation (offset +2 = 0), and clears the source cell. Then sorts the toolbox by piece type using qsort (FUN_004041ce with comparator at LAB_00402490). Finally calls `check_win_condition()` and marks the full screen dirty.
- **Mac PPC equivalent:** FUN_000054f8

### Level Navigation

#### FUN_004024b0 -- `save_current_grid`
- **Address:** 0x004024b0
- **Category:** save_load
- **Signature:** `void (void)`
- **Description:** Saves the current grid state to the saved_grids array at `DAT_00418ea0[level_data_index]`. If no buffer exists yet for this level, allocates 0x1644 bytes via malloc. Copies 0x591 dwords (= 0x1644 bytes) from `DAT_004190a0` (the full grid + toolbox area) to the save buffer.
- **Mac PPC equivalent:** FUN_000055f4

#### FUN_004024f0 -- `load_level`
- **Address:** 0x004024f0
- **Category:** level_data
- **Signature:** `void (int use_saved_state)`
- **Description:** Loads a level. First calls `parse_level_data()` (FUN_004037c0) to initialize the grid from the encoded level data. If `use_saved_state` is non-zero AND a saved grid exists for the current `level_data_index`: restores the saved grid (copies 0x591 dwords back from the save buffer) and calls `check_win_condition()`. If no saved state: calls `noop_stub()` (no-op). Sets game_mode to 2 (playing), game_initialized to 1, and marks full screen dirty.
- **Mac PPC equivalent:** FUN_00005668

#### FUN_00402560 -- `select_level`
- **Address:** 0x00402560
- **Category:** level_data
- **Signature:** `void (int selector_index)`
- **Description:** Switches to a specific level chosen from the level selector bar. First saves the current grid state. Sets `current_level_index` to the selector index, looks up the internal level data index from `level_order_table[selector_index]` (DAT_0040b168), and calls `load_level(1)` to load with saved state.
- **Mac PPC equivalent:** FUN_00005714

#### FUN_00402590 -- `advance_to_next_level`
- **Address:** 0x00402590
- **Category:** level_data
- **Signature:** `uint (void)`
- **Description:** Increments `current_level_index` by 1 and updates `level_data_index` from `level_order_table[new_index]`. Returns the new level_data_index. Does NOT call load_level itself.
- **Mac PPC equivalent:** FUN_0000576c

#### FUN_004025b0 -- `go_to_previous_level`
- **Address:** 0x004025b0
- **Category:** level_data
- **Signature:** `uint (void)`
- **Description:** If `current_level_index > 0`, decrements it by 1 and updates `level_data_index` from the level order table. Returns the new level_data_index. If already at level 0, returns the current level_data_index unchanged.
- **Mac PPC equivalent:** FUN_000057ac

#### FUN_004025e0 -- `next_level_and_load`
- **Address:** 0x004025e0
- **Category:** level_data
- **Signature:** `void (void)`
- **Description:** Saves the current grid (`save_current_grid`). If `current_level_index < 49` (0x31), advances to the next level. Then loads the new level with saved state.
- **Mac PPC equivalent:** FUN_00005800

#### FUN_00402610 -- `prev_level_and_load`
- **Address:** 0x00402610
- **Category:** level_data
- **Signature:** `void (void)`
- **Description:** Saves the current grid, goes to the previous level, then loads with saved state.
- **Mac PPC equivalent:** FUN_00005858

### Clipboard / Level Codes

#### FUN_00402670 -- `encode_base52_char`
- **Address:** 0x00402670
- **Category:** utility
- **Signature:** `int (int value)`
- **Description:** Converts a value (0-51) to a base-52 character. Values 0-25 map to 'a'-'z' (value + 0x61), values 26-51 map to 'A'-'Z' (value + 0x27, effectively value - 26 + 'A').
- **Mac PPC equivalent:** FUN_000058e4

#### FUN_00402690 -- `decode_base52_char`
- **Address:** 0x00402690
- **Category:** utility
- **Signature:** `int (int char_code)`
- **Description:** Inverse of encode_base52_char. 'A'-'Z' (< 0x5B) map to values 26-51 (char - 0x27), 'a'-'z' map to 0-25 (char - 0x61).
- **Mac PPC equivalent:** FUN_000058fc

#### FUN_004026b0 -- `copy_level_code_to_clipboard`
- **Address:** 0x004026b0
- **Category:** ui
- **Signature:** `void (void)`
- **Description:** Generates a text level code and copies it to the Windows clipboard. Format: `"1-NN-XXYYZZ..."` where NN is the level number (1-based, 2-digit zero-padded), followed by pairs of base-52 characters encoding each moveable piece's position and attributes. Steps:
  1. Scans the grid (up to address 0x41a6e4, covering grid + toolbox), collecting all moveable pieces into a local array of 6-byte entries: {grid_position(u16), rotation(byte), type(byte), color(byte)}.
  2. Sorts by comparator at LAB_00402630.
  3. For each piece, computes a linear index: `rotation * 0x11D + grid_position`, then encodes as two base-52 characters via `index / 52` and `index % 52` (`0x34 = 52`).
  4. Null-terminates the string and calls `copy_to_clipboard` (FUN_00403cb0).
  5. Frees the temporary string buffer.
- **Mac PPC equivalent:** FUN_00005914 + FUN_00002ef8 (Mac uses Scrap Manager)

#### FUN_00402810 -- `paste_level_code_from_clipboard`
- **Address:** 0x00402810
- **Category:** ui
- **Signature:** `void (void)`
- **Description:** Reads a level code from the clipboard and applies it. Validates format: must start with `"1-"`, next two chars must be digits, followed by `"-"`, and the number must equal `current_level_index + 1`. Counts moveable pieces currently on the grid. Verifies string length after prefix equals `2 * piece_count`. Validates that each decoded target cell is either empty or already contains a moveable piece (prevents overwriting non-moveable pieces). If all valid:
  1. Collects existing moveable pieces into sorted list (same as copy).
  2. Clears all moveable pieces from the grid.
  3. For each pair of base-52 characters, decodes to get linear index, computes `grid_position = index % 0x11D` and `rotation = index / 0x11D`.
  4. Places the piece from the sorted list at the decoded grid position with the decoded rotation.
  5. Calls `recalculate_and_redraw_all()`.
- **Mac PPC equivalent:** FUN_00005ad4

### Keyboard Handling

#### FUN_00402a80 -- `handle_key_input`
- **Address:** 0x00402a80
- **Category:** input
- **Signature:** `int (int key_code)`
- **Description:** Handles keyboard events from WM_CHAR. Key codes and actions:
  - **0x03 (Ctrl+C):** Calls `copy_level_code_to_clipboard`. Returns 0.
  - **0x16 (Ctrl+V):** Calls `paste_level_code_from_clipboard`. Returns 0.
  - **0x1B (Escape):** Returns 1 (signals DestroyWindow to WndProc).
  - **0x20 (Space), 0x2B (+), 0x3D (=):** If next level is accessible, calls `next_level_and_load`. Returns 0.
  - **0x2D (-):** Calls `prev_level_and_load`. Returns 0.
  - **0x4C ('L'):** Sets `cheat_skip_flag = 1`, calls `check_win_condition()` to force level completion. Returns 0.
  - **0x72 ('r'):** Calls `load_level(0)` to restart level without saved state. Returns 0.
  - All other keys: returns 0 (no action).
- **Mac PPC equivalent:** FUN_00005e64

### Initialization

#### FUN_00402b90 -- `game_init`
- **Address:** 0x00402b90
- **Category:** entry_point
- **Signature:** `void (void)`
- **Description:** Main game initialization. Steps:
  1. Calls `load_save_file()` (reads chroma.dat, populates level_completed and saved_grids).
  2. Calls `decompress_sprites()` (decodes RLE sprite data into sprite_data_ptrs).
  3. Sets `screen_width = 640`, `screen_height = 480`.
  4. Allocates framebuffer: `malloc(0xe1000)` = 640 * 480 * 3 bytes.
  5. Sets `level_data_index` from `level_order_table[0]` (first level).
  6. Calls `load_level(1)` to load the first level with saved state.
- **Mac PPC equivalent:** FUN_00005f38

### Rendering Functions

#### FUN_00402be0 -- `draw_piece_sprite`
- **Address:** 0x00402be0
- **Category:** rendering
- **Signature:** `void (byte* cell_ptr, int center_x, int center_y, int palette_offset)`
- **Description:** Draws a piece's sprite at the given pixel position. Calls `get_piece_sprite_index` to find the sprite index. If valid (>= 0), calls `blit_sprite` with position offset by -12 (to center the 24x24 sprite), source from `sprite_data_ptrs[index]`, size 24x24, stride 24, transparency threshold 0x0E, and the given palette offset.

#### FUN_00402c20 -- `blit_sprite`
- **Address:** 0x00402c20
- **Category:** rendering
- **Signature:** `void (int dst_x, int dst_y, int src_data, int src_w, int src_h, int src_stride, int transparency_threshold, int palette_offset)`
- **Description:** Blits a sprite from source data to the framebuffer. Clips to screen boundaries (handles negative coordinates by adjusting width/height and clamping to 0). For each pixel: if the source byte value >= `transparency_threshold`, looks up the color in the palette: `DAT_00415934[(source_byte + palette_offset) * 3]` for B, `+1` for G, `+2` for R. Writes BGR to the framebuffer at `framebuffer[(y * width + x) * 3]`. Pixels below threshold are transparent (skipped).

#### FUN_00402d10 -- `draw_cell`
- **Address:** 0x00402d10
- **Category:** rendering
- **Signature:** `void (int col, int row, int palette_offset)`
- **Description:** Draws a single grid cell at its correct pixel position. If `row < 15` (main grid): pixel position is `(col*24+60, row*24+30)`. If `row >= 15` (toolbox area): pixel position is `((col/6)*26+20, (col%6)*26+460)`. If the cell is currently being dragged (matches selected_grid_col/row AND drag_state==2), draws using the backup cell data (DAT_00417c78) instead of the live grid data. Delegates to `draw_piece_sprite`.

#### FUN_00402dc0 -- `draw_beam_at_cell`
- **Address:** 0x00402dc0
- **Category:** rendering
- **Signature:** `int (int col, uint row)`
- **Description:** Renders the laser beams passing through a specific grid cell. Returns 1 if any beams drawn, 0 otherwise. For each of 8 directions, combines the beam_incoming (offset +4, direction-4 & 7) and beam_outgoing (offset +0xC) to get the total beam color in that direction. If non-zero, computes pixel start/end points for the beam line segment:
  - East (0): center to right edge
  - SE (1): center to bottom-right corner
  - South (2): center to bottom edge
  - etc.
  Calls `draw_beam_line` with RGB color from `beam_color_table[color_bitmask]`. Also tracks "crossing" beams: if beam_incoming matches beam_outgoing for a direction, records it. If 2+ cardinal directions have matching crossing beams, draws a center dot at the cell center.

#### FUN_00402f30 -- `draw_beam_line`
- **Address:** 0x00402f30
- **Category:** rendering
- **Signature:** `void (uint rgb_color, int x1, int y1, int x2, int y2)`
- **Description:** Dispatches to the appropriate line-drawing primitive based on geometry:
  - x1 == x2: vertical line (`draw_vertical_line`)
  - y1 == y2: horizontal line (`draw_horizontal_line`)
  - (x2-x1) == (y2-y1): positive diagonal (`draw_diagonal_line_positive`)
  - (x2-x1) == -(y2-y1): negative diagonal (`draw_diagonal_line_negative`)

#### FUN_00402fc0 -- `draw_horizontal_line`
- **Address:** 0x00402fc0
- **Category:** rendering
- **Signature:** `void (uint rgb_color, int y, int x_start, int x_end)`
- **Description:** Draws a horizontal line in the framebuffer at row `y` from `x_start` to `x_end`. Ensures x_start <= x_end (swaps if needed). Writes 3 bytes (B, G, R) per pixel.

#### FUN_00403020 -- `draw_vertical_line`
- **Address:** 0x00403020
- **Category:** rendering
- **Signature:** `void (uint rgb_color, int x, int y_start, int y_end)`
- **Description:** Draws a vertical line at column `x`. Steps by `screen_width * 3` bytes per row.

#### FUN_004030a0 -- `draw_diagonal_line_positive`
- **Address:** 0x004030a0
- **Category:** rendering
- **Signature:** `void (uint rgb_color, int x1, int y1, int x2, int y2)`
- **Description:** Draws a diagonal line where dx == dy (SE/NW direction). Steps by `(screen_width + 1) * 3` bytes per pixel.

#### FUN_00403120 -- `draw_diagonal_line_negative`
- **Address:** 0x00403120
- **Category:** rendering
- **Signature:** `void (uint rgb_color, int x1, int y1, int x2, int y2)`
- **Description:** Draws a diagonal line where dx == -dy (NE/SW direction). Steps by `(screen_width - 1) * 3` bytes per pixel.

#### FUN_004031a0 -- `draw_number_string`
- **Address:** 0x004031a0
- **Category:** rendering
- **Signature:** `void (int x, int y, char* str, int palette_offset)`
- **Description:** Draws a numeric string at the given position. For each character: if it's a digit ('0'-'9'), looks up the digit sprite from `DAT_00418238[digit - '0']` and blits it as a 12x12 image (source stride 0x18 = 24, but only 12 pixels wide) with transparency threshold 0x0E and the given palette offset. Advances x by 8 pixels per digit. Non-digit characters (e.g., space) advance x by 4 pixels.
- **Mac PPC equivalent:** FUN_000063fc

#### FUN_00403200 -- `get_level_display_color`
- **Address:** 0x00403200
- **Category:** rendering
- **Signature:** `char (int level_index)`
- **Description:** Returns a palette offset for rendering the level number in the selector bar:
  - If `level_index == current_level_index`: returns 0x00 (current level highlight / default color)
  - If `level_completed[level_index] != 0`: returns 0x48 (72) -- blue tint
  - If `level_accessible[level_index] != 0`: returns 0x30 (48) -- green tint
  - Otherwise: returns 0x10 (16) -- red tint (inaccessible)
- **Mac PPC equivalent:** FUN_000064a0

#### FUN_00403240 -- `draw_level_selector`
- **Address:** 0x00403240
- **Category:** rendering
- **Signature:** `void (void)`
- **Description:** Draws the level selector bar at the bottom of the screen. Iterates through levels 1 to 50. For each, gets its palette color via `get_level_display_color`, formats the level number as a 2-digit string (replacing leading '0' with ' '), and draws it at `((level-1) % 25) * 20 + 10, ((level-1) / 25) * 20 + 410`.
- **Mac PPC equivalent:** FUN_000065d0 (partial)

#### FUN_004032f0 -- `render_frame`
- **Address:** 0x004032f0
- **Category:** rendering
- **Signature:** `void (void)`
- **Description:** The main rendering orchestrator, called during WM_PAINT handling. Steps:
  1. Decodes the URL/credit string (DAT_0041a820) from XOR-encoded data (DAT_0040b0e0) if first byte is zero (not yet decoded). Each byte is XOR'd with the previous encoded byte.
  2. If dirty flag is set, calls `render_board` (FUN_00403690) to redraw the full board into the framebuffer.
  3. Calls `flush_to_screen` (FUN_00403470) to blit the framebuffer via SetDIBitsToDevice.
  4. Draws status text overlays using `draw_text_in_rect`:
     - If `all_targets_satisfied == 1`: "You win!"
     - If level was previously completed: "(won)"
     - If game mode is 2 and targets are satisfied: "Click on a level or press spacebar for next."
     - Otherwise (game mode 2, not won): shows the level's help text from `DAT_00418480`.
     - Version/info text from `DAT_0041a700` area.
     - "freeware" label at bottom-left.
     - On later levels (index > 39, even or last): "more levels @" link.
     - Decoded URL string at bottom-right.
- **Mac PPC equivalent:** FUN_000066e0

#### FUN_00403470 -- `flush_to_screen`
- **Address:** 0x00403470
- **Category:** rendering
- **Signature:** `void (void)`
- **Description:** Blits the framebuffer to the screen device. If a piece is being dragged (dragged_sprite_index >= 0):
  1. Calls `save_drag_background` to save the framebuffer region under the cursor.
  2. Calls `draw_drag_overlay` to draw the piece sprite into the framebuffer.
  3. Calls `blit_framebuffer_to_device` (SetDIBitsToDevice).
  4. Calls `restore_drag_background` to undo the overlay in the framebuffer.
  If not dragging, just calls `blit_framebuffer_to_device` directly.

#### FUN_004034c0 -- `save_drag_background`
- **Address:** 0x004034c0
- **Category:** rendering
- **Signature:** `void (void)`
- **Description:** Saves a clipped 24x24 pixel region of the framebuffer (where the dragged piece will be drawn) to the backup buffer (DAT_00417058, stride 0x20 = 32 pixels). Uses `get_drag_clip_rect` and `copy_rect`.

#### FUN_00403520 -- `get_drag_clip_rect`
- **Address:** 0x00403520
- **Category:** rendering
- **Signature:** `void (int* out_x, int* out_y, int* out_w, int* out_h)`
- **Description:** Computes the clipped rectangle for the dragged piece sprite. Center is at `(drag_last_x, drag_last_y)`, nominal size is 24x24 (centered, so offset by -12). Clips to `(0, 0)` to `(screen_width, screen_height)`.

#### FUN_00403590 -- `copy_rect`
- **Address:** 0x00403590
- **Category:** rendering
- **Signature:** `void (void* dst, int dst_stride, void* src, int src_stride, int width, int height)`
- **Description:** Generic rectangle memory copy. Copies `width * 3` bytes per row for `height` rows, advancing source and destination pointers by their respective strides * 3. Uses dword and byte copies for efficiency.

#### FUN_004035f0 -- `restore_drag_background`
- **Address:** 0x004035f0
- **Category:** rendering
- **Signature:** `void (void)`
- **Description:** Restores the saved background region from the backup buffer (DAT_00417058) back to the framebuffer, undoing the drag overlay after it has been blitted to screen.

#### FUN_00403650 -- `draw_drag_overlay`
- **Address:** 0x00403650
- **Category:** rendering
- **Signature:** `void (void)`
- **Description:** Draws the dragged piece sprite at its current position `(drag_last_x - 12, drag_last_y - 12)` into the framebuffer using `blit_sprite`. Uses the sprite data from `sprite_data_ptrs[dragged_sprite_index]`, size 24x24, transparency threshold 0x0E, palette offset 0.

#### FUN_00403690 -- `render_board`
- **Address:** 0x00403690
- **Category:** rendering
- **Signature:** `void (void)`
- **Description:** Full board redraw into the framebuffer. Steps:
  1. Fills the entire framebuffer with `0xA4` (gray background, 164/255 per channel).
  2. First pass: draws all 15x15 grid cells (calls `draw_cell(col, row, 0)` for each).
  3. Second pass: for each grid cell, calls `draw_beam_at_cell(col, row)`. If beams are present (return value != 0), redraws the cell with palette offset 0x10 (pieces over beams get a slight tint to show through).
  4. Draws the 24 toolbox cells (row index 0xF, columns 0-23, calls `draw_cell(col, 0xF, 0)`).
  5. If game_mode == 2: draws the level selector bar via `draw_level_selector`.
- **Mac PPC equivalent:** FUN_000065d0

### Save/Exit

#### FUN_00403730 -- `save_and_cleanup`
- **Address:** 0x00403730
- **Category:** save_load
- **Signature:** `void (void)`
- **Description:** Called at application exit (after the message loop in WinMain). Calls `save_current_grid()` then `write_save_file()` to persist the player's progress.

### Sprite and Level Data Decompression

#### FUN_00403740 -- `decompress_sprites`
- **Address:** 0x00403740
- **Category:** rendering
- **Signature:** `void (void)`
- **Description:** Decompresses all sprite bitmaps from RLE-compressed data. Iterates backward through the sprite list (count in DAT_00415c34, compressed data pointers in PTR_DAT_00415734). For each sprite: allocates 0x240 (576) bytes = 24x24 pixels, then decodes the RLE format:
  - Byte < 0xC1: literal pixel value, copied directly.
  - Byte >= 0xC1: run-length. Repeat the NEXT byte `(value - 0xC0)` times.
  Stores decompressed bitmap pointers in `sprite_data_ptrs[i]` (DAT_00418060).
- **Mac PPC equivalent:** FUN_000068e8

#### FUN_004037c0 -- `parse_level_data`
- **Address:** 0x004037c0
- **Category:** level_data
- **Signature:** `void (void)`
- **Description:** Loads a level's raw data into the grid. Steps:
  1. Looks up the encoded piece data pointer from `level_piece_data_ptrs[level_data_index]` (DAT_0040e65c) and the help text pointer from `level_help_text_ptrs[level_data_index]` (DAT_0040e758).
  2. Copies the help text string (including null terminator) to `help_text_buffer` (DAT_00418480).
  3. Zeros out the entire grid+toolbox area (0x4FB dwords = 0x13EC bytes, covering 0x004190a0 to ~0x0041a48C).
  4. Parses the encoded level data: each piece is 5 bytes: `{type, rotation, color, col, row}`. Computes the cell offset as `(row * 15 + col) * 20` (where `row * 15 = row * 3 + row * 12`). Writes type to offset +0, rotation to offset +2, color to offset +1. Loop terminates when type byte is 0 (null terminator).
- **Mac PPC equivalent:** FUN_000069fc

### Win32 API Wrappers

#### FUN_00403860 -- `invalidate_rect_region`
- **Address:** 0x00403860
- **Category:** rendering
- **Signature:** `void (int x, int y, int width, int height)`
- **Description:** Constructs a RECT `{left=x, top=y, right=x+width, bottom=y+height}` and calls `InvalidateRect(hwnd, &rect, FALSE)` to schedule a WM_PAINT for that region.

#### LAB_004038d0 -- `WndProc` (embedded as label, not decompiled as separate function)
- **Address:** 0x004038d0
- **Category:** message_loop
- **Description:** The Window Procedure. Not fully decompiled by Ghidra as a standalone function (treated as a label/thunk within the surrounding function scope). Based on Win32 API imports and the Mac PPC equivalent event handlers, it handles:
  - **WM_PAINT (0x000F):** Calls BeginPaint, `render_frame` (FUN_004032f0), EndPaint.
  - **WM_MOUSEMOVE (0x0200):** Calls `mouse_event_adapter(0, wParam, lParam)`.
  - **WM_LBUTTONDOWN (0x0201):** Calls `mouse_event_adapter(1, wParam, lParam)`.
  - **WM_LBUTTONUP (0x0202):** Calls `mouse_event_adapter(4, wParam, lParam)`.
  - **WM_RBUTTONUP (0x0205):** Calls `mouse_event_adapter(6, wParam, lParam)`.
  - **WM_CHAR (0x0102):** Calls `handle_key_input(wParam)`. If returns 1 (Escape), calls PostQuitMessage or DestroyWindow.
  - **WM_DESTROY (0x0002):** Calls PostQuitMessage(0).
  - **Default:** Calls DefWindowProcA.
- Note: A partial decompilation exists in `/Users/pmigdal/my_repos/vibe_coding/chromatron-cc46/decompiled/wndproc_decompiled.c`.

#### FUN_00403b30 -- `WinMain`
- **Address:** 0x00403b30
- **Category:** entry_point
- **Signature:** `int (HINSTANCE hInstance, HINSTANCE hPrevInst, LPSTR lpCmdLine, int nCmdShow)`
- **Description:** Application entry point. Steps:
  1. Stores hInstance in DAT_00418054.
  2. Calls FUN_004044a8 / FUN_0040449e (CRT initialization, timezone/locale setup).
  3. Registers window class "Chromatron" with:
     - WndProc at LAB_004038d0
     - Style CS_OWNDC (0x20)
     - Chromatron icon (loaded by name)
     - Standard arrow cursor (IDC_ARROW = 0x7F00)
     - White brush background (GetStockObject(1))
  4. Computes window size: client area 640x480 + window borders (GetSystemMetrics(SM_CXFIXEDFRAME=7, SM_CYCAPTION=4)) + extra 24 pixels.
  5. Creates window with style 0xCA0000 (WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX) at position (1,1).
  6. Calls `game_init()` (FUN_00402b90).
  7. Shows window (ShowWindow, UpdateWindow), invalidates full client area.
  8. Message loop: GetMessageA / TranslateMessage / DispatchMessageA until GetMessageA returns 0.
  9. On exit: calls `save_and_cleanup()`, returns wParam from last message.
- **Mac PPC equivalent:** FUN_00002bc0 (using Carbon Window Manager, RunApplicationEventLoop)

### Clipboard Operations

#### FUN_00403cb0 -- `copy_to_clipboard`
- **Address:** 0x00403cb0
- **Category:** ui
- **Signature:** `void (char* text)`
- **Description:** Copies a null-terminated string to the Windows clipboard as CF_TEXT (format 1). Allocates global memory (GMEM_MOVEABLE | GMEM_ZEROINIT = 0x42), copies the string including null terminator, then does OpenClipboard / EmptyClipboard / SetClipboardData / CloseClipboard.

#### FUN_00403d30 -- `paste_from_clipboard`
- **Address:** 0x00403d30
- **Category:** ui
- **Signature:** `char* (void)`
- **Description:** Reads CF_TEXT data from the Windows clipboard. Opens clipboard, gets data handle, locks it. If the text length is under 256 bytes, copies it into the static buffer at DAT_00417cb8 and returns a pointer to it. Returns 0 (NULL) if clipboard is empty, data is NULL, or text is too long. Always closes the clipboard before returning.

### Low-Level Rendering

#### FUN_00403db0 -- `blit_framebuffer_to_device`
- **Address:** 0x00403db0
- **Category:** rendering
- **Signature:** `void (int x, int y, void* bits, DWORD width, uint height, int stride)`
- **Description:** Blits the framebuffer to the screen via GDI. If `DAT_004166a0` is set, initializes the BITMAPINFOHEADER first (via FUN_00403e20). Sets the height to negative (top-down bitmap, `_DAT_00417c98 = -height`), stride in header (`_DAT_00417c94 = stride`), then calls `SetDIBitsToDevice(hdc, x, y, width, abs(height), 0, 0, 0, abs(height), bits, &bitmapinfo, DIB_RGB_COLORS)`.
- **Mac PPC equivalent:** FUN_000030cc (using CGDataProvider/CGImage/CGContextDrawImage)

#### FUN_00403e20 -- `init_bitmapinfo_header`
- **Address:** 0x00403e20
- **Category:** rendering
- **Signature:** `void (BITMAPINFOHEADER* header)`
- **Description:** Initializes a 40-byte BITMAPINFOHEADER: zeros all 10 dwords, then sets biSize=0x28 (40), biPlanes=1, biBitCount=24 (0x18), biCompression=0 (BI_RGB).

#### FUN_00403e50 -- `draw_text_in_rect`
- **Address:** 0x00403e50
- **Category:** rendering
- **Signature:** `void (LPCSTR text, LONG left, LONG top, LONG right, LONG bottom)`
- **Description:** Draws text using GDI. Sets background color to gray (0xA4A4A4) via `SetBkColor`, then calls `DrawTextA(hdc, text, -1, &rect, DT_CENTER | DT_WORDBREAK)` (flags = 0x811, with DT_NOPREFIX = 0x800 and DT_CENTER = 0x01 and DT_WORDBREAK = 0x10).
- **Mac PPC equivalent:** FUN_00003228 (using DrawThemeTextBox)

### C Runtime / Library Functions (0x403eb0 and beyond)

These are C runtime library functions from Visual Studio 2003. They are NOT game logic but are called by game functions.

| Address     | Function      | Notes                                     |
|-------------|--------------|-------------------------------------------|
| 0x00403eb0  | fclose       | Closes file, flushes buffer               |
| 0x00403f06  | free         | Frees heap memory via HeapFree            |
| 0x00403f35  | malloc       | Allocates via HeapAlloc                   |
| 0x00403f73  | malloc_inner | Small-block allocator + HeapAlloc fallback|
| 0x00403fa9  | fread        | Buffered file read                        |
| 0x00404091  | fopen_inner  | Internal file open helper                 |
| 0x004040b1  | fopen        | Standard file open                        |
| 0x004040c4  | fwrite       | Buffered file write                       |
| 0x004041ce  | qsort        | Quicksort with insertion sort fallback    |
| 0x00404322  | qsort_isort  | Insertion sort for small partitions       |
| 0x00404370  | qsort_swap   | Element swap for qsort                    |
| 0x0040439c  | atexit_call  | Calls registered atexit handlers          |
| 0x004043c9  | exit_wrapper | Calls FUN_004043eb with params            |
| 0x004043da  | _exit        | CRT exit                                  |
| 0x004043eb  | exit_impl    | Runs atexit, calls ExitProcess            |

---

## Comparison Callbacks (referenced as labels, not decompiled functions)

#### LAB_00402490 -- `compare_toolbox_pieces`
- **Address:** 0x00402490
- **Category:** utility
- **Description:** Comparison function for qsort, sorting toolbox pieces. Used by `init_level_from_toolbox` to sort the toolbox array (20-byte elements) by piece type. Likely compares the first byte (piece type) of each element.

#### LAB_00402630 -- `compare_level_code_entries`
- **Address:** 0x00402630
- **Category:** utility
- **Description:** Comparison function for qsort, sorting level code piece entries (6-byte elements). Used by clipboard copy/paste to ensure consistent piece ordering in level codes.

---

## Function Address Quick Reference

| Address     | Annotated Name                  | Category        |
|-------------|--------------------------------|-----------------|
| 0x00401000  | mark_dirty_rect                | rendering       |
| 0x00401030  | add_beam_to_queue              | beam_tracing    |
| 0x00401090  | process_beam_at_cell           | beam_tracing    |
| 0x00401620  | trace_all_beams                | beam_tracing    |
| 0x00401860  | clear_beam_data                | beam_tracing    |
| 0x00401890  | emit_from_all_lasers           | beam_tracing    |
| 0x004018d0  | recalculate_beams              | beam_tracing    |
| 0x004018e0  | check_target_satisfied         | win_condition   |
| 0x00401910  | compute_level_accessibility    | level_data      |
| 0x004019a0  | load_save_file                 | save_load       |
| 0x00401b40  | save_bit_address               | save_load       |
| 0x00401b70  | save_permute                   | save_load       |
| 0x00401bd0  | save_hash                      | save_load       |
| 0x00401c00  | write_save_file                | save_load       |
| 0x00401d10  | check_win_condition            | win_condition   |
| 0x00401dc0  | get_piece_sprite_index         | rendering       |
| 0x00401f50  | recalculate_and_redraw_all     | win_condition   |
| 0x00401f70  | handle_mouse_input             | input           |
| 0x00402280  | is_moveable_piece              | piece_behavior  |
| 0x004022a0  | start_drag                     | input           |
| 0x00402350  | drop_piece                     | input           |
| 0x004023e0  | noop_stub                      | utility         |
| 0x004023f0  | init_level_from_toolbox        | level_data      |
| 0x004024b0  | save_current_grid              | save_load       |
| 0x004024f0  | load_level                     | level_data      |
| 0x00402560  | select_level                   | level_data      |
| 0x00402590  | advance_to_next_level          | level_data      |
| 0x004025b0  | go_to_previous_level           | level_data      |
| 0x004025e0  | next_level_and_load            | level_data      |
| 0x00402610  | prev_level_and_load            | level_data      |
| 0x00402670  | encode_base52_char             | utility         |
| 0x00402690  | decode_base52_char             | utility         |
| 0x004026b0  | copy_level_code_to_clipboard   | ui              |
| 0x00402810  | paste_level_code_from_clipboard| ui              |
| 0x00402a80  | handle_key_input               | input           |
| 0x00402b90  | game_init                      | entry_point     |
| 0x00402be0  | draw_piece_sprite              | rendering       |
| 0x00402c20  | blit_sprite                    | rendering       |
| 0x00402d10  | draw_cell                      | rendering       |
| 0x00402dc0  | draw_beam_at_cell              | rendering       |
| 0x00402f30  | draw_beam_line                 | rendering       |
| 0x00402fc0  | draw_horizontal_line           | rendering       |
| 0x00403020  | draw_vertical_line             | rendering       |
| 0x004030a0  | draw_diagonal_line_positive    | rendering       |
| 0x00403120  | draw_diagonal_line_negative    | rendering       |
| 0x004031a0  | draw_number_string             | rendering       |
| 0x00403200  | get_level_display_color        | rendering       |
| 0x00403240  | draw_level_selector            | rendering       |
| 0x004032f0  | render_frame                   | rendering       |
| 0x00403470  | flush_to_screen                | rendering       |
| 0x004034c0  | save_drag_background           | rendering       |
| 0x00403520  | get_drag_clip_rect             | rendering       |
| 0x00403590  | copy_rect                      | rendering       |
| 0x004035f0  | restore_drag_background        | rendering       |
| 0x00403650  | draw_drag_overlay              | rendering       |
| 0x00403690  | render_board                   | rendering       |
| 0x00403730  | save_and_cleanup               | save_load       |
| 0x00403740  | decompress_sprites             | rendering       |
| 0x004037c0  | parse_level_data               | level_data      |
| 0x00403860  | invalidate_rect_region         | rendering       |
| 0x004038a0  | mouse_event_adapter            | input           |
| 0x004038d0  | WndProc (label)                | message_loop    |
| 0x00403b30  | WinMain                        | entry_point     |
| 0x00403cb0  | copy_to_clipboard              | ui              |
| 0x00403d30  | paste_from_clipboard           | ui              |
| 0x00403db0  | blit_framebuffer_to_device     | rendering       |
| 0x00403e20  | init_bitmapinfo_header         | rendering       |
| 0x00403e50  | draw_text_in_rect              | rendering       |
| 0x00403eb0  | fclose (CRT)                   | utility         |
| 0x00403f06  | free (CRT)                     | utility         |
| 0x00403f35  | malloc (CRT)                   | utility         |
| 0x00403fa9  | fread (CRT)                    | utility         |
| 0x004040b1  | fopen (CRT)                    | utility         |
| 0x004040c4  | fwrite (CRT)                   | utility         |
| 0x004041ce  | qsort (CRT)                    | utility         |

---

## Mac PPC Cross-Reference Table

| Win32 Address | Win32 Name                     | Mac PPC Address | Mac PPC Name       |
|---------------|-------------------------------|----------------|--------------------|
| 0x00401000    | mark_dirty_rect               | 0x000034b8     | FUN_000034b8       |
| 0x00401030    | add_beam_to_queue             | 0x000034ec     | FUN_000034ec       |
| 0x00401090    | process_beam_at_cell          | 0x00003568     | FUN_00003568       |
| 0x00401620    | trace_all_beams               | 0x00003a58     | FUN_00003a58       |
| 0x00401860    | clear_beam_data               | 0x00003d60     | FUN_00003d60       |
| 0x00401890    | emit_from_all_lasers          | 0x00003e1c     | FUN_00003e1c       |
| 0x004018d0    | recalculate_beams             | 0x00003ea4     | FUN_00003ea4       |
| 0x004018e0    | check_target_satisfied        | 0x00003ecc     | FUN_00003ecc       |
| 0x00401910    | compute_level_accessibility   | 0x00004050     | FUN_00004050       |
| 0x004019a0    | load_save_file                | 0x00004138     | FUN_00004138       |
| 0x00401c00    | write_save_file               | 0x0000433c     | FUN_0000433c       |
| 0x00401d10    | check_win_condition           | 0x00004494     | FUN_00004494       |
| 0x00401dc0    | get_piece_sprite_index        | 0x000045d4     | FUN_000045d4       |
| 0x00401f50    | recalculate_and_redraw_all    | 0x00004f14     | FUN_00004f14       |
| 0x00401f70    | handle_mouse_input            | 0x000050d4     | FUN_000050d4       |
| 0x00402280    | is_moveable_piece             | 0x000034d8     | FUN_000034d8       |
| 0x004023f0    | init_level_from_toolbox       | 0x000054f8     | FUN_000054f8       |
| 0x004024b0    | save_current_grid             | 0x000055f4     | FUN_000055f4       |
| 0x004024f0    | load_level                    | 0x00005668     | FUN_00005668       |
| 0x00402560    | select_level                  | 0x00005714     | FUN_00005714       |
| 0x00402590    | advance_to_next_level         | 0x0000576c     | FUN_0000576c       |
| 0x004025b0    | go_to_previous_level          | 0x000057ac     | FUN_000057ac       |
| 0x004025e0    | next_level_and_load           | 0x00005800     | FUN_00005800       |
| 0x00402610    | prev_level_and_load           | 0x00005858     | FUN_00005858       |
| 0x00402670    | encode_base52_char            | 0x000058e4     | FUN_000058e4       |
| 0x00402690    | decode_base52_char            | 0x000058fc     | FUN_000058fc       |
| 0x004026b0    | copy_level_code_to_clipboard  | 0x00005914     | FUN_00005914       |
| 0x00402810    | paste_level_code_from_clipboard| 0x00005ad4    | FUN_00005ad4       |
| 0x00402a80    | handle_key_input              | 0x00005e64     | FUN_00005e64       |
| 0x00402b90    | game_init                     | 0x00005f38     | FUN_00005f38       |
| 0x00402c20    | blit_sprite                   | 0x000047e0     | FUN_000047e0       |
| 0x00402d10    | draw_cell                     | 0x00006128     | FUN_00006128       |
| 0x00402dc0    | draw_beam_at_cell             | 0x000061ec     | FUN_000061ec       |
| 0x004031a0    | draw_number_string            | 0x000063fc     | FUN_000063fc       |
| 0x00403200    | get_level_display_color       | 0x000064a0     | FUN_000064a0       |
| 0x00403240    | draw_level_selector           | 0x000065d0     | FUN_000065d0       |
| 0x004032f0    | render_frame                  | 0x000066e0     | FUN_000066e0       |
| 0x00403690    | render_board                  | 0x000065d0     | FUN_000065d0       |
| 0x00403730    | save_and_cleanup              | 0x000068c0     | FUN_000068c0       |
| 0x00403740    | decompress_sprites            | 0x000068e8     | FUN_000068e8       |
| 0x004037c0    | parse_level_data              | 0x000069fc     | FUN_000069fc       |
| 0x00403b30    | WinMain                       | 0x00002bc0     | FUN_00002bc0       |
| 0x00403cb0    | copy_to_clipboard             | 0x00002ef8     | FUN_00002ef8       |
| 0x00403d30    | paste_from_clipboard          | 0x00002f78     | FUN_00002f78       |
| 0x00403db0    | blit_framebuffer_to_device    | 0x000030cc     | FUN_000030cc       |
| 0x00403e50    | draw_text_in_rect             | 0x00003228     | FUN_00003228       |

---

## Architecture Summary

The game uses a classic immediate-mode software rendering pipeline:

1. **Game state** is stored in a 15x15 grid of 20-byte cells (`DAT_004190a0`), plus a toolbox area (`DAT_0041a234`) and saved grid buffers (`DAT_00418ea0[]`).

2. **Beam tracing** uses a BFS-like flood fill with double-buffered queues (max 32 beams per iteration, up to 1024 iterations). Each beam carries position, direction, color, and an entanglement ID. Special post-processing handles quantum entanglement: when entangled beams pass through a doppler, the color shift is applied to both beams of the pair (forward for one, backward for the other). Splitters and tanglers break/create entanglement.

3. **Rendering** draws to an offscreen 640x480x24bpp framebuffer, then blits to screen via `SetDIBitsToDevice`. Sprites are RLE-compressed, palette-indexed 8-bit images (24x24 pixels). Beam lines are drawn directly into the framebuffer as colored line segments. Text is rendered using `DrawTextA` (GDI). Drag-and-drop uses a save/restore technique: save the framebuffer region under the cursor, draw the piece, blit to screen, restore the saved region.

4. **Input** maps mouse events to grid/toolbox/level-selector coordinates using three hit-test regions. Drag-and-drop uses a 3-state machine (0=idle, 1=mouse-down-pending, 2=actively-dragging) with a 2-pixel threshold to distinguish clicks from drags. Left-click rotates clockwise, right-click counter-clockwise.

5. **Save/load** uses "chroma.dat" with a scrambled bitfield (32 bytes = 256 bits) using permutation tables and hash verification for level completion status, plus raw grid dumps (0x1644 bytes each) for in-progress level states. The scrambling prevents trivial editing of the save file.

6. **Level codes** encode piece positions as base-52 character pairs (covering 52*52 = 2704 possible values for rotation*285+position). Codes are shared via the system clipboard (Ctrl+C / Ctrl+V).

7. **Level data** is stored as arrays of 5-byte piece records terminated by a null type byte. A level order table maps the user-facing level sequence (1-50) to internal level data indices. Help text for each level is stored as a separate string table.
