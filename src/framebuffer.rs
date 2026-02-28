/// Software framebuffer for pixel-perfect rendering without SDL2.
/// Replaces SDL2 Canvas with a simple Vec<u32> pixel buffer.
/// Pixel format: 0x00RRGGBB (matches softbuffer's expected format).

use crate::types::{WINDOW_WIDTH, WINDOW_HEIGHT};

pub const FB_WIDTH: usize = WINDOW_WIDTH as usize;
pub const FB_HEIGHT: usize = WINDOW_HEIGHT as usize;

pub struct FrameBuffer {
    pub pixels: Vec<u32>,
}

impl FrameBuffer {
    pub fn new() -> Self {
        Self {
            pixels: vec![0; FB_WIDTH * FB_HEIGHT],
        }
    }

    /// Pack RGB into 0x00RRGGBB u32.
    #[inline]
    pub fn rgb(r: u8, g: u8, b: u8) -> u32 {
        (r as u32) << 16 | (g as u32) << 8 | b as u32
    }

    /// Fill entire buffer with a single color.
    pub fn clear(&mut self, color: u32) {
        self.pixels.fill(color);
    }

    /// Set a single pixel (bounds-checked, out-of-bounds ignored).
    #[inline]
    pub fn set_pixel(&mut self, x: i32, y: i32, color: u32) {
        if x >= 0 && y >= 0 && (x as usize) < FB_WIDTH && (y as usize) < FB_HEIGHT {
            self.pixels[y as usize * FB_WIDTH + x as usize] = color;
        }
    }

    /// Draw a line using simple stepping (not Bresenham).
    /// All beams in Chromatron are axis-aligned or 45° diagonal,
    /// so signum stepping produces identical results.
    /// Source: SDL2 canvas.draw_line replacement
    pub fn draw_line(&mut self, x0: i32, y0: i32, x1: i32, y1: i32, color: u32) {
        let dx = (x1 - x0).signum();
        let dy = (y1 - y0).signum();
        let steps = (x1 - x0).abs().max((y1 - y0).abs());
        let mut x = x0;
        let mut y = y0;
        for _ in 0..=steps {
            self.set_pixel(x, y, color);
            x += dx;
            y += dy;
        }
    }
}
