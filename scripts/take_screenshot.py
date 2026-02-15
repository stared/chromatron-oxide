"""Take an automatic screenshot of the Chromatron window.

Finds the window by title using Quartz CGWindowList, then calls screencapture -l.
Saves to screenshots/ with datetime-based naming. No manual interaction needed.

Usage: uv run scripts/take_screenshot.py [optional_suffix]
"""
import subprocess
import sys
import os
from datetime import datetime

try:
    import Quartz
except ImportError:
    # pyobjc-framework-Quartz is needed
    print("Installing pyobjc-framework-Quartz...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyobjc-framework-Quartz"])
    import Quartz

def find_window_id(title_substring="Chromatron"):
    """Find CGWindowID by window title substring."""
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
    )
    for win in window_list:
        name = win.get(Quartz.kCGWindowName, "")
        owner = win.get(Quartz.kCGWindowOwnerName, "")
        if title_substring.lower() in (name or "").lower() or title_substring.lower() in (owner or "").lower():
            wid = win.get(Quartz.kCGWindowNumber)
            print(f"Found window: '{name}' (owner: {owner}) → ID {wid}")
            return wid
    return None

def main():
    suffix = sys.argv[1] if len(sys.argv) > 1 else ""
    wid = find_window_id("Chromatron")
    if wid is None:
        print("ERROR: No Chromatron window found. Is the game running?")
        sys.exit(1)

    screenshots_dir = os.path.join(os.path.dirname(__file__), "..", "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"rust-recomp_{timestamp}"
    if suffix:
        name += f"_{suffix}"
    name += ".png"

    filepath = os.path.join(screenshots_dir, name)
    subprocess.run(["screencapture", "-l", str(wid), "-x", filepath], check=True)
    print(f"Saved: {os.path.abspath(filepath)}")

if __name__ == "__main__":
    main()
