/// Custom bitmap font renderer for MS Sans Serif 8pt.
/// Renders directly from extracted 1-bit glyph bitmaps — no SDL2_ttf/FreeType needed.
///
/// Source: sserife.fon (Wine's MS Sans Serif, LGPL 2.1) = pixel-perfect match for
/// the original Win32 SYSTEM_FONT used by Chromatron.

use crate::framebuffer::FrameBuffer;
use crate::ms_sans_serif::*;

/// Bitmap font renderer. All data is static/const — no allocation needed.
pub struct BitmapFont;

impl BitmapFont {
    pub fn new() -> Self {
        BitmapFont
    }

    /// Font cell height in pixels (tmHeight = 13).
    pub fn height(&self) -> i32 {
        FONT_HEIGHT
    }

    /// Line spacing in pixels (tmHeight + tmExternalLeading = 16).
    pub fn line_spacing(&self) -> i32 {
        LINE_SPACING
    }

    /// Look up glyph data for a character. Falls back to '?' for non-ASCII.
    fn glyph(ch: char) -> &'static GlyphData {
        let code = ch as u32;
        if code >= 32 && code <= 126 {
            &GLYPHS[(code - 32) as usize]
        } else {
            // Fallback to '?' for unknown characters
            &GLYPHS[('?' as u32 - 32) as usize]
        }
    }

    /// Measure text width in pixels (sum of advance widths).
    /// Matches Win32 GetTextExtentPoint32 behavior.
    pub fn measure_text(&self, text: &str) -> i32 {
        text.chars().map(|ch| Self::glyph(ch).advance as i32).sum()
    }

    /// Draw text directly to the framebuffer at (x, y) in black.
    pub fn draw_text(&self, fb: &mut FrameBuffer, text: &str, x: i32, y: i32) {
        if text.is_empty() { return; }

        let black = FrameBuffer::rgb(0, 0, 0);

        let mut pen_x = x;
        for ch in text.chars() {
            let glyph = Self::glyph(ch);
            let gw = glyph.width as usize;
            let gh = glyph.height as usize;
            let glyph_pitch = glyph.pitch as usize;
            let offset = glyph.bitmap_offset as usize;

            let dst_x = pen_x + glyph.bearing_x as i32;
            let dst_y = y + FONT_ASCENT - glyph.bearing_y as i32;

            for by in 0..gh {
                for bx in 0..gw {
                    let byte_idx = offset + by * glyph_pitch + (bx >> 3);
                    let bit_idx = 7 - (bx & 7);
                    if byte_idx < BITMAP_DATA.len()
                        && (BITMAP_DATA[byte_idx] & (1 << bit_idx)) != 0
                    {
                        let px = dst_x + bx as i32;
                        let py = dst_y + by as i32;
                        fb.set_pixel(px, py, black);
                    }
                }
            }

            pen_x += glyph.advance as i32;
        }
    }
}
