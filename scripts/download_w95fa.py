# /// script
# requires-python = ">=3.13"
# dependencies = ["requests"]
# ///
"""Download W95FA font (SIL OFL) — pixel-accurate MS Sans Serif revival."""
import requests
import pathlib
import zipfile
import io

dest_dir = pathlib.Path("assets/fonts")
dest_dir.mkdir(parents=True, exist_ok=True)

url = "https://arnesava.github.io/w95font/assets/files/w95font.zip"
print(f"Downloading: {url}")
r = requests.get(url, timeout=30)
r.raise_for_status()

# Extract .otf from ZIP
z = zipfile.ZipFile(io.BytesIO(r.content))
for name in z.namelist():
    print(f"  ZIP contains: {name}")
    if name.lower().endswith((".otf", ".ttf")):
        data = z.read(name)
        out = dest_dir / pathlib.Path(name).name
        out.write_bytes(data)
        print(f"  Extracted: {out} ({len(data)} bytes)")
print("Done.")
