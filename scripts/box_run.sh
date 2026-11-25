#!/usr/bin/env bash
# Runs ON the Higgsfield Blender Studio box (L40S). Usage: bash box_run.sh <slug> [samples]
# Needs ~/fv2/upurl.txt (presigned Higgsfield PUT URL). Writes ~/fv2/status.txt; ends with UPLOAD <http code>.
SLUG=$1; SMP=${2:-16}; BR=${BRANCH:-reel-ai-test}
set -x
mkdir -p ~/fv2 && cd ~/fv2; mkdir -p /tmp/keep; cp -r plan/make_*.py scripts/props_extra.py /tmp/keep/ 2>/dev/null
curl -sSL -m 60 https://codeload.github.com/nilsatore-debug/feedverse-oauth/tar.gz/refs/heads/$BR | tar xz --strip-components=1; cp /tmp/keep/make_*.py plan/ 2>/dev/null; cp /tmp/keep/props_extra.py scripts/ 2>/dev/null
mkdir -p cache/fonts cache/kokoro
( cd cache/fonts; for f in "lora/Lora%5Bwght%5D.ttf" "lora/Lora-Italic%5Bwght%5D.ttf" "inter/Inter%5Bopsz,wght%5D.ttf" "archivoblack/ArchivoBlack-Regular.ttf"; do [ -s "$(basename $f)" ] || curl -sSL -m 60 -O "https://raw.githubusercontent.com/google/fonts/main/ofl/$f"; done )
( cd cache/kokoro; [ -s kokoro-v1.0.onnx ] || curl -sSL -m 300 -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx; [ -s voices-v1.0.bin ] || curl -sSL -m 120 -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin )
pip install -q pillow numpy scipy soundfile kokoro-onnx imageio-ffmpeg 2>&1 | tail -1
mkdir -p ~/bin; ln -sf "$(python3 -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')" ~/bin/ffmpeg; export PATH=$HOME/bin:$PATH
ROOT=$HOME/fv2 python3 plan/make_$SLUG.py || { echo "PLAN_FAILED" > status.txt; exit 1; }
echo RENDERING > status.txt
( python3 scripts/tts_kokoro.py plan/$SLUG.json audio/$SLUG && python3 scripts/audio.py plan/$SLUG.json audio/$SLUG ) > audio.log 2>&1 &
scripts/render_all.sh plan/$SLUG.json shots/$SLUG $SMP
wait
echo COMPOSING >> status.txt
mkdir -p out; python3 scripts/compose.py plan/$SLUG.json shots/$SLUG audio/$SLUG out/$SLUG.mp4 > compose.log 2>&1
ffmpeg -v error -i out/$SLUG.mp4 -f null - > decode.log 2>&1
echo "TRACEBACKS $(grep -c Traceback shots/$SLUG/*.log | awk -F: '{s+=$2} END {print s}')" >> status.txt
echo "COMPOSE $(tail -1 compose.log)" >> status.txt
echo "DECODE_ERRORS $(wc -l < decode.log)" >> status.txt
python3 - "$SLUG" >> status.txt <<'PY'
import sys, glob, os
from PIL import Image, ImageStat
s = sys.argv[1]; out = []
for d in sorted(glob.glob(f'shots/{s}/*/')):
    fs = sorted(glob.glob(d + '*.jpg'))
    if not fs: out.append(f'{os.path.basename(d[:-1])}:EMPTY'); continue
    st = ImageStat.Stat(Image.open(fs[len(fs) // 2]).convert('L'))
    out.append(f'{os.path.basename(d[:-1])}:{len(fs)}f/m{round(st.mean[0])}/sd{round(st.stddev[0])}')
print('SHOTS ' + ' '.join(out))
PY
code=$(curl -s -o /dev/null -w '%{http_code}' -X PUT -H "Content-Type: video/mp4" -H "If-None-Match: *" --data-binary @out/$SLUG.mp4 "$(cat upurl.txt)")
echo "UPLOAD $code" >> status.txt
