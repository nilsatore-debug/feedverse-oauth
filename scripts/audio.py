"""Feedverse v2 audio: procedural music bed, pulse-train fart synthesis, scene SFX, Kokoro voice lines, mix.

  tools/venv311/bin/python -I scripts/audio_v2.py plan/fart_v2.json audio/fart_v2
Needs <out>/vo/<id>.wav from scripts/tts_kokoro.py (voice_lines in the plan).
Writes <out>/mix.wav (48 kHz stereo) and stems.
"""
import json, os, sys, wave
import numpy as np
from scipy.signal import butter, lfilter, sosfilt, resample_poly

SR = 48000
rng = np.random.default_rng(7)

def write(path, x):
    x = np.clip(x, -1, 1)
    if x.ndim == 1: x = np.stack([x, x], 1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype('<i2').tobytes())

def read(path):
    with wave.open(path, 'rb') as w:
        sr = w.getframerate(); ch = w.getnchannels(); sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw == 2: x = np.frombuffer(raw, '<i2').astype(np.float32) / 32768
    else: x = np.frombuffer(raw, '<f4').astype(np.float32)
    if ch == 2: x = x.reshape(-1, 2).mean(1)
    if sr != SR:
        from math import gcd
        g = gcd(sr, SR); x = resample_poly(x, SR // g, sr // g).astype(np.float32)
    return x

def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo / (SR / 2), hi / (SR / 2)], 'band', output='sos'), x)
def lp(x, fc, order=2):
    return sosfilt(butter(order, fc / (SR / 2), 'low', output='sos'), x)
def hp(x, fc, order=2):
    return sosfilt(butter(order, fc / (SR / 2), 'high', output='sos'), x)
def env(n, a=0.005, r=0.05):
    e = np.ones(n); na = max(1, int(a * SR)); nr = max(1, min(n - na, int(r * SR)))
    e[:na] = np.linspace(0, 1, na); e[-nr:] *= np.linspace(1, 0, nr) ** 2; return e
def norm(x, p=0.9):
    m = np.max(np.abs(x)) or 1; return x / m * p
def noise(n): return rng.standard_normal(n)
def smooth(n, rate):
    k = max(2, int(n * rate / SR) + 2); return np.interp(np.linspace(0, k - 1, n), np.arange(k), rng.standard_normal(k))
def reverb(x, amt=0.25, size=0.6):
    ir_n = int(size * SR); t = np.arange(ir_n) / SR
    ir = noise(ir_n) * np.exp(-t * (6 / size)); ir = lp(ir, 4000); ir /= np.sqrt((ir ** 2).sum())
    wet = np.convolve(x, ir)[:len(x)] if len(x) < 4 * SR else fftconv(x, ir)
    return x * (1 - amt) + wet * amt
def fftconv(a, b):
    n = len(a) + len(b) - 1; N = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(a, N) * np.fft.rfft(b, N), N)[:len(a)]

# ---------------------------------------------------------------- farts: pulse train through a resonant "cheek" filter
def fart(n_level, seed):
    """n_level: 1..21. Higher = longer, lower, louder, wetter, more chaotic."""
    r = np.random.default_rng(seed)
    k = (n_level - 1) / 20.0
    dur = 0.28 + 2.6 * k ** 1.2 + r.uniform(-0.05, 0.1)
    n = int(dur * SR); t = np.arange(n) / SR
    f0 = (230 - 150 * k) * r.uniform(0.85, 1.15); f1 = f0 * r.uniform(0.55, 0.85)
    if n_level == 1: f0, f1 = 520, 640
    f = f0 + (f1 - f0) * (t / dur) ** 0.8
    f *= 1 + (0.06 + 0.25 * k) * smooth(n, 30)
    # build pulse train with jitter
    x = np.zeros(n); phase = 0.0; i = 0
    while i < n:
        per = SR / max(30, f[i]); amp = 0.6 + 0.4 * r.random()
        if r.random() < 0.04 + 0.15 * k: amp *= 0.15  # sputter gaps
        j = int(i)
        if j < n: x[j] += amp
        i += per * r.uniform(0.85, 1.15)
    # resonant body: two damped resonances + lowpassed noise "air"
    body = bp(x, 80 + 40 * (1 - k), 900 - 300 * k, 2) * 4 + bp(x, 250, 1600, 1) * 0.8
    air = bp(noise(n), 200, 2500, 2) * (0.04 + 0.25 * k) * (0.5 + 0.5 * np.abs(smooth(n, 12)))
    wet = (r.random(n) < 0.002 + 0.01 * k) * r.standard_normal(n) * 0.8 * k
    y = body + air + lp(wet, 3000)
    if n_level == 1:
        y = bp(x, 400, 1600, 2) * 3 + bp(noise(n), 600, 3000) * 0.05
    sub = np.sin(2 * np.pi * np.cumsum(f * 0.5) / SR) * 0.35 * k
    y = y + sub
    y = np.tanh(y * (1.2 + 3 * k)) * env(n, 0.006, min(0.25, dur * 0.3))
    if n_level >= 12:  # rumble tail
        m = int((0.8 + 1.6 * k) * SR); tt = np.arange(m) / SR
        rum = lp(noise(m), 90, 2) * 6 * np.exp(-tt * 1.8)
        y = np.concatenate([y, np.zeros(m)]); y[n - int(0.2 * SR):n - int(0.2 * SR) + m] += rum[:len(y) - (n - int(0.2 * SR))]
    y = reverb(y, 0.12 + 0.25 * k, 0.4 + 1.2 * k)
    gain = 0.45 + 0.55 * min(1, k * 2)
    return norm(y, gain)

# ---------------------------------------------------------------- music
BPM = 124; BEAT = 60 / BPM
def kick(n=int(0.35 * SR)):
    t = np.arange(n) / SR; f = 50 + 110 * np.exp(-t * 35)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) + 0.15 * np.exp(-t * 200) * noise(n)
def snare(n=int(0.25 * SR)):
    t = np.arange(n) / SR
    return (bp(noise(n), 1500, 7000) * 0.9 + np.sin(2 * np.pi * 190 * t) * 0.5) * np.exp(-t * 18)
def clap(n=int(0.2 * SR)):
    t = np.arange(n) / SR; e = np.exp(-t * 22) * (1 + 0.6 * (np.sin(2 * np.pi * 90 * t) > 0.7))
    return bp(noise(n), 1000, 4000) * e
def hat(n=int(0.06 * SR), open_=False):
    if open_: n = int(0.22 * SR)
    t = np.arange(n) / SR; return hp(noise(n), 7000) * np.exp(-t * (18 if open_ else 70))
def pluck(freq, n, bright=1.0):
    t = np.arange(n) / SR
    saw = 2 * ((freq * t) % 1) - 1; sq = np.sign(np.sin(2 * np.pi * freq * 1.003 * t))
    return lp(0.6 * saw + 0.3 * sq, 900 + 2500 * bright) * np.exp(-t * 7)
def bass(freq, n):
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) * 0.8 + 0.25 * np.tanh(3 * np.sin(2 * np.pi * freq * t))) * env(n, 0.005, 0.04)
def pad(freqs, n):
    t = np.arange(n) / SR; y = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) + 0.5 * np.sin(2 * np.pi * f * 2.003 * t) for f in freqs)
    return lp(y, 1500) * env(n, 0.4, 0.6)

NOTE = lambda m: 440 * 2 ** ((m - 69) / 12)
PROG = [(45, [57, 60, 64]), (41, [57, 60, 65]), (43, [55, 59, 62]), (40, [55, 59, 64])]  # Am F G Em

def place(buf, x, t, g=1.0):
    i = int(t * SR)
    if i >= len(buf): return
    m = min(len(x), len(buf) - i); buf[i:i + m] += x[:m] * g

def music(D, sect):
    """sect: list of (t0, t1, level 0..3)."""
    y = np.zeros(int(D * SR))
    K, S, C, H, HO = kick(), snare(), clap(), hat(), hat(open_=True)
    for t0, t1, lvl in sect:
        if lvl < 0: continue
        nb = int((t1 - t0) / BEAT + 0.5)
        for b in range(nb):
            tb = t0 + b * BEAT
            if tb >= t1: break
            bar = int((tb - sect[0][0]) / (4 * BEAT)); root, chord = PROG[bar % 4]
            beat_in_bar = b % 4
            if lvl == 0:
                if beat_in_bar == 0: place(y, pad([NOTE(m) for m in chord], int(4 * BEAT * SR)), tb, 0.12)
                place(y, H, tb + BEAT / 2, 0.15); continue
            place(y, K, tb, 0.9)
            if beat_in_bar in (1, 3): place(y, S, tb, 0.45); place(y, C, tb, 0.25 if lvl >= 2 else 0)
            for h in range(2 if lvl < 2 else 4):
                place(y, H, tb + h * BEAT / (2 if lvl < 2 else 4), 0.18 if h % 2 else 0.1)
            if lvl >= 2 and beat_in_bar == 3: place(y, HO, tb + BEAT / 2, 0.12)
            bn = int(BEAT / 2 * SR)
            for e in range(2):
                fr = NOTE(root - 12 + (12 if (e == 1 and lvl >= 2) else 0))
                place(y, bass(fr, bn), tb + e * BEAT / 2, 0.42)
            if beat_in_bar == 0: place(y, pad([NOTE(m) for m in chord], int(4 * BEAT * SR)), tb, 0.06 + 0.03 * lvl)
            if lvl >= 1:
                arp = chord + [chord[0] + 12]
                for s in range(2 if lvl < 3 else 4):
                    m = arp[(b * 2 + s) % len(arp)] + 12
                    place(y, pluck(NOTE(m), int(0.25 * SR), 0.5 + 0.2 * lvl), tb + s * BEAT / (2 if lvl < 3 else 4), 0.10)
    return y

def riser(dur, f0=200, f1=2000):
    n = int(dur * SR); t = np.arange(n) / SR; u = t / dur
    f = f0 * (f1 / f0) ** u
    saw = 2 * ((np.cumsum(f) / SR) % 1) - 1
    nz = bp(noise(n), 500, 9000) * u ** 2
    roll = np.zeros(n); tt = 0.0; S = snare(int(0.12 * SR))
    while tt < dur:
        place(roll, S, tt, 0.25 + 0.6 * tt / dur); tt += max(0.035, 0.25 * (1 - tt / dur) ** 1.5)
    return (lp(saw, 3000) * 0.25 * u + nz * 0.5 + roll) * np.minimum(1, (1 - u) * 50 + 0.02)

def boom(dur=3.0):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 30 + 80 * np.exp(-t * 3)
    return norm(np.tanh(2.5 * (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.3) + lp(noise(n), 400) * 3 * np.exp(-t * 2.2))), 1.0)

# ---------------------------------------------------------------- sfx
def sfx(kind, dur=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    if kind == 'whoosh':
        return norm(bp(noise(n), 300, 5000) * np.sin(np.pi * t / dur) ** 2, 0.5)
    if kind == 'ding':
        y = np.zeros(int(1.4 * SR)); tt = np.arange(len(y)) / SR
        for f, t0 in ((1318.5, 0), (1046.5, 0.25)):
            m = tt >= t0; y[m] += (np.sin(2 * np.pi * f * (tt[m] - t0)) + 0.3 * np.sin(2 * np.pi * 2.76 * f * (tt[m] - t0))) * np.exp(-(tt[m] - t0) * 3.5)
        return norm(y, 0.6)
    if kind == 'door':
        return norm(lp(noise(n), 1200) * np.sin(np.pi * t / dur) ** 2 + 0.3 * np.sin(2 * np.pi * 90 * t) * np.sin(np.pi * t / dur), 0.5)
    if kind == 'steps':
        y = np.zeros(n); tt = 0.0
        while tt < dur - 0.05:
            m = int(0.07 * SR); place(y, lp(noise(m), 600) * np.exp(-np.arange(m) / SR * 60), tt, rng.uniform(0.5, 1)); tt += rng.uniform(0.04, 0.11)
        return norm(y, 0.6)
    if kind == 'slide_down':
        f = 900 * (0.25 ** (t / dur)); return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.02, 0.1) * (1 + 0.15 * np.sin(2 * np.pi * 6 * t)), 0.45)
    if kind == 'breath':
        e = (np.sin(2 * np.pi * t / 1.1) > 0) * 1.0; return norm(bp(noise(n), 300, 2500) * lp(e, 8) * env(n, 0.1, 0.2), 0.35)
    if kind == 'alarm':
        sq = np.sign(np.sin(2 * np.pi * 950 * t)) * (np.sin(2 * np.pi * t / 0.36) > 0); return norm(lp(sq, 4000) * env(n, 0.01, 0.05), 0.35)
    if kind == 'thud':
        return norm(lp(noise(n), 300) * np.exp(-t * 25) + np.sin(2 * np.pi * 70 * t) * np.exp(-t * 20), 0.6)
    if kind == 'coo':
        f = 520 + 80 * np.sin(2 * np.pi * 4 * t); return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / dur) ** 2, 0.3)
    if kind == 'car_alarm':
        y = np.zeros(n)
        for k, (lo, hi, rate) in enumerate(((700, 1400, 3.0), (900, 1200, 6.0), (600, 1100, 1.6))):
            f = lo + (hi - lo) * (0.5 + 0.5 * np.sin(2 * np.pi * rate * t)); y += np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * (t > k * 0.12)
        return norm(lp(y, 5000) * env(n, 0.02, 0.1), 0.35)
    if kind == 'glass':
        y = hp(noise(n), 2500) * np.exp(-t * 6) * 1.2
        for k in range(60):
            t0 = rng.uniform(0, dur * 0.8); m = int(0.05 * SR); fr = rng.uniform(3000, 9000)
            place(y, np.sin(2 * np.pi * fr * np.arange(m) / SR) * np.exp(-np.arange(m) / SR * 80) * 0.5, t0)
        return norm(y + lp(noise(n), 200) * np.exp(-t * 8) * 1.5, 0.8)
    if kind == 'rumble':
        return norm(lp(noise(n), 120, 2) * env(n, 0.3, 0.6), 0.8)
    if kind == 'heli':
        chop = (np.sin(2 * np.pi * 14 * t) > 0.6) * 1.0; return norm(lp(noise(n), 500) * (0.3 + lp(chop, 60)) * env(n, 0.2, 0.3), 0.6)
    if kind == 'jingle':
        y = np.zeros(int(1.6 * SR)); tt = np.arange(len(y)) / SR
        for k, f in enumerate((523.25, 659.25, 783.99, 1046.5)):
            m = tt >= 0.13 * k; x = tt[m] - 0.13 * k; y[m] += (np.tanh(1.5 * np.sin(2 * np.pi * f * x)) * 0.6) * np.exp(-x * (3 if k == 3 else 7))
        return norm(lp(y, 5000), 0.6)
    if kind == 'sting':
        return norm(np.sin(2 * np.pi * 98 * t) * np.exp(-t * 2.5) + 0.5 * np.sin(2 * np.pi * 196 * t) * np.exp(-t * 4) + hp(noise(n), 2000) * np.exp(-t * 10) * 0.5, 0.7)
    if kind == 'horns':
        y = np.zeros(n)
        for k in range(6):
            t0 = rng.uniform(0, dur - 0.5); m = int(rng.uniform(0.2, 0.5) * SR); fr = rng.uniform(300, 480); tt = np.arange(m) / SR
            place(y, np.tanh(2 * np.sin(2 * np.pi * fr * tt)) * env(m, 0.01, 0.05), t0, 0.5)
        return norm(lp(y, 3000) + lp(noise(n), 400) * 0.6, 0.5)
    if kind == 'jet':
        f = 300 + 200 * t / dur; return norm(bp(noise(n), 200, 3000) * np.sin(np.pi * t / dur) ** 1.5 + 0.2 * np.sin(2 * np.pi * np.cumsum(f * 3) / SR) * np.sin(np.pi * t / dur), 0.6)
    if kind == 'thruster':
        return norm(bp(noise(n), 400, 3000) * env(n, 0.05, 0.4) * (t < dur * 0.7), 0.4)
    if kind == 'ufo':
        f = 600 + 300 * np.sin(2 * np.pi * 7 * t) + 400 * (t / dur) ** 3 * 4; return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.05, 0.3), 0.4)
    if kind == 'zaps':
        y = np.zeros(n)
        for k in range(18):
            t0 = rng.uniform(0, dur - 0.1); m = int(0.08 * SR); place(y, hp(noise(m), 1500) * np.exp(-np.arange(m) / SR * 40) * np.sign(np.sin(2 * np.pi * 120 * np.arange(m) / SR)), t0, 0.6)
        return norm(y, 0.6)
    if kind == 'space_hum':
        return norm(lp(noise(n), 150) * 0.5 + 0.2 * np.sin(2 * np.pi * 55 * t), 0.35) * env(n, 0.3, 0.3)
    return sfx2(kind, dur)


def sfx2(kind, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    if kind == 'typing':
        y = np.zeros(n); tt = 0.0
        while tt < dur - 0.03:
            m = int(0.025 * SR); place(y, bp(noise(m), 1500, 6000) * np.exp(-np.arange(m) / SR * 180), tt, rng.uniform(0.4, 1)); tt += rng.uniform(0.06, 0.14)
        return norm(y, 0.5)
    if kind == 'power_on':
        f = 120 * (12 ** (t / dur)); y = np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / dur) ** 0.5 * env(n, 0.01, 0.15)
        return norm(y + 0.4 * np.sin(2 * np.pi * 880 * t) * np.exp(-((t - dur * 0.8) * 12) ** 2), 0.5)
    if kind == 'blink':
        return norm(np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 40), 0.3)
    if kind == 'data':
        y = np.zeros(n); tt = 0.0
        while tt < dur - 0.03:
            m = int(0.03 * SR); fr = rng.choice([880, 1320, 1760, 2640, 3520])
            place(y, np.sign(np.sin(2 * np.pi * fr * np.arange(m) / SR)) * env(m, 0.001, 0.01), tt, rng.uniform(0.2, 0.6)); tt += rng.uniform(0.02, 0.05)
        return norm(lp(y, 6000) + bp(noise(n), 2000, 8000) * 0.15, 0.4) * env(n, 0.05, 0.3)
    if kind == 'sad_blip':
        y = np.zeros(n)
        for k, f in enumerate((660, 520, 392)):
            m = int(0.22 * SR); tt = np.arange(m) / SR; place(y, np.sign(np.sin(2 * np.pi * f * tt)) * env(m, 0.005, 0.06), 0.24 * k, 0.5)
        return norm(lp(y, 3000), 0.45)
    if kind == 'printer':
        y = lp(noise(n), 900) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 7 * t))) + 0.25 * np.sign(np.sin(2 * np.pi * 220 * t)) * (np.sin(2 * np.pi * 3.7 * t) > 0)
        return norm(lp(y, 2500) * env(n, 0.05, 0.2), 0.5)
    if kind == 'thuds':
        y = np.zeros(n); tt = 0.0
        while tt < dur - 0.1:
            m = int(0.12 * SR); place(y, sfx('thud', 0.12), tt, rng.uniform(0.4, 0.8)); tt += rng.uniform(0.035, 0.06)
        return norm(y, 0.6)
    if kind == 'rattle':
        y = np.zeros(n)
        for k in range(5):
            m = int(0.15 * SR); place(y, lp(noise(m), 1500) * np.exp(-np.arange(m) / SR * 25), 0.36 * k, 0.8)
        return norm(y, 0.55)
    if kind == 'buzz':
        return norm(lp(np.sign(np.sin(2 * np.pi * 110 * t)), 2000) * env(n, 0.01, 0.05), 0.4)
    if kind == 'brakes':
        f = 2600 + 300 * np.sin(2 * np.pi * 9 * t); return norm(bp(noise(n), 1800, 4500) * 0.5 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3, 0.35) * env(n, 0.02, 0.4)
    if kind == 'march':
        y = np.zeros(n); tt = 0.0
        while tt < dur - 0.1:
            m = int(0.1 * SR); hit = lp(noise(m), 500) * np.exp(-np.arange(m) / SR * 40) + 0.4 * np.sin(2 * np.pi * 90 * np.arange(m) / SR) * np.exp(-np.arange(m) / SR * 30)
            clank = bp(noise(m), 3000, 7000) * np.exp(-np.arange(m) / SR * 60) * 0.5
            place(y, hit + clank, tt, 1.0); tt += 0.36
        return norm(y, 0.7)
    if kind == 'servo':
        f = 300 + 500 * (t / dur); return norm(np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.3 + bp(noise(n), 500, 2000) * 0.4, 0.35) * env(n, 0.05, 0.3)
    if kind == 'heartbeat':
        y = np.zeros(n); tt = 0.05
        while tt < dur - 0.3:
            for dt, g in ((0.0, 1.0), (0.22, 0.7)):
                m = int(0.18 * SR); tm = np.arange(m) / SR; place(y, np.sin(2 * np.pi * (45 + 40 * np.exp(-tm * 30)) * tm) * np.exp(-tm * 18), tt + dt, g)
            tt += 0.85
        return norm(y, 0.9)
    if kind == 'launches':
        y = np.zeros(n)
        for k in range(10):
            m = int(0.8 * SR); tm = np.arange(m) / SR; place(y, bp(noise(m), 300, 3000) * np.sin(np.pi * tm / 0.8) ** 2, rng.uniform(0, dur - 0.8), 0.5)
        return norm(y, 0.5)
    if kind == 'grid':
        y = np.zeros(n)
        for k in range(3):
            m = int(0.25 * SR); tm = np.arange(m) / SR; place(y, np.sin(2 * np.pi * 60 * tm) * 0.6 + bp(noise(m), 1000, 5000) * np.exp(-tm * 20) * 0.6, 0.3 * k, 0.8)
        return norm(y, 0.6)
    if kind == 'assemble':
        y = np.zeros(n); tt = 0.0
        while tt < dur - 0.05:
            m = int(0.04 * SR); place(y, bp(noise(m), 2000, 8000) * np.exp(-np.arange(m) / SR * 100), tt, rng.uniform(0.3, 0.7)); tt += rng.uniform(0.02, 0.05)
        return norm(y, 0.45)
    if kind == 'warp':
        f = 80 * (20 ** (t / dur)); y = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4 + bp(noise(n), 200, 6000) * (t / dur)
        return norm(y * env(n, 0.05, 0.2) + boom(dur)[:n] * 0.4 * (t < 0.6), 0.8)
    if kind == 'powerdown':
        f = 900 * (0.08 ** (t / dur)); return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * (1 - t / dur) ** 0.7, 0.45)
    if kind == 'room':
        return norm(lp(noise(n), 300) * 0.3 + 0.05 * np.sin(2 * np.pi * 60 * t), 0.15) * env(n, 0.3, 0.5)
    if kind == 'gasp_chord':
        return np.zeros(n)
    raise ValueError(kind)

def glitch(level, seed):
    """Beat hit: digital stutter + sub drop; grows with level (1..19)."""
    r = np.random.default_rng(seed); k = (level - 1) / 18.0
    dur = 0.35 + 0.5 * k; n = int(dur * SR); t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(40 + 120 * np.exp(-t * 18)) / SR) * np.exp(-t * (7 - 3 * k))
    st = np.zeros(n); tt = 0.0; f0 = r.uniform(300, 900)
    while tt < 0.18 + 0.15 * k:
        m = int(0.025 * SR); place(st, np.sign(np.sin(2 * np.pi * f0 * np.arange(m) / SR)) * 0.5, tt, 1.0); tt += 0.035; f0 *= r.uniform(0.8, 1.3)
    nz = bp(noise(n), 2000, 9000) * np.exp(-t * 25) * 0.5
    return norm(sub * (0.6 + 0.6 * k) + lp(st, 5000) * 0.5 + nz, 0.6 + 0.35 * k)

def voice_fx(x, kind):
    if kind == 'robot':
        t = np.arange(len(x)) / SR; rm = x * np.sin(2 * np.pi * 55 * t)
        y = 0.55 * x + 0.6 * rm; y = np.round(y * 24) / 24
        y = y + 0.3 * np.roll(y, int(0.012 * SR)); return reverb(lp(y, 6000), 0.2, 0.4)
    if kind == 'ai':
        y = x + 0.35 * np.roll(x, int(0.009 * SR)) + 0.25 * np.roll(x, int(0.017 * SR)); return reverb(y, 0.3, 0.9)
    if kind == 'old':
        return reverb(lp(x, 5000), 0.12, 0.4)
    return x

def main(plan_path, out):
    plan = json.load(open(plan_path)); D = plan['duration']; N = int(D * SR); M = plan['music']
    os.makedirs(out, exist_ok=True)
    mus = music(D, [tuple(x) for x in M['sections']])
    rt, rd = M['riser']; place(mus, riser(rd, 150, 2500), rt, 0.55)
    dt_, dd = M['drone']; place(mus, pad([NOTE(45), NOTE(52), NOTE(57)], int((dd + 0.6) * SR)), dt_, 0.14)
    place(mus, pad([NOTE(53), NOTE(57), NOTE(60), NOTE(65)], int(3.4 * SR)), M['end_pad'], 0.13)
    place(mus, sfx('sting', 1.5), M['end_pad'], 0.5)
    hits = np.zeros(N)
    for it in plan['counter']['items']:
        if it['n'] < len(plan['counter']['items']): place(hits, glitch(it['n'], 300 + it['n']), it['t'], 1.0)
    fx = np.zeros(N)
    for t, k, d, g in plan['sfx']:
        if g > 0: place(fx, sfx(k, d), t, g)
    for s in plan['shots']:
        if s['t0'] > 0.5 and not s.get('inset'): place(fx, sfx('whoosh', 0.3), s['t0'] - 0.15, 0.16)
    vo = np.zeros(N); vdir = os.path.join(out, 'vo')
    for v in plan['voice_lines']:
        x = read(os.path.join(vdir, f"{v['id']}.wav")); x = hp(x, 80); x = voice_fx(x, v.get('fx'))
        place(vo, norm(x, 0.95), v['t'], v.get('gain', 1.0))
    venv = lp(np.abs(vo), 8, 1); g = np.clip(venv / (venv.max() + 1e-9) * 3, 0, 1)
    mix = mus * 0.5 * (1 - 0.7 * g) + hits * 0.8 * (1 - 0.5 * g) + fx * 0.75 * (1 - 0.5 * g) + vo * 1.0
    mix = np.tanh(mix * 1.1) * 0.9
    st = np.stack([mix, mix], 1)
    st[:, 0] += 0.04 * np.roll(mus + fx, 240); st[:, 1] += 0.04 * np.roll(mus + fx, 480)
    st /= max(1.0, np.abs(st).max() / 0.98)
    write(os.path.join(out, 'mix_raw.wav'), st)
    print('audio ok', D)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
