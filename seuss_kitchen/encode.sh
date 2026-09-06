#!/usr/bin/env bash
# Encode rendered flythrough frames into an H.264 mp4.
# Usage: encode.sh [frames_dir] [out.mp4] [fps]
set -euo pipefail
FRAMES=${1:-"$(dirname "$0")/../renders/frames"}
OUT=${2:-"$(dirname "$0")/../renders/flythrough.mp4"}
FPS=${3:-24}
FFMPEG=$(python3 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || echo ffmpeg)
"$FFMPEG" -y -framerate "$FPS" -i "$FRAMES/frame_%04d.png" -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart "$OUT"
echo "wrote $OUT"
