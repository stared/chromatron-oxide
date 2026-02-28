#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:-dist/Chromatron.app}"
OUTPUT_DMG="${2:-dist/Chromatron-macos-unsigned.dmg}"

mkdir -p "$(dirname "$OUTPUT_DMG")"
mkdir -p dist/dmg-src
rm -rf dist/dmg-src/*
cp -R "$APP_PATH" dist/dmg-src/

hdiutil create \
  -volname "Chromatron" \
  -srcfolder "dist/dmg-src" \
  -ov \
  -format UDZO \
  "$OUTPUT_DMG"
