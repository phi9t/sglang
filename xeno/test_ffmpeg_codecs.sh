#!/usr/bin/env bash
set -euo pipefail

echo "[FFMPEG] Checking encoders..." >&2
FFMPEG_BIN="${FFMPEG_BIN:-$(command -v ffmpeg)}"
echo "[FFMPEG] using ffmpeg: $FFMPEG_BIN" >&2

if ! ENCODERS="$($FFMPEG_BIN -hide_banner -encoders 2>/dev/null)"; then
  echo "[FFMPEG] Failed to list encoders" >&2
  exit 1
fi

if ! printf '%s\n' "$ENCODERS" | grep -q 'libx264'; then
  printf '%s\n' "$ENCODERS" >&2
  echo "[FFMPEG] libx264 encoder not found" >&2
  exit 1
fi
if ! printf '%s\n' "$ENCODERS" | grep -q 'mjpeg'; then
  printf '%s\n' "$ENCODERS" >&2
  echo "[FFMPEG] mjpeg encoder not found" >&2
  exit 1
fi

TMP_DIR="${TMPDIR:-/tmp}/ffmpeg_xeno_test_$$"
mkdir -p "$TMP_DIR"
IMG="$TMP_DIR/test.jpg"
MP4="$TMP_DIR/test.mp4"

echo "[FFMPEG] Encoding JPEG test image..." >&2
"$FFMPEG_BIN" -hide_banner -loglevel error -f lavfi -i testsrc=size=64x64:rate=1:duration=1 -frames:v 1 "$IMG"

echo "[FFMPEG] Encoding H.264 test video..." >&2
"$FFMPEG_BIN" -hide_banner -loglevel error -f lavfi -i testsrc=size=64x64:rate=1:duration=1 -c:v libx264 -t 1 -pix_fmt yuv420p "$MP4"

echo "[FFMPEG] Decoding JPEG..." >&2
"$FFMPEG_BIN" -hide_banner -loglevel error -i "$IMG" -f null -

echo "[FFMPEG] Decoding H.264 MP4..." >&2
"$FFMPEG_BIN" -hide_banner -loglevel error -i "$MP4" -f null -

echo "[FFMPEG] OK"
