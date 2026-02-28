# /// script
# requires-python = ">=3.13"
# dependencies = ["requests"]
# ///
"""Download Wine's ms_sans_serif.ttf (LGPL 2.1) from GitLab API."""
import requests
import pathlib

dest = pathlib.Path("assets/fonts/ms_sans_serif.ttf")
dest.parent.mkdir(parents=True, exist_ok=True)

url = "https://gitlab.winehq.org/api/v4/projects/wine%2Fwine/repository/files/fonts%2Fms_sans_serif.ttf/raw?ref=master"
print(f"Downloading: {url}")
r = requests.get(url, timeout=15)
r.raise_for_status()
dest.write_bytes(r.content)
print(f"OK: {len(r.content)} bytes -> {dest}")
