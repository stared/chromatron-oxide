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

    // Decompress all sprites
    // Source: FUN_00403740 @ 0x403740 (decompress_sprites), called from FUN_00402b90 (game_init)
    let sprites: Vec<Vec<u8>> = levels::SPRITES_RLE
        .iter()
        .map(|rle| decompress_sprite(rle))
        .collect();

    // Initialize game
    // Source: FUN_00402b90 @ 0x402b90 (game_init)
    let mut game = Game::new();

    // Main loop
    // Source: WinMain message loop: GetMessage → TranslateMessage → DispatchMessage
    'running: loop {
        for event in event_pump.poll_iter() {
            match event {
                Event::Quit { .. } => break 'running,

                // Keyboard events
                // Source: WndProc WM_CHAR (0x102) → FUN_00402a80
                Event::KeyDown { keycode: Some(key), keymod, .. } => {
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
            render::render(&mut canvas, &game, &sprites);
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
