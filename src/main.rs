/// Chromatron — Pixel-perfect recompilation in Rust + winit/softbuffer
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
mod ms_sans_serif;
mod bitmap_font;
mod framebuffer;

use std::num::NonZeroU32;
use std::sync::Arc;

use softbuffer::Surface;
use winit::application::ApplicationHandler;
use winit::dpi::LogicalSize;
use winit::event::{ElementState, MouseButton, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::keyboard::{KeyCode, ModifiersState, PhysicalKey};
use winit::window::{Window, WindowId};

#[cfg(target_os = "macos")]
use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};

use crate::bitmap_font::BitmapFont;
use crate::framebuffer::{FrameBuffer, FB_WIDTH, FB_HEIGHT};
use crate::game::Game;
use crate::render::decompress_sprite;
use crate::types::*;

/// Force the window's CALayer tree to use contentsScale=1.0, matching SDL2 behavior.
/// This prevents the visible resize animation when moving between 1× and 2× displays,
/// because the backing store stays at 640×480 pixels regardless of display DPI.
///
/// Source: SDL2 keeps contentsScale=1.0 on its CALayer. Softbuffer's KVO observer
/// (cg.rs:75-81) propagates the root layer's scale to its sublayer, which we undo here.
#[cfg(target_os = "macos")]
fn force_1x_backing(window: &Window) {
    use objc2::msg_send;
    use objc2::rc::Retained;
    use objc2_foundation::NSObject;
    use objc2_quartz_core::{CALayer, CATransaction};

    let Ok(handle) = window.window_handle() else { return };
    let RawWindowHandle::AppKit(appkit) = handle.as_raw() else { return };

    // SAFETY: The pointer came from winit's WindowHandle, guaranteed to be a valid NSView.
    let view: &NSObject = unsafe { appkit.ns_view.cast().as_ref() };
    let root_layer: Option<Retained<CALayer>> = unsafe { msg_send![view, layer] };
    let Some(root_layer) = root_layer else { return };

    // Wrap in a transaction with animations disabled to prevent any visual transition.
    CATransaction::begin();
    CATransaction::setDisableActions(true);

    root_layer.setContentsScale(1.0);
    if let Some(sublayers) = unsafe { root_layer.sublayers() } {
        for sublayer in &sublayers {
            sublayer.setContentsScale(1.0);
        }
    }

    CATransaction::commit();
}

struct App {
    window: Option<Arc<Window>>,
    surface: Option<Surface<Arc<Window>, Arc<Window>>>,
    game: Game,
    sprites: Vec<Vec<u8>>,
    font: BitmapFont,
    fb: FrameBuffer,
    modifiers: ModifiersState,
    cursor_x: i32,
    cursor_y: i32,
    scale_factor: f64,
}

impl App {
    fn new() -> Self {
        // Initialize bitmap font renderer
        // Source: Win32 uses default SYSTEM_FONT (MS Sans Serif 8pt at 96 DPI)
        let font = BitmapFont::new();
        eprintln!("Font loaded: height={}, line_spacing={}", font.height(), font.line_spacing());

        // Decompress all sprites
        // Source: FUN_00403740 @ 0x403740 (decompress_sprites), called from FUN_00402b90 (game_init)
        let sprites: Vec<Vec<u8>> = levels::SPRITES_RLE
            .iter()
            .map(|rle| decompress_sprite(rle))
            .collect();

        // Initialize game
        // Source: FUN_00402b90 @ 0x402b90 (game_init)
        let game = Game::new();

        Self {
            window: None,
            surface: None,
            game,
            sprites,
            font,
            fb: FrameBuffer::new(),
            modifiers: ModifiersState::empty(),
            cursor_x: 0,
            cursor_y: 0,
            scale_factor: 1.0,
        }
    }

    fn present(&mut self) {
        let Some(surface) = self.surface.as_mut() else { return };
        let Some(window) = self.window.as_ref() else { return };

        #[cfg(target_os = "macos")]
        {
            // On macOS, always present at 640×480 and force contentsScale=1.0.
            // The CALayer displays the buffer at logical size regardless of display DPI,
            // matching SDL2's behavior and avoiding Retina resize animations.
            surface.resize(
                NonZeroU32::new(FB_WIDTH as u32).unwrap(),
                NonZeroU32::new(FB_HEIGHT as u32).unwrap(),
            ).expect("Failed to resize surface");

            let mut buffer = surface.buffer_mut().expect("Failed to get buffer");
            buffer[..self.fb.pixels.len()].copy_from_slice(&self.fb.pixels);
            buffer.present().expect("Failed to present buffer");

            // WORKAROUND: softbuffer's KVO observer resets contentsScale on every present(),
            // so we must re-force 1.0 after each call. Without this, moving the window to a
            // Retina display causes a visible resize animation as the backing jumps to 2×.
            force_1x_backing(window);
        }

        #[cfg(not(target_os = "macos"))]
        {
            let size = window.inner_size();
            let dst_w = size.width as usize;
            let dst_h = size.height as usize;

            if dst_w == 0 || dst_h == 0 { return; }

            surface.resize(
                NonZeroU32::new(dst_w as u32).unwrap(),
                NonZeroU32::new(dst_h as u32).unwrap(),
            ).expect("Failed to resize surface");

            let mut buffer = surface.buffer_mut().expect("Failed to get buffer");

            if dst_w == FB_WIDTH && dst_h == FB_HEIGHT {
                // 1:1 — direct copy
                buffer[..self.fb.pixels.len()].copy_from_slice(&self.fb.pixels);
            } else {
                // Nearest-neighbor scale from 640×480 to physical size
                for dst_y in 0..dst_h {
                    let src_y = dst_y * FB_HEIGHT / dst_h;
                    let dst_row = dst_y * dst_w;
                    let src_row = src_y * FB_WIDTH;
                    for dst_x in 0..dst_w {
                        let src_x = dst_x * FB_WIDTH / dst_w;
                        buffer[dst_row + dst_x] = self.fb.pixels[src_row + src_x];
                    }
                }
            }

            buffer.present().expect("Failed to present buffer");
        }
    }
}

impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.window.is_some() { return; }

        // Source: WinMain @ 0x403b30 — CreateWindowEx with 640×480 client area
        let attrs = Window::default_attributes()
            .with_title("Chromatron 1.14")
            .with_inner_size(LogicalSize::new(WINDOW_WIDTH, WINDOW_HEIGHT))
            .with_resizable(false);

        let window = Arc::new(event_loop.create_window(attrs).expect("Failed to create window"));
        self.scale_factor = window.scale_factor();

        let context = softbuffer::Context::new(window.clone()).expect("Failed to create softbuffer context");
        let surface = Surface::new(&context, window.clone()).expect("Failed to create surface");

        self.window = Some(window.clone());
        self.surface = Some(surface);

        // Initial render
        render::render(&mut self.fb, &self.game, &self.sprites, &self.font);
        #[cfg(not(target_arch = "wasm32"))]
        save_framebuffer(&self.fb);
        self.present();
        self.game.dirty = false;
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        match event {
            WindowEvent::CloseRequested => {
                // Save on exit
                // Source: WinMain post-loop: FUN_00403730 (save_on_exit)
                self.game.save_grid_state();
                event_loop.exit();
            }

            WindowEvent::ModifiersChanged(mods) => {
                self.modifiers = mods.state();
            }

            // Keyboard events
            // Source: WndProc WM_CHAR (0x102) → FUN_00402a80
            WindowEvent::KeyboardInput { event, .. } => {
                if event.state != ElementState::Pressed { return; }
                let PhysicalKey::Code(key) = event.physical_key else { return };

                // F12: re-render + save raw 640×480 framebuffer
                if key == KeyCode::F12 {
                    render::render(&mut self.fb, &self.game, &self.sprites, &self.font);
                    #[cfg(not(target_arch = "wasm32"))]
                    save_framebuffer(&self.fb);
                    self.present();
                    return;
                }

                let ctrl = self.modifiers.control_key();
                let code = match key {
                    KeyCode::Escape => 0x1b,
                    KeyCode::Space => 0x20,
                    KeyCode::Equal => 0x3d,
                    KeyCode::NumpadAdd => 0x2b,
                    KeyCode::Minus | KeyCode::NumpadSubtract => 0x2d,
                    KeyCode::KeyR => 0x72,
                    KeyCode::KeyL => 0x4c,
                    KeyCode::KeyC if ctrl => 0x03,
                    KeyCode::KeyV if ctrl => 0x16,
                    _ => return,
                };
                if input::handle_keypress(&mut self.game, code) {
                    self.game.save_grid_state();
                    event_loop.exit();
                    return;
                }
                self.game.dirty = true;
            }

            // Mouse events
            // Source: WndProc WM_MOUSEMOVE/WM_LBUTTONDOWN/UP/WM_RBUTTONDOWN/UP
            WindowEvent::ScaleFactorChanged { scale_factor, .. } => {
                self.scale_factor = scale_factor;
                // On macOS, immediately undo the scale change to keep 1× backing.
                #[cfg(target_os = "macos")]
                if let Some(window) = self.window.as_ref() {
                    force_1x_backing(window);
                }
            }

            #[cfg(not(target_os = "macos"))]
            WindowEvent::Resized(_) => {
                // Re-present at new physical size (e.g. after DPI change on Linux/Windows)
                self.present();
            }

            WindowEvent::CursorMoved { position, .. } => {
                // CursorMoved gives physical coords; divide by scale_factor
                // to get game coordinates (640×480)
                self.cursor_x = (position.x / self.scale_factor) as i32;
                self.cursor_y = (position.y / self.scale_factor) as i32;
                input::handle_mouse(&mut self.game, MouseAction::Move, self.cursor_x, self.cursor_y);
            }
            WindowEvent::MouseInput { state, button, .. } => {
                let action = match (state, button) {
                    (ElementState::Pressed, MouseButton::Left) => MouseAction::LeftDown,
                    (ElementState::Pressed, MouseButton::Right) => MouseAction::RightDown,
                    (ElementState::Pressed, MouseButton::Middle) => MouseAction::MiddleDown,
                    (ElementState::Released, MouseButton::Left) => MouseAction::LeftUp,
                    (ElementState::Released, MouseButton::Right) => MouseAction::RightUp,
                    (ElementState::Released, MouseButton::Middle) => MouseAction::MiddleUp,
                    _ => return,
                };
                input::handle_mouse(&mut self.game, action, self.cursor_x, self.cursor_y);
            }

            WindowEvent::RedrawRequested => {
                if self.game.dirty {
                    render::render(&mut self.fb, &self.game, &self.sprites, &self.font);
                    self.present();
                    self.game.dirty = false;
                }
            }

            _ => {}
        }
    }

    fn about_to_wait(&mut self, _event_loop: &ActiveEventLoop) {
        if self.game.dirty {
            if let Some(window) = self.window.as_ref() {
                window.request_redraw();
            }
        }
    }
}

fn main() {
    let event_loop = EventLoop::new().expect("Failed to create event loop");
    event_loop.set_control_flow(ControlFlow::Wait);

    let mut app = App::new();

    #[cfg(not(target_arch = "wasm32"))]
    event_loop.run_app(&mut app).expect("Event loop error");

    #[cfg(target_arch = "wasm32")]
    {
        console_error_panic_hook::set_once();
        let _ = console_log::init();
        event_loop.spawn_app(app);
    }
}

/// Save the current framebuffer as a 640×480 BMP.
#[cfg(not(target_arch = "wasm32"))]
fn save_framebuffer(fb: &FrameBuffer) {
    let w = WINDOW_WIDTH as usize;
    let h = WINDOW_HEIGHT as usize;

    // Write as BMP (simple, no extra dependency)
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let path = format!("screenshots/framebuffer_{}.bmp", timestamp);

    let row_bytes = w * 3;
    let row_padded = (row_bytes + 3) & !3;
    let pixel_data_size = row_padded * h;
    let file_size = 54 + pixel_data_size;
    let mut bmp = Vec::with_capacity(file_size);

    // BMP file header (14 bytes)
    bmp.extend_from_slice(b"BM");
    bmp.extend_from_slice(&(file_size as u32).to_le_bytes());
    bmp.extend_from_slice(&[0u8; 4]); // reserved
    bmp.extend_from_slice(&54u32.to_le_bytes()); // offset to pixel data

    // DIB header (40 bytes, BITMAPINFOHEADER)
    bmp.extend_from_slice(&40u32.to_le_bytes()); // header size
    bmp.extend_from_slice(&(w as i32).to_le_bytes()); // width
    bmp.extend_from_slice(&(-(h as i32)).to_le_bytes()); // height (negative = top-down)
    bmp.extend_from_slice(&1u16.to_le_bytes()); // planes
    bmp.extend_from_slice(&24u16.to_le_bytes()); // bits per pixel
    bmp.extend_from_slice(&[0u8; 24]); // compression through to color_important (all zeros)

    // Pixel data: convert 0x00RRGGBB to BGR
    for row in 0..h {
        for col in 0..w {
            let pixel = fb.pixels[row * w + col];
            let r = ((pixel >> 16) & 0xFF) as u8;
            let g = ((pixel >> 8) & 0xFF) as u8;
            let b = (pixel & 0xFF) as u8;
            bmp.push(b); // B
            bmp.push(g); // G
            bmp.push(r); // R
        }
        // BMP rows must be 4-byte aligned
        let padding = row_padded - row_bytes;
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
