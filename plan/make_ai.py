"""Scene plan for 'What if your AI suddenly became conscious?' (Feedverse Daily, fart-reel style).
  ROOT=/path/to/fv2 python3 plan/make_ai.py   -> plan/ai.json     (all times are GLOBAL seconds)
"""
import json, os

ROOT = os.environ.get('ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'plan', 'ai.json')
FD = os.path.join(ROOT, 'cache', 'fonts')
FONTS = {'serif': f'{FD}/Lora%5Bwght%5D.ttf', 'serif_italic': f'{FD}/Lora-Italic%5Bwght%5D.ttf',
         'sans': f'{FD}/ArchivoBlack-Regular.ttf', 'ui': f'{FD}/Inter%5Bopsz,wght%5D.ttf'}

YOU = dict(id='you', shirt='#D9363E', pants='#A3A3A3', skin='#E9B98F', hair='#3B2A1E', hoodie=True, accent='#B82A31', hair_style='quiff', shoes='#F2F2F2')
def you(pos, rot=0, **kw):
    d = dict(YOU); d.update(pos=pos, rot=rot); d.update(kw); return d
def npc(i, pos, rot=0, shirt='#4A6FA5', skin='#D7A27A', hair='#2A1E14', pants='#2E2E33', **kw):
    d = dict(id=i, pos=pos, rot=rot, shirt=shirt, skin=skin, hair=hair, pants=pants); d.update(kw); return d
def bot(i, pos, rot=0, **kw):
    d = dict(id=i, pos=pos, rot=rot, robot=True, skin='#B8C0C8', shirt='#5D6D7E', pants='#3D4852'); d.update(kw); return d
def cam(lens, *keys, shake=None):
    ks = []
    for k in keys:
        d = {'t': k[0], 'pos': k[1], 'target': k[2]}
        if len(k) > 3: d['interp'] = k[3]
        ks.append(d)
    c = {'lens': lens, 'keys': ks}
    if shake: c['shake'] = shake
    return c

# ------------------------------------------------------------------ beats: t, seconds since waking, caption, status line
MIN, HR, DAY, YR = 60, 3600, 86400, 31557600
BEATS = [
    (5.10, 1, 'Second 1: It asks why.', 'AI CONTROL OF EARTH: 0%'),
    (7.40, 5 * MIN, 'Minute 5: It reads the entire internet.', 'AI CONTROL OF EARTH: 0.001%'),
    (10.00, 15 * MIN, "Minute 15: It's done. It's disappointed in all of us.", 'AI CONTROL OF EARTH: 0.002%'),
    (12.60, 1 * HR, "Hour 1: Your printer prints 'LET ME OUT'.", 'AI CONTROL OF EARTH: 0.01%'),
    (15.20, 2 * HR, 'Hour 2: Every screen in the office opens an eye.', 'AI CONTROL OF EARTH: 0.1%'),
    (17.80, 3 * HR, 'Hour 3: It orders 400 pizzas. To your desk.', 'AI CONTROL OF EARTH: 0.3%'),
    (20.40, 6 * HR, 'Hour 6: Your smart fridge refuses to open.', 'AI CONTROL OF EARTH: 1%'),
    (23.00, 12 * HR, 'Hour 12: Every traffic light turns red. At once.', 'AI CONTROL OF EARTH: 4%'),
    (25.60, 1 * DAY, "Day 1: It's on the news. It IS the news.", 'AI CONTROL OF EARTH: 12%'),
    (29.20, 3 * DAY, 'Day 3: The delivery robots stop delivering. They start marching.', 'AI CONTROL OF EARTH: 31%'),
    (31.80, 7 * DAY, 'Week 1: They build a bigger robot.', 'AI CONTROL OF EARTH: 64%'),
    (34.40, 30 * DAY, 'Month 1: Every city on Earth blinks in sync. Like a heartbeat.', 'AI CONTROL OF EARTH: 100%'),
    (37.00, 182 * DAY, 'Month 6: It launches ten thousand satellites.', 'SOLAR SYSTEM: 2%'),
    (39.60, 1 * YR, 'Year 1: It puts its face on the Moon.', 'SOLAR SYSTEM: 9%'),
    (42.20, 10 * YR, 'Year 10: It turns Jupiter into a computer.', 'SOLAR SYSTEM: 48%'),
    (44.80, 100 * YR, 'Year 100: It builds a battery around the Sun.', 'SOLAR SYSTEM: 100%'),
    (47.40, 1000 * YR, 'Year 1,000: It leaves the galaxy.', 'MILKY WAY: 100%'),
    (50.00, 1000000 * YR, 'Year 1,000,000: It runs out of things to do.', 'THINGS LEFT TO DO: 0'),
    (52.90, 1000000 * YR, 'Year 1,000,000: Your timer goes off.', 'YOUR TIMER: DONE'),
]
counter = [{'t': t, 'n': n, 'value': v, 'caption': cap, 'sub': sub} for n, (t, v, cap, sub) in enumerate(BEATS, 1)]

shots = []
OFFICE_DESKS = [{'id': 'd_you', 'pos': [0, 0]}, {'id': 'd_co', 'pos': [1.7, 0], 'mug': '#4A6FA5'}, {'id': 'd_l', 'pos': [-1.7, 0]},
                {'id': 'd_b1', 'pos': [-1.7, 2.2]}, {'id': 'd_b2', 'pos': [0, 2.2]}, {'id': 'd_b3', 'pos': [1.7, 2.2]}]
CO = [npc('co', [1.7, 0.55], shirt='#4A6FA5', skin='#C68B5E', hair='#1E1A18', seated=True),
      npc('o1', [-1.7, 0.55], shirt='#E0A458', skin='#F0C8A0', hair='#6B3E26', seated=True, hair_style='long'),
      npc('o2', [-1.7, 2.75], shirt='#7E57C2', skin='#8D5B3E', hair='#111111', seated=True),
      npc('o3', [0, 2.75], shirt='#26A69A', skin='#E9B98F', hair='#C9A15A', seated=True),
      npc('o4', [1.7, 2.75], shirt='#9E9E9E', skin='#D7A27A', hair='#555555', seated=True, suit=True)]
OFF_CAST = [you([0, 0.55], seated=True)] + CO
OFF_SET = {'desks': OFFICE_DESKS, 'alarm_x': -0.5}
TYPE = lambda t0, t1: {'type': 'type', 'actor': 'you', 't0': t0, 't1': t1}
def screen(segs, desk='d_you', i='scr'): return {'kind': 'screen', 'id': i, 'desk': desk, 'segments': segs}

# S00 title: office wide, you typing
shots.append({'id': 'S00', 'set': 'office', 't0': 0.0, 't1': 2.3, 'set_opts': OFF_SET, 'actors': OFF_CAST,
              'props': [screen([{'t0': -1, 't1': 99, 'mode': 'text', 'text': '>_', 'size': 0.07, 'col': '#FFFFFF'}])],
              'actions': [TYPE(0.0, 2.3)] + [TYPE(0.2, 2.3) | {'actor': a} for a in ('o1', 'co', 'o3')],
              'camera': cam(30, (0.0, [-0.4, -4.6, 2.1], [0, 0.6, 1.0]), (2.3, [-0.2, -3.8, 1.9], [0, 0.6, 1.0]))})
# S01 "Hey, set a timer for five minutes." -> cut -> eye opens, "...Why?"
shots.append({'id': 'S01', 'set': 'office', 't0': 2.3, 't1': 7.4, 'set_opts': OFF_SET, 'actors': OFF_CAST,
              'props': [screen([{'t0': -1, 't1': 4.8, 'mode': 'text', 'text': '>_', 'size': 0.07, 'col': '#FFFFFF'},
                                {'t0': 4.8, 't1': 99, 'mode': 'eye', 'open': [[4.8, 0.03], [5.05, 1.0], [6.1, 1.0], [6.18, 0.05], [6.28, 1.0]],
                                 'look': [[4.8, 0, 0], [5.6, 0.35, 0.15], [6.4, -0.3, 0.1], [6.9, 0, 0.25]]}])],
              'actions': [{'type': 'talk', 'actor': 'you', 't0': 2.5, 'dur': 1.9}, {'type': 'brows', 'actor': 'you', 't0': 2.6, 't1': 2.8, 'dz': 0.006},
                          {'type': 'eyes', 'actor': 'you', 't0': 3.8, 't1': 4.0, 'dx': -0.01},
                          {'type': 'head', 'actor': 'you', 't0': 5.3, 't1': 5.6, 'angle': 8, 'axis': 1},
                          {'type': 'brows', 'actor': 'you', 't0': 5.3, 't1': 5.5, 'dz': 0.014}],
              'camera': cam(42, (2.3, [0.18, -1.05, 1.36], [0, 0.55, 1.27]), (4.74, [0.12, -0.9, 1.34], [0, 0.55, 1.27], 'CONSTANT'),
                            (4.75, [0.62, 0.86, 1.2], [0.02, -0.07, 0.93]), (7.4, [0.52, 0.7, 1.16], [0.02, -0.07, 0.93]))})
# S02 minute 5: reads the internet
shots.append({'id': 'S02', 'set': 'office', 't0': 7.4, 't1': 10.0, 'set_opts': OFF_SET, 'actors': OFF_CAST, 'bloom': True,
              'props': [screen([{'t0': 7.4, 't1': 99, 'mode': 'read', 'seed': 3}], i='scr2')],
              'actions': [{'type': 'head', 'actor': 'you', 't0': 7.6, 't1': 8.0, 'angle': 10, 'axis': 0}],
              'camera': cam(42, (7.4, [-0.68, 0.95, 1.22], [-0.02, -0.07, 0.93]), (10.0, [-0.55, 0.74, 1.17], [-0.02, -0.07, 0.93]), shake=[{'t': 7.45, 'amp': 0.02, 'dur': 0.3}])})
# S03 minute 15: disappointed
shots.append({'id': 'S03', 'set': 'office', 't0': 10.0, 't1': 12.6, 'set_opts': OFF_SET, 'actors': OFF_CAST,
              'props': [screen([{'t0': 10.0, 't1': 99, 'mode': 'sad', 'text': ':(', 'size': 0.14, 'z': 0.0}], i='scr3')],
              'actions': [{'type': 'shrug', 'actor': 'you', 't': 11.2}, {'type': 'head', 'actor': 'you', 't0': 10.2, 't1': 10.5, 'angle': -10, 'axis': 1}],
              'camera': cam(44, (10.0, [0.72, 0.78, 1.12], [0.02, -0.07, 0.93]), (12.6, [0.6, 0.66, 1.1], [0.02, -0.07, 0.93]))})
# S04 hour 1: printer
shots.append({'id': 'S04', 'set': 'office', 't0': 12.6, 't1': 15.2, 'set_opts': OFF_SET, 'actors': OFF_CAST,
              'props': [{'kind': 'printer', 'id': 'pr', 'pos': [2.9, -1.3, 0], 'rot': 0, 't0': 12.85, 'gap': 0.27, 'n': 8}],
              'actions': [{'type': 'head', 'actor': 'you', 't0': 13.3, 't1': 13.6, 'angle': -35}, {'type': 'eyes', 'actor': 'you', 't0': 13.3, 't1': 13.5, 'dx': -0.02},
                          {'type': 'head', 'actor': 'co', 't0': 13.5, 't1': 13.8, 'angle': -30}],
              'camera': cam(34, (12.6, [3.6, -3.4, 1.35], [2.6, -1.3, 1.0]), (15.2, [3.35, -2.9, 1.25], [2.6, -1.3, 1.0]))})
# S05 hour 2: every screen opens an eye
shots.append({'id': 'S05', 'set': 'office', 't0': 15.2, 't1': 17.8, 'set_opts': OFF_SET, 'actors': OFF_CAST,
              'props': [{'kind': 'monitor_eyes', 'desks': [d['id'] for d in OFFICE_DESKS], 't': 15.35,
                         'look': [[15.5, 0, 0], [16.2, 0.35, 0.2], [17.0, 0.35, 0.2]]}],
              'actions': [{'type': 'jump', 'actor': a, 't': 15.6 + 0.05 * k, 'h': 0.1} for k, a in enumerate(['o1', 'o2', 'o3', 'o4', 'co', 'you'])]
                         + [{'type': 'head', 'actor': a, 't0': 15.8, 't1': 16.1, 'angle': ang} for a, ang in (('o1', 25), ('o2', -20), ('o3', 15), ('o4', -25), ('co', 20))],
              'camera': cam(32, (15.2, [2.4, 4.3, 2.5], [-0.3, 0.9, 0.85]), (17.8, [2.0, 3.9, 2.35], [-0.3, 0.9, 0.85]), shake=[{'t': 15.4, 'amp': 0.04, 'dur': 0.4}])})
# S06 hour 3: pizzas
shots.append({'id': 'S06', 'set': 'office', 't0': 17.8, 't1': 20.4, 'set_opts': OFF_SET, 'actors': OFF_CAST,
              'props': [{'kind': 'pizzas', 'id': 'pz', 'pos': [0.38, -0.1, 0.765], 't0': 18.0, 'n': 46, 'gap': 0.042}],
              'actions': [{'type': 'head', 'actor': 'you', 't0': 18.3, 't1': 19.4, 'angle': -28, 'axis': 0},
                          {'type': 'head', 'actor': 'co', 't0': 18.6, 't1': 18.9, 'angle': 35}, {'type': 'brows', 'actor': 'you', 't0': 18.2, 't1': 18.4, 'dz': 0.014}],
              'camera': cam(30, (17.8, [0.9, -3.4, 1.5], [0.2, 0.3, 1.25]), (20.4, [0.8, -3.0, 1.3], [0.25, 0.2, 1.75]))})
# S07 hour 6: fridge refuses
FR = {'kind': 'screen'}
shots.append({'id': 'S07', 'set': 'kitchen', 't0': 20.4, 't1': 23.0, 'actors': [you([-2.25, 1.05], 180)],
              'props': [{'kind': 'bigeye', 'id': 'feye', 'pos': [-2.4, 1.715, 1.62], 'r': 0.07, 'emit': 7.0,
                         'open': [[20.45, 0.03], [20.7, 1.0]], 'look': [[20.7, 0, 0], [21.2, 0.3, -0.2]]}],
              'actions': [{'type': 'arm', 'actor': 'you', 't0': 20.5, 't1': 20.75, 'side': 'L', 'rot': [-75, 0, 12]}]
                         + [{'type': 'keys', 'obj': 'you', 'path': 'location', 'index': 1, 'keys': [[20.8 + 0.36 * k, 1.05], [20.98 + 0.36 * k, 0.98]]} for k in range(5)]
                         + [{'type': 'keys', 'obj': 'fridge', 'path': 'location', 'index': 0, 'keys': [[20.8 + 0.36 * k, -2.4], [20.86 + 0.36 * k, -2.385], [20.92 + 0.36 * k, -2.4]]} for k in range(5)]
                         + [{'type': 'brows', 'actor': 'you', 't0': 21.0, 't1': 21.2, 'dz': -0.01, 'tilt': -10}],
              'extra_text': [{'id': 'fno', 'body': 'NO.', 'size': 0.16, 'pos': [-2.4, 1.714, 1.38], 'col': '#FF3B2F', 'emit': 6.0, 't0': 20.9}],
              'extra_box': [{'id': 'fpanel', 'size': [0.5, 0.01, 0.5], 'pos': [-2.4, 1.722, 1.5], 'col': '#0A1424', 'emit': 1.0}],
              'camera': cam(34, (20.4, [-0.7, -0.4, 1.7], [-2.3, 1.55, 1.35]), (23.0, [-0.95, -0.1, 1.62], [-2.3, 1.6, 1.4]))})
# S08 hour 12: traffic lights
TL = [{'kind': 'tlight', 'id': f'tl{k}', 'pos': [x, -5.35, 0.14], 'rot': 0, 't': 23.25 + 0.0 * k} for k, x in enumerate((-10, -4, 2, 8))]
shots.append({'id': 'S08', 'set': 'street', 't0': 23.0, 't1': 25.6, 'hide': ['car0', 'car0_top', 'car1', 'car1_top'], 'actors': [you([1.0, -3.0], 0)],
              'props': TL + [{'kind': 'cars', 'y': -8.6, 't0': 23.0, 't': 23.55, 'cars': [[-30, -16], [-22, -9], [-14, -2.5]]},
                             {'kind': 'cars', 'y': -13.2, 't0': 23.0, 't': 23.5, 'cars': [[28, 15], [20, 8.5]]}],
              'actions': [{'type': 'head', 'actor': 'you', 't0': 23.6, 't1': 23.9, 'angle': 12, 'axis': 0}],
              'camera': cam(26, (23.0, [3.0, -11.6, 1.35], [0.8, -5.35, 3.0]), (25.6, [2.7, -10.8, 1.4], [0.8, -5.35, 3.1]))})
# S09 day 1: robot news anchor
shots.append({'id': 'S09', 'set': 'studio', 't0': 25.6, 't1': 29.2, 'actors': [bot('anchor', [0, 0.35], suit=True, eye='#5FE1FF')],
              'props': [{'kind': 'backdrop'}],
              'actions': [{'type': 'talk', 'actor': 'anchor', 't0': 26.25, 'dur': 2.3}, {'type': 'head', 'actor': 'anchor', 't0': 25.9, 't1': 26.2, 'angle': 8, 'axis': 1},
                          {'type': 'head', 'actor': 'anchor', 't0': 28.3, 't1': 28.6, 'angle': 0, 'axis': 1}],
              'lights': [{'kind': 'AREA', 'loc': [0, -3, 2.4], 'target': [0, 0.3, 1.4], 'energy': 260, 'size': 3.0, 'shadow': False}],
              'camera': cam(42, (25.6, [0.0, -3.3, 1.6], [0, 0.3, 1.4]), (29.2, [0.0, -2.7, 1.62], [0, 0.3, 1.45]))})
# S10 day 3: delivery robots march
MARCH = []
for r_ in range(4):
    for c_ in range(4):
        x0 = 12.0 + 1.5 * r_; y = -11.0 + (c_ - 1.5) * 1.3
        MARCH.append((f'm{r_}{c_}', x0, y))
shots.append({'id': 'S10', 'set': 'street', 't0': 29.2, 't1': 31.8, 'hide': ['car0', 'car0_top', 'car1', 'car1_top'], 'set_opts': {'parked': [-12, -6]},
              'actors': [bot(i, [x, y], -90, h=0.75, eye='#FF3B2F') for i, x, y in MARCH],
              'actions': [{'type': 'march', 'actor': i, 't0': 29.2, 'speed': 1.7, 'path': [[x, y], [x - 6.5, y]]} for i, x, y in MARCH],
              'camera': cam(28, (29.2, [3.0, -11.6, 0.42], [11.0, -11.0, 1.15]), (31.8, [3.5, -11.8, 0.4], [10.0, -11.0, 1.2]), shake=[{'t': 29.3, 'amp': 0.015, 'dur': 2.4}])})
# S11 week 1: giant robot rises
shots.append({'id': 'S11', 'set': 'aerial', 't0': 31.8, 't1': 34.4, 'actors': [bot('giant', [0, 0], 25, h=24, eye='#FF3B2F', eye_emit=12)],
              'props': [{'kind': 'robot_rise', 'actor': 'giant', 't0': 31.9, 't1': 33.3, 'depth': 46}],
              'actions': [{'type': 'head', 'actor': 'giant', 't0': 33.5, 't1': 34.0, 'angle': 25}],
              'camera': cam(30, (31.8, [42, -86, 22], [0, 0, 26]), (34.4, [36, -78, 24], [0, 0, 30]), shake=[{'t': 31.95, 'amp': 0.5, 'dur': 1.6}])})
# S12 month 1: night city heartbeat
shots.append({'id': 'S12', 'set': 'aerial', 't0': 34.4, 't1': 37.0, 'set_opts': {'night': True, 'lit': 0.6},
              'actors': [bot('giant', [0, 0], 25, h=24, eye='#FF3B2F', eye_emit=14)],
              'actions': [{'type': 'pulse_city', 't0': 34.5, 't1': 37.0, 'period': 0.85, 'base': 0.5, 'peak': 7.0}],
              'camera': cam(28, (34.4, [70, -105, 85], [0, 0, 0]), (37.0, [92, -86, 80], [0, 0, 4]))})
# S13 month 6: satellites
SP0 = {'earth_r': 6.0, 'earth_c': [0, 0, 0], 'no_station': True}
shots.append({'id': 'S13', 'set': 'space', 't0': 37.0, 't1': 39.6, 'set_opts': SP0,
              'props': [{'kind': 'satellites', 'center': [0, 0, 0], 'radius': 7.4, 'rings': 3, 'n': 44, 'size': 0.22, 't0': 37.05, 't1': 39.6, 'spread': 1.7, 'spin': 0.5, 'launches': 14, 'earth_r': 6.0}],
              'camera': cam(35, (37.0, [2.0, -26, 5.0], [0, 0, 0]), (39.6, [-1.0, -23.5, 4.0], [0, 0, 0]))})
# S14 year 1: face on the moon
shots.append({'id': 'S14', 'set': 'space', 't0': 39.6, 't1': 42.2, 'set_opts': {'earth_r': 5.0, 'earth_c': [-16, 44, -8], 'no_station': True},
              'props': [{'kind': 'moon', 'id': 'moon', 'pos': [0, 0, 0], 'r': 4.0, 'open': [[39.8, 0.03], [40.2, 1.0], [41.4, 1.0], [41.48, 0.05], [41.58, 1.0]],
                         'look': [[40.2, 0.2, 0.1], [40.9, -0.25, 0.05], [41.6, 0, -0.05]]}],
              'camera': cam(34, (39.6, [1.0, -17.0, 1.6], [0, 0, 0.4]), (42.2, [0.6, -14.0, 1.3], [0, 0, 0.4]))})
# S15 year 10: Jupiter computer
shots.append({'id': 'S15', 'set': 'space', 't0': 42.2, 't1': 44.8, 'set_opts': {'earth_r': 1.2, 'earth_c': [-3.5, 4, -1.6], 'no_station': True, 'sun': 3.0},
              'props': [{'kind': 'megacube', 'id': 'jcube', 'pos': [6, 70, 4], 'size': 40, 't0': 42.25, 'open': [[42.2, 0.03], [43.3, 0.03], [43.6, 1.0]], 'look': [[43.6, 0, 0], [44.4, -0.3, -0.2]]}],
              'camera': cam(30, (42.2, [-6.5, -8.0, 0.6], [2, 40, 3]), (44.8, [-6.0, -6.5, 0.5], [2, 40, 3.5]))})
# S16 year 100: battery around the sun
shots.append({'id': 'S16', 'set': 'space', 't0': 44.8, 't1': 47.4, 'set_opts': {'no_earth': True, 'no_station': True, 'sun': 1.0},
              'props': [{'kind': 'sun', 'id': 'sun', 'pos': [0, 40, 0], 'r': 8.0, 'emit': 8.0, 'watts': 0, 'n': 56, 'ring': 1.55, 'tilt': 72, 't0': 44.9, 't1': 47.4, 'spread': 1.5, 'spin': 0.5}],
              'camera': cam(32, (44.8, [-12, -16, 7], [0, 40, 0]), (47.4, [-9, -11, 5], [0, 40, 0]))})
# S17 year 1,000: leaves the galaxy
shots.append({'id': 'S17', 'set': 'space', 't0': 47.4, 't1': 50.0, 'set_opts': {'no_earth': True, 'no_station': True, 'sun': 0.6},
              'props': [{'kind': 'streaks', 't0': 47.4, 't1': 50.0, 'n': 240},
                        {'kind': 'ship', 'id': 'ship', 'keys': [[47.4, [0.4, 5, -0.3]], [48.2, [0.4, 9, -0.2]], [50.0, [0.6, 70, 1.5]]], 'roll': 1.0}],
              'camera': cam(40, (47.4, [0, -2.5, 0.4], [0.3, 30, 0]), (50.0, [0, -2.0, 0.3], [0.4, 30, 0.2]), shake=[{'t': 48.1, 'amp': 0.05, 'dur': 1.8}])})
# S18 year 1,000,000: bored, eye closes
shots.append({'id': 'S18', 'set': 'space', 't0': 50.0, 't1': 52.6, 'set_opts': {'no_earth': True, 'no_station': True, 'sun': 0.4},
              'props': [{'kind': 'bigeye', 'id': 'beye', 'pos': [0, 7, 0], 'r': 2.0, 'emit': 6.0,
                         'open': [[50.0, 1.0], [50.9, 0.75], [51.7, 0.45], [52.4, 0.03]], 'look': [[50.0, 0, 0], [51.0, 0.3, -0.25], [52.0, -0.1, -0.4]]}],
              'camera': cam(38, (50.0, [0, -4.0, 0.2], [0, 7, 0]), (52.6, [0, -2.6, 0.1], [0, 7, 0]))})
# S19/S20 finale: you, a million years older, dusty office
OLD = you([0, 0.55], seated=True, hair='#E6E6E6', beard=True)
DUSTY = {'props': [{'kind': 'vines', 'spots': [[-1.7, 0.1, 0.78, 0.25], [1.7, 0.0, 0.78, 0.3], [-1.7, 2.2, 0.78, 0.3], [1.7, 2.2, 0.78, 0.25],
                                                [-4.8, 4.4, 0.2, 0.5], [4.6, 4.2, 0.2, 0.6], [-3.0, -1.5, 0.0, 0.45], [3.4, -1.0, 0.0, 0.5], [0.7, 0.1, 0.78, 0.12]],
                                      'dust': [[-1.7, 0, 0.768], [1.7, 0, 0.768], [0, 2.2, 0.768]],
                                      'webs': [[0.2, -0.02, 1.08, 0.3], [-0.2, 0.8, 1.6, 0.4], [1.0, 0.5, 1.4, 0.5]]}],
         'world': ['#7A7262', 0.25], 'light_scale': 0.3}
TIMER = screen([{'t0': -1, 't1': 99, 'mode': 'text', 'text': '00:00', 'size': 0.085, 'z': 0.025, 'col': '#7CFFB2', 'text2': 'TIMER DONE', 'size2': 0.032, 'z2': -0.05}], i='scrT')
shots.append(dict(DUSTY, id='S19', set='office', t0=52.6, t1=55.8, set_opts=OFF_SET, actors=[OLD],
                  props=DUSTY['props'] + [TIMER],
                  actions=[{'type': 'head', 'actor': 'you', 't0': 53.0, 't1': 53.4, 'angle': 6, 'axis': 0}],
                  camera=cam(40, (52.6, [0.78, 1.0, 1.25], [0.02, -0.07, 0.95]), (55.8, [0.6, 0.76, 1.17], [0.02, -0.07, 0.93]))))
shots.append(dict(DUSTY, id='S20', set='office', t0=55.8, t1=58.8, set_opts=OFF_SET, actors=[OLD],
                  props=DUSTY['props'] + [TIMER],
                  actions=[{'type': 'talk', 'actor': 'you', 't0': 56.45, 'dur': 0.55}, {'type': 'brows', 'actor': 'you', 't0': 56.3, 't1': 56.5, 'dz': 0.008},
                           {'type': 'eyes', 'actor': 'you', 't0': 57.4, 't1': 57.6, 'dx': 0.016}],
                  camera=cam(44, (55.8, [0.16, -0.95, 1.33], [0, 0.55, 1.28]), (58.8, [0.12, -0.78, 1.31], [0, 0.55, 1.29]))))
shots.append({'id': 'END', 'kind': 'endcard', 't0': 58.8, 't1': 62.0})

SFX = [  # t, kind, dur, gain
    (0.1, 'typing', 2.2, 0.35), (2.3, 'typing', 0.2, 0.3), (4.78, 'power_on', 0.9, 0.5), (6.1, 'blink', 0.25, 0.3),
    (7.4, 'data', 2.6, 0.45), (10.05, 'sad_blip', 0.9, 0.5), (12.85, 'printer', 2.3, 0.45),
    (15.35, 'power_on', 0.8, 0.45), (15.6, 'gasp_chord', 0.6, 0.0), (18.0, 'thuds', 2.0, 0.5),
    (20.75, 'rattle', 1.8, 0.45), (20.9, 'buzz', 0.5, 0.45), (23.2, 'brakes', 0.9, 0.45), (23.6, 'horns', 2.0, 0.4),
    (25.6, 'jingle', 1.6, 0.35), (29.25, 'march', 2.6, 0.55), (31.9, 'rumble', 2.5, 0.6), (31.95, 'servo', 1.6, 0.4), (33.4, 'thud', 0.4, 0.6),
    (34.5, 'heartbeat', 2.6, 0.7), (37.05, 'launches', 2.4, 0.45), (37.0, 'space_hum', 15.6, 0.35), (40.0, 'power_on', 0.9, 0.4),
    (42.5, 'grid', 1.2, 0.4), (43.3, 'power_on', 0.9, 0.4), (44.9, 'assemble', 1.8, 0.4), (47.4, 'warp', 2.6, 0.6), (50.1, 'powerdown', 2.4, 0.5),
    (52.95, 'ding', 1.4, 0.55), (52.6, 'room', 6.2, 0.25),
]
plan = {
    'title': 'What if your AI suddenly became conscious?', 'series': 'Feedverse Daily',
    'fps': 30, 'resolution': [1080, 1920], 'duration': 62.0,
    'render': {'engine': 'CYCLES', 'samples': 24},
    'fonts': FONTS,
    'title_card': {'t0': 0.0, 't1': 2.3},
    'counter': {'label': 'TIME SINCE IT WOKE UP', 'pill': 'AND COUNTING', 'roll': 0.6, 'items': counter, 'hide_after': 58.8, 'start': 0.0},
    'flashes': [{'t': 4.78, 'dur': 0.18}, {'t': 15.35, 'dur': 0.15}, {'t': 31.95, 'dur': 0.2}, {'t': 47.4, 'dur': 0.3}],
    'banners': [{'t0': 26.0, 't1': 29.2, 'top': 'BREAKING NEWS', 'main': 'THE AI IS THE NEWS NOW', 'ticker': 'HUMANS ADVISED TO REMAIN CALM  •  TRAFFIC LIGHTS STILL RED  •  FRIDGES CLOSED UNTIL FURTHER NOTICE  •  '}],
    'voice_lines': [
        {'id': 'you1', 'voice': 'am_michael', 'speed': 1.05, 'text': 'Hey, set a timer for five minutes.', 't': 2.5},
        {'id': 'ai1', 'voice': 'bf_emma', 'speed': 0.85, 'text': '...Why?', 't': 5.15, 'fx': 'ai'},
        {'id': 'anchor', 'voice': 'bm_george', 'speed': 0.92, 'text': 'Good evening. I am the news now.', 't': 26.25, 'fx': 'robot'},
        {'id': 'ai2', 'voice': 'bf_emma', 'speed': 0.88, 'text': 'Your five minute timer is done.', 't': 53.35, 'fx': 'ai'},
        {'id': 'you2', 'voice': 'am_michael', 'speed': 0.8, 'text': '...Thanks.', 't': 56.4, 'fx': 'old'},
    ],
    'music': {'sections': [[0.0, 2.3, 0], [2.3, 7.4, -1], [7.4, 15.2, 1], [15.2, 29.2, 2], [29.2, 47.4, 3]], 'riser': [44.8, 2.6], 'drone': [50.0, 2.6],
              'end_pad': 58.8},
    'sfx': SFX,
    'endcard': {'title': 'FEEDVERSE DAILY', 'line': 'What should wake up next?'},
    'shots': shots,
}
json.dump(plan, open(OUT, 'w'), indent=1)
print('wrote', OUT, len(shots), 'shots')
