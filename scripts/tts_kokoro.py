"""Local neural TTS (Kokoro-82M ONNX, Apache-2.0) for Feedverse narration.

  tools/venv_tts/bin/python -I scripts/tts_kokoro.py plan/v2.json audio/v2
Writes <out>/vo/<id>.wav (24 kHz mono, trimmed) and <out>/vo_timings.json.
"""
import json, os, sys
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro

MODEL = os.environ.get('KOKORO_MODEL', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache', 'kokoro', '')+'kokoro-v1.0.onnx')
VOICES = os.environ.get('KOKORO_VOICES', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache', 'kokoro', '')+'voices-v1.0.bin')

def trim(x, sr, thr=0.012):
    a = np.abs(x); idx = np.where(a > thr * a.max())[0]
    return x[max(0, idx[0] - int(0.02 * sr)): idx[-1] + int(0.06 * sr)]

def main(plan_path, out):
    plan = json.load(open(plan_path))
    k = Kokoro(MODEL, VOICES)
    os.makedirs(os.path.join(out, 'vo'), exist_ok=True)
    tim_path = os.path.join(out, 'vo_timings.json')
    tim = json.load(open(tim_path)) if os.path.exists(tim_path) else {}
    for line in plan['voice_lines']:
        p = os.path.join(out, 'vo', f"{line['id']}.wav")
        sig = f"{line['voice']}|{line.get('speed', 1.0)}|{line['text']}"
        if os.path.exists(p) and tim.get(line['id'], {}).get('sig') == sig:
            continue
        s, sr = k.create(line['text'], voice=line['voice'], speed=line.get('speed', 1.0), lang=line.get('lang', 'en-gb' if line['voice'][0] == 'b' else 'en-us'))
        s = trim(np.asarray(s, np.float32), sr)
        s = s / (np.abs(s).max() + 1e-9) * 0.95
        sf.write(p, s, sr)
        tim[line['id']] = {'dur': round(len(s) / sr, 3), 'sig': sig}
        print(line['id'], tim[line['id']]['dur'], flush=True)
    json.dump(tim, open(tim_path, 'w'), indent=1)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
