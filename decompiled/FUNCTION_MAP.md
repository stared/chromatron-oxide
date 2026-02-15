# Chromatron Win32 Function Map

All game logic lives in 0x00401000–0x00403EB0. CRT/stdlib starts at 0x00403F35.

## Data Structures

### Grid: DAT_004190a0 — 15×15 cells, each 20 (0x14) bytes
```
Offset  Size  Field
0       1     type (piece type, see enum below)
1       1     color/subtype (e.g. laser color bitmask, filter color, target required color)
2       1     rotation/direction (0–7, for 8 compass directions)
3       1     (padding/flags)
4–11    8     beam_incoming[8] — one byte per direction, color bitmask of beams hitting this cell from each direction
12–19   8     beam_outgoing[8] — beams leaving this cell in each direction
```

### Piece Types
```
0  = EMPTY
1  = WALL (immovable obstacle)
2  = LASER (emitter) — color in byte[1], direction in byte[2]
3  = REFLECTOR (mirror) — rotatable, reflects beam
4  = BENDER — angled reflector, converts H/V to diagonal and vice versa
5  = FILTER — byte[1] = allowed color mask
6  = PRISM — bends R/G/B differently
7  = DOPPLER — color shift R→G→B→R (forward) or reverse
8  = SPLITTER — splits beam + passes through
9  = TANGLER (quantum tangler) — entangled beam pairs
10 = TARGET (pinwheel) — byte[1] = required color; special: 0=black (must NOT be hit)
11 = CONDUIT — passes beam through on axis-aligned directions only
12 = TELEPORTER — beam jumps to next teleporter in same direction
```

### Color Bitmask
```
bit 0 (0x1) = RED
bit 1 (0x2) = GREEN
bit 2 (0x4) = BLUE
```
Combinations: 0x3=Yellow(R+G), 0x5=Magenta(R+B), 0x6=Cyan(G+B), 0x7=White(R+G+B)

### 8 Directions (indexed 0–7)
```
0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW
```
Direction deltas at DAT_0040b034 (dx) and DAT_0040b054 (dy).

## Key Global Variables

| Address | Name | Description |
|---------|------|-------------|
| DAT_004190a0 | grid[15][15] | Main game grid, 15×15 cells × 20 bytes |
| DAT_0041a234 | toolbox_pieces | Toolbox storage area |
| DAT_0041a800 | game_state | 0=not playing, 2=playing |
| DAT_0041a980 | win_flag | 1=level won, 0=not won |
| DAT_00417c70 | current_level | Current level index (0–49) |
| DAT_0041a864 | level_data_index | Index into level data arrays |
| DAT_0041a860 | cheat_flag | Set by 'L' key, forces win |
| DAT_0041a880 | level_accessible[64] | 1=level is accessible |
| DAT_0041a9a0 | level_completed[64] | 1=level has been completed |
| DAT_00417c58 | framebuffer | Software framebuffer (640×480×3 = 0xE1000 bytes, RGB24) |
| DAT_00417c60 | fb_width | Framebuffer width (640 = 0x280) |
| DAT_00417c5c | fb_height | Framebuffer height (480 = 0x1E0) |
| DAT_00418050 | hwnd | Window handle |
| DAT_0041804c | hdc | Device context for painting |
| DAT_00417c74 | drag_state | 0=idle, 1=click-started, 2=dragging |
| DAT_0041846c | selected_x | Grid X of selected/dragged piece |
| DAT_00418468 | selected_y | Grid Y of selected/dragged piece |
| DAT_00417c64 | drag_pixel_x | Current drag position (pixels) |
| DAT_00417c68 | drag_pixel_y | Current drag position (pixels) |
| DAT_00418464 | sprite_draw_x | Last sprite draw position for restore |
| DAT_00418460 | sprite_draw_y | Last sprite draw position for restore |
| DAT_0040b0bc | drag_sprite_idx | Sprite index of dragged piece (-1=none) |
| DAT_00417c6c | entangle_counter | Counter for entanglement IDs |
| DAT_00418c80 | beam_queue_a | Double-buffered beam propagation queue A |
| DAT_0041a804 | beam_queue_b | Double-buffered beam propagation queue B |
| DAT_0041a984 | beam_queue_count | Number of beams in current queue |
| DAT_0041a808 | beam_queue_prev_count | Number of beams in previous queue |
| DAT_00418ea0 | saved_states[64] | Saved grid states per level (malloc'd) |
| DAT_00415934 | palette[256×3] | Color palette (RGB values for sprite indices) |
| DAT_00418060 | sprites[N] | Sprite data pointers (24×24 pixels, RLE-decompressed) |
| DAT_0040b168 | level_order[50] | Level number → level data index mapping |
| DAT_0040e65c | level_grid_data[N] | Pointers to level grid definitions |
| DAT_0040e758 | level_text_data[N] | Pointers to level instruction text strings |
| DAT_0040b074 | doppler_fwd[8] | Doppler forward color shift table |
| DAT_0040b088 | doppler_rev[8] | Doppler reverse color shift table |
| DAT_0040b0c0 | beam_colors[8] | RGB color values for beam rendering by color index |
| DAT_0040b09c | save_permutation[32] | Permutation table for save file scrambling |
| DAT_0041a820 | website_url | XOR-decoded "silverspaceship.com" |
| DAT_00418480 | instruction_text | Current level instruction text buffer |
| DAT_0041a700 | status_text | Status text area |
| DAT_00417058 | sprite_backup[32×24×3] | Backup buffer for dragged sprite background |

## Functions (Game Logic Only)

### Beam Tracing

| Address | Name | Size | Description |
|---------|------|------|-------------|
| 0x401000 | invalidate_rect | 39 | Sets dirty flag, calls InvalidateRect wrapper |
| 0x401030 | beam_queue_add | 89 | Add beam entry (x,y,dir,color,entangle_id) to queue. Max 32 entries. |
| 0x401090 | beam_interact_piece | 1232 | **Core beam-piece interaction.** Giant switch on piece type (0–12). Handles reflection, splitting, filtering, prism refraction, doppler shift, tangler entanglement, teleportation. |
| 0x401620 | trace_all_beams | 570 | **Main beam propagation loop.** Double-buffered BFS: propagates beams step by step across grid, calls beam_interact_piece at each cell. Handles doppler entanglement resolution. Max 0x400 iterations. |
| 0x401860 | clear_beam_data | 44 | Zero all beam fields (bytes 3–11, i.e. incoming+outgoing) in all grid cells |
| 0x401890 | emit_from_lasers | 64 | Scan grid for type==2 (LASER), call trace_all_beams for each |
| 0x4018d0 | recalculate_beams | 10 | clear_beam_data() + emit_from_lasers() |

### Win Condition

| Address | Name | Size | Description |
|---------|------|------|-------------|
| 0x4018e0 | check_target_satisfied | 39 | For a target cell: OR all 8 beam bytes, compare to required color |
| 0x401d10 | check_win_condition | 162 | Recalculate beams, check ALL targets, update win_flag. If won and not already completed, mark completed + save + unlock levels. |
| 0x401910 | compute_level_access | 129 | Progressive unlock: unlock N levels based on highest completed. Thresholds: >8→+1, >18→+1, >25→+1, >34→+2 |

### Save/Load

| Address | Name | Size | Description |
|---------|------|------|-------------|
| 0x4019a0 | load_save_file | 412 | Read "chroma.dat", decode completion bits with scramble, restore saved grid states |
| 0x401c00 | write_save_file | 262 | Encode completion bits, write to "chroma.dat" with grid states |
| 0x401b40 | save_bit_index | 38 | Maps (level, sub-index) → scrambled bit position |
| 0x401b70 | save_permute | 90 | Permutation function using DAT_0040b09c table |
| 0x401bd0 | save_checksum | 33 | Per-level checksum: (level * 0x909 >> 4 + level * 0x909) % 15 + 1 |
| 0x403730 | save_on_exit | 10 | save_current_state() + write_save_file() |

### Level Management

| Address | Name | Size | Description |
|---------|------|------|-------------|
| 0x4024b0 | save_grid_state | 64 | Save current grid to saved_states[current_level] (malloc 0x1644 if needed) |
| 0x4024f0 | load_level | 100 | Load level from saved state or fresh from level data. Set game_state=2. |
| 0x402560 | select_level | 37 | Save current, set level index, load new level |
| 0x402590 | next_level | 27 | Increment level counter, update data index |
| 0x4025b0 | prev_level | 37 | Decrement level counter, update data index |
| 0x4025e0 | advance_to_next | 42 | Save + next_level + load |
| 0x402610 | go_to_previous | 32 | Save + prev_level + load |
| 0x4037c0 | load_level_data | 156 | Parse level grid data: copy instruction text, zero grid, parse 5-byte piece records (type, rotation, color, x, y) |

### Input Handling

| Address | Name | Size | Description |
|---------|------|------|-------------|
| 0x401f70 | handle_mouse | 784 | **Main mouse handler.** Converts pixel coords to grid coords (3 regions: main grid, toolbox, level numbers). Handles click, drag start, drag move, drop, rotate. |
| 0x402280 | is_moveable | 23 | Returns 1 if piece type is 3–9 (reflector through tangler) |
| 0x4022a0 | start_drag | 164 | Begin dragging piece: record source cell, get sprite index, set drag_state=2 |
| 0x402350 | drop_piece | 142 | Place dragged piece at target cell (if empty). Copy 20-byte cell data. |
| 0x4023f0 | init_toolbox | 155 | Move all moveable pieces from grid to toolbox area, sort, recalculate |
| 0x402a80 | handle_keypress | 113 | Keyboard dispatch: Ctrl+C→copy, Ctrl+V→paste, Space/+/=→next level, -→prev level, L→cheat win, R→reset level, ESC→quit |
| 0x4038a0 | mouse_dispatch | 45 | Extract mouse x,y from LPARAM, forward to handle_mouse |
| 0x4038d0 | WndProc | 554 | **Window procedure.** WM_PAINT→render, WM_KEYDOWN→keys, WM_LBUTTON*→mouse, WM_CREATE→store hwnd, WM_DESTROY→quit |

### Clipboard (Solution Sharing)

| Address | Name | Size | Description |
|---------|------|------|-------------|
| 0x402670 | encode_char | 17 | Map index to printable char (a-z for 0-25, A-Z for 26-51) |
| 0x402690 | decode_char | 17 | Reverse: uppercase→subtract 0x27, lowercase→subtract 0x61 |
| 0x4026b0 | copy_solution | 343 | Ctrl+C: encode all moveable piece positions to string "1-NN-xxxx", copy to clipboard |
| 0x402810 | paste_solution | 613 | Ctrl+V: decode clipboard string, validate, place pieces on grid |
| 0x403cb0 | set_clipboard | 114 | Win32 clipboard write (GlobalAlloc, OpenClipboard, SetClipboardData) |
| 0x403d30 | get_clipboard | 125 | Win32 clipboard read (GetClipboardData, GlobalLock) |

### Rendering

| Address | Name | Size | Description |
|---------|------|------|-------------|
| 0x402b90 | game_init | 68 | Load save, decompress sprites, alloc framebuffer (640×480×3), load first level |
| 0x402be0 | draw_piece_at | 63 | Get sprite index for piece, call blit_sprite |
| 0x402c20 | blit_sprite | 240 | **Sprite blitter.** Draws 24×24 sprite to framebuffer with palette lookup and transparency threshold. |
| 0x402d10 | draw_piece_on_grid | 175 | Convert grid coords to pixels, draw piece (handles main grid vs toolbox positions) |
| 0x402dc0 | draw_beams_at_cell | 334 | Draw beam lines for a cell. 8 directions, uses draw_line for each active beam. Draws center dot if beams cross. |
| 0x402f30 | draw_line | 137 | Line dispatcher: vertical, horizontal, diagonal-down, diagonal-up |
| 0x402fc0 | draw_hline | 93 | Horizontal line: write RGB pixels |
| 0x403020 | draw_vline | 113 | Vertical line: write RGB pixels with stride |
| 0x4030a0 | draw_diag_down | 122 | Diagonal (top-left to bottom-right) line |
| 0x403120 | draw_diag_up | 120 | Diagonal (bottom-left to top-right) line |
| 0x4031a0 | draw_number | 88 | Draw a number string using digit sprites |
| 0x403200 | get_level_color | 52 | Return palette offset for level number: 0=current, 'H'=completed(blue), 0x30=accessible(green), 0x10=inaccessible(red) |
| 0x403240 | draw_level_numbers | 167 | Draw all 50 level numbers at bottom of screen (25 per row, 20px spacing) |
| 0x4032f0 | render_all | 378 | **WM_PAINT handler body.** Decode website URL, render grid+beams, draw "You win!" or status text, instruction text, level numbers, "freeware", website |
| 0x403470 | paint_to_screen | 67 | Save dragged sprite bg → SetDIBitsToDevice → restore dragged sprite |
| 0x4034c0 | save_sprite_bg | 83 | Copy framebuffer region under sprite to backup buffer |
| 0x403520 | get_sprite_rect | 107 | Calculate clipped 24×24 rect for current sprite position |
| 0x403590 | memcpy_rect | 95 | Copy rectangular region between buffers |
| 0x4035f0 | restore_sprite_bg | 83 | Restore framebuffer region from backup buffer |
| 0x403650 | draw_dragged_sprite | 51 | Draw the currently dragged piece sprite at drag position |
| 0x403690 | render_grid | 151 | **Full grid render.** Fill framebuffer with 0xA4 (gray), draw all pieces, draw all beams, draw toolbox pieces, draw level numbers |
| 0x403740 | decompress_sprites | 115 | RLE-decompress sprite data from embedded arrays. Each sprite is 24×24=576 (0x240) bytes. 0xC1+ = run-length encoding. |
| 0x403db0 | blit_to_screen | 98 | SetDIBitsToDevice: copy framebuffer to screen via DIB |
| 0x403e20 | init_bitmapinfo | 39 | Initialize BITMAPINFOHEADER (40 bytes, 24bpp, BI_RGB) |
| 0x403e50 | draw_text | 87 | DrawTextA with SetBkColor(0xA4A4A4) — text on gray background |

### Entry Point

| Address | Name | Size | Description |
|---------|------|------|-------------|
| 0x403b30 | WinMain | 382 | RegisterClassEx, CreateWindowEx(640+borders × 480+borders), message loop. Window title "Chromatron 1.14". |

### Utility

| Address | Name | Size | Description |
|---------|------|------|-------------|
| 0x401dc0 | get_sprite_index | 287 | Map piece (type, color, rotation) → sprite sheet index. Large switch. |
| 0x401f50 | recalc_and_redraw | 28 | check_win_condition() + invalidate_all() |
| 0x403860 | invalidate_rect_win32 | 63 | Call Win32 InvalidateRect with RECT |
| 0x4023e0 | noop | 1 | Empty function (unused key handler) |

## Layout Constants (from screenshots + code)

```
Window:           640×480 client area
Grid origin:      (60, 30) = (0x3C, 0x1E)
Cell size:        24px (0x18)
Grid:             15×15 cells → 360×360 pixels
Toolbox origin:   (460, 20) = (0x1CC, 0x14)
Toolbox cell:     26px (0x1A)
Toolbox grid:     6 columns × 4 rows
Level nums:       2 rows of 25, 20px (0x14) spacing
Level row 1:      y=410 (0x19A), x starts at 10 (0x0A)
Level row 2:      y=430 (0x1AE)
Background:       RGB(164, 164, 164) = 0xA4A4A4
Sprite size:      24×24 pixels
Framebuffer:      640×480×3 bytes (RGB24, bottom-up for SetDIBitsToDevice)
```

## Rendering Pipeline

1. `render_grid()` fills framebuffer with gray (0xA4)
2. Draw all pieces (main grid 15×15 + toolbox)
3. Draw all beam lines (iterate grid, for each cell with beams, draw colored lines)
4. `render_all()` adds text overlays (DrawTextA directly to DC, not framebuffer)
5. `paint_to_screen()` → SetDIBitsToDevice copies framebuffer to window
6. Dragged sprite uses save/restore pattern (save bg, draw sprite, blit, restore bg)

## Beam Propagation Algorithm

1. Clear all beam data in grid
2. For each laser (type==2): add initial beam to queue (position, direction, color, entangle_id=0)
3. **BFS loop** (max 1024 iterations):
   a. Swap beam queues (double-buffer)
   b. For each beam in current queue:
      - Advance beam one step in its direction (using dx/dy delta tables)
      - Mark cell's beam data (incoming + outgoing)
      - Call `beam_interact_piece()` — the piece switch handles reflection, splitting, etc.
      - Entangled beams get special doppler resolution
   c. Repeat until queue empty or max iterations
4. Entanglement: tangler creates beam pairs with matching IDs; doppler shifts are mirrored for entangled partners
