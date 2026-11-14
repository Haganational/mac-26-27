#!/usr/bin/env bash
# Download the host Piper voice ($VOICE) and every anchor voice in mac/anchors.py into voices/.
# A voice that fails to download is skipped with a warning; its anchors then read in the host voice.
set -u
mkdir -p voices
base=https://huggingface.co/rhasspy/piper-voices/resolve/main
{ python -c "from mac.anchors import voice_path; print(voice_path('${VOICE:-en_US-ryan-high}'))"
  python -c "from mac.anchors import VOICE_POOL, voice_path; print('\n'.join(voice_path(v) for p in VOICE_POOL.values() for v in p))"; } |
while read -r path; do
  name=$(basename "$path")
  for ext in onnx onnx.json; do
    [ -s "voices/$name.$ext" ] && continue
    curl -sSfL -o "voices/$name.$ext" "$base/$path.$ext" || { rm -f "voices/$name.onnx" "voices/$name.onnx.json"; echo "::warning::Piper voice $name did not download"; break; }
  done
done
ls voices/*.onnx 2>/dev/null | wc -l | xargs echo "Piper voices ready:"
