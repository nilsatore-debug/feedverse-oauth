"""Feedverse Daily v2 shot builder (Blender 4.x, EEVEE). One shot per call; all times are GLOBAL seconds.

  xvfb-run -a blender -b --python scripts/shot_v2.py -- --plan plan/v2.json --shot S01 --out shots/v2/S01 [--fps 60] [--frames a-b] [--res 1080x1920]
"""
import argparse, json, math, os, random, sys, time
import bpy, bmesh
from mathutils import Vector, Euler

FPS = 30
SCENE = None
FONTS = {}
_M = {}; _MESH = {}; OBJ = {}

def srgb2lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def lin(h):
    h = h.lstrip('#'); return tuple(srgb2lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
def F(t): return t * FPS

def coll(name='set'):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name); SCENE.collection.children.link(c)
    return c

def mat(hexcol, rough=0.7, emit=0.0, metal=0.0, unique=None):
    key = (hexcol, rough, emit, metal, unique)
    if key in _M: return _M[key]
    m = bpy.data.materials.new(unique or f'm_{hexcol}')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*lin(hexcol), 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if 'Specular IOR Level' in b.inputs: b.inputs['Specular IOR Level'].default_value = 0.25
    if emit:
        b.inputs['Emission Color'].default_value = (*lin(hexcol), 1)
        b.inputs['Emission Strength'].default_value = emit
    _M[key] = m
    return m

def mat_alpha(hexcol, alpha, emit=0.3, name='m_alpha'):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; n = nt.nodes; l = nt.links
    b = n['Principled BSDF']; out = n['Material Output']
    b.inputs['Base Color'].default_value = (*lin(hexcol), 1); b.inputs['Roughness'].default_value = 0.9
    b.inputs['Emission Color'].default_value = (*lin(hexcol), 1); b.inputs['Emission Strength'].default_value = emit
    tr = n.new('ShaderNodeBsdfTransparent'); mix = n.new('ShaderNodeMixShader'); mix.name = 'ALPHA'
    mix.inputs['Fac'].default_value = alpha
    l.new(tr.outputs[0], mix.inputs[1]); l.new(b.outputs[0], mix.inputs[2]); l.new(mix.outputs[0], out.inputs['Surface'])
    for k_, v_ in (('blend_method', 'BLEND'), ('surface_render_method', 'BLENDED'), ('shadow_method', 'NONE')):
        try: setattr(m, k_, v_)
        except Exception: pass
    try: m.show_transparent_back = False
    except Exception: pass
    return m

def mat_checker(c1, c2, scale=1.0):
    m = bpy.data.materials.new('m_checker'); m.use_nodes = True
    nt = m.node_tree; n = nt.nodes; l = nt.links
    b = n['Principled BSDF']; b.inputs['Roughness'].default_value = 0.5
    geo = n.new('ShaderNodeNewGeometry'); mp = n.new('ShaderNodeMapping'); mp.inputs['Location'].default_value = (0.13, 0.13, 0.37)
    ck = n.new('ShaderNodeTexChecker'); ck.inputs['Scale'].default_value = scale
    ck.inputs['Color1'].default_value = (*lin(c1), 1); ck.inputs['Color2'].default_value = (*lin(c2), 1)
    l.new(geo.outputs['Position'], mp.inputs['Vector']); l.new(mp.outputs[0], ck.inputs['Vector']); l.new(ck.outputs['Color'], b.inputs['Base Color'])
    return m

_BM = {}
def mat_building(wall, win='#2E3F55', roof='#5E5E5E', lit=0.0):
    kk = (wall, win, roof, lit)
    if kk in _BM: return _BM[kk]
    m = bpy.data.materials.new('m_bldg'); m.use_nodes = True; _BM[kk] = m
    nt = m.node_tree; n = nt.nodes; l = nt.links
    b = n['Principled BSDF']; b.inputs['Roughness'].default_value = 0.8
    geo = n.new('ShaderNodeNewGeometry')
    sp = n.new('ShaderNodeSeparateXYZ'); l.new(geo.outputs['Position'], sp.inputs[0])
    sn = n.new('ShaderNodeSeparateXYZ'); l.new(geo.outputs['Normal'], sn.inputs[0])
    va = n.new('ShaderNodeCombineXYZ'); l.new(sp.outputs['X'], va.inputs['X']); l.new(sp.outputs['Z'], va.inputs['Y'])
    vb = n.new('ShaderNodeCombineXYZ'); l.new(sp.outputs['Y'], vb.inputs['X']); l.new(sp.outputs['Z'], vb.inputs['Y'])
    ax = n.new('ShaderNodeMath'); ax.operation = 'ABSOLUTE'; l.new(sn.outputs['X'], ax.inputs[0])
    mv = n.new('ShaderNodeMix'); mv.data_type = 'VECTOR'
    l.new(ax.outputs[0], mv.inputs['Factor']); l.new(va.outputs[0], mv.inputs[4]); l.new(vb.outputs[0], mv.inputs[5])
    br = n.new('ShaderNodeTexBrick'); br.offset = 0.0
    br.inputs['Scale'].default_value = 0.3; br.inputs['Mortar Size'].default_value = 0.3
    br.inputs['Brick Width'].default_value = 1.0; br.inputs['Row Height'].default_value = 1.0
    br.inputs['Color1'].default_value = (*lin(win), 1); br.inputs['Color2'].default_value = (*lin(win), 1)
    br.inputs['Mortar'].default_value = (*lin(wall), 1)
    l.new(mv.outputs[1], br.inputs['Vector'])
    az = n.new('ShaderNodeMath'); az.operation = 'ABSOLUTE'; l.new(sn.outputs['Z'], az.inputs[0])
    mc = n.new('ShaderNodeMix'); mc.data_type = 'RGBA'
    l.new(az.outputs[0], mc.inputs['Factor']); l.new(br.outputs['Color'], mc.inputs[6]); mc.inputs[7].default_value = (*lin(roof), 1)
    l.new(mc.outputs[2], b.inputs['Base Color'])
    if lit:
        inv = n.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; l.new(br.outputs['Fac'], inv.inputs[1])
        side = n.new('ShaderNodeMath'); side.operation = 'SUBTRACT'; side.inputs[0].default_value = 1.0; l.new(az.outputs[0], side.inputs[1])
        mul = n.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; l.new(inv.outputs[0], mul.inputs[0]); l.new(side.outputs[0], mul.inputs[1])
        val = n.new('ShaderNodeValue'); val.name = 'LITV'; val.outputs[0].default_value = lit
        mul2 = n.new('ShaderNodeMath'); mul2.operation = 'MULTIPLY'; l.new(mul.outputs[0], mul2.inputs[0]); l.new(val.outputs[0], mul2.inputs[1])
        b.inputs['Emission Color'].default_value = (*lin(LIT_COL[0]), 1); l.new(mul2.outputs[0], b.inputs['Emission Strength'])
        BLDG_LIT.append(m)
    return m
LIT_COL = ['#FFD27A']

def _mesh(kind):
    if kind in _MESH: return _MESH[kind]
    me = bpy.data.meshes.new(kind); bm = bmesh.new()
    if kind == 'cube': bmesh.ops.create_cube(bm, size=1.0)
    elif kind == 'ico': bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    elif kind == 'ico3': bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    elif kind == 'cyl': bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=10, radius1=1.0, radius2=1.0, depth=1.0)
    bm.to_mesh(me); bm.free(); me.materials.append(None)
    _MESH[kind] = me
    return me

def obj(name, kind, size, loc, m=None, parent=None, rot=(0, 0, 0), c='set'):
    o = bpy.data.objects.new(name, _mesh(kind)); coll(c).objects.link(o)
    o.scale = size; o.location = loc; o.rotation_euler = rot
    if parent: o.parent = parent
    if m:
        o.material_slots[0].link = 'OBJECT'; o.material_slots[0].material = m
    OBJ[name] = o
    return o

def box(name, size, loc, m=None, parent=None, rot=(0, 0, 0), c='set'):
    return obj(name, 'cube', size, loc, m, parent, rot, c)

def empty(name, loc=(0, 0, 0), parent=None, rot=(0, 0, 0), c='set'):
    e = bpy.data.objects.new(name, None); coll(c).objects.link(e)
    e.location = loc; e.rotation_euler = rot
    if parent: e.parent = parent
    OBJ[name] = e
    return e

def text(name, body, size, loc, m, font, rot=(math.radians(90), 0, 0), extrude=0.01, c='set'):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size; cu.extrude = extrude
    cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.font = bpy.data.fonts.load(font, check_existing=True)
    o = bpy.data.objects.new(name, cu); coll(c).objects.link(o); o.location = loc; o.rotation_euler = rot
    o.data.materials.append(m); OBJ[name] = o
    return o

def light(name, kind, loc, target, energy, color='#FFFFFF', radius=0.02, spot=60, size=1.0, shadow=True):
    ld = bpy.data.lights.new(name, kind); ld.energy = energy; ld.color = lin(color)
    ld.use_shadow = shadow
    if kind in ('SPOT', 'POINT'): ld.shadow_soft_size = radius
    if kind == 'SPOT': ld.spot_size = math.radians(spot); ld.spot_blend = 0.3
    if kind == 'AREA': ld.size = size
    if kind == 'SUN': ld.angle = math.radians(radius)
    try: ld.use_contact_shadow = True
    except Exception: pass
    o = bpy.data.objects.new(name, ld); coll('set').objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    OBJ[name] = o
    return o

def world(hexcol, strength):
    w = bpy.data.worlds.new('world'); SCENE.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (*lin(hexcol), 1); bg.inputs['Strength'].default_value = strength

def interp(mode): bpy.context.preferences.edit.keyframe_new_interpolation_type = mode

def key(o, path, t, value=None, index=-1, mode='BEZIER'):
    interp(mode)
    if value is not None:
        if index >= 0: getattr(o, path)[index] = value
        else: setattr(o, path, value)
    o.keyframe_insert(data_path=path, frame=F(t), index=index)

# ---------------------------------------------------------------- characters
ACT = {}

def human(a):
    s = a.get('h', 1.0); i = a['id']
    R = a.get('robot', False)
    if R:
        sk = mat(a.get('skin', '#B8C0C8'), 0.3, metal=0.7); sh = mat(a.get('shirt', '#5D6D7E'), 0.35, metal=0.6)
        pa = mat(a.get('pants', '#3D4852'), 0.4, metal=0.5); ha = mat('#2B3138', 0.4)
    else:
        sk, sh, pa, ha = mat(a['skin']), mat(a['shirt']), mat(a.get('pants', '#2E2E33')), mat(a.get('hair', '#2A1E14'))
    dark = mat('#1C1C1C'); white = mat('#F4F4F0', 0.4)
    root = empty(i, (a['pos'][0], a['pos'][1], a.get('z', 0.0)), rot=(0, 0, math.radians(a.get('rot', 0))), c='actors')
    A = {'root': root, 'theta': root.rotation_euler.z, 'eye_x': 0.0, 'head': 0.0, 'kind': 'human', 's': s}
    for side, sx in (('L', -1), ('R', 1)):
        hip = empty(f'{i}_hip{side}', (sx * 0.1 * s, 0, 0.82 * s), root, c='actors')
        box(f'{i}_leg{side}', (0.17 * s, 0.2 * s, 0.78 * s), (0, 0, -0.39 * s), pa, hip, c='actors')
        box(f'{i}_shoe{side}', (0.19 * s, 0.29 * s, 0.08 * s), (0, -0.04 * s, -0.78 * s), mat(a.get('shoes', '#1C1C1C')), hip, c='actors')
        A['hip' + side] = hip
    chest = empty(f'{i}_chest', (0, 0, 0.82 * s), root, c='actors'); A['chest'] = chest
    box(f'{i}_torso', (0.46 * s, 0.26 * s, 0.62 * s), (0, 0, 0.31 * s), sh, chest, c='actors')
    if a.get('hoodie'):
        box(f'{i}_hood', (0.36 * s, 0.1 * s, 0.2 * s), (0, 0.15 * s, 0.56 * s), sh, chest, c='actors')
        box(f'{i}_pocket', (0.26 * s, 0.012, 0.1 * s), (0, -0.134 * s, 0.14 * s), mat(a.get('accent', '#23706B')), chest, c='actors')
        for sx in (-1, 1):
            box(f'{i}_string{sx}', (0.015, 0.012, 0.12 * s), (sx * 0.05 * s, -0.135 * s, 0.48 * s), white, chest, c='actors')
    if a.get('suit'):
        box(f'{i}_collar', (0.2 * s, 0.012, 0.12 * s), (0, -0.134 * s, 0.54 * s), white, chest, c='actors')
        box(f'{i}_tie', (0.07 * s, 0.014, 0.42 * s), (0, -0.138 * s, 0.33 * s), mat(a.get('tie', '#B22234')), chest, c='actors')
    if a.get('astro'):
        box(f'{i}_pack', (0.4 * s, 0.22 * s, 0.55 * s), (0, 0.22 * s, 0.32 * s), mat('#DADADA'), chest, c='actors')
        box(f'{i}_panel', (0.18 * s, 0.012, 0.12 * s), (0, -0.135 * s, 0.4 * s), mat('#3A6EA5', 0.4, 1.0), chest, c='actors')
    for side, sx in (('L', -1), ('R', 1)):
        sho = empty(f'{i}_sho{side}', (sx * 0.3 * s, 0, 0.58 * s), chest, c='actors')
        box(f'{i}_arm{side}', (0.13 * s, 0.15 * s, 0.56 * s), (0, 0, -0.26 * s), sh, sho, c='actors')
        box(f'{i}_hand{side}', (0.115 * s, 0.13 * s, 0.11 * s), (0, 0, -0.59 * s), sk if not a.get('astro') else mat('#BBBBBB'), sho, c='actors')
        A['sho' + side] = sho
    if a.get('mug'):
        obj(f'{i}_mug', 'cyl', (0.06 * s, 0.06 * s, 0.11 * s), (0, -0.08 * s, -0.62 * s), mat(a['mug']), A['shoR'], c='actors')
    head = empty(f'{i}_head', (0, 0, 1.44 * s), root, c='actors'); A['headE'] = head
    box(f'{i}_neck', (0.13 * s, 0.11 * s, 0.07 * s), (0, 0, 0.02 * s), sk, head, c='actors')
    box(f'{i}_skull', (0.32 * s, 0.30 * s, 0.34 * s), (0, 0, 0.21 * s), sk, head, c='actors')
    if not R:
        box(f'{i}_nose', (0.045 * s, 0.045 * s, 0.07 * s), (0, -0.168 * s, 0.19 * s), sk, head, c='actors')
        for sx in (-1, 1): box(f'{i}_ear{sx}', (0.03 * s, 0.07 * s, 0.09 * s), (sx * 0.172 * s, 0.0, 0.2 * s), sk, head, c='actors')
    else:
        for sx in (-1, 1): obj(f'{i}_bolt{sx}', 'cyl', (0.04 * s, 0.04 * s, 0.05 * s), (sx * 0.17 * s, 0.0, 0.2 * s), ha, head, rot=(0, math.radians(90), 0), c='actors')
        obj(f'{i}_ant', 'cyl', (0.012 * s, 0.012 * s, 0.16 * s), (0, 0, 0.46 * s), ha, head, c='actors')
        obj(f'{i}_antb', 'ico', (0.035 * s, 0.035 * s, 0.035 * s), (0, 0, 0.55 * s), mat(a.get('eye', '#FF3B2F'), 0.4, 6.0), head, c='actors')
        box(f'{i}_panel', (0.2 * s, 0.012, 0.16 * s), (0, -0.135 * s, 0.38 * s), mat('#1B2430', 0.4), chest, c='actors')
        for k in range(3): box(f'{i}_pled{k}', (0.03 * s, 0.014, 0.03 * s), ((k - 1) * 0.055 * s, -0.142 * s, 0.38 * s), mat(('#3BFF6F', '#FFC21A', '#5FE1FF')[k], 0.4, 6.0), chest, c='actors')
    if a.get('mask'):
        mk = empty(f'{i}_mask', (0.25 * s, -0.3 * s, -0.75 * s), head, c='actors')
        box(f'{i}_maskface', (0.26 * s, 0.06 * s, 0.2 * s), (0, -0.17 * s, 0.17 * s), mat('#3A3F3A', 0.6), mk, c='actors')
        obj(f'{i}_maskfilter', 'cyl', (0.07 * s, 0.07 * s, 0.08 * s), (0, -0.24 * s, 0.12 * s), mat('#5B6B4E', 0.6), mk, rot=(math.radians(90), 0, 0), c='actors')
        for sx in (-1, 1): obj(f'{i}_masklens{sx}', 'cyl', (0.045 * s, 0.045 * s, 0.02 * s), (sx * 0.075 * s, -0.205 * s, 0.25 * s), mat('#9FD3E8', 0.1), mk, rot=(math.radians(90), 0, 0), c='actors')
    eyes = empty(f'{i}_eyes', (0, 0, 0), head, c='actors'); A['eyes'] = eyes
    brows = empty(f'{i}_brows', (0, 0, 0), head, c='actors'); A['brows'] = brows
    if R:
        ec = mat(a.get('eye', EYE_COL), 0.4, a.get('eye_emit', 8.0))
        box(f'{i}_visor', (0.28 * s, 0.012, 0.09 * s), (0, -0.152 * s, 0.25 * s), mat('#0B1622', 0.3), head, c='actors')
        for sx in (-1, 1):
            box(f'{i}_pupil{sx}', (0.06 * s, 0.012, 0.05 * s), (sx * 0.07 * s, -0.159 * s, 0.25 * s), ec, eyes, c='actors')
            b = box(f'{i}_brow{sx}', (0.09 * s, 0.014, 0.014 * s), (sx * 0.075 * s, -0.154 * s, 0.315 * s), ha, brows, c='actors'); A[f'brow{sx}'] = b
        A['mouth'] = box(f'{i}_mouth', (0.14 * s, 0.012, 0.02 * s), (0, -0.153 * s, 0.1 * s), ec, head, c='actors')
    else:
        for sx in (-1, 1):
            box(f'{i}_white{sx}', (0.088 * s, 0.012, 0.064 * s), (sx * 0.075 * s, -0.152 * s, 0.25 * s), white, head, c='actors')
            box(f'{i}_pupil{sx}', (0.036 * s, 0.012, 0.048 * s), (sx * 0.075 * s, -0.158 * s, 0.245 * s), dark, eyes, c='actors')
            b = box(f'{i}_brow{sx}', (0.09 * s, 0.014, 0.018 * s), (sx * 0.075 * s, -0.154 * s, 0.305 * s), ha, brows, c='actors')
            A[f'brow{sx}'] = b
        A['mouth'] = box(f'{i}_mouth', (0.1 * s, 0.012, 0.02 * s), (0, -0.153 * s, 0.1 * s), mat('#5A2A2A'), head, c='actors')
        if a.get('beard'):
            bm_ = mat(a.get('hair', '#DDDDDD'))
            box(f'{i}_beard', (0.3 * s, 0.05 * s, 0.2 * s), (0, -0.15 * s, 0.03 * s), bm_, head, c='actors')
            box(f'{i}_stache', (0.14 * s, 0.03 * s, 0.03 * s), (0, -0.172 * s, 0.13 * s), bm_, head, c='actors')
    if R: pass
    elif a.get('astro'):
        box(f'{i}_helmet', (0.42 * s, 0.42 * s, 0.44 * s), (0, 0, 0.22 * s), mat_alpha('#CFE8FF', 0.25, 0.1, f'{i}_visor'), head, c='actors')
        box(f'{i}_ring', (0.44 * s, 0.44 * s, 0.05 * s), (0, 0, -0.02 * s), mat('#DADADA'), head, c='actors')
    else:
        box(f'{i}_hairtop', (0.345 * s, 0.32 * s, 0.075 * s), (0, 0.005 * s, 0.37 * s), ha, head, c='actors')
        if a.get('hair_style') == 'long':
            box(f'{i}_hairback', (0.36 * s, 0.09 * s, 0.44 * s), (0, 0.13 * s, 0.15 * s), ha, head, c='actors')
            for sx in (-1, 1):
                box(f'{i}_hairside{sx}', (0.04 * s, 0.26 * s, 0.3 * s), (sx * 0.178 * s, 0.03 * s, 0.22 * s), ha, head, c='actors')
        else:
            box(f'{i}_hairback', (0.345 * s, 0.07 * s, 0.25 * s), (0, 0.13 * s, 0.25 * s), ha, head, c='actors')
            if a.get('hair_style') == 'quiff':
                box(f'{i}_quiff', (0.3 * s, 0.12 * s, 0.07 * s), (0, -0.09 * s, 0.42 * s), ha, head, c='actors')
    if a.get('seated'):
        for side in 'LR':
            A['hip' + side].rotation_euler.x = math.radians(90)
        root.location.z = a.get('z', 0.0) - 0.36 * s
    ACT[i] = A
    return A

def dog(a):
    i = a['id']; s = a.get('h', 1.0)
    fur = mat(a.get('fur', '#C68642')); dark = mat('#1C1C1C'); ear = mat(a.get('ear', '#8B5A2B')); white = mat('#F4F4F0')
    root = empty(i, (a['pos'][0], a['pos'][1], 0), rot=(0, 0, math.radians(a.get('rot', 0))), c='actors')
    body = empty(f'{i}_body', (0, 0, 0.0), root, c='actors')
    box(f'{i}_torso', (0.34 * s, 0.72 * s, 0.3 * s), (0, 0, 0.45 * s), fur, body, c='actors')
    legs = {}
    for nm, x, y in (('FL', -0.11, -0.27), ('FR', 0.11, -0.27), ('BL', -0.11, 0.27), ('BR', 0.11, 0.27)):
        hip = empty(f'{i}_hip{nm}', (x * s, y * s, 0.34 * s), body, c='actors')
        box(f'{i}_leg{nm}', (0.1 * s, 0.1 * s, 0.32 * s), (0, 0, -0.16 * s), fur, hip, c='actors')
        box(f'{i}_paw{nm}', (0.11 * s, 0.13 * s, 0.05 * s), (0, -0.02 * s, -0.32 * s), mat('#F0E0C8'), hip, c='actors')
        legs[nm] = hip
    neck = empty(f'{i}_neck', (0, -0.34 * s, 0.56 * s), body, c='actors')
    box(f'{i}_head', (0.28 * s, 0.28 * s, 0.26 * s), (0, -0.1 * s, 0.1 * s), fur, neck, c='actors')
    box(f'{i}_snout', (0.16 * s, 0.16 * s, 0.12 * s), (0, -0.3 * s, 0.05 * s), mat('#E8C89A'), neck, c='actors')
    box(f'{i}_nose', (0.07 * s, 0.04 * s, 0.05 * s), (0, -0.39 * s, 0.1 * s), dark, neck, c='actors')
    for sx in (-1, 1):
        box(f'{i}_white{sx}', (0.06 * s, 0.012, 0.06 * s), (sx * 0.07 * s, -0.245 * s, 0.17 * s), white, neck, c='actors')
        box(f'{i}_pupil{sx}', (0.03 * s, 0.014, 0.04 * s), (sx * 0.07 * s, -0.252 * s, 0.165 * s), dark, neck, c='actors')
        box(f'{i}_ear{sx}', (0.06 * s, 0.1 * s, 0.18 * s), (sx * 0.16 * s, -0.06 * s, 0.1 * s), ear, neck, c='actors')
    tail = empty(f'{i}_tailE', (0, 0.36 * s, 0.55 * s), body, c='actors')
    box(f'{i}_tail', (0.06 * s, 0.06 * s, 0.25 * s), (0, 0.06 * s, 0.1 * s), fur, tail, rot=(math.radians(-35), 0, 0), c='actors')
    A = {'root': root, 'body': body, 'legs': legs, 'neck': neck, 'tail': tail, 'theta': root.rotation_euler.z, 'kind': 'dog', 's': s}
    if a.get('lying'):
        body.location.z = -0.28 * s
        for nm in ('FL', 'FR'): legs[nm].rotation_euler.x = math.radians(85)
        for nm in ('BL', 'BR'): legs[nm].rotation_euler.x = math.radians(-85)
        neck.rotation_euler.x = math.radians(25)
    ACT[i] = A
    return A

def pigeon(a):
    i = a['id']; s = a.get('h', 1.0)
    g = mat('#8A8F98'); dg = mat('#4A5060'); white = mat('#F4F4F0'); dark = mat('#111111')
    root = empty(i, (a['pos'][0], a['pos'][1], a.get('z', 0)), rot=(0, 0, math.radians(a.get('rot', 0))), c='actors')
    box(f'{i}_body', (0.13 * s, 0.24 * s, 0.14 * s), (0, 0, 0.1 * s), g, root, c='actors')
    box(f'{i}_wing', (0.15 * s, 0.16 * s, 0.06 * s), (0, 0.03 * s, 0.13 * s), dg, root, c='actors')
    box(f'{i}_tail', (0.08 * s, 0.1 * s, 0.03 * s), (0, 0.15 * s, 0.1 * s), dg, root, c='actors')
    box(f'{i}_head', (0.09 * s, 0.09 * s, 0.09 * s), (0, -0.12 * s, 0.21 * s), dg, root, c='actors')
    box(f'{i}_beak', (0.03 * s, 0.05 * s, 0.025 * s), (0, -0.18 * s, 0.2 * s), mat('#E39B2D'), root, c='actors')
    for sx in (-1, 1):
        box(f'{i}_eye{sx}', (0.012, 0.03 * s, 0.03 * s), (sx * 0.046 * s, -0.13 * s, 0.23 * s), white, root, c='actors')
    for sx in (-1, 1):
        box(f'{i}_foot{sx}', (0.02 * s, 0.05 * s, 0.04 * s), (sx * 0.03 * s, -0.01 * s, 0.02 * s), mat('#D46A4E'), root, c='actors')
    ACT[i] = {'root': root, 'kind': 'pigeon', 'theta': root.rotation_euler.z, 's': s}

# ---------------------------------------------------------------- actions
def unwrap(prev, th):
    while th - prev > math.pi: th -= 2 * math.pi
    while th - prev < -math.pi: th += 2 * math.pi
    return th

def act_walk(A, t0, path, speed, stride=0.62, swing=0.48, arm=0.38, bob=0.025):
    r = A['root']; times = [t0]
    for p, q in zip(path, path[1:]): times.append(times[-1] + math.dist(p, q) / speed)
    for k in (0, 1): key(r, 'location', t0, path[0][k], k, 'LINEAR')
    for i, (p, q) in enumerate(zip(path, path[1:])):
        th = unwrap(A['theta'], math.atan2(q[0] - p[0], -(q[1] - p[1])))
        key(r, 'rotation_euler', times[i], A['theta'], 2); key(r, 'rotation_euler', times[i] + 0.12, th, 2); A['theta'] = th
        for k in (0, 1): key(r, 'location', times[i + 1], q[k], k, 'LINEAR')
    t1 = times[-1]; w = 2 * math.pi / stride; t = t0; z0 = r.location.z
    while t <= t1 + 1e-6:
        ph = math.sin(w * (t - t0))
        if A['kind'] == 'dog':
            L = A['legs']
            for nm, sg in (('FL', 1), ('BR', 1), ('FR', -1), ('BL', -1)): key(L[nm], 'rotation_euler', t, sg * 0.5 * ph, 0)
            key(A['tail'], 'rotation_euler', t, 0.5 * math.sin(2 * w * (t - t0)), 1)
        else:
            key(A['hipL'], 'rotation_euler', t, swing * ph, 0); key(A['hipR'], 'rotation_euler', t, -swing * ph, 0)
            key(A['shoL'], 'rotation_euler', t, -arm * ph, 0); key(A['shoR'], 'rotation_euler', t, arm * ph, 0)
            key(r, 'location', t, z0 + bob * abs(math.cos(w * (t - t0))), 2)
        t += 1 / 20
    if A['kind'] == 'dog':
        for nm in A['legs']: key(A['legs'][nm], 'rotation_euler', t1 + 0.1, 0.0, 0)
    else:
        for n in ('hipL', 'hipR', 'shoL', 'shoR'): key(A[n], 'rotation_euler', t1 + 0.1, 0.0, 0)
        key(r, 'location', t1 + 0.1, z0, 2)

def act_clench(A, t):
    r = A['root']; key(r, 'scale', t - 0.02, 1.0, 2); key(r, 'scale', t + 0.06, 0.965, 2); key(r, 'scale', t + 0.32, 1.0, 2)

def act_eyes(A, t0, t1, dx):
    dx = max(-0.024, min(0.024, dx)) * A['s']
    key(A['eyes'], 'location', t0, A['eye_x'], 0); key(A['eyes'], 'location', t1, dx, 0); A['eye_x'] = dx

def act_head(A, t0, t1, angle, axis=2):
    e = A['headE'] if A['kind'] == 'human' else A['neck']
    cur = e.rotation_euler[axis]
    key(e, 'rotation_euler', t0, cur, axis); key(e, 'rotation_euler', t1, math.radians(angle), axis)

def act_brows(A, t0, t1, dz, tilt=0.0):
    key(A['brows'], 'location', t0, A['brows'].location.z, 2); key(A['brows'], 'location', t1, dz * A['s'], 2)
    for sx in (-1, 1):
        b = A[f'brow{sx}']
        key(b, 'rotation_euler', t0, b.rotation_euler.y, 1); key(b, 'rotation_euler', t1, math.radians(tilt) * sx, 1)

def act_mouth(A, t0, t1, sz, sx=1.0):
    m = A['mouth']
    key(m, 'scale', t0, m.scale.z, 2); key(m, 'scale', t1, 0.02 * A['s'] * sz, 2)
    key(m, 'scale', t0, m.scale.x, 0); key(m, 'scale', t1, 0.1 * A['s'] * sx, 0)

def act_arm(A, t0, t1, side, x=0.0, y=0.0, z=0.0):
    e = A['sho' + side]
    for k, v in enumerate((x, y, z)):
        key(e, 'rotation_euler', t0, e.rotation_euler[k], k); key(e, 'rotation_euler', t1, math.radians(v), k)

def act_cover_nose(A, t0, t1=None):
    act_arm(A, t0, t0 + 0.25, 'R', -150, 0, -25)
    act_head(A, t0, t0 + 0.3, 10, 0)
    if t1:
        act_arm(A, t1, t1 + 0.3, 'R', 0, 0, 0); act_head(A, t1, t1 + 0.3, 0, 0)

def act_sip(A, t0, t1):
    act_arm(A, t0, t0 + 0.3, 'R', -125, 0, -20); act_arm(A, t1 - 0.3, t1, 'R', -40, 0, 0)

def act_shrug(A, t):
    for side, z in (('L', 25), ('R', -25)):
        act_arm(A, t, t + 0.18, side, -35, 0, z); act_arm(A, t + 0.6, t + 0.85, side, 0, 0, 0)
    c = A['chest']; key(c, 'location', t, c.location.z, 2); key(c, 'location', t + 0.18, c.location.z + 0.04, 2)
    key(c, 'location', t + 0.6, c.location.z + 0.04, 2); key(c, 'location', t + 0.85, c.location.z, 2)
    act_brows(A, t, t + 0.15, 0.02); act_brows(A, t + 0.6, t + 0.85, 0.0)

def act_turn(A, t0, t1, angle):
    r = A['root']; th = unwrap(A['theta'], math.radians(angle))
    key(r, 'rotation_euler', t0, A['theta'], 2); key(r, 'rotation_euler', t1, th, 2); A['theta'] = th

def act_faint(A, t, fall_to=0.0, dur=0.55, axis=0, sign=1):
    r = A['root']; z0 = r.location.z
    key(r, 'rotation_euler', t, r.rotation_euler[axis], axis)
    key(r, 'rotation_euler', t + dur, r.rotation_euler[axis] + sign * math.radians(95), axis)
    if fall_to is not None and abs(z0 - fall_to) > 0.01:
        n = 8
        for k in range(n + 1):
            u = k / n; key(r, 'location', t + 0.1 + u * dur, z0 + (fall_to - z0) * u * u, 2)
        key(r, 'location', t + 0.1 + dur + 0.08, fall_to + 0.04, 2); key(r, 'location', t + 0.1 + dur + 0.16, fall_to, 2)

def act_jump(A, t, h=0.15):
    r = A['root']; z0 = r.location.z
    key(r, 'location', t, z0, 2); key(r, 'location', t + 0.12, z0 + h, 2); key(r, 'location', t + 0.26, z0, 2)

def act_talk(A, t0, dur, seed=0):
    rnd = random.Random(seed); m = A['mouth']; base = 0.02 * A['s']
    key(m, 'scale', t0 - 0.03, base, 2); t = t0
    while t < t0 + dur - 0.05:
        key(m, 'scale', t + 0.045, base * rnd.uniform(2.2, 3.8), 2); key(m, 'scale', t + 0.1, base * rnd.uniform(1.0, 1.5), 2)
        t += rnd.uniform(0.11, 0.16)
    key(m, 'scale', t0 + dur, base, 2)

def act_keys(ac):
    o = OBJ[ac['obj']]; idx = ac.get('index', -1); path = ac['path']
    for t, v in ac['keys']:
        if isinstance(v, list): v = Vector(v) if path != 'rotation_euler' else Euler([math.radians(x) for x in v])
        elif path == 'rotation_euler' and ac.get('deg', True): v = math.radians(v)
        key(o, path, t, v, idx, ac.get('interp', 'BEZIER'))

def act_color(ac):
    o = OBJ[ac['obj']]
    m = o.material_slots[0].material
    nm = m.copy(); o.material_slots[0].material = nm
    for other in ac.get('also', []):
        OBJ[other].material_slots[0].link = 'OBJECT'; OBJ[other].material_slots[0].material = nm
    inp = nm.node_tree.nodes['Principled BSDF'].inputs['Base Color']
    for t, hexc in ac['keys']:
        interp('BEZIER'); inp.default_value = (*lin(hexc), 1); inp.keyframe_insert('default_value', frame=F(t))

def act_flash(ac):
    o = OBJ[ac['obj']]; ld = OBJ[ac['light']].data if ac.get('light') else None
    m = o.material_slots[0].material.copy(); o.material_slots[0].material = m
    es = m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
    t = ac['t0']; on = True
    interp('CONSTANT')
    es.default_value = 0.0; es.keyframe_insert('default_value', frame=F(t - 0.05))
    if ld: ld.energy = 0; ld.keyframe_insert('energy', frame=F(t - 0.05))
    while t < ac['t1']:
        es.default_value = ac.get('emit', 8.0) if on else 0.3; es.keyframe_insert('default_value', frame=F(t))
        if ld: ld.energy = ac.get('energy', 800) if on else 0; ld.keyframe_insert('energy', frame=F(t))
        t += ac.get('period', 0.3) / 2; on = not on

def act_spin(ac):
    o = OBJ[ac['obj']]; ax = ac.get('axis', 2)
    key(o, 'rotation_euler', ac['t0'], 0.0, ax, 'LINEAR')
    key(o, 'rotation_euler', ac['t1'], 2 * math.pi * ac['rps'] * (ac['t1'] - ac['t0']), ax, 'LINEAR')

def act_hide(ac):
    o = OBJ[ac['obj']]; interp('CONSTANT')
    for t, hidden in ac['keys']:
        o.hide_render = bool(hidden); o.keyframe_insert('hide_render', frame=F(t))

# ---------------------------------------------------------------- clouds
def build_cloud(c):
    rnd = random.Random(c.get('seed', 0)); m = mat_alpha(c.get('color', '#86C232'), 0.0, c.get('emit', 0.35), f"cloud_{c['id']}")
    root = empty(c['id'], tuple(c['keys'][0]['pos']), c='fx'); r = c['radius']
    t_start, t_end = c['keys'][0]['t'], c['keys'][-1]['t']
    for b in range(c['blobs']):
        off = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(c.get('zmin', -0.6), 1))).normalized() * rnd.uniform(0, r)
        sz = r * rnd.uniform(0.5, 0.85) if b else r * 0.8
        o = obj(f"{c['id']}_b{b}", 'ico', (sz, sz, sz), off, m, root, rot=(rnd.uniform(0, 6), rnd.uniform(0, 6), rnd.uniform(0, 6)), c='fx')
        o.visible_shadow = False
        ph = rnd.uniform(0, 6.28); t = t_start
        while t <= t_end + 0.5:
            f = 1 + 0.12 * math.sin(ph + 7 * (t - t_start)); key(o, 'scale', t, (sz * f,) * 3); t += 0.25
        key(o, 'rotation_euler', t_start, o.rotation_euler[2], 2, 'LINEAR')
        key(o, 'rotation_euler', t_end + 0.5, o.rotation_euler[2] + rnd.uniform(-1.5, 1.5), 2, 'LINEAR')
    alpha = m.node_tree.nodes['ALPHA'].inputs['Fac']; dist = 0.0; prev = Vector(c['keys'][0]['pos'])
    for k in c['keys']:
        p = Vector(k['pos']); dist += (p - prev).length; prev = p
        key(root, 'location', k['t'], p); key(root, 'scale', k['t'], (k['scale'],) * 3)
        if c.get('roll'): key(root, 'rotation_euler', k['t'], -dist / max(r, 0.1), 0)
        interp('BEZIER'); alpha.default_value = k['alpha']; alpha.keyframe_insert('default_value', frame=F(k['t']))

# ---------------------------------------------------------------- props
def prop_plant(p):
    i = p['id']; x, y, z = p['pos']; s = p.get('scale', 1.0)
    root = empty(i, (x, y, z))
    obj(f'{i}_pot', 'cyl', (0.11 * s, 0.11 * s, 0.18 * s), (0, 0, 0.09 * s), mat('#B5523B'), root)
    obj(f'{i}_soil', 'cyl', (0.1 * s, 0.1 * s, 0.01), (0, 0, 0.18 * s), mat('#3B2A1E'), root)
    box(f'{i}_stem', (0.025 * s, 0.025 * s, 0.3 * s), (0, 0, 0.33 * s), mat('#3F7D3A'), root)
    leaf = mat('#4CAF50', 0.6, unique=f'{i}_leafmat')
    for k in range(6):
        ang = k * 60
        piv = empty(f'{i}_lp{k}', (0, 0, (0.3 + 0.06 * (k % 3)) * s), root, rot=(math.radians(-40), 0, math.radians(ang)))
        box(f'{i}_leaf{k}', (0.08 * s, 0.2 * s, 0.015 * s), (0, -0.11 * s, 0), leaf, piv)
    box(f'{i}_flower', (0.07 * s, 0.07 * s, 0.07 * s), (0, 0, 0.5 * s), mat('#F2C14E', 0.6, unique=f'{i}_flowermat'), root)

def act_wilt(ac):
    i = ac['obj']; t0, t1 = ac['t0'], ac['t1']
    for k in range(6):
        piv = OBJ[f'{i}_lp{k}']
        key(piv, 'rotation_euler', t0 + 0.05 * k, piv.rotation_euler.x, 0); key(piv, 'rotation_euler', t1 + 0.05 * k, math.radians(75), 0)
    st = OBJ[f'{i}_stem']; key(st, 'rotation_euler', t0, 0.0, 1); key(st, 'rotation_euler', t1, math.radians(35), 1)
    fl = OBJ[f'{i}_flower']
    key(fl, 'location', t0, Vector(fl.location)); key(fl, 'location', t1, Vector((0.12, 0, 0.3)))
    key(fl, 'location', t1 + 0.35, Vector((0.22, -0.05, 0.035 - OBJ[i].location.z * 0 )))
    act_color({'obj': f'{i}_leaf0', 'also': [f'{i}_leaf{k}' for k in range(1, 6)], 'keys': [[t0, '#4CAF50'], [t1, '#7A5A2E']]})
    act_color({'obj': f'{i}_flower', 'keys': [[t0, '#F2C14E'], [t1, '#5B4636']]})

def prop_heli(p):
    i = p['id']; root = empty(i, tuple(p['pos']), rot=(0, 0, math.radians(p.get('rot', 0))))
    body = mat(p.get('color', '#D9432B'), 0.4)
    box(f'{i}_body', (0.9, 1.6, 0.8), (0, 0, 0), body, root)
    box(f'{i}_glass', (0.8, 0.5, 0.5), (0, -0.85, 0.08), mat('#2E4A66', 0.1), root)
    box(f'{i}_boom', (0.18, 1.8, 0.18), (0, 1.6, 0.15), body, root)
    box(f'{i}_fin', (0.06, 0.3, 0.5), (0, 2.45, 0.35), body, root)
    for sx in (-1, 1): box(f'{i}_skid{sx}', (0.06, 1.5, 0.06), (sx * 0.45, 0, -0.62), mat('#333333'), root)
    hub = empty(f'{i}_rotor', (0, 0, 0.5), root)
    box(f'{i}_blade1', (3.6, 0.16, 0.03), (0, 0, 0), mat('#222222'), hub)
    box(f'{i}_blade2', (0.16, 3.6, 0.03), (0, 0, 0), mat('#222222'), hub)
    trot = empty(f'{i}_trotor', (0.08, 2.45, 0.4), root)
    box(f'{i}_tblade', (0.02, 0.6, 0.06), (0, 0, 0), mat('#222222'), trot)

def prop_ufo(p):
    i = p['id']; root = empty(i, tuple(p['pos']))
    obj(f'{i}_disc', 'cyl', (1.6, 1.6, 0.25), (0, 0, 0), mat('#9AA4AE', 0.25, metal=0.6), root)
    obj(f'{i}_rim', 'cyl', (1.75, 1.75, 0.08), (0, 0, -0.05), mat('#5F6B76', 0.3, metal=0.6), root)
    obj(f'{i}_dome', 'ico', (0.7, 0.7, 0.45), (0, 0, 0.2), mat_alpha('#8FF0C8', 0.55, 0.6, f'{i}_domem'), root)
    box(f'{i}_alien', (0.22, 0.2, 0.3), (0, 0, 0.3), mat('#7BD36A'), root)
    for sx in (-1, 1): box(f'{i}_aeye{sx}', (0.07, 0.02, 0.05), (sx * 0.05, -0.105, 0.36), mat('#111111'), root)
    for k in range(8):
        a = k * math.pi / 4; obj(f'{i}_lt{k}', 'ico', (0.09, 0.09, 0.09), (1.55 * math.cos(a), 1.55 * math.sin(a), -0.05), mat('#FFE066', 0.4, 5.0), root)

def prop_plane(p):
    i = p['id']; root = empty(i, tuple(p['pos']), rot=(0, 0, math.radians(p.get('rot', 0))))
    w = mat('#F2F2F2', 0.35); b = mat(p.get('color', '#2F6DB5'), 0.4)
    obj(f'{i}_fus', 'cyl', (0.55, 0.55, 7.0), (0, 0, 0), w, root, rot=(math.radians(90), 0, 0))
    obj(f'{i}_nose', 'ico', (0.55, 0.9, 0.55), (0, -3.5, 0), w, root)
    box(f'{i}_wing', (7.5, 1.4, 0.12), (0, 0.2, -0.2), w, root)
    box(f'{i}_stab', (2.6, 0.7, 0.08), (0, 3.2, 0.1), w, root)
    box(f'{i}_fin', (0.1, 1.0, 1.4), (0, 3.2, 0.8), b, root)
    box(f'{i}_stripe', (1.13, 6.0, 0.12), (0, 0.2, -0.05), b, root)
    for sx in (-1, 1): obj(f'{i}_eng{sx}', 'cyl', (0.3, 0.3, 0.9), (sx * 1.9, 0.0, -0.5), mat('#BBBBBB'), root, rot=(math.radians(90), 0, 0))
    for k in range(10): box(f'{i}_win{k}', (1.12, 0.12, 0.12), (0, -2.6 + k * 0.5, 0.18), mat('#1E2A38'), root)

def prop_traffic(p):
    rnd = random.Random(p.get('seed', 2)); pal = ['#D9432B', '#2F6DB5', '#F2C14E', '#EDEDED', '#3E3E46', '#4CAF50']
    for k in range(p.get('n', 30)):
        lane = rnd.choice(p['lanes']); x0, y0, x1, y1 = lane
        u0 = rnd.uniform(0, 1); sp = rnd.uniform(0.25, 0.4)
        o = empty(f"car_{p['id']}_{k}", (0, 0, 0))
        ang = math.atan2(x1 - x0, -(y1 - y0)); o.rotation_euler.z = ang
        box(f"carb_{p['id']}_{k}", (1.8, 4.0, 1.0), (0, 0, 0.6), mat(rnd.choice(pal), 0.35), o)
        box(f"cart_{p['id']}_{k}", (1.6, 2.0, 0.6), (0, 0.3, 1.35), mat('#2E4A66', 0.2), o)
        for t, u in ((p['t0'], u0), (p['t1'], u0 + sp)):
            key(o, 'location', t, Vector((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, 0)), mode='LINEAR')

def prop_debris(p):
    rnd = random.Random(p.get('seed', 4)); c = Vector(p['pos'])
    m = [mat(h, 0.8) for h in p.get('colors', ['#8A8F98', '#B8B2A7', '#6B6259'])]
    for k in range(p.get('n', 24)):
        sz = rnd.uniform(0.05, 0.18) * p.get('scale', 1.0)
        o = box(f"deb_{p['id']}_{k}", (sz, sz, sz), tuple(c + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * p.get('spread', 2.0)), rnd.choice(m))
        z0 = o.location.z; t0 = p['t0'] + rnd.uniform(0, 0.6); up = rnd.uniform(1.0, 3.5) * p.get('lift', 1.0)
        key(o, 'location', p['t0'] - 0.05, Vector(o.location))
        key(o, 'location', t0, Vector(o.location)); key(o, 'location', p['t1'], Vector((o.location.x, o.location.y, z0 + up)))
        key(o, 'rotation_euler', t0, Euler((0, 0, 0))); key(o, 'rotation_euler', p['t1'], Euler((rnd.uniform(-6, 6), rnd.uniform(-6, 6), rnd.uniform(-6, 6))))

def act_shatter(ac):
    """Glass shards burst from a facade rectangle toward -y with gravity."""
    rnd = random.Random(ac.get('seed', 9)); x0, x1, z0, z1 = ac['rect']; y = ac['y']; t = ac['t']
    g = mat_alpha('#CFE8FF', 0.75, 0.6, 'shard')
    for k in range(ac.get('n', 60)):
        p0 = Vector((rnd.uniform(x0, x1), y, rnd.uniform(z0, z1)))
        v = Vector((rnd.uniform(-2, 2), -rnd.uniform(3, 9), rnd.uniform(0, 4)))
        sz = rnd.uniform(0.06, 0.22)
        o = box(f'shard{k}', (sz, 0.01, sz * rnd.uniform(0.6, 1.4)), tuple(p0), g)
        key(o, 'location', t - 0.05, p0.copy())
        n = 10; dur = ac.get('dur', 1.4)
        for j in range(1, n + 1):
            tt = dur * j / n; pos = p0 + v * tt + Vector((0, 0, -9.8 * tt * tt / 2))
            pos.z = max(pos.z, 0.16); key(o, 'location', t + tt, pos)
        key(o, 'rotation_euler', t, Euler((0, 0, 0))); key(o, 'rotation_euler', t + dur, Euler((rnd.uniform(-9, 9), rnd.uniform(-9, 9), rnd.uniform(-9, 9))))

def prop_patch(p):
    i = p['id']; m = mat_alpha(p.get('color', '#86C232'), 0.0, p.get('emit', 1.0), f'{i}_m')
    o = obj(i, 'ico3', (0.1, 0.1, 0.1), tuple(p['pos']), m, rot=tuple(math.radians(v) for v in p.get('rot', (0, 0, 0)))); o.visible_shadow = False
    a = m.node_tree.nodes['ALPHA'].inputs['Fac']
    for t, sx, sy, sz, al in p['keys']:
        key(o, 'scale', t, (sx, sy, sz)); interp('BEZIER'); a.default_value = al; a.keyframe_insert('default_value', frame=F(t))

def prop_aura(p):
    i = p['id']; m = mat_alpha(p.get('color', '#7CFF4F'), 0.0, 3.0, f'{i}_m')
    o = obj(i, 'ico3', (0.1, 0.1, 0.1), tuple(p['pos']), m); o.visible_shadow = False
    a = m.node_tree.nodes['ALPHA'].inputs['Fac']
    for t, sc, al in p['keys']:
        key(o, 'scale', t, (sc, sc, sc * 1.3)); interp('BEZIER'); a.default_value = al; a.keyframe_insert('default_value', frame=F(t))

def prop_bolts(p):
    """Zig-zag emissive bolts that flicker on/off."""
    rnd = random.Random(p.get('seed', 6)); m = mat('#E8FFB0', 0.5, 12.0); c = Vector(p['pos'])
    for k in range(p.get('n', 6)):
        root = empty(f"bolt{k}", tuple(c)); ang = rnd.uniform(0, 6.28); pt = Vector((0, 0, 0))
        for j in range(5):
            d = Vector((math.cos(ang) * 0.35 + rnd.uniform(-0.2, 0.2), math.sin(ang) * 0.35 + rnd.uniform(-0.2, 0.2), rnd.uniform(0.1, 0.5)))
            mid = pt + d / 2; L = d.length
            seg = box(f"bolt{k}_{j}", (0.03, 0.03, L), tuple(mid), m, root); seg.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); pt = pt + d
        interp('CONSTANT'); t = p['t0'] + rnd.uniform(0, 0.3); vis = False
        root.hide_render = True; root.keyframe_insert('hide_render', frame=F(p['t0'] - 0.05))
        for ch in root.children: ch.hide_render = True; ch.keyframe_insert('hide_render', frame=F(p['t0'] - 0.05))
        while t < p['t1']:
            vis = not vis
            for ch in root.children: ch.hide_render = not vis; ch.keyframe_insert('hide_render', frame=F(t))
            t += rnd.uniform(0.05, 0.18)
        for ch in root.children: ch.hide_render = True; ch.keyframe_insert('hide_render', frame=F(p['t1']))

# ================================================================ AI-reel additions
EYE_COL = '#5FE1FF'

def eye(name, parent, loc, r, face='+y', col=EYE_COL, emit=6.0, pupil=True, open_keys=None, look_keys=None, c='set'):
    """Glowing round eye made of flat discs. face: '+y' or '-y' = direction it looks. open_keys: [[t, 0..1]] lid opening."""
    sg = 1 if face == '+y' else -1
    root = empty(name, loc, parent, rot=(0, 0, 0), c=c)
    rx = math.radians(90)
    obj(f'{name}_rim', 'cyl', (r * 1.12, r * 1.12, 0.004 * r / 0.05), (0, 0, 0), mat('#0B1622', 0.5), root, rot=(rx, 0, 0), c=c)
    obj(f'{name}_iris', 'cyl', (r, r, 0.004 * r / 0.05), (0, sg * 0.002 * r / 0.05, 0), mat(col, 0.4, emit), root, rot=(rx, 0, 0), c=c)
    if pupil:
        pe = empty(f'{name}_pE', (0, sg * 0.004 * r / 0.05, 0), root, c=c)
        obj(f'{name}_pupil', 'cyl', (r * 0.42, r * 0.42, 0.004 * r / 0.05), (0, 0, 0), mat('#061018', 0.5), pe, rot=(rx, 0, 0), c=c)
        obj(f'{name}_glint', 'cyl', (r * 0.12, r * 0.12, 0.004 * r / 0.05), (r * 0.16, sg * 0.002 * r / 0.05, r * 0.16), mat('#FFFFFF', 0.4, 8.0), pe, rot=(rx, 0, 0), c=c)
        for t, dx, dz in (look_keys or []):
            key(pe, 'location', t, Vector((dx * r, sg * 0.004 * r / 0.05, dz * r)))
    if open_keys:
        for t, v in open_keys: key(root, 'scale', t, (1.0, 1.0, max(0.03, v)))
    return root

def screen_root(desk):
    d = OBJ[desk]
    return empty(f'{desk}_scrE', (0, -0.0705, 0.9), d, rot=(math.radians(-12), 0, 0))

def emit_keys(m, keys):
    es = m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
    for t, v in keys:
        interp('CONSTANT' if len(keys) > 1 else 'BEZIER'); es.default_value = v; es.keyframe_insert('default_value', frame=F(t))

def vis_keys(o, keys, recursive=True):
    """keys: [[t, visible]]"""
    obs = [o] + (list(o.children_recursive) if recursive else [])
    interp('CONSTANT')
    for ob in obs:
        for t, v in keys:
            ob.hide_render = not v; ob.keyframe_insert('hide_render', frame=F(t))

def prop_screen(p):
    """Content on a desk laptop screen (faces the person in the chair, +y). modes: eye, read, sad, text, off."""
    root = screen_root(p['desk']); i = p['id']
    bg = mat('#0A1424', 0.5, p.get('bg_emit', 1.2), unique=f'{i}_bgm')
    box(f'{i}_bg', (0.335, 0.002, 0.215), (0, 0.0012, 0), bg, root)
    for seg in p['segments']:
        t0, t1, mode = seg['t0'], seg['t1'], seg['mode']; sid = f"{i}_{mode}_{int(t0 * 100)}"
        grp = empty(sid, (0, 0.0025, 0), root)
        if mode == 'eye':
            eye(f'{sid}_eye', grp, (0, 0, 0.0), 0.06, '+y', open_keys=seg.get('open'), look_keys=seg.get('look'))
        elif mode == 'read':
            rnd = random.Random(seg.get('seed', 1)); mm = [mat('#7CFFB2', 0.5, 5.0), mat(EYE_COL, 0.5, 5.0), mat('#FFFFFF', 0.5, 4.0)]
            for r_ in range(11):
                z = 0.088 - r_ * 0.0175
                b = box(f'{sid}_l{r_}', (0.28, 0.0015, 0.007), (0, 0, z), rnd.choice(mm), grp)
                tt = t0; interp('CONSTANT')
                while tt < t1:
                    w = rnd.uniform(0.05, 0.29); b.scale.x = w; b.location.x = -0.14 + w / 2; b.keyframe_insert('scale', index=0, frame=F(tt)); b.keyframe_insert('location', index=0, frame=F(tt))
                    tt += rnd.uniform(0.04, 0.1)
        elif mode in ('text', 'sad'):
            body = seg.get('text', ':(')
            text(f'{sid}_t', body, seg.get('size', 0.1), (0, 0, seg.get('z', 0.0)), mat(seg.get('col', EYE_COL), 0.5, 5.0), FONTS['sans'],
                 rot=(math.radians(90), 0, math.radians(180)), extrude=0.0005).parent = grp
            if seg.get('text2'):
                text(f'{sid}_t2', seg['text2'], seg.get('size2', 0.03), (0, 0, seg.get('z2', -0.07)), mat('#FFFFFF', 0.5, 3.0), FONTS['sans'],
                     rot=(math.radians(90), 0, math.radians(180)), extrude=0.0005).parent = grp
        vis_keys(grp, [[-1.0, False], [t0, True], [t1, False]])

def prop_monitor_eyes(p):
    """Eyes on every listed desk laptop at once."""
    for k, d in enumerate(p['desks']):
        root = screen_root(d)
        box(f'me{k}_bg', (0.335, 0.002, 0.215), (0, 0.0012, 0), mat('#0A1424', 0.5, 1.2), root)
        e = eye(f'me{k}', root, (0, 0.0025, 0), 0.07, '+y', open_keys=[[p['t'] - 0.05 + 0.04 * k, 0.03], [p['t'] + 0.15 + 0.04 * k, 1.0]], look_keys=p.get('look'))
        vis_keys(e, [[-1, False], [p['t'] - 0.06 + 0.04 * k, True]])

def prop_printer(p):
    i = p['id']; root = empty(i, tuple(p['pos']), rot=(0, 0, math.radians(p.get('rot', 0))))
    box(f'{i}_table', (0.9, 0.6, 0.72), (0, 0, 0.36), mat('#5B6670', 0.5), root)
    box(f'{i}_body', (0.6, 0.45, 0.3), (0, 0, 0.87), mat('#E8E8E8', 0.4), root)
    box(f'{i}_top', (0.5, 0.35, 0.05), (0, 0.04, 1.045), mat('#CFCFCF', 0.4), root)
    box(f'{i}_slot', (0.42, 0.02, 0.03), (0, -0.226, 0.92), mat('#222222'), root)
    led = box(f'{i}_led', (0.04, 0.01, 0.02), (0.22, -0.228, 0.98), mat('#3BFF6F', 0.4, 6.0), root)
    pm = mat('#FAFAF7', 0.8); tm = mat('#111111', 0.6)
    rnd = random.Random(3)
    for k in range(p.get('n', 7)):
        t = p['t0'] + k * p.get('gap', 0.28)
        pg = empty(f'{i}_pg{k}', (0, -0.2, 0.92), root)
        box(f'{i}_paper{k}', (0.3, 0.42, 0.003), (0, -0.21, 0), pm, pg)
        tx = text(f'{i}_ptxt{k}', p.get('text', 'LET ME OUT'), 0.05, (0, -0.21, 0.003), tm, FONTS['sans'], rot=(0, 0, 0), extrude=0.0005); tx.parent = pg
        end = Vector((rnd.uniform(-0.5, 0.5), -0.9 - rnd.uniform(0, 0.7), -0.9 + 0.012 * k))
        key(pg, 'location', t - 0.02, Vector((0, -0.2, 0.92))); key(pg, 'scale', t - 0.02, (1, 0.02, 1)); key(pg, 'scale', t + 0.12, (1, 1, 1))
        key(pg, 'location', t + 0.12, Vector((0, -0.25, 0.92))); key(pg, 'location', t + 0.75, Vector((0, -0.2, 0.92)) + end)
        key(pg, 'rotation_euler', t + 0.12, Euler((0, 0, 0))); key(pg, 'rotation_euler', t + 0.75, Euler((0, 0, rnd.uniform(-1.2, 1.2))))
        vis_keys(pg, [[-1, False], [t - 0.02, True]])

def prop_pizzas(p):
    i = p['id']; x, y, z = p['pos']; rnd = random.Random(5)
    cm = mat('#D9B98A', 0.8); lm = mat('#C0392B', 0.6)
    for k in range(p.get('n', 40)):
        t = p['t0'] + k * p.get('gap', 0.045); h = 0.055
        b = empty(f'{i}_{k}', (x, y, z + h * k + h / 2), rot=(0, 0, math.radians(rnd.uniform(-8, 8))))
        box(f'{i}_{k}_box', (0.42, 0.42, h * 0.95), (0, 0, 0), cm, b)
        box(f'{i}_{k}_logo', (0.14, 0.14, 0.004), (0, 0, h * 0.48), lm, b)
        key(b, 'location', t - 0.01, Vector((x, y, z + h * k + h / 2 + 0.9))); key(b, 'location', t + 0.09, Vector((x, y, z + h * k + h / 2)))
        vis_keys(b, [[-1, False], [t - 0.01, True]])

def prop_tlight(p):
    i = p['id']; root = empty(i, tuple(p['pos']), rot=(0, 0, math.radians(p.get('rot', 0))))
    obj(f'{i}_pole', 'cyl', (0.07, 0.07, 3.0), (0, 0, 1.5), mat('#3A3A3A'), root)
    box(f'{i}_house', (0.32, 0.28, 0.9), (0, 0, 3.3), mat('#202020', 0.5), root)
    t = p['t']
    for k, (col, z) in enumerate((('#FF2A1A', 3.6), ('#FFC21A', 3.3), ('#2AFF6A', 3.0))):
        m = mat(col, 0.4, 0.0, unique=f'{i}_lm{k}')
        obj(f'{i}_lamp{k}', 'cyl', (0.12, 0.12, 0.03), (0, -0.15, z), m, root, rot=(math.radians(90), 0, 0))
        if k == 0: emit_keys(m, [[-1, 0.1], [t, 4.0]])
        elif k == 2: emit_keys(m, [[-1, 3.0], [t, 0.1]])
        else: emit_keys(m, [[-1, 0.1], [t - 0.25, 3.0], [t, 0.1]])

def prop_cars(p):
    """Cars driving in a lane that all brake at t."""
    pal = ['#2F6DB5', '#D9432B', '#F2C14E', '#EDEDED', '#3E3E46']
    for k, (x0, x1) in enumerate(p['cars']):
        o = empty(f"drv{k}", (x0, p['y'], 0), rot=(0, 0, math.radians(90 if x1 > x0 else -90)))
        box(f"drv{k}_b", (1.7, 3.8, 0.8), (0, 0, 0.6), mat(pal[k % 5], 0.35), o)
        box(f"drv{k}_t", (1.5, 2.0, 0.6), (0, 0.2, 1.25), mat('#2E4A66', 0.2), o)
        bl = mat('#FF3B2F', 0.4, 0.5, unique=f'drv{k}_blm')
        box(f"drv{k}_brake", (1.4, 0.05, 0.14), (0, 1.92, 0.72), bl, o)
        emit_keys(bl, [[-1, 0.5], [p['t'], 10.0]])
        key(o, 'location', p['t0'], Vector((x0, p['y'], 0)), mode='LINEAR')
        key(o, 'location', p['t'], Vector((x0 + (x1 - x0) * 0.85, p['y'], 0)))
        key(o, 'location', p['t'] + 0.5, Vector((x1, p['y'], 0)))

def prop_backdrop(p):
    """News studio backdrop."""
    box('bd_wall', (6, 0.1, 3.4), (0, 1.6, 1.7), mat('#0E2A5A', 0.5, 0.6))
    for k in range(7): box(f'bd_strip{k}', (6, 0.02, 0.04), (0, 1.54, 0.4 + 0.42 * k), mat('#2C6BD9', 0.5, 2.0))
    box('bd_screen', (2.6, 0.04, 0.95), (0.0, 1.52, 2.62), mat('#06101E', 0.5, 0.5))
    text('bd_logo', p.get('logo', 'FEEDVERSE 6 NEWS'), 0.11, (0, -0.535, 0.62), mat('#E8C547', 0.5, 2.0), FONTS['sans'])
    box('bd_eyepanel', (0.7, 0.03, 0.7), (-0.72, 1.5, 1.75), mat('#06101E', 0.5, 0.5))
    eye('bd_eye', None, (-0.72, 1.47, 1.75), 0.24, '-y', emit=6.0, look_keys=[[0, 0.3, 0], [27.0, 0.3, 0]])
    box('bd_floor', (8, 6, 0.05), (0, 0, -0.025), mat('#1A1F2B', 0.4))

def prop_robot_rise(p):
    """Animate an actor root rising from below ground."""
    o = OBJ[p['actor']]; z1 = o.location.z
    key(o, 'location', p['t0'], Vector((o.location.x, o.location.y, z1 - p.get('depth', 40))))
    key(o, 'location', p['t1'], Vector((o.location.x, o.location.y, z1)))

def prop_satellites(p):
    rnd = random.Random(p.get('seed', 8)); c = Vector(p.get('center', (0, 0, -7)))
    body = mat('#D8D8D8', 0.35, metal=0.5); pan = mat('#1F3B73', 0.25, 0.6); glow = mat(EYE_COL, 0.4, 8.0)
    for ring in range(p.get('rings', 3)):
        tilt = (math.radians(rnd.uniform(-35, 35)), math.radians(rnd.uniform(-35, 35)), 0)
        rr = empty(f'sring{ring}', tuple(c), rot=tilt)
        R = p['radius'] * (1 + 0.08 * ring); n = p.get('n', 40)
        for k in range(n):
            a = 2 * math.pi * k / n + rnd.uniform(-0.04, 0.04); s = p.get('size', 0.12)
            sat = empty(f's{ring}_{k}', (R * math.cos(a), R * math.sin(a), rnd.uniform(-0.1, 0.1)), rr, rot=(0, 0, a))
            box(f's{ring}_{k}_b', (s, s, s), (0, 0, 0), body, sat)
            box(f's{ring}_{k}_p', (s * 4, s * 0.1, s * 1.2), (0, 0, 0), pan, sat)
            box(f's{ring}_{k}_g', (s * 0.3, s * 0.3, s * 0.3), (0, 0, s * 0.6), glow, sat)
            t = p['t0'] + (ring * n + k) / (p.get('rings', 3) * n) * p.get('spread', 1.6)
            key(sat, 'scale', t - 0.01, (0.001, 0.001, 0.001)); key(sat, 'scale', t + 0.2, (1, 1, 1))
        key(rr, 'rotation_euler', p['t0'], tilt[2], 2, 'LINEAR'); key(rr, 'rotation_euler', p['t1'], tilt[2] + p.get('spin', 0.5) * (1 if ring % 2 else -1), 2, 'LINEAR')
    for k in range(p.get('launches', 12)):
        u = rnd.uniform(0, 2 * math.pi); v = rnd.uniform(0.2, 1.2)
        nrm = Vector((math.sin(v) * math.cos(u), -abs(math.sin(v) * math.sin(u)), math.cos(v))).normalized()
        t = p['t0'] + rnd.uniform(0, 1.8); R0 = p.get('earth_r', 6.0)
        o = obj(f'launch{k}', 'cyl', (0.04, 0.04, 0.6), tuple(c + nrm * R0), mat('#FFE6A0', 0.4, 10.0)); o.rotation_euler = nrm.to_track_quat('Z', 'Y').to_euler()
        key(o, 'location', t, c + nrm * R0); key(o, 'location', t + 0.8, c + nrm * (R0 + 3.5))
        vis_keys(o, [[-1, False], [t, True], [t + 0.8, False]])

def prop_moon(p):
    i = p['id']; c = Vector(p['pos']); R = p['r']; rnd = random.Random(2)
    obj(i, 'ico3', (R, R, R), tuple(c), mat('#B9B9B4', 0.9))
    dm = mat('#8E8E8A', 0.95)
    for k in range(30):
        u = rnd.uniform(0, 2 * math.pi); v = math.acos(rnd.uniform(-1, 1))
        n = Vector((math.sin(v) * math.cos(u), math.sin(v) * math.sin(u), math.cos(v)))
        if n.y < -0.55 and abs(n.x) < 0.5 and abs(n.z) < 0.5: continue
        s = rnd.uniform(0.08, 0.25) * R
        o = obj(f'{i}_cr{k}', 'ico', (s, s, 0.05 * R), tuple(c + n * (R - 0.01 * R)), dm); o.rotation_euler = n.to_track_quat('Z', 'Y').to_euler()
    eye(f'{i}_eye', None, tuple(c + Vector((0, -R * 1.002, 0.1 * R))), R * 0.38, '-y', emit=7.0, open_keys=p.get('open'), look_keys=p.get('look'))

def prop_megacube(p):
    i = p['id']; c = Vector(p['pos']); S = p['size']; rnd = random.Random(4)
    box(i, (S, S, S), tuple(c), mat('#262D3A', 0.45, metal=0.3))
    light(f'{i}_rim', 'SUN', (40, -10, 30), (0, 0, 0), 2.5, '#9FD8FF', radius=1.0)
    gm = mat('#1E8FE0', 0.4, 0.0, unique=f'{i}_grid')
    for k in range(18):
        z = c.z - S / 2 + S * (k + 0.5) / 18
        box(f'{i}_h{k}', (S * 1.002, S * 1.002, S * 0.006), (c.x, c.y, z), gm)
    for k in range(12):
        x = c.x - S / 2 + S * (k + 0.5) / 12
        box(f'{i}_v{k}', (S * 0.006, S * 1.004, S * 1.004), (x, c.y, c.z), gm)
    emit_keys(gm, [[-1, 0.0], [p['t0'] + 0.3, 0.4], [p['t0'] + 0.6, 0.8], [p['t0'] + 0.9, 1.3]])
    eye(f'{i}_eye', None, tuple(c + Vector((0, -S * 0.512, 0))), S * 0.18, '-y', emit=8.0, open_keys=p.get('open'), look_keys=p.get('look'))

def prop_sun(p):
    i = p['id']; c = Vector(p['pos']); R = p['r']
    sm = mat('#FFB830', 0.5, p.get('emit', 6.0), unique=f'{i}_m'); obj(i, 'ico3', (R, R, R), tuple(c), sm)
    co = obj(f'{i}_corona', 'ico3', (R * 1.3,) * 3, tuple(c), mat_alpha('#FF8A1A', 0.22, 3.0, f'{i}_cor')); co.visible_shadow = False
    if p.get('dim'): emit_keys(sm, [[p['dim'][0], p.get('emit', 6.0)], [p['dim'][1], p['dim'][2]]]) if False else None
    light(f'{i}_l', 'POINT', tuple(c), (0, 0, 0), p.get('watts', 4e5), '#FFD27A', radius=R)
    rnd = random.Random(1); pm = mat('#1F3B73', 0.25, 0.4); fm = mat('#9AA4AE', 0.3, metal=0.6)
    ring = empty(f'{i}_ring', tuple(c), rot=(math.radians(p.get('tilt', 70)), 0, 0))
    n = p.get('n', 48); Rr = R * p.get('ring', 1.6)
    for k in range(n):
        a = 2 * math.pi * k / n
        pe = empty(f'{i}_p{k}', (Rr * math.cos(a), Rr * math.sin(a), 0), ring, rot=(0, 0, a))
        box(f'{i}_pb{k}', (0.06 * R, 0.5 * R * 6.28 / n * 1.6, 0.35 * R), (0, 0, 0), pm, pe)
        box(f'{i}_pf{k}', (0.08 * R, 0.5 * R * 6.28 / n * 1.7, 0.03 * R), (0, 0, 0.18 * R), fm, pe)
        t = p['t0'] + p.get('spread', 1.4) * k / n
        key(pe, 'scale', t - 0.01, (0.001,) * 3); key(pe, 'scale', t + 0.15, (1, 1, 1))
    key(ring, 'rotation_euler', p['t0'], 0.0, 2, 'LINEAR'); key(ring, 'rotation_euler', p['t1'], p.get('spin', 0.6), 2, 'LINEAR')

def prop_ship(p):
    i = p['id']; root = empty(i, tuple(p['keys'][0][1]))
    box(f'{i}_hull', (1.0, 1.0, 1.0), (0, 0, 0), mat('#0C1018', 0.4, metal=0.6), root)
    for k in range(4):
        box(f'{i}_g{k}', (1.004, 1.004, 0.02), (0, 0, -0.35 + 0.23 * k), mat(EYE_COL, 0.4, 5.0), root)
    for sx in (-1, 1):
        for sz in (-1, 1): obj(f'{i}_th{sx}{sz}', 'cyl', (0.14, 0.14, 0.3), (sx * 0.28, -0.6, sz * 0.28), mat('#FFFFFF', 0.4, 12.0), root, rot=(math.radians(90), 0, 0))
    for t, pos in p['keys']: key(root, 'location', t, Vector(pos))
    key(root, 'rotation_euler', p['keys'][0][0], 0.0, 1, 'LINEAR'); key(root, 'rotation_euler', p['keys'][-1][0], p.get('roll', 1.2), 1, 'LINEAR')

def prop_streaks(p):
    """Stars streaking past the camera along -y (warp)."""
    rnd = random.Random(p.get('seed', 9)); sm = mat('#FFFFFF', 0.5, 8.0); bm = mat('#9FD8FF', 0.5, 8.0)
    for k in range(p.get('n', 220)):
        x = rnd.uniform(-14, 14); z = rnd.uniform(-9, 9)
        if abs(x) < 1.2 and abs(z) < 1.2: x += 3
        L = rnd.uniform(2, 7); y0 = rnd.uniform(-10, 160); sp = rnd.uniform(60, 110)
        o = box(f'stk{k}', (0.03, L, 0.03), (x, y0, z), sm if k % 3 else bm)
        dur = p['t1'] - p['t0']
        key(o, 'location', p['t0'], Vector((x, y0, z)), mode='LINEAR'); key(o, 'location', p['t1'], Vector((x, y0 - sp * dur, z)), mode='LINEAR')
        # wrap: when far behind camera, reappear far ahead (cheap: duplicate track)
        o.animation_data.action.fcurves[1].modifiers.new('CYCLES') if False else None

def prop_bigeye(p):
    eye(p['id'], None, tuple(p['pos']), p['r'], '-y', emit=p.get('emit', 7.0), open_keys=p.get('open'), look_keys=p.get('look'))

def prop_vines(p):
    rnd = random.Random(p.get('seed', 12)); gm = [mat('#3E7D3A', 0.8), mat('#4F8A3B', 0.8), mat('#2F6B33', 0.8)]
    for k, (x, y, z, s) in enumerate(p['spots']):
        for j in range(rnd.randint(3, 6)):
            obj(f'vine{k}_{j}', 'ico', (s * rnd.uniform(0.5, 1.0), s * rnd.uniform(0.5, 1.0), s * rnd.uniform(0.4, 0.9)),
                (x + rnd.uniform(-s, s), y + rnd.uniform(-s, s), z + rnd.uniform(0, s)), rnd.choice(gm))
    dm = mat('#9C9486', 0.95)
    for k, (x, y, z) in enumerate(p.get('dust', [])):
        box(f'dust{k}', (0.5, 0.4, 0.004), (x, y, z), dm)
    for k, (x, y, z, L) in enumerate(p.get('webs', [])):
        box(f'web{k}', (L, 0.004, 0.004), (x, y, z), mat('#DDDDDD', 0.6), rot=(0, math.radians(rnd.uniform(-40, 40)), 0))

def act_emit(ac):
    o = OBJ[ac['obj']]; m = o.material_slots[0].material
    if ac.get('copy', True): m = m.copy(); o.material_slots[0].material = m
    emit_keys(m, ac['keys'])

def act_pulse_city(ac):
    """Heartbeat pulse on every lit building material."""
    for m in BLDG_LIT:
        v = m.node_tree.nodes['LITV'].outputs[0]; t = ac['t0']; interp('BEZIER')
        v.default_value = ac.get('base', 0.4); v.keyframe_insert('default_value', frame=F(t - 0.05))
        while t < ac['t1']:
            for dt, val in ((0.0, ac.get('base', 0.4)), (0.06, ac.get('peak', 6.0)), (0.2, 1.0), (0.3, ac.get('peak', 6.0) * 0.7), (0.5, ac.get('base', 0.4))):
                v.default_value = val; v.keyframe_insert('default_value', frame=F(t + dt))
            t += ac.get('period', 0.85)

BLDG_LIT = []

# ---------------------------------------------------------------- sets
def eevee_lights_sun(target=(0, 0, 0), loc=(-6, -10, 14), energy=4.0, color='#FFF4E0'):
    light('sun', 'SUN', loc, target, energy, color, radius=0.4)

def set_kitchen(S, fonts):
    box('floor', (8, 7, 0.05), (0, 0.5, -0.025), mat_checker('#D9C2A0', '#C4A97F', 1.2))
    wall = mat('#F1E3C6', 0.85)
    box('wall_back', (8, 0.1, 3.2), (0, 2.6, 1.6), wall)
    box('wall_left', (0.1, 7, 3.2), (-3.2, 0.5, 1.6), mat('#E7D2AE'))
    box('win_frame', (1.6, 0.06, 1.2), (1.4, 2.53, 1.85), mat('#FFFFFF'))
    box('win_pane', (1.45, 0.05, 1.05), (1.4, 2.52, 1.85), mat('#BFE6FF', 0.3, 2.2))
    box('win_bar', (0.05, 0.07, 1.05), (1.4, 2.5, 1.85), mat('#FFFFFF'))
    cab = mat('#3E6E8E', 0.6); top = mat('#E8E2D6', 0.4)
    box('counter', (3.4, 0.65, 0.9), (0.9, 2.2, 0.45), cab); box('counter_top', (3.5, 0.72, 0.05), (0.9, 2.2, 0.92), top)
    box('upper_cab', (1.4, 0.4, 0.7), (-0.4, 2.35, 2.25), cab)
    box('fridge', (0.85, 0.75, 1.95), (-2.4, 2.1, 0.975), mat('#E9ECEF', 0.35))
    box('fridge_handle', (0.04, 0.05, 0.6), (-2.05, 1.7, 1.3), mat('#9AA0A6', 0.3))
    box('coffee', (0.3, 0.3, 0.4), (0.0, 2.2, 1.15), mat('#2B2B2B', 0.4))
    box('coffee_light', (0.05, 0.01, 0.05), (0.0, 2.045, 1.2), mat('#FF4A3D', 0.5, 4.0))
    obj('plant_k', 'ico', (0.22, 0.22, 0.25), (2.3, 2.2, 1.25), mat('#4F8A3B'))
    obj('pot_k', 'cyl', (0.12, 0.12, 0.2), (2.3, 2.2, 1.05), mat('#C0603E'))
    box('rug', (2.2, 1.5, 0.012), (-1.1, -0.3, 0.006), mat('#B5523B', 0.9))
    obj('dogbed', 'cyl', (0.55, 0.55, 0.08), (-1.4, -0.4, 0.04), mat('#5C6BC0', 0.9))
    box('frame1', (0.5, 0.03, 0.4), (-1.6, 2.54, 2.0), mat('#6D4C41')); box('frame1_art', (0.42, 0.02, 0.32), (-1.6, 2.52, 2.0), mat('#F2C14E', 0.6))
    light('sun', 'SUN', (3, 8, 6), (0, 0, 0), 3.2, '#FFF1D6', radius=0.5)
    light('fill', 'AREA', (0, -4, 3), (0, 1, 1), 300, '#FFF6EA', size=5, shadow=False)
    world('#FFF4E6', 0.55)

def set_elevator(S, fonts):
    steel = mat('#A7ADB3', 0.4); wood = mat('#7A5C42', 0.6)
    box('el_floor', (2.5, 1.8, 0.05), (0, 0.1, -0.025), mat('#6B6259', 0.8))
    box('el_back', (2.5, 0.05, 2.65), (0, 0.975, 1.3), steel)
    for sx in (-1, 1):
        box(f'el_side{sx}', (0.05, 1.8, 2.65), (sx * 1.225, 0.1, 1.3), steel)
        box(f'el_panel{sx}', (0.02, 1.7, 1.0), (sx * 1.195, 0.1, 0.6), wood)
    box('el_ceiling', (2.5, 1.8, 0.05), (0, 0.1, 2.625), mat('#D8D4CC'))
    box('el_lightpanel', (1.2, 0.6, 0.02), (0, 0.15, 2.595), mat('#FFF6E0', 0.5, 5.0))
    box('el_rail', (2.2, 0.04, 0.04), (0, 0.93, 1.0), mat('#C8C8C8', 0.3))
    for nm, x, w in (('el_frontL', -1.12, 0.26), ('el_frontR', 1.12, 0.26)):
        box(nm, (w, 0.05, 2.65), (x, -0.775, 1.3), steel)
    box('el_frontT', (2.5, 0.05, 0.25), (0, -0.775, 2.52), steel)
    box('door_L', (1.0, 0.04, 2.4), (-0.5, -0.74, 1.2), mat('#8E949A', 0.35))
    box('door_R', (1.0, 0.04, 2.4), (0.5, -0.74, 1.2), mat('#8E949A', 0.35))
    box('door_gap', (0.012, 0.03, 2.4), (0, -0.765, 1.2), mat('#222222'))
    box('ind', (0.36, 0.03, 0.18), (0, -0.745, 2.52), mat('#111111'))
    text('ind_txt', S.get('floor_label', '3'), 0.13, (0, -0.725, 2.515), mat('#FF3B2F', 0.5, 6.0), fonts['sans'], rot=(math.radians(-90), 0, math.radians(180)))
    light('el_fill', 'AREA', (0, 0.15, 2.5), (0, 0.15, 0), 140, '#FFF2DC', size=1.4)
    light('el_key', 'SPOT', (0.9, 0.9, 2.4), (0, -0.3, 1.0), 220, '#FFF4E2', radius=0.02, spot=90)
    world('#2A2A30', 0.4)

def set_landing(S, fonts):
    set_elevator(S, fonts)
    for n in ('door_L', 'door_R', 'door_gap', 'ind', 'ind_txt', 'el_frontL', 'el_frontR', 'el_frontT', 'el_key'):
        o = OBJ.get(n)
        if o and n not in ('door_L', 'door_R', 'door_gap'):
            o.hide_render = True
    landing = mat('#CBBFAF', 0.9)
    box('land_wallL', (5.0, 0.1, 6.0), (-3.5, -0.8, 3.0), landing); box('land_wallR', (5.0, 0.1, 6.0), (3.5, -0.8, 3.0), landing)
    box('land_wallT', (2.0, 0.1, 3.6), (0, -0.8, 4.2), landing)
    for sx in (-1, 1): box(f'land_trim{sx}', (0.08, 0.14, 2.44), (sx * 1.04, -0.82, 1.22), mat('#5B5B5B', 0.4))
    box('land_trimT', (2.16, 0.14, 0.08), (0, -0.82, 2.44), mat('#5B5B5B', 0.4))
    OBJ['door_L'].location.y = -0.725; OBJ['door_R'].location.y = -0.725; OBJ['door_gap'].hide_render = True
    box('ind_plate', (0.42, 0.04, 0.28), (0, -0.87, 2.85), mat('#111111'))
    text('land_ind', S.get('floor_label', '2'), 0.22, (0, -0.895, 2.84), mat('#FF3B2F', 0.5, 6.0), fonts['sans'])
    box('land_sign', (1.4, 0.03, 0.34), (2.4, -0.87, 1.7), mat('#2F5D8C', 0.6))
    text('land_sign_t', S.get('sign', 'ACCOUNTING'), 0.17, (2.4, -0.89, 1.7), mat('#FFFFFF'), fonts['sans'])
    obj('land_plant', 'ico', (0.35, 0.35, 0.45), (-2.2, -1.6, 0.75), mat('#4F8A3B')); obj('land_pot', 'cyl', (0.25, 0.25, 0.45), (-2.2, -1.6, 0.22), mat('#7A7A7A'))
    box('land_floor', (12, 9, 0.05), (0, -5.3, -0.03), mat_checker('#BDB4A6', '#A89F90', 1.0))
    light('land_key', 'SPOT', (2.2, -5.5, 4.2), (0, -0.5, 1.0), 1600, '#FFF4E2', radius=0.02, spot=60)
    light('land_fill', 'AREA', (0, -6.5, 3.5), (0, 0, 1.2), 300, '#DDE6F0', size=4.0, shadow=False)
    world('#E8E4DC', 0.45)

def set_office(S, fonts):
    box('floor', (14, 12, 0.05), (0, 1, -0.025), mat('#6D7B8A', 0.95))
    wall = mat('#ECE7DC', 0.85)
    box('wall_back', (14, 0.1, 3.4), (0, 5.0, 1.7), wall); box('wall_left', (0.1, 12, 3.4), (-5.5, 1, 1.7), wall)
    box('wall_right', (0.1, 12, 3.4), (5.5, 1, 1.7), mat('#DCD3C2', 0.85))
    for k, x in enumerate((-3.6, -1.2, 1.2, 3.6)):
        box(f'win{k}', (1.8, 0.06, 1.4), (x, 4.94, 1.9), mat('#BFE6FF', 0.3, 1.8))
        box(f'winf{k}', (1.9, 0.08, 0.08), (x, 4.93, 1.2), mat('#FFFFFF'))
    box('ceiling', (14, 12, 0.1), (0, 1, 3.45), mat('#F4F2EE'))
    for k, (x, y) in enumerate(((-2, -1), (2, -1), (-2, 2.5), (2, 2.5))):
        box(f'lamp{k}', (1.4, 0.5, 0.03), (x, y, 3.39), mat('#FFF8EA', 0.5, 3.0))
    dm = mat('#E8E2D6', 0.5); lm = mat('#555555', 0.4)
    for d in S.get('desks', []):
        nm = d['id']; x, y = d['pos']; r = math.radians(d.get('rot', 0))
        root = empty(nm, (x, y, 0), rot=(0, 0, r))
        box(f'{nm}_top', (1.4, 0.75, 0.05), (0, 0, 0.74), dm, root)
        for sx in (-1, 1):
            for sy in (-1, 1): box(f'{nm}_leg{sx}{sy}', (0.04, 0.04, 0.72), (sx * 0.65, sy * 0.33, 0.36), lm, root)
        box(f'{nm}_lap', (0.36, 0.25, 0.02), (0, 0.05, 0.775), mat('#B0B4BA', 0.35), root)
        box(f'{nm}_lscr', (0.36, 0.015, 0.24), (0, -0.08, 0.9), mat('#B0B4BA', 0.35), root, rot=(math.radians(-12), 0, 0))
        box(f'{nm}_lapple', (0.05, 0.005, 0.05), (0, -0.092, 0.9), mat('#FFFFFF', 0.5, 1.0), root, rot=(math.radians(-12), 0, 0))
        box(f'{nm}_mug', (0.08, 0.08, 0.1), (0.45, 0.1, 0.8), mat(d.get('mug', '#F2F2F2'), 0.5), root)
        box(f'{nm}_papers', (0.22, 0.3, 0.03), (-0.45, 0.0, 0.78), mat('#FFFFFF', 0.8), root)
        if d.get('chair', True):
            box(f'{nm}_seat', (0.5, 0.5, 0.08), (0, 0.55, 0.46), mat('#2E3A59', 0.7), root)
            box(f'{nm}_back', (0.5, 0.08, 0.6), (0, 0.82, 0.8), mat('#2E3A59', 0.7), root)
            box(f'{nm}_pole', (0.05, 0.05, 0.42), (0, 0.55, 0.21), lm, root)
    box('exit_door', (1.0, 0.06, 2.1), (5.46, 2.0, 1.05), mat('#8C6A4F', 0.6), rot=(0, 0, math.radians(90)))
    box('exit_sign', (0.06, 0.5, 0.2), (5.44, 2.0, 2.35), mat('#2ECC71', 0.5, 4.0))
    text('exit_txt', 'EXIT', 0.13, (5.4, 2.0, 2.35), mat('#FFFFFF', 0.5, 2.0), fonts['sans'], rot=(math.radians(90), 0, math.radians(-90)))
    box('alarm', (0.25, 0.08, 0.25), (S.get('alarm_x', -1.0), 4.93, 2.7), mat('#E53935', 0.4, 0.3))
    light('alarm_light', 'POINT', (S.get('alarm_x', -1.0), 4.4, 2.7), (0, 0, 0), 0, '#FF2A1A', radius=0.05, shadow=False)
    box('water', (0.4, 0.4, 1.2), (-4.8, 4.4, 0.6), mat('#DADADA')); obj('water_b', 'cyl', (0.18, 0.18, 0.4), (-4.8, 4.4, 1.4), mat('#8FD3FF', 0.2))
    light('sun', 'SUN', (-4, 10, 8), (0, 0, 0), 2.2, '#FFF4E0', radius=0.5)
    light('key', 'SPOT', (3, -4.5, 3.3), (0, 1, 0.5), 1800, '#FFF6EA', radius=0.02, spot=80)
    light('fill', 'AREA', (0, 0, 3.3), (0, 0, 0), 500, '#FFFFFF', size=6, shadow=False)
    world('#F4F1EA', 0.55)

CITY_LIT = [0.0]
def city_blocks(rnd, xr, yr, skip=(), hmin=7, hmax=30):
    pal = ['#C9B79C', '#9FB4C7', '#D8A47F', '#B5B8A3', '#E0D6C8', '#8E9AAF', '#C48B6E', '#A7C4A0']
    for bx in xr:
        for by in yr:
            if (bx, by) in skip: continue
            for k in range(rnd.randint(1, 3)):
                w = rnd.uniform(4, 8); d = rnd.uniform(4, 8); h = rnd.uniform(hmin, hmax)
                cx = bx * 14 + rnd.uniform(-3, 3); cy = by * 14 + rnd.uniform(-3, 3)
                box(f'b{bx}_{by}_{k}', (w, d, h), (cx, cy, h / 2), mat_building(rnd.choice(pal), '#33465E', '#6A6A6A', CITY_LIT[0]))

def set_street(S, fonts):
    rnd = random.Random(S.get('seed', 7))
    box('road', (120, 16, 0.05), (0, -11, -0.025), mat('#3A3A3C', 0.9))
    for k in range(-15, 16): box(f'lane{k}', (2.0, 0.15, 0.01), (k * 4.0, -10, 0.005), mat('#EDEDED', 0.6))
    box('sidewalk', (120, 6.5, 0.14), (0, -1.75, 0.07), mat('#B8B2A7', 0.9))
    box('curb', (120, 0.25, 0.16), (0, -5.0, 0.08), mat('#8F8A82', 0.9))
    box('office', (12, 10, 20), (0, 6.5, 10), mat_building('#D9CFC0', '#2E3F55', '#6E6E6E'))
    box('office_doors', (2.3, 0.08, 2.7), (0, 1.47, 1.35), mat('#1F2A33', 0.15))
    box('awning', (3.4, 1.0, 0.12), (0, 1.0, 2.95), mat('#8B2E2E', 0.7))
    pal = ['#C9B79C', '#9FB4C7', '#D8A47F', '#B5B8A3', '#E0D6C8', '#8E9AAF', '#C48B6E']
    for side in (-1, 1):
        x = side * 6.2
        while abs(x) < 40:
            w = rnd.uniform(4, 8); h = rnd.uniform(7, 30); d = rnd.uniform(6, 12); cx = x + side * w / 2
            box(f'bldg{side}_{int(abs(x))}', (w - 0.3, d, h), (cx, 1.6 + d / 2, h / 2), mat_building(rnd.choice(pal), '#33465E', '#5E5E5E'))
            x += side * w
    for k in range(8):
        h = rnd.uniform(20, 45); box(f'far{k}', (6, 6, h), (rnd.uniform(-30, 30), rnd.uniform(16, 30), h / 2), mat_building(rnd.choice(pal), '#33465E', '#5E5E5E'))
    if S.get('wire'):
        for x in S['wire']['poles']:
            obj(f'pole{x}', 'cyl', (0.09, 0.09, 5.2), (x, -4.5, 2.6), mat('#5B4636'))
            box(f'pole_bar{x}', (0.9, 0.08, 0.08), (x, -4.5, 5.0), mat('#5B4636'))
        xs = S['wire']['poles']
        box('wire', (abs(xs[-1] - xs[0]) + 4, 0.025, 0.025), ((xs[0] + xs[-1]) / 2, -4.5, S['wire'].get('z', 4.95)), mat('#151515'))
    for k, x in enumerate(S.get('parked', [])):
        col = ['#D9432B', '#2F6DB5', '#F2C14E', '#EDEDED', '#3E3E46'][k % 5]
        root = empty(f'pk{k}', (x, -6.3, 0))
        box(f'pk{k}_body', (3.8, 1.7, 0.75), (0, 0, 0.55), mat(col, 0.35), root)
        box(f'pk{k}_top', (2.1, 1.5, 0.6), (0.2, 0, 1.22), mat('#2E4A66', 0.2), root)
        for sy in (-1, 1):
            for sx in (-1, 1): obj(f'pk{k}_wh{sx}{sy}', 'cyl', (0.33, 0.33, 0.25), (sx * 1.2, sy * 0.8, 0.33), mat('#1C1C1C'), root, rot=(math.radians(90), 0, 0))
        box(f'pk{k}_hl', (0.05, 1.4, 0.14), (-1.92, 0, 0.72), mat('#FFF6C8', 0.4, 0.5), root)
        box(f'pk{k}_tl', (0.05, 1.4, 0.14), (1.92, 0, 0.72), mat('#FF3B2F', 0.4, 0.5), root)
    for x in (-3.6, 3.6):
        obj(f'tree_trunk{x}', 'cyl', (0.1, 0.1, 1.8), (x, -3.8, 1.04), mat('#5A3E2B')); obj(f'tree_crown{x}', 'ico', (0.9, 0.9, 1.0), (x, -3.8, 2.6), mat('#4F8A3B', 0.8))
    for k, (x, col) in enumerate(((-7, '#2F6DB5'), (9, '#D9432B'))):
        box(f'car{k}', (3.6, 1.6, 0.8), (x, -8.0 - k * 4, 0.6), mat(col, 0.35)); box(f'car{k}_top', (2.0, 1.4, 0.6), (x + 0.2, -8.0 - k * 4, 1.25), mat('#2E4A66', 0.2))
    light('sun', 'SUN', (0, -10, 20), (2.5, 4, 0), 4.0, '#FFF4E0', radius=0.5)
    world(S.get('sky', '#8EC5F0'), 0.9)

def set_aerial(S, fonts):
    rnd = random.Random(S.get('seed', 11)); CITY_LIT[0] = S.get('lit', 0.0)
    box('ground', (300, 300, 0.05), (0, 0, -0.03), mat('#3A3A3C', 0.9))
    for bx in range(-6, 7):
        for by in range(-6, 7):
            box(f'blk{bx}_{by}', (10.5, 10.5, 0.14), (bx * 14, by * 14, 0.07), mat('#B8B2A7', 0.9))
    city_blocks(rnd, range(-6, 7), range(-6, 7), skip={(0, 0)})
    box('park', (10, 10, 0.16), (0, 0, 0.08), mat('#5E9E4A', 0.9))
    for k in range(6): obj(f'ptree{k}', 'ico', (0.9, 0.9, 1.0), (rnd.uniform(-4, 4), rnd.uniform(-4, 4), 1.0), mat('#3E7D3A'))
    if S.get('night'):
        light('sun', 'SUN', (-40, -60, 80), (0, 0, 0), 0.25, '#9FB7FF', radius=0.5); world('#070B18', 0.35)
    else:
        light('sun', 'SUN', (-40, -60, 80), (0, 0, 0), 4.0, '#FFF4E0', radius=0.5); world('#8EC5F0', 1.0)
    if S.get('no_park_trees'): pass

def set_space(S, fonts):
    rnd = random.Random(5)
    world('#02030A', 0.0)
    R = S.get('earth_r', 6.0); c = Vector(S.get('earth_c', (0, 0, -7.0)))
    if S.get('no_earth'): R = 0.001; c = Vector((0, 0, -500))
    earth = obj('earth', 'ico3', (R, R, R), tuple(c), mat('#2F6FB5', 0.6))
    obj('atmo', 'ico3', (R * 1.03, R * 1.03, R * 1.03), tuple(c), mat_alpha('#8FD0FF', 0.18, 1.5, 'atmo'))
    land = mat('#8E9A5B', 0.85); sand = mat('#C9B37A', 0.85)
    pts = []
    for k in range(46):
        u = rnd.uniform(0, 2 * math.pi); v = math.acos(rnd.uniform(-1.0, 1.0))
        n = Vector((math.sin(v) * math.cos(u), math.sin(v) * math.sin(u), math.cos(v)))
        pts.append(n)
        sz = rnd.uniform(0.6, 1.5)
        sz = sz * R / 6.0; o = obj(f'land{k}', 'ico', (sz, sz * rnd.uniform(0.6, 1.4), 0.04 * R / 6.0), tuple(c + n * (R - 0.01)), land if k % 5 else sand)
        o.rotation_euler = n.to_track_quat('Z', 'Y').to_euler()
    for k in range(24):
        u = rnd.uniform(0, 2 * math.pi); v = math.acos(rnd.uniform(-1.0, 1.0))
        n = Vector((math.sin(v) * math.cos(u), math.sin(v) * math.sin(u), math.cos(v)))
        o = obj(f'wisp{k}', 'ico', (rnd.uniform(0.6, 1.4) * R / 6, 0.4 * R / 6, 0.02 * R), tuple(c + n * (R + 0.02 * R)), mat_alpha('#FFFFFF', 0.6, 0.2, f'wisp{k}'))
        o.rotation_euler = n.to_track_quat('Z', 'Y').to_euler()
    star = mat('#FFFFFF', 0.5, 6.0)
    for k in range(160):
        d = Vector((rnd.uniform(-1, 1), rnd.uniform(0.2, 1), rnd.uniform(-0.3, 1))).normalized() * 70
        s = rnd.uniform(0.06, 0.16); box(f'star{k}', (s, s, s), tuple(d), star)
    if S.get('no_station'):
        light('sun', 'SUN', (-20, -10, 10), (0, 0, -4), S.get('sun', 5.0), '#FFF6E8', radius=0.3); return
    # ISS-like station
    st = empty('station', tuple(S.get('station', (1.6, 1.5, 0.4))), rot=(0, 0, math.radians(20)))
    box('st_mod', (0.7, 2.4, 0.7), (0, 0, 0), mat('#E6E6E6', 0.4), st)
    box('st_mod2', (0.55, 0.55, 1.6), (0, 0.6, 0), mat('#D0D0D0', 0.4), st)
    for sx in (-1, 1):
        box(f'st_truss{sx}', (3.2, 0.12, 0.12), (sx * 1.9, 0, 0), mat('#9A9A9A'), st)
        for sy in (-1, 1): box(f'st_panel{sx}{sy}', (2.4, 0.9, 0.03), (sx * 2.2, sy * 0.6, 0), mat('#1F3B73', 0.25, 0.1), st)
    light('sun', 'SUN', (-20, -10, 10), (0, 0, -4), 5.0, '#FFF6E8', radius=0.3)

def set_studio(S, fonts):
    box('desk', (1.9, 0.7, 1.0), (0, -0.15, 0.5), mat('#1F3B73', 0.5))
    box('desk_strip', (1.92, 0.02, 0.12), (0, -0.51, 0.82), mat('#E8C547', 0.4))
    box('desk_top', (2.0, 0.78, 0.04), (0, -0.15, 1.02), mat('#D8DDE6', 0.3))
    light('st_key', 'SPOT', (-1.4, -3.0, 3.0), (0, 0.3, 1.4), 900, '#FFF4E8', radius=0.02, spot=45)
    light('st_fill', 'AREA', (1.6, -2.4, 2.0), (0, 0.3, 1.4), 200, '#DDE8FF', size=1.5, shadow=False)
    world('#202634', 0.6)

def set_lobby(S, fonts):
    box('lob_floor', (6, 14, 0.05), (0, 1.5, -0.025), mat_checker('#E3DBCB', '#B9AE98', 1.0))
    box('lob_wallL', (0.1, 14, 4.2), (-3.0, 1.5, 2.1), mat('#7F8C8D', 0.8)); box('lob_wallR', (0.1, 14, 4.2), (3.0, 1.5, 2.1), mat('#C9B79C', 0.7))
    wall = mat('#E6E1D6', 0.8)
    box('lob_backL', (2.0, 0.12, 4.2), (-2.0, 6.5, 2.1), wall); box('lob_backR', (2.0, 0.12, 4.2), (2.0, 6.5, 2.1), wall); box('lob_backT', (2.0, 0.12, 1.6), (0, 6.5, 3.4), wall)
    frame = mat('#2A2A2A', 0.5)
    box('lob_door_frameT', (2.1, 0.16, 0.1), (0, 6.5, 2.6), frame)
    for sx in (-1, 1): box(f'lob_door_frame{sx}', (0.08, 0.16, 2.6), (sx * 1.02, 6.5, 1.3), frame)
    for nm, x in (('lobby_door_L', -0.5), ('lobby_door_R', 0.5)):
        d = box(nm, (1.0, 0.04, 2.5), (x, 6.47, 1.25), mat_alpha('#BFE3F2', 0.25, 0.1, nm + '_g')); d.visible_shadow = False
    text('lob_exit', 'EXIT', 0.18, (0, 6.42, 3.0), mat('#3BD16F', 0.5, 4.0), fonts['sans'])
    box('lob_outside', (30, 12, 0.05), (0, 13, -0.03), mat('#A3A3A3', 0.9))
    for k, x in enumerate((-6, -2.5, 2.5, 6)): box(f'lob_out_b{k}', (3.0, 3.0, 9 + 3 * k % 7), (x, 18, 4.5), mat('#C7B9A5', 0.9))
    box('lob_desk', (1.4, 0.7, 1.05), (2.0, 2.6, 0.525), mat('#5C3D2E', 0.6)); box('lob_desk_top', (1.5, 0.8, 0.05), (2.0, 2.6, 1.07), mat('#D9C7A8', 0.4))
    obj('lob_pot', 'cyl', (0.25, 0.25, 0.5), (-2.4, 4.6, 0.25), mat('#8C4A2F')); obj('lob_leaf', 'ico', (0.4, 0.4, 0.5), (-2.4, 4.6, 0.95), mat('#3E7D3A', 0.8))
    box('lob_ceiling', (6, 14, 0.1), (0, 1.5, 4.25), mat('#F0EDE6'))
    for k, y in enumerate((-1, 2, 5)): box(f'lob_lamp{k}', (1.6, 0.5, 0.03), (0, y, 4.19), mat('#FFF6E0', 0.5, 2.0))
    light('lob_key', 'SPOT', (2.2, -2.6, 3.9), (0, 2.2, 0.4), 900, '#FFF1DD', radius=0.05, spot=75)
    light('lob_fill', 'AREA', (0, 2.0, 4.1), (0, 2.0, 0), 150, '#FFF6EA', size=4.0, shadow=False)
    world('#CFE6F5', 1.0)

def set_sky(S, fonts):
    rnd = random.Random(S.get('seed', 3)); world(S.get('sky', '#7FB8EE'), 1.0)
    cm = mat('#FFFFFF', 0.9)
    zc = S.get('deck_z', 0.0)
    for k in range(S.get('n', 70)):
        x = rnd.uniform(-60, 60); y = rnd.uniform(-20, 120); sz = rnd.uniform(3, 9)
        obj(f'cl{k}', 'ico', (sz, sz * rnd.uniform(0.7, 1.3), sz * 0.45), (x, y, zc + rnd.uniform(-1.5, 1.5)), cm)
    if S.get('ground'):
        box('gnd', (600, 600, 0.1), (0, 0, zc - 40), mat('#6E8F5A', 0.9))
    light('sun', 'SUN', (-20, -30, 40), (0, 0, 0), 4.0, '#FFF4E0', radius=1.0)

BUILDERS = {'kitchen': set_kitchen, 'elevator': set_elevator, 'landing': set_landing, 'office': set_office,
            'street': set_street, 'aerial': set_aerial, 'space': set_space, 'studio': set_studio, 'lobby': set_lobby, 'sky': set_sky}

# ---------------------------------------------------------------- camera
def build_camera(cam):
    cd = bpy.data.cameras.new('cam'); cd.lens = cam.get('lens', 35); cd.sensor_fit = 'AUTO'; cd.clip_start = 0.05; cd.clip_end = 500
    rig = empty('cam_rig', c='cam'); c = bpy.data.objects.new('cam', cd); coll('cam').objects.link(c); c.parent = rig
    tg = empty('cam_target', c='cam')
    con = c.constraints.new('TRACK_TO'); con.target = tg; con.track_axis = 'TRACK_NEGATIVE_Z'; con.up_axis = 'UP_Y'
    for k in cam['keys']:
        key(rig, 'location', k['t'], Vector(k['pos']), mode=k.get('interp', 'BEZIER'))
        key(tg, 'location', k['t'], Vector(k['target']), mode=k.get('interp', 'BEZIER'))
        if 'lens' in k:
            interp('BEZIER'); cd.lens = k['lens']; cd.keyframe_insert('lens', frame=F(k['t']))
    rnd = random.Random(3)
    for sh in cam.get('shake', []):
        t = sh['t']; amp = sh.get('amp', 0.05); dur = sh.get('dur', 0.5)
        key(c, 'location', t - 0.02, Vector((0, 0, 0)))
        n = int(dur * 24)
        for k in range(1, n + 1):
            a = amp * (1 - k / n)
            key(c, 'location', t + k / 24, Vector((rnd.uniform(-a, a), rnd.uniform(-a, a) * 0.5, rnd.uniform(-a, a))))
        key(c, 'location', t + dur + 0.05, Vector((0, 0, 0)))
    SCENE.camera = c

# ---------------------------------------------------------------- main
PROPS = {'plant': prop_plant, 'heli': prop_heli, 'ufo': prop_ufo, 'plane': prop_plane, 'traffic': prop_traffic, 'debris': prop_debris,
         'patch': prop_patch, 'aura': prop_aura, 'bolts': prop_bolts, 'screen': prop_screen, 'monitor_eyes': prop_monitor_eyes,
         'printer': prop_printer, 'pizzas': prop_pizzas, 'tlight': prop_tlight, 'cars': prop_cars, 'backdrop': prop_backdrop,
         'satellites': prop_satellites, 'moon': prop_moon, 'megacube': prop_megacube, 'sun': prop_sun, 'ship': prop_ship,
         'streaks': prop_streaks, 'bigeye': prop_bigeye, 'vines': prop_vines}
LATE_PROPS = {'robot_rise': prop_robot_rise}
_EXTRA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'props_extra.py')
if os.path.exists(_EXTRA):  # per-reel props: define functions and add them to PROPS / LATE_PROPS / BUILDERS
    exec(open(_EXTRA).read(), globals())

def setup_render(plan, shot, a, res):
    r = SCENE.render; R = plan['render']
    r.resolution_x, r.resolution_y = res; r.resolution_percentage = 100
    eng = a.engine or R.get('engine', 'CYCLES')
    if eng == 'CYCLES':
        r.engine = 'CYCLES'; cy = SCENE.cycles
        dev = 'CPU'
        try:
            pr = bpy.context.preferences.addons['cycles'].preferences
            for typ in ('OPTIX', 'CUDA'):
                try:
                    pr.compute_device_type = typ; pr.get_devices()
                    gpus = [d for d in pr.devices if d.type == typ]
                    if gpus:
                        for d in pr.devices: d.use = d.type == typ
                        dev = 'GPU'; break
                except Exception: pass
        except Exception: pass
        cy.device = dev; print('[render] cycles device', dev, flush=True)
        cy.samples = a.samples or shot.get('samples', R.get('samples', 24)); cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.05
        cy.use_denoising = True
        try: cy.denoiser = 'OPENIMAGEDENOISE'; cy.denoising_use_gpu = (dev == 'GPU')
        except Exception: pass
        cy.max_bounces = 4; cy.diffuse_bounces = 2; cy.glossy_bounces = 1; cy.transmission_bounces = 2; cy.transparent_max_bounces = 12
        cy.caustics_reflective = False; cy.caustics_refractive = False
        try: r.use_persistent_data = True
        except Exception: pass
    else:
        for e in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
            try: r.engine = e; break
            except Exception: pass
        ee = SCENE.eevee
        for k, v in (('taa_render_samples', a.samples or R.get('samples', 8)), ('use_gtao', True), ('use_soft_shadows', False), ('use_shadows', True)):
            try: setattr(ee, k, v)
            except Exception: pass
    r.film_transparent = bool(shot.get('transparent'))
    SCENE.view_settings.view_transform = 'Standard'; SCENE.view_settings.look = shot.get('look', 'None')
    try: SCENE.view_settings.exposure = shot.get('exposure', R.get('exposure', 0.0))
    except Exception: pass
    if shot.get('transparent'):
        r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGBA'
    else:
        r.image_settings.file_format = 'JPEG'; r.image_settings.color_mode = 'RGB'; r.image_settings.quality = 93

def main():
    global SCENE, FPS, FONTS
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', required=True); ap.add_argument('--shot', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--fps', type=int, default=None); ap.add_argument('--frames', default=None); ap.add_argument('--res', default=None)
    ap.add_argument('--samples', type=int, default=None); ap.add_argument('--engine', default=None)
    ap.add_argument('--save-blend', action='store_true'); ap.add_argument('--build-only', action='store_true')
    a = ap.parse_args(argv)
    plan = json.load(open(a.plan)); FPS = a.fps or plan['fps']; FONTS = plan['fonts']
    shot = next(s for s in plan['shots'] if s['id'] == a.shot)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    SCENE = bpy.context.scene; SCENE.render.fps = FPS
    S = dict(plan.get('sets', {}).get(shot['set'], {})); S.update(shot.get('set_opts', {}))
    BUILDERS[shot['set']](S, plan['fonts'])
    for nm in shot.get('hide', []):
        if nm in OBJ: OBJ[nm].hide_render = True
    for k, L in enumerate(shot.get('lights', [])):
        light(f'xl{k}', L['kind'], L['loc'], L.get('target', (0, 0, 0)), L['energy'], L.get('color', '#FFFFFF'),
              radius=L.get('radius', 0.05), spot=L.get('spot', 60), size=L.get('size', 2.0), shadow=L.get('shadow', True))
    if shot.get('light_scale'):
        for o in SCENE.objects:
            if o.type == 'LIGHT' and not o.name.startswith('xl'): o.data.energy *= shot['light_scale']
    if 'world' in shot: world(shot['world'][0], shot['world'][1])
    for ac in shot.get('actors', []):
        {'human': human, 'dog': dog, 'pigeon': pigeon}[ac.get('kind', 'human')](ac)
    for p in shot.get('props', []):
        if p['kind'] in PROPS: PROPS[p['kind']](p)
    for c in shot.get('clouds', []): build_cloud(c)
    for e in shot.get('extra_box', []):
        box(e['id'], tuple(e['size']), tuple(e['pos']), mat(e['col'], 0.5, e.get('emit', 0.0)))
    for e in shot.get('extra_text', []):
        o = text(e['id'], e['body'], e['size'], tuple(e['pos']), mat(e['col'], 0.5, e.get('emit', 0.0)), FONTS['sans'], extrude=e.get('extrude', 0.002))
        if 't0' in e: vis_keys(o, [[-1, False], [e['t0'], True]], recursive=False)
    for p in shot.get('props', []):
        if p['kind'] in LATE_PROPS: LATE_PROPS[p['kind']](p)
    for ac in shot.get('actions', []):
        t = ac['type']; A = ACT.get(ac.get('actor'))
        if t == 'walk': act_walk(A, ac['t0'], ac['path'], ac.get('speed', 1.4))
        elif t == 'run': act_walk(A, ac['t0'], ac['path'], ac.get('speed', 3.6), stride=0.38, swing=0.8, arm=0.9, bob=0.05)
        elif t == 'march': act_walk(A, ac['t0'], ac['path'], ac.get('speed', 1.2), stride=0.5, swing=0.55, arm=0.6, bob=0.03)
        elif t == 'clench': act_clench(A, ac['t'])
        elif t == 'eyes': act_eyes(A, ac['t0'], ac['t1'], ac['dx'])
        elif t == 'head': act_head(A, ac['t0'], ac['t1'], ac['angle'], ac.get('axis', 2))
        elif t == 'brows': act_brows(A, ac['t0'], ac['t1'], ac['dz'], ac.get('tilt', 0))
        elif t == 'mouth': act_mouth(A, ac['t0'], ac['t1'], ac['sz'], ac.get('sx', 1.0))
        elif t == 'arm': act_arm(A, ac['t0'], ac['t1'], ac['side'], *ac['rot'])
        elif t == 'cover_nose': act_cover_nose(A, ac['t0'], ac.get('t1'))
        elif t == 'sip': act_sip(A, ac['t0'], ac['t1'])
        elif t == 'shrug': act_shrug(A, ac['t'])
        elif t == 'turn': act_turn(A, ac['t0'], ac['t1'], ac['angle'])
        elif t == 'faint': act_faint(A, ac['t'], ac.get('fall_to'), ac.get('dur', 0.55), ac.get('axis', 0), ac.get('sign', 1))
        elif t == 'jump': act_jump(A, ac['t'], ac.get('h', 0.15))
        elif t == 'talk': act_talk(A, ac['t0'], ac['dur'])
        elif t == 'keys': act_keys(ac)
        elif t == 'color': act_color(ac)
        elif t == 'flash': act_flash(ac)
        elif t == 'spin': act_spin(ac)
        elif t == 'hide': act_hide(ac)
        elif t == 'wilt': act_wilt(ac)
        elif t == 'emit': act_emit(ac)
        elif t == 'pulse_city': act_pulse_city(ac)
        elif t == 'type':
            for k, tt in enumerate([ac['t0'] + 0.11 * j for j in range(int((ac['t1'] - ac['t0']) / 0.11))]):
                sd = 'LR'[k % 2]; o = A['sho' + sd]
                key(o, 'rotation_euler', tt, ac.get('x', -55) * math.pi / 180 - (0.08 if k % 2 else 0), 0)
                key(o, 'rotation_euler', tt + 0.055, ac.get('x', -55) * math.pi / 180 + 0.06, 0)
    build_camera(shot['camera'])
    res = [int(v) for v in (a.res or 'x'.join(map(str, shot.get('res', plan['resolution'])))).split('x')]
    setup_render(plan, shot, a, res)
    f0, f1 = round(shot['t0'] * FPS), round(shot['t1'] * FPS) - 1
    if a.frames:
        lo, hi = [int(v) for v in a.frames.split('-')]; f0, f1 = max(f0, lo), min(f1, hi)
    os.makedirs(a.out, exist_ok=True)
    if a.save_blend: bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(a.out, f'{a.shot}.blend')))
    if a.build_only: return
    r = SCENE.render; ext = '.png' if shot.get('transparent') else '.jpg'
    todo = [f for f in range(f0, f1 + 1) if not os.path.exists(os.path.join(a.out, f'f_{f:05d}{ext}'))]
    if not todo: print(f'[{a.shot}] nothing to do', flush=True); return
    t = time.time()
    SCENE.frame_start, SCENE.frame_end = todo[0], todo[-1]
    r.filepath = os.path.join(os.path.abspath(a.out), 'f_#####'); r.use_file_extension = True; r.use_overwrite = False; r.use_placeholder = False
    bpy.ops.render.render(animation=True)
    dt = time.time() - t
    with open(os.path.join(a.out, 'times.jsonl'), 'a') as fh:
        fh.write(json.dumps({'shot': a.shot, 'res': res, 'fps': FPS, 'frames': len(todo), 'total_s': round(dt, 2), 'mean_s': round(dt / len(todo), 3)}) + '\n')
    print(f'[{a.shot}] {len(todo)} frames {dt:.1f}s', flush=True)

if __name__ == '__main__':
    main()
