#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${1:-dist/Chromatron.app}"
BINARY_PATH="${2:-target/release/chromatron}"
PLIST_TEMPLATE="${3:-.github/templates/Chromatron-Info.plist}"

mkdir -p "$APP_ROOT/Contents/MacOS"
mkdir -p "$APP_ROOT/Contents/Resources"

cp "$BINARY_PATH" "$APP_ROOT/Contents/MacOS/chromatron"
cp "$PLIST_TEMPLATE" "$APP_ROOT/Contents/Info.plist"
chmod +x "$APP_ROOT/Contents/MacOS/chromatron"
