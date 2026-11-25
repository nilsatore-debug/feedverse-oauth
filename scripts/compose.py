"""Compose v2: rendered shot frames + reference-style overlays (Pillow) -> H.264, then mux the mix (FFmpeg).

  tools/venv311/bin/python -I scripts/compose_v2.py plan/fart_v2.json shots/fart_v2_1080x1920_30 audio/fart_v2 out/fart_v2.mp4 [--until S] [--from S] [--scale 0.5]
"""
import argparse, json, math, os, subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W0, H0 = 1080, 1920
_F = {}
def font(path, size, wght=None):
    k = (path, size, wght)
    if k not in _F:
        f = ImageFont.truetype(path, size)
        if wght is not None:
            try: f.set_variation_by_axes([wght] if 'Lora' in path else [14 if size < 30 else 32, wght])
            except Exception:
                try: f.set_variation_by_axes([wght])
                except Exception: pass
        _F[k] = f
    return _F[k]

def wrap(d, text, f, width):
    out, cur = [], ''
    for w in text.split():
        nx = (cur + ' ' + w).strip()
        if d.textlength(nx, font=f) <= width: cur = nx
        else: out.append(cur); cur = w
    out.append(cur); return out

def spaced(d, xy, text, f, fill, spacing):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill); x += d.textlength(ch, font=f) + spacing
    return x

def shadowed(layer_fn, size=(W0, H0), blur=5, alpha=150, off=(0, 3)):
    fg = Image.new('RGBA', size, (0, 0, 0, 0)); layer_fn(ImageDraw.Draw(fg), (255, 255, 255, 255))
    sh = Image.new('RGBA', size, (0, 0, 0, 0)); layer_fn(ImageDraw.Draw(sh), (0, 0, 0, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new('RGBA', size, (0, 0, 0, 0)); out.alpha_composite(sh, off); out.alpha_composite(fg)
    return out

def fmt(v):
    v = max(1.0, v)
    for lim, div, name in ((60, 1, 'SECOND'), (3600, 60, 'MINUTE'), (86400, 3600, 'HOUR'), (7 * 86400, 86400, 'DAY'),
                           (30 * 86400, 7 * 86400, 'WEEK'), (365.25 * 86400, 30 * 86400, 'MONTH'), (1e30, 365.25 * 86400, 'YEAR')):
        if v < lim:
            n = max(1, int(v / div)); return f'{n:,} {name}' + ('S' if n != 1 else '')

class Overlay:
    def __init__(self, plan):
        self.p = plan; F = plan['fonts']
        self.serif, self.ital, self.sans = F['serif'], F['serif_italic'], F['ui']
        self.items = plan['counter']['items']; self.cache = {}
        self.title = self._title()

    def _title(self):
        f = font(self.serif, 86, 500)
        def draw(d, col):
            lines = wrap(d, self.p['title'], f, 920); y = 300
            for ln in lines:
                w = d.textlength(ln, font=f); d.text(((W0 - w) / 2, y), ln, font=f, fill=col); y += 104
        return shadowed(draw, blur=8, alpha=170)

    def state(self, t):
        cur = None
        for it in self.items:
            if t >= it['t']: cur = it
        return cur

    def value_at(self, t):
        it = self.state(t)
        if it is None: return None, None
        i = self.items.index(it); prev = max(1.0, self.items[i - 1]['value'] if i else 1.0)
        u = min(1.0, (t - it['t']) / self.p['counter']['roll']); u = 1 - (1 - u) ** 3
        return prev * (max(1.0, it['value']) / prev) ** u, it

    def block(self, value, it, t):
        sub = it['sub']; vs = fmt(value)
        key = (vs, it['n'])
        if key in self.cache: return self.cache[key]
        c = self.p['counter']; x = 63
        fl = font(self.sans, 23, 600); fv = font(self.serif, 96, 400); fs = font(self.sans, 22, 700); fn = font(self.sans, 18, 500); fp = font(self.sans, 18, 800)
        def draw(d, col):
            spaced(d, (x, 284), c['label'], fl, col, 2.5)
            d.text((x - 3, 310), vs, font=fv, fill=col)
            spaced(d, (x, 428), sub, fs, col, 1.6)
        im = shadowed(draw, size=(1000, 560), blur=5, alpha=140)
        d = ImageDraw.Draw(im); pill = c['pill']; tw = d.textlength(pill, font=fp)
        d.rounded_rectangle([x, 466, x + tw + 24, 498], 6, fill=(229, 57, 69, 255))
        d.text((x + 12, 469), pill, font=fp, fill=(255, 255, 255, 255))
        self.cache[key] = im
        return im

    def caption(self, text):
        k = ('cap', text)
        if k in self.cache: return self.cache[k]
        f = font(self.ital, 50, 450)
        def draw(d, col):
            y = 548
            for ln in wrap(d, text, f, 930):
                d.text((63, y), ln, font=f, fill=col); y += 62
        im = shadowed(draw, size=(W0, 800), blur=5, alpha=150); self.cache[k] = im; return im

    def banner(self, bn, t):
        k = min(1.0, (t - bn['t0']) / 0.22); x = int(-W0 * (1 - k) ** 2)
        ban = Image.new('RGBA', (W0, H0), (0, 0, 0, 0)); bd = ImageDraw.Draw(ban); y0 = 1440
        ft = font(self.sans, 34, 800); tw = bd.textlength(bn['top'], font=ft)
        bd.rectangle([40 + x, y0, 40 + x + tw + 40, y0 + 58], fill=(200, 32, 45, 255)); bd.text((60 + x, y0 + 8), bn['top'], font=ft, fill='white')
        bd.rectangle([40 + x, y0 + 58, 1040 + x, y0 + 196], fill=(250, 250, 250, 255))
        sz = 76
        while bd.textlength(bn['main'], font=font(self.sans, sz, 900)) > 940: sz -= 2
        bd.text((64 + x, y0 + 127 - sz * 0.62), bn['main'], font=font(self.sans, sz, 900), fill=(15, 20, 35))
        bd.rectangle([40 + x, y0 + 196, 1040 + x, y0 + 252], fill=(15, 20, 35, 255))
        tick = bn['ticker'] * 3; ftk = font(self.sans, 28, 700); off = int((t - bn['t0']) * 180)
        tl = Image.new('RGBA', (1000, 56), (0, 0, 0, 0)); ImageDraw.Draw(tl).text((10 - off, 12), tick, font=ftk, fill=(232, 197, 71))
        ban.alpha_composite(tl, (40 + x, y0 + 196))
        return ban

    def apply(self, im, t):
        tc = self.p['title_card']
        if tc['t0'] <= t < tc['t1']:
            a = min(1.0, (tc['t1'] - t) / 0.3, (t - tc['t0']) / 0.2 + 0.0001)
            lay = self.title if a >= 1 else Image.blend(Image.new('RGBA', (W0, H0), (0, 0, 0, 0)), self.title, a)
            im.alpha_composite(lay)
        if t < self.p['counter']['hide_after']:
            v, it = self.value_at(t)
            if it is not None:
                im.alpha_composite(self.block(v, it, t), (0, 0))
                txt = it['caption']; age = t - it['t']
                cap = self.caption(txt)
                if age < 0.18: cap = Image.blend(Image.new('RGBA', cap.size, (0, 0, 0, 0)), cap, max(0.0, age / 0.18))
                im.alpha_composite(cap, (0, 0))
        for bn in self.p.get('banners', []):
            if bn['t0'] <= t < bn['t1']: im.alpha_composite(self.banner(bn, t), (0, 0))
        for fl in self.p.get('flashes', []):
            if fl['t'] <= t < fl['t'] + fl['dur']:
                a = 1 - (t - fl['t']) / fl['dur']
                im.alpha_composite(Image.new('RGBA', (W0, H0), (255, 255, 255, int(255 * a ** 1.5))))
        return im

class Weather:
    def __init__(self, plan, anchor_dir, shot):
        self.p = plan; self.w = plan['weather']; self.dir = anchor_dir; self.shot = shot
        self.sans = plan['fonts']['sans']; self.serif = plan['fonts']['serif']; self.bg = self._static()

    def _static(self):
        im = Image.new('RGB', (W0, H0)); d = ImageDraw.Draw(im)
        for y in range(H0):
            k = y / H0; d.line([(0, y), (W0, y)], fill=(int(12 + 22 * k), int(24 + 34 * k), int(48 + 64 * k)))
        y0 = 640
        d.rectangle([40, y0, 760, y0 + 76], fill=(200, 32, 45)); d.text((62, y0 + 12), f"{self.w['station']}  WEATHER", font=font(self.sans, 46, 800), fill='white')
        d.rounded_rectangle([800, y0 + 6, 1040, y0 + 70], 32, fill='white'); d.ellipse([822, y0 + 24, 850, y0 + 52], fill=(220, 30, 40))
        d.text((864, y0 + 14), 'LIVE', font=font(self.sans, 42, 800), fill=(200, 32, 45))
        d.text((44, y0 + 96), self.w['segment'], font=font(self.serif, 58, 600), fill='white')
        mx0, my0, mx1, my1 = 40, 820, 1040, 1300
        mp = Image.new('RGB', (mx1 - mx0, my1 - my0), (233, 226, 208)); md = ImageDraw.Draw(mp); step, road = 160, 28
        for gx in range(-60, mx1 - mx0 + step, step):
            for gy in range(-60, my1 - my0 + step, step):
                md.rectangle([gx + road / 2, gy + road / 2, gx + step - road / 2, gy + step - road / 2], fill=(214, 204, 182))
            md.rectangle([gx - road / 2, 0, gx + road / 2, my1 - my0], fill=(154, 163, 173))
        for gy in range(-60, my1 - my0 + step, step): md.rectangle([0, gy - road / 2, mx1 - mx0, gy + road / 2], fill=(154, 163, 173))
        md.rectangle([260 + road / 2, 180 + road / 2, 420 - road / 2, 340 - road / 2], fill=(242, 193, 78))
        im.paste(mp, (mx0, my0)); self.block_c = (mx0 + 340, my0 + 260)
        d.rectangle([mx0, my0, mx1, my1], outline='white', width=5)
        self.leg = [('YOU', (75, 83, 32)), ('HAZARDOUS', (126, 0, 35)), ('UNHEALTHY', (232, 90, 30)), ('MODERATE', (240, 200, 40)), ('GOOD', (76, 175, 80))]
        d.rectangle([720, 840, 1020, 1280], fill='white'); seg = (1260 - 880) / 5; self.leg_y = {}
        d.text((736, 846), 'AIR QUALITY', font=font(self.sans, 22, 700), fill=(90, 90, 90))
        for k, (nm, col) in enumerate(self.leg):
            ya = 880 + k * seg; d.rectangle([940, ya, 995, ya + seg - 5], fill=col)
            f = font(self.sans, 30 if nm != 'YOU' else 40, 800); tw = d.textlength(nm, font=f)
            d.text((920 - tw, ya + seg / 2 - f.size / 2 - 2), nm, font=f, fill=(30, 30, 30)); self.leg_y[nm] = ya + seg / 2
        return im

    def frame(self, t, f):
        im = self.bg.copy().convert('RGBA'); t0 = self.shot['t0']; bt = self.w['banner_t']
        lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        g = min(1.0, (t - t0) / 2.0); g = 1 - (1 - g) ** 2
        if t >= bt: g = 1 + 0.35 * min(1, (t - bt) / 0.4)
        R = 60 + 170 * g; cx, cy = self.block_c
        for k, (dx, dy, rr) in enumerate([(0, 0, 1), (-0.6, -0.2, 0.7), (0.6, -0.15, 0.75), (-0.3, 0.45, 0.65), (0.35, 0.45, 0.7), (0, -0.55, 0.6)]):
            r = R * rr * (1 + 0.05 * math.sin(4 * t + k)); x, y = cx + dx * R, cy + dy * R
            d.ellipse([x - r, y - r, x + r, y + r], fill=(110, 190, 50, 125))
        im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(6)))
        dd = ImageDraw.Draw(im); dd.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(220, 30, 40), outline='white', width=5)
        lab = self.w['map_label']; f2 = font(self.sans, 36, 800); tw = dd.textlength(lab, font=f2)
        dd.rounded_rectangle([cx - tw / 2 - 14, cy + 32, cx + tw / 2 + 14, cy + 82], 10, fill=(20, 20, 20, 230)); dd.text((cx - tw / 2, cy + 38), lab, font=f2, fill='white')
        ya, yb = self.leg_y['MODERATE'], self.leg_y['HAZARDOUS']
        py = ya + (yb - ya) * max(0, min(1, (t - t0) / (bt - t0 - 0.3))) if t < bt else self.leg_y['YOU']
        dd.polygon([(1000, py), (1034, py - 20), (1034, py + 20)], fill=(20, 20, 20))
        fp = os.path.join(self.dir, f'f_{f:05d}.png')
        if os.path.exists(fp): im.alpha_composite(Image.open(fp).convert('RGBA').resize((520, 700), Image.LANCZOS), (500, 1220))
        if t >= bt:
            k = min(1.0, (t - bt) / 0.18); x = int(-W0 * (1 - k) ** 2)
            ban = Image.new('RGBA', (W0, 280), (0, 0, 0, 0)); bd = ImageDraw.Draw(ban)
            bd.rectangle([0, 0, W0, 14], fill=(232, 197, 71)); bd.rectangle([0, 14, W0, 210], fill=(46, 125, 50))
            txt = self.w['banner']; sz = 124
            while bd.textlength(txt, font=font(self.sans, sz, 900)) > 1000: sz -= 2
            f3 = font(self.sans, sz, 900); tw = bd.textlength(txt, font=f3); bd.text(((W0 - tw) / 2, 112 - sz * 0.62), txt, font=f3, fill='white')
            bd.rectangle([0, 210, W0, 266], fill=(15, 15, 15)); bd.text((40, 218), 'ADVISORY: HOLD YOUR BREATH  •  STAY INDOORS', font=font(self.sans, 32, 700), fill=(232, 197, 71))
            im.alpha_composite(ban, (x, 1560))
        return im

def endcard(plan, last, t, t0):
    bg = last.filter(ImageFilter.GaussianBlur(14)).convert('RGBA')
    bg.alpha_composite(Image.new('RGBA', bg.size, (8, 8, 12, 200)))
    a = min(1.0, (t - t0) / 0.4)
    E = plan['endcard']; F = plan['fonts']
    def draw(d, col):
        f1 = font(F['serif'], 104, 600); f2 = font(F['serif_italic'], 58, 400); f3 = font(F['ui'], 30, 700)
        for txt, f, y in ((E['title'], f1, 780), (E['line'], f2, 930)):
            w = d.textlength(txt, font=f); d.text(((W0 - w) / 2, y), txt, font=f, fill=col)
        tx = 'COMMENT BELOW'; w = d.textlength(tx, font=f3) + 6 * len(tx)
        spaced(d, ((W0 - w) / 2, 1060), tx, f3, (col[0], col[1], col[2], int(col[3] * 0.8)), 6)
    txt = shadowed(draw, blur=6, alpha=160)
    if a < 1: txt = Image.blend(Image.new('RGBA', txt.size, (0, 0, 0, 0)), txt, a)
    bg.alpha_composite(txt); return bg

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('plan'); ap.add_argument('frames'); ap.add_argument('audio'); ap.add_argument('out')
    ap.add_argument('--from', dest='t_from', type=float, default=0.0); ap.add_argument('--until', type=float, default=None)
    ap.add_argument('--scale', type=float, default=1.0)
    a = ap.parse_args(); plan = json.load(open(a.plan)); fps = plan['fps']
    t1 = min(a.until or plan['duration'], plan['duration']); f0, f1 = round(a.t_from * fps), round(t1 * fps)
    W, H = int(W0 * a.scale) // 2 * 2, int(H0 * a.scale) // 2 * 2
    ov = Overlay(plan)
    wshot = next((s for s in plan['shots'] if s.get('kind') == 'weather'), None)
    wx = None
    vtmp = a.out.replace('.mp4', '_v.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', vtmp], stdin=subprocess.PIPE)
    last = Image.new('RGB', (W0, H0)); missing = 0
    for f in range(f0, f1):
        t = f / fps
        shot = next((s for s in plan['shots'] if s['t0'] <= t < s['t1'] and not s.get('inset')), None)
        kind = shot.get('kind') if shot else 'black'
        if kind == 'weather': im = wx.frame(t, f)
        elif kind == 'endcard': im = endcard(plan, last, t, shot['t0'])
        elif kind == 'black' or shot is None: im = Image.new('RGBA', (W0, H0), (0, 0, 0, 255))
        else:
            fp = os.path.join(a.frames, shot['id'], f'f_{f:05d}.jpg')
            if os.path.exists(fp):
                b = Image.open(fp).convert('RGB')
                if b.size != (W0, H0): b = b.resize((W0, H0), Image.LANCZOS)
                last = b; im = b.convert('RGBA')
            else:
                im = last.convert('RGBA'); missing += 1
        if kind != 'endcard': im = ov.apply(im, t)
        im = im.convert('RGB')
        if (W, H) != (W0, H0): im = im.resize((W, H), Image.LANCZOS)
        ff.stdin.write(im.tobytes())
    ff.stdin.close(); ff.wait()
    dur = (f1 - f0) / fps
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', vtmp, '-ss', f'{a.t_from:.3f}', '-t', f'{dur:.3f}', '-i', os.path.join(a.audio, 'mix_raw.wav'),
                    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', 'loudnorm=I=-14:TP=-1.0:LRA=11,aresample=48000', '-c:a', 'aac', '-b:a', '192k',
                    '-t', f'{dur:.3f}', '-movflags', '+faststart', a.out], check=True)
    os.remove(vtmp)
    print(f'wrote {a.out} frames={f1 - f0} missing={missing}')

if __name__ == '__main__':
    main()
