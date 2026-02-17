# /// script
# requires-python = ">=3.13"
# dependencies = ["requests"]
# ///
"""Download Wine's sserife.fon (MS Sans Serif bitmap font, LGPL 2.1).

This is the actual Windows bitmap font, not a vector approximation.
FreeType (used by SDL2_ttf) supports loading .fon files natively.
"""
import requests
import pathlib

dest = pathlib.Path("assets/fonts/sserife.fon")
dest.parent.mkdir(parents=True, exist_ok=True)

# Wine's pre-built sserife.fon from deepin-wine-ubuntu package
url = "https://github.com/wszqkzqk/deepin-wine-ubuntu/raw/refs/heads/master/deepin-fonts-wine_2.18-12_all/usr/share/deepin-wine/wine/fonts/sserife.fon"
print(f"Downloading: {url}")
r = requests.get(url, timeout=30)
r.raise_for_status()
dest.write_bytes(r.content)
print(f"OK: {len(r.content)} bytes -> {dest}")

# Also try the Wine GitLab source (fallback)
if len(r.content) < 1000:
    print("Warning: file seems too small, trying Wine GitLab fallback...")
    url2 = "https://gitlab.winehq.org/api/v4/projects/wine%2Fwine/repository/files/fonts%2Fsserife.fon/raw?ref=master"
    print(f"Downloading: {url2}")
    r2 = requests.get(url2, timeout=30)
    r2.raise_for_status()
    dest.write_bytes(r2.content)
    print(f"OK: {len(r2.content)} bytes -> {dest}")
