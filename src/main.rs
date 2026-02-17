/// Chromatron — Pixel-perfect recompilation in Rust + SDL2
/// Original by Sean Barrett / Silver Spaceship Software
///
/// Source: WinMain @ FUN_00403b30, message loop, WndProc @ 0x4038d0

mod types;
mod levels;
mod beam;
mod game;
mod render;
mod input;
mod font;

use sdl2::event::Event;
use sdl2::keyboard::Keycode;
use sdl2::pixels::PixelFormatEnum;
use sdl2::rect::Rect;

use crate::game::Game;
use crate::render::decompress_sprite;
use crate::types::*;

fn main() {
    // Initialize SDL2
    // Source: WinMain @ 0x403b30 — CreateWindowEx with 640×480 client area
    let sdl_context = sdl2::init().expect("Failed to init SDL2");
    let video = sdl_context.video().expect("Failed to init video");

    let window = video
        .window("Chromatron 1.14", WINDOW_WIDTH, WINDOW_HEIGHT)
        .position_centered()
        .build()
        .expect("Failed to create window");

    let mut canvas = window.into_canvas().build().expect("Failed to create canvas");
    let mut event_pump = sdl_context.event_pump().expect("Failed to get event pump");

    // Initialize SDL2_ttf and load system font
    // Source: Win32 uses default SYSTEM_FONT (MS Sans Serif 8pt/13px bitmap)
    // sserife.fon = Wine's pre-built MS Sans Serif bitmap font (LGPL 2.1)
    // FreeType (used by SDL2_ttf) supports loading .fon files natively.
    let ttf_context = sdl2::ttf::init().expect("Failed to init SDL2_ttf");
    let mut font = ttf_context.load_font("assets/fonts/sserife.fon", 13)
        .unwrap_or_else(|e| {
            eprintln!("sserife.fon failed ({e}), falling back to Geneva.ttf");
            let mut f = ttf_context.load_font("assets/fonts/Geneva.ttf", 13)
                .expect("Failed to load assets/fonts/Geneva.ttf");
            f.set_hinting(sdl2::ttf::Hinting::Mono);
            f
        });
    font.set_kerning(false);

    // Decompress all sprites
    // Source: FUN_00403740 @ 0x403740 (decompress_sprites), called from FUN_00402b90 (game_init)
    let sprites: Vec<Vec<u8>> = levels::SPRITES_RLE
        .iter()
        .map(|rle| decompress_sprite(rle))
        .collect();

    // Initialize game
    // Source: FUN_00402b90 @ 0x402b90 (game_init)
    let mut game = Game::new();

    // Initial render + save framebuffer for comparison
    render::render(&mut canvas, &game, &sprites, &font);
    save_framebuffer(&canvas);
    canvas.present();
    game.dirty = false;

    // Main loop
    // Source: WinMain message loop: GetMessage → TranslateMessage → DispatchMessage
    'running: loop {
        for event in event_pump.poll_iter() {
            match event {
                Event::Quit { .. } => break 'running,

                // Keyboard events
                // Source: WndProc WM_CHAR (0x102) → FUN_00402a80
                Event::KeyDown { keycode: Some(key), keymod, .. } => {
                    // F12: re-render + save raw 640×480 framebuffer
                    if key == Keycode::F12 {
                        render::render(&mut canvas, &game, &sprites, &font);
                        save_framebuffer(&canvas);
                        canvas.present();
                        continue;
                    }
                    let code = match key {
                        Keycode::Escape => 0x1b,
                        Keycode::Space => 0x20,
                        Keycode::Equals => 0x3d,
                        Keycode::KpPlus => 0x2b,
                        Keycode::Minus | Keycode::KpMinus => 0x2d,
                        Keycode::R => 0x72,
                        Keycode::L => 0x4c,
                        Keycode::C if keymod.contains(sdl2::keyboard::Mod::LCTRLMOD)
                            || keymod.contains(sdl2::keyboard::Mod::RCTRLMOD) => 0x03,
                        Keycode::V if keymod.contains(sdl2::keyboard::Mod::LCTRLMOD)
                            || keymod.contains(sdl2::keyboard::Mod::RCTRLMOD) => 0x16,
                        _ => continue,
                    };
                    if input::handle_keypress(&mut game, code) {
                        break 'running;
                    }
                    game.dirty = true;
                }

                // Mouse events
                // Source: WndProc WM_MOUSEMOVE/WM_LBUTTONDOWN/UP/WM_RBUTTONDOWN/UP
                Event::MouseMotion { x, y, .. } => {
                    input::handle_mouse(&mut game, MouseAction::Move, x, y);
                }
                Event::MouseButtonDown { mouse_btn, x, y, .. } => {
                    let action = match mouse_btn {
                        sdl2::mouse::MouseButton::Left => MouseAction::LeftDown,
                        sdl2::mouse::MouseButton::Right => MouseAction::RightDown,
                        sdl2::mouse::MouseButton::Middle => MouseAction::MiddleDown,
                        _ => continue,
                    };
                    input::handle_mouse(&mut game, action, x, y);
                }
                Event::MouseButtonUp { mouse_btn, x, y, .. } => {
                    let action = match mouse_btn {
                        sdl2::mouse::MouseButton::Left => MouseAction::LeftUp,
                        sdl2::mouse::MouseButton::Right => MouseAction::RightUp,
                        sdl2::mouse::MouseButton::Middle => MouseAction::MiddleUp,
                        _ => continue,
                    };
                    input::handle_mouse(&mut game, action, x, y);
                }

                _ => {}
            }
        }

        // Render if dirty
        if game.dirty {
            render::render(&mut canvas, &game, &sprites, &font);
            canvas.present();
            game.dirty = false;
        }

        // Cap at ~60fps
        std::thread::sleep(std::time::Duration::from_millis(16));
    }

    // Save on exit
    // Source: WinMain post-loop: FUN_00403730 (save_on_exit)
    game.save_grid_state();
    // TODO: write save file
}

/// Save the current canvas framebuffer as a 640×480 PNG.
fn save_framebuffer(canvas: &sdl2::render::Canvas<sdl2::video::Window>) {
    let (w, h) = (WINDOW_WIDTH, WINDOW_HEIGHT);
    let pitch = w as usize * 3;
    let mut pixels = vec![0u8; pitch * h as usize];

    canvas.read_pixels(
        Rect::new(0, 0, w, h),
        PixelFormatEnum::RGB24,
    ).map(|data| {
        pixels = data;
    }).ok();

    // Write as BMP (simple, no extra dependency)
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let path = format!("screenshots/framebuffer_{}.bmp", timestamp);

    // BMP header (54 bytes) + pixel data
    let file_size = 54 + pixels.len() as u32;
    let mut bmp = Vec::with_capacity(file_size as usize);

    // BMP file header (14 bytes)
    bmp.extend_from_slice(b"BM");
    bmp.extend_from_slice(&file_size.to_le_bytes());
    bmp.extend_from_slice(&[0u8; 4]); // reserved
    bmp.extend_from_slice(&54u32.to_le_bytes()); // offset to pixel data

    // DIB header (40 bytes, BITMAPINFOHEADER)
    bmp.extend_from_slice(&40u32.to_le_bytes()); // header size
    bmp.extend_from_slice(&(w as i32).to_le_bytes()); // width
    bmp.extend_from_slice(&(-(h as i32)).to_le_bytes()); // height (negative = top-down)
    bmp.extend_from_slice(&1u16.to_le_bytes()); // planes
    bmp.extend_from_slice(&24u16.to_le_bytes()); // bits per pixel
    bmp.extend_from_slice(&[0u8; 24]); // compression through to color_important (all zeros)

    // Pixel data (BMP stores BGR, we have RGB — swap)
    for row in 0..h as usize {
        for col in 0..w as usize {
            let i = row * pitch + col * 3;
            if i + 2 < pixels.len() {
                bmp.push(pixels[i + 2]); // B
                bmp.push(pixels[i + 1]); // G
                bmp.push(pixels[i]);     // R
            }
        }
        // BMP rows must be 4-byte aligned
        let padding = (4 - (w as usize * 3) % 4) % 4;
        for _ in 0..padding {
            bmp.push(0);
        }
    }

    std::fs::create_dir_all("screenshots").ok();
    match std::fs::write(&path, &bmp) {
        Ok(_) => eprintln!("Framebuffer saved: {}", path),
        Err(e) => eprintln!("Failed to save framebuffer: {}", e),
    }
}
