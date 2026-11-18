# -*- coding: utf-8 -*-
"""
会津若松城（鶴ヶ城）慶応四年（1868）秋 ― 映画風テストショット
「朝霧の中から天守が現れる」  8秒 / 24fps / 2.39:1（シネスコ）

■ これは何か
  Blender のスクリプト 1 本で、内堀の水面・本丸の石垣（野面積み）・天守台・五重の天守・走長屋・隅櫓・
  土塀・松・朝霧・朝日・遠景の山並み・カメラワークまでを生成し、8 秒のショットを描画できる状態にします。
  外部アセット・有料サービスは使いません。大阪城のスクリプト（osaka-castle/）とは独立しています。

■ 使い方（Windows の例）
  A. 画面で使う
     Blender（4.2 LTS 以降。5.2 LTS 推奨）→「Scripting」タブ → このファイルを開いて ▶（スクリプト実行）
     → シーンが生成されます → 「レンダー」メニュー →「アニメーションをレンダリング」
     描く大きさは下の CFG["QUALITY"] で切り替えます（最初は "TEST" のまま）。
  B. コマンドで使う（PowerShell。blender.exe の場所は環境に合わせて変更）
     & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P aizu_wakamatsu_castle_1868.py -- --quality TEST --render
       --quality TEST | PREVIEW | FINAL  : 1280×536（確認用）/ 1920×804 / 3840×1608（4K）
       --benchmark                       : 最初・中間・最後の 3 コマだけ描き、1 コマの時間と全体の見込みを表示
       --render                          : 全コマを描く
       --frames 1-48                     : 描くコマの範囲
       --device AUTO | GPU | CPU         : AUTO は GPU（OptiX / CUDA / HIP / oneAPI / Metal）があれば使う
       --out フォルダ                     : 出力先（省略時はこのファイルの隣の render\\品質名\\）
       --exr                             : 色調整用に 16bit の OpenEXR（マルチレイヤー）で書き出す
       --save ファイル.blend               : 生成したシーンを .blend として保存
  4K（FINAL）の前に、必ず --benchmark で 1 コマの時間を確かめてください。

■ 史実と推測
  コメントの【資料】は資料で確認できたこと、【推測】は資料で確認できず推測で作った部分です。
  推測の一覧は ASSUMPTIONS にまとめ、生成したシーンのテキスト「AZ_考証メモ」にも書き出します。
  映像を公開するときは「建築の細部・配置は推測を含む再現」と明記してください。
"""

import bpy
import bmesh
import math
import os
import sys
import time
import random
import datetime
from mathutils import Vector, Matrix

try:
    import numpy as np
except ImportError:          # Blender には numpy が同梱されているので通常ここには来ない
    np = None

# =============================================================================
# 0. 設定
# =============================================================================
CFG = {
    "QUALITY": "TEST",          # TEST / PREVIEW / FINAL（下の QUALITY_PRESETS）
    "DEVICE": "AUTO",           # AUTO / GPU / CPU
    "FPS": 24,
    "FRAME_START": 1,
    "FRAME_END": 192,           # 24fps × 8 秒
    "OUTPUT_DIR": "",           # 空ならこのファイルの隣の render/<品質>/
    "EXR": False,               # True で 16bit OpenEXR（マルチレイヤー）
    "SEED": 1868,
    # 太陽：慶応四年八月十日（新暦 1868-09-25）、日の出から何分後か
    #  【資料】籠城戦は慶応4年8月23日（新暦10月8日）から。この日付はその前の、まだ無傷の城。
    "DATE": (1868, 9, 25),
    "MIN_AFTER_SUNRISE": 55,          # 日の出から約1時間（霧が残り、光が金色の時間帯）
    "LAT": 37.4875, "LON": 139.9297,     # 鶴ヶ城の位置（緯度・経度）
    "VIEW": "AUTO",             # 色の見え方：AUTO（AgX）/ "AgX" / "ACES 2.0"（Blender 5.x）
    "EXPOSURE": 0.0,
    "USE_FOG": True,
    "USE_DOF": True,
    "USE_COMPOSITOR": True,     # 光のにじみ（グレア）とレンズのわずかな色ずれ
}
CFG.update(globals().get("AIZU_OVERRIDES", {}))

QUALITY_PRESETS = {
    # res: 解像度 / samples: 最大サンプル / noise: 適応サンプリングのしきい値 / stone: 石垣の格子の細かさ(m)
    "TEST":    dict(res=(1280, 536),  samples=64,  noise=0.03,  stone=0.16, bounces=4, vol_bounces=0, blur=False, bit16=False),
    "PREVIEW": dict(res=(1920, 804),  samples=160, noise=0.02,  stone=0.10, bounces=6, vol_bounces=0, blur=True,  bit16=False),
    "FINAL":   dict(res=(3840, 1608), samples=512, noise=0.012, stone=0.05, bounces=8, vol_bounces=1, blur=True,  bit16=True),
}

PREFIX = "AZ_"
ROOT_NAME = "AZ_会津若松城1868"
BV = bpy.app.version

# =============================================================================
# 1. 史料と推測（寸法の単位は m。水面を高さ 0、+Y を北、+X を東とする）
# =============================================================================
# 【資料】天守は外観五層（加藤明成の代、寛永16年＝1639年に五層へ改築とされる。城主名には異説あり）
# 【資料】壁は白亜（白漆喰）。屋根は赤瓦（鉄分を含む釉薬の瓦。採用は1643年説・1648年説あり）
# 【資料】天守台などの石垣は野面積み（蒲生氏郷の時代のものが残るとされる）
# 【資料】天守は明治7年（1874年）に取り壊され、石垣だけが残った。現在の天守は1965年の再建
# 以下の寸法・配置はすべて【推測】（古写真・現地資料と照合して直す前提の仮の値）
LAYOUT = {
    "HON_Z": 16.0,              # 【推測】本丸の高さ（水面から石垣の天端まで）
    "HON_X0": -180.0, "HON_X1": 140.0, "HON_Y1": 230.0,   # 【推測】本丸の範囲（南の天端が y=0）
    "BATTER": 6.5,              # 【推測】石垣の傾き（天端から根元までの水平距離）
    "CONCAVE": 1.7,             # 石垣の反り（扇の勾配）
    "WALL_BOTTOM": -1.5,        # 水面下の石垣の根元
    "MOAT_OUT": (-255.0, 215.0, -108.0, 320.0),  # 【推測】内堀の外側の岸（西, 東, 南, 北）。南側の堀幅は約100m
    "BANK_Z": 2.4,              # 堀の外の地面の高さ
    "TENSHU_C": (-20.0, 14.0),  # 【推測】天守の中心（本丸の南辺の近く）
    "TENSHUDAI_H": 8.0,         # 【推測】天守台の高さ（本丸の地面から）
    "TENSHUDAI_BATTER": 2.2,
}
# 天守の各重：(幅 W[東西], 奥行 D[南北], 壁の高さ, 屋根の高さ, 軒の出, 千鳥破風を付ける面)
# 【資料】外観五層の層塔型  【推測】各重の寸法、逓減の割合、破風の数と位置、窓の数と位置
TENSHU_LEVELS = [
    (22.0, 19.0, 4.2, 2.6, 3.0, ("E", "W")),
    (18.4, 15.6, 3.4, 2.4, 2.7, ("S", "N")),
    (15.2, 12.6, 3.2, 2.3, 2.5, ("E", "W")),
    (12.2, 9.8,  3.0, 2.2, 2.4, ()),
    (9.4,  7.4,  3.2, 3.6, 2.3, ()),          # 最上重：入母屋屋根
]
ROOF_CURVE, ROOF_LIFT, TOP_LIFT = 1.45, 0.45, 0.6   # 屋根の反り（照り）と隅の反り上がり。城郭らしく控えめに

# カメラ：(フレーム, カメラ位置, 注視点, 焦点距離mm, 絞りF値)
#  内堀の水面すれすれから、朝霧の中の石垣をなめるように上昇し、霧の上に天守が現れる
#  南西から北東を向く：朝日は右前方（逆光ぎみ）、天守の背後に磐梯山（北東約18km）
CAM_KEYS = [
    (1,   (-118.0, -52.0, 1.2),  (-62.0, 2.0, 12.0),  28.0, 2.8),
    (40,  (-117.0, -52.5, 3.0),  (-60.0, 3.0, 15.0),  28.5, 2.8),
    (120, (-113.0, -56.0, 22.0), (-40.0, 10.0, 33.0), 30.5, 4.0),
    (192, (-108.0, -60.0, 40.0), (-22.0, 14.0, 38.0), 33.0, 5.6),
]

ASSUMPTIONS = [
    ("天守の寸法と比率", "各重の幅・奥行・高さ、屋根の勾配と反りは推測。古写真との照合が必要"),
    ("破風の数と位置", "千鳥破風を一・三重目の東西、二重目の南北に置いたのは推測"),
    ("窓", "窓の数・大きさ・格子の形は推測"),
    ("鯱", "大棟の鯱の形・材質（ここでは青銅色）は推測"),
    ("軒裏・破風板", "白漆喰で塗り込めた仕上げは推測"),
    ("天守の位置と天守台の高さ", "本丸南辺の近くに置き、天守台を高さ9mとしたのは推測"),
    ("本丸の石垣の高さ・内堀の幅", "高さ16m・堀幅約75mは推測"),
    ("走長屋・隅櫓・土塀の配置", "天守の東に走長屋、南東隅に二重櫓、西に土塀を置いたのは推測（現存の復元建物を参考にした配置）"),
    ("石の色・大きさ", "石垣の石の色と大きさの分布は推測"),
    ("本丸御殿", "本丸に御殿があったことは確かだが、建物の数・大きさ・配置・屋根の仕上げ（ここでは赤瓦）は推測。霧の中のかたまりとして簡略化"),
    ("松の位置", "本丸の松の本数・位置は推測"),
    ("遠景", "山並みは会津盆地の地形を簡略化したもの。磐梯山の位置（北東約18km）だけ実際の方角に合わせた"),
    ("霧", "朝霧の濃さと高さは演出"),
]

RNG = random.Random(CFG["SEED"])
MAT = {}
COL = {}
CAM = {}
_MESH = {}
STATE = {"times": []}


def log(*args):
    print("[会津若松城]", *args, flush=True)


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


# =============================================================================
# 2. 汎用ユーティリティ（コレクション・メッシュ）
# =============================================================================
def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
    parent = parent if parent is not None else bpy.context.scene.collection
    if c.name not in parent.children:
        parent.children.link(c)
    return c


def cleanup():
    """以前このスクリプトが作ったもの（AZ_ で始まるもの）だけを削除する。"""
    sc = bpy.context.scene
    if sc.world and sc.world.name.startswith(PREFIX):
        sc.world = None
    cng = getattr(sc, "compositing_node_group", None)
    if cng is not None and cng.name.startswith(PREFIX):
        sc.compositing_node_group = None
    root = bpy.data.collections.get(ROOT_NAME)
    if root:
        for ob in list(root.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)

        def rm(c):
            for ch in list(c.children):
                rm(ch)
            bpy.data.collections.remove(c)
        rm(root)
    for ob in list(bpy.data.objects):
        if ob.name.startswith(PREFIX):
            bpy.data.objects.remove(ob, do_unlink=True)
    for data in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights,
                 bpy.data.node_groups, bpy.data.worlds, bpy.data.collections, bpy.data.texts,
                 bpy.data.textures):
        for d in list(data):
            if d.name.startswith(PREFIX) and d.users == 0:
                data.remove(d)
    _MESH.clear()


def new_obj(name, data, col, loc=(0, 0, 0), rot=(0, 0, 0), scl=(1, 1, 1)):
    ob = bpy.data.objects.new(PREFIX + name, data)
    col.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scl
    return ob


def bm_box(bm, sx, sy, sz, c=(0, 0, 0), base=True, rot_z=0.0):
    m = (Matrix.Translation((c[0], c[1], c[2] + (sz / 2 if base else 0)))
         @ Matrix.Rotation(rot_z, 4, 'Z') @ Matrix.Diagonal((sx, sy, sz, 1.0)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)


def bm_beam(bm, p0, p1, t, cyl=False, seg=6):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    if d.length < 1e-6:
        return
    R = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    mid = Matrix.Translation((p0 + p1) / 2)
    if cyl:
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                              radius1=t, radius2=t, depth=d.length, matrix=mid @ R)
    else:
        bmesh.ops.create_cube(bm, size=1.0, matrix=mid @ R @ Matrix.Diagonal((t, t, d.length, 1.0)))


def bm_ico(bm, r, c=(0, 0, 0), scl=(1, 1, 1), sub=2):
    m = Matrix.Translation(c) @ Matrix.Diagonal((scl[0], scl[1], scl[2], 1.0))
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r, matrix=m)


def bm_loft(bm, rings, cap_top=False):
    """長方形のリングを下から順につないで側面を張る。rings: [(幅, 奥行, z), ...]"""
    loops = []
    for (w, d, z) in rings:
        loops.append([bm.verts.new((sx * w / 2, sy * d / 2, z))
                      for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for a, b in zip(loops, loops[1:]):
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_top:
        bm.faces.new(loops[-1])


def rect_ring(w, d, seg):
    """長方形の外周の点列。cf = 隅への近さ（隅=1, 辺の中央=0）"""
    corners = [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]
    pts = []
    for s in range(4):
        (x0, y0), (x1, y1) = corners[s], corners[(s + 1) % 4]
        for k in range(seg):
            u = k / seg
            pts.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, abs(2 * u - 1) ** 4))
    return pts


def bm_jroof(bm, w0, d0, w1, d1, h, rings=7, seg=10, curve=1.7, lift=0.7, flare=0.015,
             t_end=1.0, zoff=0.0, cap=True):
    """反りのある和風の屋根（寄棟・入母屋風）。原点は軒先の高さ。
    w0,d0=軒先の大きさ / w1,d1=上端の大きさ / h=屋根の高さ / lift=隅の反り上がり"""
    loops = []
    for r in range(rings + 1):
        t = t_end * r / rings
        w, d = lerp(w0, w1, t), lerp(d0, d1, t)
        z = zoff + h * (t ** curve)
        loop = []
        for (x, y, cf) in rect_ring(w, d, seg):
            k = (1.0 - t) ** 2
            s = 1.0 + flare * cf * k
            loop.append(bm.verts.new((x * s, y * s, z + lift * cf * k)))
        loops.append(loop)
    n = len(loops[0])
    for a, b in zip(loops, loops[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap and t_end >= 1.0:
        bm.faces.new(loops[-1])


def bm_hips(bm, w0, d0, w1, d1, h, lift, curve=1.7, flare=0.015, zoff=0.1, rad=0.22, n=8):
    """隅棟：屋根の四隅の稜線に沿った丸い棟。"""
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        pts = []
        for i in range(n + 1):
            t = i / n
            k = (1 - t) ** 2
            sc_ = 1 + flare * k
            pts.append((sx * lerp(w0, w1, t) / 2 * sc_, sy * lerp(d0, d1, t) / 2 * sc_,
                        zoff + h * t ** curve + lift * k + rad * 0.7))
        for a, b in zip(pts, pts[1:]):
            bm_beam(bm, a, b, rad, True, 6)


def bm_prism(bm, w, length, h, z0=0.0, c=(0, 0), over=0.0):
    """切妻屋根（三角柱）。棟は Y 方向。over=軒の出。"""
    vs = []
    for y in (-length / 2 - over, length / 2 + over):
        vs.append([bm.verts.new((c[0] - w / 2 - over, c[1] + y, z0)),
                   bm.verts.new((c[0] + w / 2 + over, c[1] + y, z0)),
                   bm.verts.new((c[0], c[1] + y, z0 + h))])
    a, b = vs
    bm.faces.new((a[0], a[2], b[2], b[0]))
    bm.faces.new((a[1], b[1], b[2], a[2]))
    bm.faces.new((a[0], a[1], a[2]))
    bm.faces.new((b[2], b[1], b[0]))


def bm_rough_stone(bm, size, seed):
    """不揃いな切石（隅石）。"""
    r = random.Random(seed)
    m = Matrix.Diagonal((size, size * r.uniform(0.92, 1.0), size * r.uniform(0.9, 1.0), 1.0))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    vs = res["verts"]
    bmesh.ops.bevel(bm, geom=list({e for v in vs for e in v.link_edges}), offset=0.06 * size,
                    segments=2, affect='EDGES')
    for v in bm.verts:
        v.co += Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))) * size * 0.025


def mesh(name, fn, mats, smooth_=False):
    key = PREFIX + name
    if key in _MESH:
        return _MESH[key]
    bm = bmesh.new()
    fn(bm)
    if smooth_:
        for f in bm.faces:
            f.smooth = True
    me = bpy.data.meshes.new(key)
    bm.to_mesh(me)
    bm.free()
    for k in mats:
        me.materials.append(MAT[k])
    _MESH[key] = me
    return me


def multi_mesh(name, parts):
    """複数マテリアルを1メッシュに。parts = [(関数(bm), マテリアルキー), ...]"""
    key = PREFIX + name
    if key in _MESH:
        return _MESH[key]
    bm = bmesh.new()
    keys = []
    for fn, mk in parts:
        if mk not in keys:
            keys.append(mk)
        n0 = len(bm.faces)
        fn(bm)
        bm.faces.ensure_lookup_table()
        for i in range(n0, len(bm.faces)):
            bm.faces[i].material_index = keys.index(mk)
    me = bpy.data.meshes.new(key)
    bm.to_mesh(me)
    bm.free()
    for k in keys:
        me.materials.append(MAT[k])
    _MESH[key] = me
    return me


def add_solidify(ob, t, offset=-1.0):
    m = ob.modifiers.new("Solidify", 'SOLIDIFY')
    m.thickness = t
    m.offset = offset
    return m


def fcurves_of(id_data):
    """アニメーションカーブ一覧（4.x の action.fcurves と 5.x のスロット付きアクションの両対応）。"""
    ad = getattr(id_data, "animation_data", None)
    if ad is None or ad.action is None:
        return []
    act = ad.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        return list(cb.fcurves) if cb else []
    except Exception:
        return []


def add_time_driver(sock, expr):
    """ソケットの値をフレームの式で動かす（簡単な式なので Python の自動実行を許可しなくても動く）。"""
    fc = sock.driver_add("default_value")
    fc.driver.type = 'SCRIPTED'
    fc.driver.expression = expr


# =============================================================================
# 3. シェーダーノードの補助
# =============================================================================
def _in(nt, sock, val):
    if isinstance(val, bpy.types.NodeSocket):
        nt.links.new(val, sock)
    else:
        if isinstance(val, tuple) and len(val) == 3 and sock.type == 'RGBA':
            val = (*val, 1.0)
        sock.default_value = val


def MATH(nt, op, a, b=0.0, clamp_=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp_
    _in(nt, n.inputs[0], a)
    _in(nt, n.inputs[1], b)
    return n.outputs[0]


def MIXC(nt, fac, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = 'RGBA'
    _in(nt, n.inputs[0], fac)
    _in(nt, n.inputs[6], a)
    _in(nt, n.inputs[7], b)
    return n.outputs[2]


def MIXF(nt, fac, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = 'FLOAT'
    _in(nt, n.inputs[0], fac)
    _in(nt, n.inputs[2], a)
    _in(nt, n.inputs[3], b)
    return n.outputs[0]


def MAPR(nt, v, a, b, c=0.0, d=1.0):
    n = nt.nodes.new("ShaderNodeMapRange")
    _in(nt, n.inputs["Value"], v)
    n.inputs["From Min"].default_value = a
    n.inputs["From Max"].default_value = b
    n.inputs["To Min"].default_value = c
    n.inputs["To Max"].default_value = d
    return n.outputs[0]


def SEP(nt, vec):
    n = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(vec, n.inputs[0])
    return n.outputs


def COMB(nt, x, y, z):
    n = nt.nodes.new("ShaderNodeCombineXYZ")
    for i, v in enumerate((x, y, z)):
        _in(nt, n.inputs[i], v)
    return n.outputs[0]


def NOISE(nt, vec, scale, detail=4.0, rough=0.55, w=None):
    n = nt.nodes.new("ShaderNodeTexNoise")
    if w is not None:
        n.noise_dimensions = '4D'
        _in(nt, n.inputs["W"], w)
    nt.links.new(vec, n.inputs["Vector"])
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    return n.outputs["Fac"]


def WHITE(nt, vec):
    n = nt.nodes.new("ShaderNodeTexWhiteNoise")
    n.noise_dimensions = '3D'
    nt.links.new(vec, n.inputs["Vector"])
    return n.outputs["Value"]


def VSCALE(nt, vec, s3):
    n = nt.nodes.new("ShaderNodeVectorMath")
    n.operation = 'MULTIPLY'
    nt.links.new(vec, n.inputs[0])
    n.inputs[1].default_value = s3
    return n.outputs[0]


def COORD(nt, kind="Object"):
    return nt.nodes.new("ShaderNodeTexCoord").outputs[kind]


def POS(nt):
    return nt.nodes.new("ShaderNodeNewGeometry").outputs["Position"]


def NORMAL(nt):
    return nt.nodes.new("ShaderNodeNewGeometry").outputs["Normal"]


def ATTR(nt, name):
    n = nt.nodes.new("ShaderNodeAttribute")
    n.attribute_type = 'GEOMETRY'
    n.attribute_name = name
    return n.outputs["Fac"]


def BUMP(nt, height, strength, distance, bsdf):
    n = nt.nodes.new("ShaderNodeBump")
    n.inputs["Strength"].default_value = strength
    n.inputs["Distance"].default_value = distance
    nt.links.new(height, n.inputs["Height"])
    nt.links.new(n.outputs["Normal"], bsdf.inputs["Normal"])


def new_mat(key, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0):
    m = bpy.data.materials.new(PREFIX + key)
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF") or nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    MAT[key] = m
    return m, nt, b


def simple_mat(key, color, rough=0.6, var=0.15, scale=2.0, metal=0.0):
    m, nt, b = new_mat(key, color, rough, metal)
    if var > 0:
        n = NOISE(nt, COORD(nt), scale)
        dark = tuple(c * (1 - var) for c in color)
        light = tuple(min(1.0, c * (1 + var)) for c in color)
        nt.links.new(MIXC(nt, n, dark, light), b.inputs["Base Color"])
    return m


# =============================================================================
# 4. マテリアル
# =============================================================================
def build_materials():
    # --- 赤瓦：【資料】鉄分を含む釉薬をかけた瓦。【推測】色味・つやの強さ ------------
    #     本瓦葺きの丸瓦の列（下り方向の筋）と、瓦 1 枚ずつのわずかな色の違い・釉薬のつや
    m, nt, b = new_mat("Akagawara", (0.20, 0.045, 0.025), 0.38)
    b.inputs["Coat Weight"].default_value = 0.25          # 釉薬のつや
    b.inputs["Coat Roughness"].default_value = 0.22
    p = SEP(nt, POS(nt))
    nrm = SEP(nt, NORMAL(nt))
    ew = MATH(nt, 'GREATER_THAN', MATH(nt, 'ABSOLUTE', nrm["X"]), MATH(nt, 'ABSOLUTE', nrm["Y"]))
    along = MIXF(nt, ew, p["X"], p["Y"])                   # 列が並ぶ方向（屋根面の向きで切り替え）
    rows = MATH(nt, 'POWER', MATH(nt, 'ABSOLUTE', MATH(nt, 'SINE', MATH(nt, 'MULTIPLY', along, math.pi / 0.30))), 0.55)
    course = MATH(nt, 'POWER', MATH(nt, 'ABSOLUTE', MATH(nt, 'SINE', MATH(nt, 'MULTIPLY', p["Z"], math.pi / 0.17))), 3.0)
    BUMP(nt, MATH(nt, 'ADD', rows, MATH(nt, 'MULTIPLY', course, -0.25)), 0.45, 0.08, b)
    cell = COMB(nt, MATH(nt, 'FLOOR', MATH(nt, 'DIVIDE', along, 0.30)), MATH(nt, 'FLOOR', MATH(nt, 'DIVIDE', p["Z"], 0.17)), 0.0)
    tile = WHITE(nt, cell)
    col = MIXC(nt, tile, (0.13, 0.026, 0.015), (0.21, 0.048, 0.026))
    col = MIXC(nt, MATH(nt, 'MULTIPLY', MAPR(nt, NOISE(nt, COORD(nt), 0.35, 3.0), 0.45, 0.7), 0.5), col, (0.14, 0.05, 0.035))  # 雨だれのくすみ
    nt.links.new(col, b.inputs["Base Color"])
    nt.links.new(MAPR(nt, tile, 0.0, 1.0, 0.32, 0.48), b.inputs["Roughness"])

    # --- 白漆喰：【資料】白亜の壁。【推測】汚れ方（軒下の雨筋・足元のくすみ） -------------
    m, nt, b = new_mat("Shikkui", (0.80, 0.79, 0.75), 0.82)
    co = COORD(nt)
    streak = NOISE(nt, VSCALE(nt, co, (2.4, 2.4, 0.12)), 1.0, 3.0)       # 縦に伸びた雨筋
    blot = NOISE(nt, co, 0.6, 4.0)
    base = MIXC(nt, blot, (0.74, 0.73, 0.69), (0.84, 0.83, 0.79))
    dirt = MATH(nt, 'MULTIPLY', MAPR(nt, streak, 0.5, 0.75), 0.35)
    nt.links.new(MIXC(nt, dirt, base, (0.55, 0.54, 0.50)), b.inputs["Base Color"])
    BUMP(nt, NOISE(nt, co, 14.0, 2.0), 0.08, 0.01, b)

    # --- 窓の奥（暗い室内）・格子 -------------------------------------------------
    simple_mat("Pane", (0.012, 0.011, 0.010), 0.6, 0)
    simple_mat("WoodDark", (0.06, 0.045, 0.032), 0.6, 0.2, 4.0)      # 窓枠・戸
    m, nt, b = new_mat("Shachi", (0.05, 0.075, 0.06), 0.35, 0.85)    # 【推測】鯱（青銅色）
    nt.links.new(MIXC(nt, NOISE(nt, COORD(nt), 3.0), (0.04, 0.06, 0.05), (0.11, 0.15, 0.11)), b.inputs["Base Color"])

    # --- 石垣（野面積み）：石の形はメッシュの凹凸（build_stone_face）で作り、
    #     石ごとの乱数(s_rand)と目地からの距離(s_joint)を頂点属性から読む --------------
    m, nt, b = new_mat("Ishigaki", (0.4, 0.38, 0.35), 0.86)
    co = COORD(nt)
    s_rand, s_joint = ATTR(nt, "s_rand"), ATTR(nt, "s_joint")
    # 石の色：灰色〜青灰色、ときどき茶色い石
    col = MIXC(nt, s_rand, (0.20, 0.20, 0.19), (0.46, 0.45, 0.42))
    brown = MATH(nt, 'MULTIPLY', MATH(nt, 'GREATER_THAN', MATH(nt, 'FRACT', MATH(nt, 'MULTIPLY', s_rand, 7.31)), 0.72), 0.7)
    col = MIXC(nt, brown, col, (0.36, 0.29, 0.21))
    detail = NOISE(nt, co, 2.2, 6.0)
    col = MIXC(nt, MATH(nt, 'MULTIPLY', detail, 0.5), col, (0.13, 0.13, 0.12))               # 石肌の斑
    lichen = MATH(nt, 'MULTIPLY', MAPR(nt, NOISE(nt, co, 0.9, 4.0), 0.55, 0.72), 0.55)
    col = MIXC(nt, lichen, col, (0.52, 0.53, 0.46))                                        # 地衣類の白っぽい斑
    wz = SEP(nt, POS(nt))["Z"]
    wet = MAPR(nt, MATH(nt, 'ADD', wz, MATH(nt, 'MULTIPLY', detail, 0.8)), 1.6, -0.1)       # 水際は濡れて暗い
    moss = MATH(nt, 'MULTIPLY', MAPR(nt, wz, 4.5, 0.3), MAPR(nt, NOISE(nt, co, 0.45, 3.0), 0.42, 0.62))
    joint_moss = MATH(nt, 'MULTIPLY', MAPR(nt, s_joint, 0.25, 0.0), MAPR(nt, NOISE(nt, co, 0.3, 2.0), 0.45, 0.6))
    col = MIXC(nt, MATH(nt, 'MULTIPLY', MATH(nt, 'MAXIMUM', moss, joint_moss), 0.75), col, (0.07, 0.10, 0.04))
    col = MIXC(nt, MATH(nt, 'MULTIPLY', wet, 0.7), col, (0.045, 0.05, 0.045))
    stain = MATH(nt, 'MULTIPLY', MAPR(nt, NOISE(nt, VSCALE(nt, co, (1.5, 1.5, 0.08)), 1.0, 3.0), 0.55, 0.75), 0.35)
    col = MIXC(nt, stain, col, (0.10, 0.09, 0.08))                                         # 上から流れた雨の染み
    col = MIXC(nt, MAPR(nt, s_joint, 0.12, 0.0), col, (0.02, 0.019, 0.017))                # 目地の暗がり
    nt.links.new(col, b.inputs["Base Color"])
    nt.links.new(MATH(nt, 'SUBTRACT', 0.9, MATH(nt, 'MULTIPLY', wet, 0.5)), b.inputs["Roughness"])
    BUMP(nt, MATH(nt, 'ADD', detail, MATH(nt, 'MULTIPLY', NOISE(nt, co, 9.0, 3.0), 0.4)), 0.35, 0.03, b)

    # --- 隅石（算木積みの切石） ---------------------------------------------------
    m, nt, b = new_mat("IshigakiBlock", (0.5, 0.48, 0.44), 0.85)
    co = COORD(nt)
    n1 = NOISE(nt, co, 2.0, 6.0)
    col = MIXC(nt, n1, (0.30, 0.29, 0.27), (0.50, 0.49, 0.46))
    wz = SEP(nt, POS(nt))["Z"]
    col = MIXC(nt, MATH(nt, 'MULTIPLY', MAPR(nt, wz, 1.6, -0.1), 0.7), col, (0.05, 0.05, 0.045))
    nt.links.new(col, b.inputs["Base Color"])
    BUMP(nt, MATH(nt, 'ADD', n1, MATH(nt, 'MULTIPLY', NOISE(nt, co, 8.0), 0.3)), 0.45, 0.05, b)

    # --- 水（内堀）：深い緑がかった水。さざ波を時間で動かす ---------------------------
    m, nt, b = new_mat("Water", (0.005, 0.016, 0.014), 0.03)
    b.inputs["IOR"].default_value = 1.333
    co = COORD(nt)
    w1 = NOISE(nt, VSCALE(nt, co, (1.0, 2.2, 1.0)), 0.18, 2.0, 0.5, w=0.0)
    w2 = NOISE(nt, co, 1.4, 3.0, 0.5, w=0.0)
    for nd in nt.nodes:
        if nd.bl_idname == "ShaderNodeTexNoise" and nd.noise_dimensions == '4D':
            add_time_driver(nd.inputs["W"], "frame/150")
    BUMP(nt, MATH(nt, 'ADD', w1, MATH(nt, 'MULTIPLY', w2, 0.3)), 0.12, 0.15, b)

    # --- 地面・草・土・砂利 -------------------------------------------------------
    m, nt, b = new_mat("Grass", (0.08, 0.10, 0.04), 0.95)
    nt.links.new(MIXC(nt, NOISE(nt, POS(nt), 0.08, 5.0), (0.05, 0.075, 0.03), (0.12, 0.13, 0.05)), b.inputs["Base Color"])
    simple_mat("Earth", (0.20, 0.16, 0.11), 0.95, 0.25, 0.3)
    simple_mat("Gravel", (0.33, 0.31, 0.27), 0.95, 0.12, 0.6)
    simple_mat("Ita", (0.13, 0.11, 0.09), 0.85, 0.2, 1.0)            # 城下の屋根（遠景）
    simple_mat("PineLeaf", (0.022, 0.05, 0.022), 0.85, 0.25, 0.8)
    simple_mat("Bark", (0.09, 0.065, 0.05), 0.9, 0.2, 2.0)
    simple_mat("TreeFar", (0.03, 0.05, 0.03), 0.95, 0.2, 0.05)

    # --- 遠景の山：距離に応じて空の色へ溶かす（空気遠近法） ---------------------------
    m, nt, b = new_mat("Mountain", (0.05, 0.07, 0.06), 1.0)
    cam_d = nt.nodes.new("ShaderNodeCameraData")
    far = MAPR(nt, cam_d.outputs["View Distance"], 3000.0, 22000.0, 0.45, 0.93)
    haze = nt.nodes.new("ShaderNodeRGB")
    haze.name = "Haze"
    haze.outputs[0].default_value = (0.55, 0.62, 0.75, 1.0)
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(haze.outputs[0], em.inputs["Color"])
    em.inputs["Strength"].default_value = 0.32
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(far, mix.inputs[0])
    nt.links.new(b.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    MAT["MountainHaze"] = haze

    # --- 朝霧（ボリューム）：水面近くほど濃く、上端は波打つ。ゆっくり流れる -----------------
    m = bpy.data.materials.new(PREFIX + "Fog")
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.93, 0.94, 0.96, 1.0)
    vol.inputs["Anisotropy"].default_value = 0.5               # 前方散乱：太陽側の霧が金色に光る
    pos = POS(nt)
    pz = SEP(nt, pos)["Z"]
    drift = nt.nodes.new("ShaderNodeVectorMath")                # 霧が東へゆっくり流れる
    drift.operation = 'ADD'
    nt.links.new(pos, drift.inputs[0])
    for i, expr in ((0, "frame*0.05"), (1, "frame*0.012")):
        fc = drift.inputs[1].driver_add("default_value", i)
        fc.driver.type = 'SCRIPTED'
        fc.driver.expression = expr
    big = NOISE(nt, drift.outputs[0], 0.012, 3.0, 0.55)        # 霧の塊（約80m）
    small = NOISE(nt, drift.outputs[0], 0.06, 4.0, 0.6)        # 細かなちぎれ（約15m）
    top_wave = MATH(nt, 'ADD', MATH(nt, 'MULTIPLY', MATH(nt, 'SUBTRACT', big, 0.5), 12.0),
                    MATH(nt, 'MULTIPLY', MATH(nt, 'SUBTRACT', small, 0.5), 4.0))
    fog_top = nt.nodes.new("ShaderNodeValue")
    fog_top.name = fog_top.label = "FogTop"
    fog_top.outputs[0].default_value = 27.0                     # 霧の層の上端（m）。天守台の少し上まで
    rel = MATH(nt, 'SUBTRACT', MATH(nt, 'ADD', fog_top.outputs[0], top_wave), pz)
    layer = MAPR(nt, rel, -3.0, 11.0, 0.0, 1.0)                 # 上端から 11m 下で最も濃い
    layer = MATH(nt, 'MULTIPLY', layer, layer)
    patch = MAPR(nt, MATH(nt, 'ADD', MATH(nt, 'MULTIPLY', big, 0.7), MATH(nt, 'MULTIPLY', small, 0.3)), 0.30, 0.66, 0.15, 1.15)
    fog_d = nt.nodes.new("ShaderNodeValue")
    fog_d.name = fog_d.label = "FogDensity"
    fog_d.outputs[0].default_value = 0.019                      # 霧の中の見通し 約100〜200m
    haze_d = nt.nodes.new("ShaderNodeValue")
    haze_d.name = haze_d.label = "HazeDensity"
    haze_d.outputs[0].default_value = 0.0009                    # 全体のかすみ（見通し 約3km）
    dens = MATH(nt, 'ADD', MATH(nt, 'MULTIPLY', MATH(nt, 'MULTIPLY', layer, patch), fog_d.outputs[0]), haze_d.outputs[0])
    nt.links.new(dens, vol.inputs["Density"])
    # 霧の中で何度も散乱した光（多重散乱）を、濃さに比例する発光で近似する。
    #  これがないと霧が灰色に沈む（散乱を何回も追うと、描画時間が数倍になる）
    glow = nt.nodes.new("ShaderNodeValue")
    glow.name = glow.label = "FogGlow"
    glow.outputs[0].default_value = 0.42
    vol.inputs["Emission Color"].default_value = (0.84, 0.89, 1.0, 1.0)     # 空の光を受けた青みの白（日なたは太陽の散乱で暖色に）
    nt.links.new(MATH(nt, 'MULTIPLY', dens, glow.outputs[0]), vol.inputs["Emission Strength"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    MAT["Fog"] = m


# =============================================================================
# 5. 太陽の位置（日付・緯度経度から計算）と空
# =============================================================================
def solar_position(dt_utc, lat, lon):
    """太陽の方位（北=0, 東=90）と高度（度）。精度は約0.1度（映像には十分）。"""
    n = (dt_utc - datetime.datetime(2000, 1, 1, 12)).total_seconds() / 86400.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24
    ha = math.radians((gmst * 15 + lon) % 360) - ra
    la = math.radians(lat)
    el = math.asin(math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.sin(ha), math.tan(dec) * math.cos(la) - math.sin(la) * math.cos(ha))
    return math.degrees(az) % 360, math.degrees(el)


def sun_for_shot():
    """指定日の日の出（太陽の上端が地平線に出る時刻）から MIN_AFTER_SUNRISE 分後の太陽。"""
    y, m, d = CFG["DATE"]
    lmt = datetime.timedelta(hours=CFG["LON"] / 15.0)       # 当時の地方時（UTC との差）
    t = datetime.datetime(y, m, d, 3, 0) - lmt
    for _ in range(6 * 60):
        if solar_position(t, CFG["LAT"], CFG["LON"])[1] > -0.83:
            break
        t += datetime.timedelta(minutes=1)
    sunrise_local = t + lmt
    t += datetime.timedelta(minutes=CFG["MIN_AFTER_SUNRISE"])
    az, el = solar_position(t, CFG["LAT"], CFG["LON"])
    log("日の出（地方時）%s、ショットの太陽：方位 %.1f°、高度 %.1f°" % (sunrise_local.strftime("%H:%M"), az, el))
    return az, el


def sun_dir_vec(az, el):
    a, e = math.radians(az), math.radians(el)
    return (math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e))


def sun_color(el):
    """太陽の高さに応じた色（地平線近くほど赤い）。"""
    t = smooth(0.0, 25.0, el)
    return (1.0, lerp(0.50, 0.86, t), lerp(0.26, 0.72, t))


def build_world(az, el):
    w = bpy.data.worlds.new(PREFIX + "World")
    if hasattr(w, "use_nodes") and not w.use_nodes:
        w.use_nodes = True
    bpy.context.scene.world = w
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    types = [i.identifier for i in sky.bl_rna.properties["sky_type"].enum_items]
    for t in ("MULTIPLE_SCATTERING", "NISHITA", "HOSEK_WILKIE"):
        if t in types:
            sky.sky_type = t
            break
    sky.sun_disc = False                       # 太陽そのものは太陽ライトで（影がきれいに出る）
    sky.sun_elevation = math.radians(max(el, 0.5))
    sky.sun_rotation = math.radians(az)        # sun_rotation は方位（北=0, 東=90）と一致（実測で確認）
    for attr, val in (("altitude", 220.0), ("air_density", 1.0), ("aerosol_density", 3.0),
                      ("dust_density", 3.0), ("ozone_density", 1.0), ("turbidity", 4.0)):
        if hasattr(sky, attr):
            setattr(sky, attr, val)
    sky_col = sky.outputs[0]
    # 高い雲（高積雲）：視線を高さ約2.5kmの面に投影したノイズ。太陽側ほど金色に、反対側は青灰色に
    #  （ボリュームの雲より軽く、4Kでも描画時間がほとんど増えない）
    view = nt.nodes.new("ShaderNodeVectorMath")
    view.operation = 'NORMALIZE'
    nt.links.new(nt.nodes.new("ShaderNodeTexCoord").outputs["Generated"], view.inputs[0])
    v = SEP(nt, view.outputs["Vector"])
    vz = MATH(nt, 'MAXIMUM', v["Z"], 0.03)
    plane = COMB(nt, MATH(nt, 'DIVIDE', v["X"], vz), MATH(nt, 'DIVIDE', v["Y"], vz), 0.0)
    n1 = NOISE(nt, plane, 0.9, 7.0, 0.62)
    n2 = NOISE(nt, VSCALE(nt, plane, (5.0, 9.0, 1.0)), 1.0, 4.0, 0.6)          # 筋状の細かな雲
    cover = MAPR(nt, MATH(nt, 'ADD', n1, MATH(nt, 'MULTIPLY', n2, 0.25)), 0.60, 0.80)
    cover = MATH(nt, 'MULTIPLY', cover, MAPR(nt, v["Z"], 0.03, 0.22))           # 地平線近くは薄く
    sd = sun_dir_vec(az, el)
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = 'DOT_PRODUCT'
    nt.links.new(view.outputs["Vector"], dot.inputs[0])
    dot.inputs[1].default_value = sd
    glow = MATH(nt, 'POWER', MAPR(nt, dot.outputs["Value"], 0.2, 1.0), 2.0)
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(sky_col, bw.inputs[0])
    tint = MIXC(nt, glow, (0.80, 0.83, 0.92), (1.0, 0.70, 0.42))
    sc_ = nt.nodes.new("ShaderNodeVectorMath")
    sc_.operation = 'SCALE'
    nt.links.new(tint, sc_.inputs[0])
    nt.links.new(MATH(nt, 'MULTIPLY', bw.outputs[0], MATH(nt, 'ADD', 0.95, MATH(nt, 'MULTIPLY', glow, 2.2))), sc_.inputs["Scale"])
    cloud_amt = nt.nodes.new("ShaderNodeValue")
    cloud_amt.name = cloud_amt.label = "CloudAmount"
    cloud_amt.outputs[0].default_value = 0.85
    sky_col = MIXC(nt, MATH(nt, 'MULTIPLY', cover, cloud_amt.outputs[0]), sky_col, sc_.outputs[0])
    nt.links.new(sky_col, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.09 if sky.sky_type != "HOSEK_WILKIE" else 0.4
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    log("空：", sky.sky_type)


def build_sun(az, el):
    ld = bpy.data.lights.new(PREFIX + "Sun", 'SUN')
    ob = new_obj("Sun", ld, COL["env"])
    ob.rotation_euler = (math.radians(90 - max(el, 0.5)), 0.0, math.radians(180 - az))
    ld.color = sun_color(el)
    ld.energy = 7.0
    ld.angle = math.radians(0.53)              # 太陽の見かけの大きさ
    CAM["sun"] = ob


# =============================================================================
# 6. 石垣（野面積み）：Voronoi で石を並べ、メッシュを実際に凹凸させる
# =============================================================================
def _hash(iu, iv, seed):
    h = (iu.astype(np.uint64) * np.uint64(73856093)) ^ (iv.astype(np.uint64) * np.uint64(19349663)) \
        ^ np.uint64((seed * 83492791) & 0xffffffff)
    h ^= h >> np.uint64(13)
    h *= np.uint64(0x5bd1e995)
    h ^= h >> np.uint64(15)
    return h


def voronoi(u, v, cu, cv, seed):
    """2D Voronoi：最も近い石の中心までの距離 d1、2番目 d2、石ごとの乱数。距離は石の大きさで正規化。"""
    gu = np.floor(u / cu).astype(np.int64)
    gv = np.floor(v / cv).astype(np.int64)
    d1 = np.full(u.shape, 1e9)
    d2 = np.full(u.shape, 1e9)
    h1 = np.zeros(u.shape, np.uint64)
    for du in (-1, 0, 1):
        for dv in (-1, 0, 1):
            iu, iv = gu + du, gv + dv
            h = _hash(iu, iv, seed)
            ju = (h & np.uint64(0xffff)).astype(np.float64) / 65535.0
            jv = ((h >> np.uint64(16)) & np.uint64(0xffff)).astype(np.float64) / 65535.0
            su = (iu + 0.05 + 0.9 * ju) * cu
            sv = (iv + 0.15 + 0.7 * jv) * cv            # 縦方向のばらつきを抑え、横長の石が段に並ぶ
            d = np.hypot((u - su) / cu, (v - sv) / cv)
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d))
            h1 = np.where(closer, h, h1)
            d1 = np.where(closer, d, d1)
    rnd = ((h1 >> np.uint64(32)) & np.uint64(0xffff)).astype(np.float64) / 65535.0
    return d1, d2, rnd


def stone_relief(s, z, seed, amp):
    """野面積みの凹凸。大きな石（約1.3m×0.9m）のすき間に小さな間詰石を詰める。
    戻り値：(出っ張り[m], 石ごとの乱数, 目地からの近さ 0=目地)"""
    d1, d2, rb = voronoi(s, z, 1.75, 1.05, seed)        # 大石：約1.7m×1.0m（大きさは不揃い）
    eb = d2 - d1                                        # 目地（境界）からの距離に相当
    d1s, d2s, rs = voronoi(s, z, 0.52, 0.38, seed + 17)
    es = d2s - d1s
    face_b = np.clip(eb / 0.22, 0, 1) ** 0.35           # 石の面は平たく、縁だけが丸く落ちる
    face_s = np.clip(es / 0.25, 0, 1) ** 0.45
    # 石ごとの傾き（自然石の面は壁と平行ではない）：乱数から作った向きで面を少し傾ける
    tilt = (np.sin(rb * 37.0) * (s / 1.75 % 1.0 - 0.5) + np.cos(rb * 53.0) * (z / 1.05 % 1.0 - 0.5)) * 0.5
    k = np.clip((eb - 0.07) / 0.10, 0, 1)                # 0 = 大石のすき間（間詰石の領域）
    k = k * k * (3 - 2 * k)
    h_big = amp * (0.25 + 0.75 * face_b) * (0.55 + 0.9 * rb) * (1.0 + 0.45 * tilt)
    h_small = amp * 0.5 * face_s * (0.6 + 0.8 * rs)
    h = h_small * (1 - k) + h_big * k
    rand = np.where(k > 0.5, rb, rs)
    joint = np.minimum(np.clip(eb / 0.07, 0, 1) * k + np.clip(es / 0.10, 0, 1) * (1 - k), 1.0)
    return h, rand, joint


def build_stone_face(name, p0, dvec, nvec, length, z_bot, z_top, batter, concave, res, seed,
                     ext0=True, ext1=True, amp=0.30):
    """石垣の 1 面。p0=天端の始点(x,y)、dvec=面に沿った向き、nvec=外向きの法線、
    ext0/ext1=両端が出隅か（出隅なら根元ほど外へ張り出し、隣の面とつながる）。"""
    H = z_top - z_bot
    nz = max(2, int(math.ceil(H / res)) + 1)
    L_max = length + 2 * batter
    nu = max(2, int(math.ceil(L_max / res)) + 1)
    t = np.linspace(0.0, 1.0, nz)                       # 0=根元, 1=天端
    off = batter * (1 - t) ** concave                   # 天端からの張り出し
    u = np.linspace(0.0, 1.0, nu)
    T, U = np.meshgrid(t, u, indexing="ij")
    OFF = np.repeat(off[:, None], nu, axis=1)
    s0 = -OFF * (1.0 if ext0 else 0.0)
    s1 = length + OFF * (1.0 if ext1 else 0.0)
    S = s0 + (s1 - s0) * U                              # 面に沿った位置（m）
    Z = z_bot + H * T
    h, rnd, joint = stone_relief(S, Z, seed, amp)
    # 出隅の近く（隅石の裏）と天端は凹凸を弱める（隣の面との継ぎ目を隠す）
    dist_end = np.minimum(S - s0 if ext0 else 99.0, s1 - S if ext1 else 99.0)
    taper = np.clip(dist_end / 1.4, 0, 1) * np.clip((z_top - Z) / 0.6, 0, 1)
    h = h * taper
    px = p0[0] + dvec[0] * S + nvec[0] * (OFF + h)
    py = p0[1] + dvec[1] * S + nvec[1] * (OFF + h)
    verts = np.stack([px, py, Z], axis=-1).reshape(-1, 3)
    idx = np.arange(nz * nu).reshape(nz, nu)
    a, b_, c, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]
    faces = np.stack([a, b_, c, d], axis=-1).reshape(-1, 4)
    me = bpy.data.meshes.new(PREFIX + name)
    me.from_pydata(verts.tolist(), [], faces.tolist())
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    for attr, arr in (("s_rand", rnd), ("s_joint", joint)):
        at = me.attributes.new(attr, 'FLOAT', 'POINT')
        at.data.foreach_set("value", arr.reshape(-1).astype(np.float32))
    me.materials.append(MAT["Ishigaki"])
    me.update()
    ob = new_obj(name, me, COL["ishigaki"])
    return ob


def build_corner_stones(name, corner, n_a, n_b, z_bot, z_top, batter, concave, seed):
    """出隅の隅石（算木積み）：長い石の向きを段ごとに交互に変えて積む。"""
    r = random.Random(seed)
    stones = [mesh("cornerstone%d" % k, lambda bm, k=k: bm_rough_stone(bm, 1.0, 900 + k), ["IshigakiBlock"], True)
              for k in range(5)]
    away_a = Vector((n_b[0], n_b[1])) * -1.0           # 面Aの上を隅から離れる向き（= 面Bの内向き）
    away_b = Vector((n_a[0], n_a[1])) * -1.0
    na, nb = Vector(n_a), Vector(n_b)
    z = z_bot + 0.1
    layer = 0
    while z < z_top - 0.45:
        hgt = r.uniform(0.78, 0.95)
        t = (z + hgt / 2 - z_bot) / (z_top - z_bot)
        off = batter * (1 - t) ** concave
        cpt = Vector(corner) + (na + nb) * off
        L = r.uniform(2.0, 2.7)
        w = r.uniform(0.95, 1.15)
        if layer % 2 == 0:
            ctr = cpt + away_a * (L / 2) - na * (w / 2)
            rot = math.atan2(away_a.y, away_a.x)
        else:
            ctr = cpt + away_b * (L / 2) - nb * (w / 2)
            rot = math.atan2(away_b.y, away_b.x)
        ob = new_obj("%s_%02d" % (name, layer), stones[layer % 5], COL["ishigaki"],
                     (ctr.x, ctr.y, z + hgt / 2), (0, 0, rot), (L, w, hgt))
        z += hgt + 0.03
        layer += 1


def build_ishigaki():
    q = QUALITY_PRESETS[CFG["QUALITY"]]
    res = q["stone"]
    hz, B, C = LAYOUT["HON_Z"], LAYOUT["BATTER"], LAYOUT["CONCAVE"]
    x0, x1, y1 = LAYOUT["HON_X0"], LAYOUT["HON_X1"], LAYOUT["HON_Y1"]
    zb = LAYOUT["WALL_BOTTOM"]
    # 本丸の南面（カメラの正面）は細かく、東西の面は粗く
    build_stone_face("Ishigaki_S", (x0, 0.0), (1, 0), (0, -1), x1 - x0, zb, hz, B, C, res, 11)
    build_stone_face("Ishigaki_E", (x1, 0.0), (0, 1), (1, 0), y1, zb, hz, B, C, res * 2.2, 12)
    build_stone_face("Ishigaki_W", (x0, y1), (0, -1), (-1, 0), y1, zb, hz, B, C, res * 2.2, 13)
    build_corner_stones("CornerSE", (x1, 0.0), (0, -1), (1, 0), zb, hz, B, C, 21)
    build_corner_stones("CornerSW", (x0, 0.0), (-1, 0), (0, -1), zb, hz, B, C, 22)
    # 天守台
    tx, ty = LAYOUT["TENSHU_C"]
    W1, D1 = TENSHU_LEVELS[0][0] + 2.4, TENSHU_LEVELS[0][1] + 2.4
    tb, th = LAYOUT["TENSHUDAI_BATTER"], LAYOUT["TENSHUDAI_H"]
    z0, z1 = hz - 0.4, hz + th
    xa, xb, ya, yb = tx - W1 / 2, tx + W1 / 2, ty - D1 / 2, ty + D1 / 2
    tres = res * 1.2
    build_stone_face("Tenshudai_S", (xa, ya), (1, 0), (0, -1), W1, z0, z1, tb, 1.4, tres, 31)
    build_stone_face("Tenshudai_E", (xb, ya), (0, 1), (1, 0), D1, z0, z1, tb, 1.4, tres, 32)
    build_stone_face("Tenshudai_N", (xb, yb), (-1, 0), (0, 1), W1, z0, z1, tb, 1.4, tres * 2, 33)
    build_stone_face("Tenshudai_W", (xa, yb), (0, -1), (-1, 0), D1, z0, z1, tb, 1.4, tres, 34)
    for k, (cx, cy, na, nb) in enumerate(((xa, ya, (-1, 0), (0, -1)), (xb, ya, (0, -1), (1, 0)),
                                          (xb, yb, (1, 0), (0, 1)), (xa, yb, (0, 1), (-1, 0)))):
        build_corner_stones("TenshudaiCorner%d" % k, (cx, cy), na, nb, z0, z1, tb, 1.4, 40 + k)
    # 天守台の上面
    new_obj("TenshudaiTop", mesh("tenshudai_top", lambda bm: bm_box(bm, W1, D1, 0.3, c=(tx, ty, z1 - 0.3)), ["Gravel"]), COL["ishigaki"])
    LAYOUT["TENSHU_BASE_Z"] = z1


# =============================================================================
# 7. 地形：水面・本丸の地面・堀の外の岸・遠景
# =============================================================================
def build_terrain():
    c = COL["env"]
    hz = LAYOUT["HON_Z"]
    x0, x1, y1 = LAYOUT["HON_X0"], LAYOUT["HON_X1"], LAYOUT["HON_Y1"]
    ox0, ox1, oy0, oy1 = LAYOUT["MOAT_OUT"]
    bz = LAYOUT["BANK_Z"]
    new_obj("Water", mesh("water", lambda bm: bm_box(bm, ox1 - ox0 + 20, oy1 - oy0 + 20, 0.02,
                                                       c=((ox0 + ox1) / 2, (oy0 + oy1) / 2, -0.02)), ["Water"]), c)
    new_obj("HonmaruTop", mesh("hon_top", lambda bm: bm_box(bm, x1 - x0, y1, 0.3, c=((x0 + x1) / 2, y1 / 2, hz - 0.3)), ["Gravel"]), c)
    # 本丸の上の芝（天端の縁沿い）
    new_obj("HonmaruGrass", mesh("hon_grass", lambda bm: bm_box(bm, x1 - x0 - 1.0, 3.0, 0.32, c=((x0 + x1) / 2, 1.9, hz - 0.3)), ["Grass"]), c)
    # 堀の外の地面（土手の斜面＋平地）。堀の外形の穴をあけた大きな面
    R = 30000.0

    def ground(bm):
        o = [bm.verts.new((x, y, bz)) for x, y in ((-R, -R), (R, -R), (R, R), (-R, R))]
        i_ = [bm.verts.new((x, y, bz)) for x, y in ((ox0 - 6, oy0 - 6), (ox1 + 6, oy0 - 6), (ox1 + 6, oy1 + 6), (ox0 - 6, oy1 + 6))]
        for k in range(4):
            j = (k + 1) % 4
            bm.faces.new((o[k], o[j], i_[j], i_[k]))
    new_obj("Ground", mesh("ground", ground, ["Grass"]), c)

    def bank(bm):    # 堀の外側の土手（水面から地面まで）
        rings = [(ox1 - ox0, oy1 - oy0, -1.0), (ox1 - ox0 + 12, oy1 - oy0 + 12, bz)]
        bm_loft(bm, rings)
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bmesh.ops.translate(bm, vec=((ox0 + ox1) / 2, (oy0 + oy1) / 2, 0), verts=bm.verts[:])
    new_obj("Bank", mesh("bank", bank, ["Earth"]), c)


def build_mountains():
    """会津盆地を囲む山並み（簡略化）。北東約18kmに磐梯山。"""
    def fn(bm):
        segs = 360
        first = prev = None
        for k in range(segs):
            az = 360.0 * k / segs
            a = math.radians(az)
            r = 16000 + 4000 * math.sin(math.radians(az * 3 + 40))
            n = 0.5 + 0.5 * math.sin(math.radians(az * 7.3)) * math.cos(math.radians(az * 2.1 + 15))
            east = 0.5 + 0.5 * math.sin(a)
            hgt = 250 + 450 * n + 350 * east
            db = abs(((az - 45.0) + 180) % 360 - 180)          # 磐梯山（北東）
            if db < 14:
                r = 17600
                hgt = max(hgt, 1600 * (1 - db / 14) ** 1.6 + 350)
            x, y = math.sin(a) * r, math.cos(a) * r
            pair = (bm.verts.new((x, y, -50)), bm.verts.new((x * 1.03, y * 1.03, hgt)))
            if prev:
                bm.faces.new((prev[0], pair[0], pair[1], prev[1]))
            else:
                first = pair
            prev = pair
        bm.faces.new((prev[0], first[0], first[1], prev[1]))
    new_obj("Mountains", mesh("mountains", fn, ["Mountain"]), COL["env"])


def build_far_trees_and_town():
    """堀の外の木立と城下の屋根（霧の中のシルエット。配置は推測・簡略化）。"""
    r = random.Random(CFG["SEED"] + 3)
    ox0, ox1, oy0, oy1 = LAYOUT["MOAT_OUT"]
    bz = LAYOUT["BANK_Z"]

    def trees(bm):
        for _ in range(420):
            x, y = r.uniform(-2600, 2600), r.uniform(-300, 3000)
            if ox0 - 30 < x < ox1 + 30 and oy0 - 30 < y < oy1 + 30:
                continue
            s = r.uniform(6, 13)
            bm_ico(bm, s, (x, y, bz + s * 0.9), (1.0, 1.0, r.uniform(0.7, 1.1)), sub=2)
    ft = new_obj("FarTrees", mesh("far_trees", trees, ["TreeFar"]), COL["env"])
    leafy(ft, 3.0, 5.0)

    def town(bm):
        for _ in range(360):
            x, y = r.uniform(-2400, 2400), r.uniform(-1600, 2600)
            if ox0 - 60 < x < ox1 + 60 and oy0 - 60 < y < oy1 + 60:
                continue
            w, l = r.uniform(7, 14), r.uniform(9, 20)
            rot = r.choice((0.0, math.pi / 2))
            bm_box(bm, w, l, 3.2, c=(x, y, bz), rot_z=rot)
    new_obj("FarTown", mesh("far_town", town, ["Ita"]), COL["env"])


# =============================================================================
# 8. 天守・走長屋・隅櫓・土塀・松
# =============================================================================
def window_mesh():
    """窓：暗い室内＋白い枠と縦格子（【推測】形）。正面 -Y。"""
    def frame(bm):
        for (a, b) in (((-0.75, -0.6), (0.75, -0.6)), ((-0.75, 0.6), (0.75, 0.6)),
                       ((-0.75, -0.6), (-0.75, 0.6)), ((0.75, -0.6), (0.75, 0.6))):
            bm_beam(bm, (a[0], -0.12, a[1]), (b[0], -0.12, b[1]), 0.16)
        for k in (-0.45, -0.15, 0.15, 0.45):
            bm_beam(bm, (k, -0.1, -0.55), (k, -0.1, 0.55), 0.08)
    return multi_mesh("tenshu_window", [
        (lambda bm: bm_box(bm, 1.5, 0.14, 1.2, c=(0, -0.04, 0), base=False), "Pane"),
        (frame, "Shikkui"),
    ])


def hafu_mesh(gw, gh, depth):
    """千鳥破風：赤瓦の斜面＋白漆喰の妻壁と破風板（【推測】仕上げ）。正面 -Y。"""
    def slopes(bm):
        A, B, C = (-gw / 2, 0, 0), (gw / 2, 0, 0), (0, 0, gh)
        A2, B2, C2 = (-gw / 2, depth, 0), (gw / 2, depth, 0), (0, depth, gh)
        v = {k: bm.verts.new(p) for k, p in (("A", A), ("B", B), ("C", C), ("A2", A2), ("B2", B2), ("C2", C2))}
        bm.faces.new((v["A"], v["C"], v["C2"], v["A2"]))
        bm.faces.new((v["B"], v["B2"], v["C2"], v["C"]))

    def gable_wall(bm):
        yf = 0.3
        a, b, c_ = bm.verts.new((-gw / 2 + 0.3, yf, 0.1)), bm.verts.new((gw / 2 - 0.3, yf, 0.1)), bm.verts.new((0, yf, gh - 0.3))
        bm.faces.new((a, b, c_))

    def boards(bm):
        bm_beam(bm, (-gw / 2 - 0.2, -0.08, -0.1), (0, -0.08, gh + 0.1), 0.32)
        bm_beam(bm, (gw / 2 + 0.2, -0.08, -0.1), (0, -0.08, gh + 0.1), 0.32)
        bm_box(bm, 0.6, 0.15, 0.8, c=(0, -0.12, gh - 1.0))    # 懸魚
    return multi_mesh("hafu_%.1f_%.1f" % (gw, gh), [(slopes, "Akagawara"), (gable_wall, "Shikkui"), (boards, "Shikkui")])


def roof_set(name, col, cx, cy, z, W0, D0, w1, d1, rh, lift, curve=ROOF_CURVE, ridge=False):
    """屋根一式：軒裏（白漆喰）・赤瓦・隅棟・鬼瓦。原点 z は軒先の高さ。"""
    noji = new_obj(name + "_nokiura", mesh(name + "_nokiura", lambda bm: bm_jroof(bm, W0, D0, w1, d1, rh, lift=lift, curve=curve), ["Shikkui"]), col, (cx, cy, z))
    add_solidify(noji, 0.55)            # 軒の厚み（垂木・茅負を塗り込めた白い軒）
    kawara = new_obj(name + "_kawara", mesh(name + "_kawara", lambda bm: bm_jroof(bm, W0 + 0.1, D0 + 0.1, w1, d1, rh, lift=lift, zoff=0.1, curve=curve), ["Akagawara"]), col, (cx, cy, z))
    add_solidify(kawara, 0.16)
    new_obj(name + "_hips", mesh(name + "_hips", lambda bm: bm_hips(bm, W0 + 0.1, D0 + 0.1, w1, d1, rh, lift, curve=curve, zoff=0.12, rad=0.26), ["Akagawara"], True), col, (cx, cy, z))

    def oni(bm):
        for sx in (-1, 1):
            for sy in (-1, 1):
                bm_box(bm, 0.45, 0.45, 0.6, c=(sx * W0 / 2 * 1.03, sy * D0 / 2 * 1.03, lift - 0.05), rot_z=math.pi / 4)
    new_obj(name + "_oni", mesh(name + "_oni", oni, ["Akagawara"]), col, (cx, cy, z))
    if ridge:
        rl = max(W0, D0) * 0.5
        new_obj(name + "_ridge", mesh(name + "_ridge", lambda bm: bm_box(bm, w1 + 0.6, 0.7, 0.6), ["Akagawara"]), col, (cx, cy, z + rh - 0.1))


def build_tenshu():
    c = COL["tenshu"]
    kx, ky = LAYOUT["TENSHU_C"]
    z = LAYOUT["TENSHU_BASE_Z"]
    n = len(TENSHU_LEVELS)
    win = window_mesh()
    for i, (w, d, h, rh, o, hafu) in enumerate(TENSHU_LEVELS):
        top = i == n - 1
        p = "Tenshu%d" % i
        new_obj(p + "_wall", mesh(p + "_wall", lambda bm, w=w, d=d, h=h: bm_loft(bm, [(w, d, 0.0), (w, d, h + 0.3)], cap_top=False), ["Shikkui"]), c, (kx, ky, z))
        # 窓（各面に等間隔。数は推測）
        k = 0
        for side, ln, rot in (("S", w, 0.0), ("N", w, math.pi), ("E", d, math.pi / 2), ("W", d, -math.pi / 2)):
            nwin = max(2, int(ln / 3.6))
            for j in range(nwin):
                u = (j + 0.5) / nwin - 0.5
                pos = {"S": (kx + u * ln, ky - d / 2 - 0.02), "N": (kx - u * ln, ky + d / 2 + 0.02),
                       "E": (kx + w / 2 + 0.02, ky + u * ln), "W": (kx - w / 2 - 0.02, ky - u * ln)}[side]
                new_obj("%s_win%02d" % (p, k), win, c, (*pos, z + h * 0.56), (0, 0, rot))
                k += 1
        rz = z + h
        if not top:
            w1, d1 = TENSHU_LEVELS[i + 1][0] + 0.6, TENSHU_LEVELS[i + 1][1] + 0.6
            lift = ROOF_LIFT
        else:
            w1, d1 = w * 0.55, 0.5            # 入母屋：棟は東西方向
            lift = TOP_LIFT
        roof_set(p, c, kx, ky, rz, w + 2 * o, d + 2 * o, w1, d1, rh, lift, ridge=top)
        for side in hafu:                     # 千鳥破風（【推測】位置）
            sl = w if side in "SN" else d
            gw, gh = sl * 0.36, rh * 1.25 + 0.5
            R = (d / 2 if side in "SN" else w / 2) + o * 0.55
            pos, rot = {"S": ((kx, ky - R), 0.0), "N": ((kx, ky + R), math.pi),
                        "E": ((kx + R, ky), math.pi / 2), "W": ((kx - R, ky), -math.pi / 2)}[side]
            new_obj("%s_hafu%s" % (p, side), hafu_mesh(gw, gh, 4.6), c, (*pos, rz + rh * 0.1), (0, 0, rot))
        z = rz + rh
    # 入母屋の妻（三角の壁）と鯱（【推測】形・色）
    w_top, d_top = TENSHU_LEVELS[-1][0], TENSHU_LEVELS[-1][1]
    rl = w_top * 0.55
    for sx in (-1, 1):
        def gable(bm, sx=sx):
            a = bm.verts.new((sx * rl / 2, -d_top * 0.36, z - 2.0))
            b = bm.verts.new((sx * rl / 2, d_top * 0.36, z - 2.0))
            c_ = bm.verts.new((sx * rl / 2, 0.0, z - 0.2))
            bm.faces.new((a, b, c_) if sx > 0 else (c_, b, a))
        new_obj("Tenshu_tsuma%+d" % sx, mesh("tenshu_tsuma%+d" % sx, gable, ["Shikkui"]), c, (kx, ky, 0))

        def shachi(bm, sx=sx):
            bm_ico(bm, 0.55, (0, 0, 0.7), (0.7, 0.9, 1.3), sub=2)               # 胴
            bm_ico(bm, 0.45, (0, 0.0, 1.55), (0.6, 0.75, 0.8), sub=1)           # 頭
            bm_ico(bm, 0.5, (0, 0.0, 2.15), (0.25, 0.9, 0.9), sub=1)            # 反り返った尾
        new_obj("Shachi%+d" % sx, mesh("shachi", shachi, ["Shachi"], True), c,
                (kx + sx * (rl / 2 + 0.2), ky, z + 0.25), (0, 0, 0.0 if sx < 0 else math.pi))
    CAM["tenshu_top"] = z


def build_hashiri_nagaya():
    """走長屋（天守の東から南東隅へ）・隅櫓（南東隅）・土塀（天守の西）。配置は【推測】。"""
    c = COL["buildings"]
    hz = LAYOUT["HON_Z"]
    tx, ty = LAYOUT["TENSHU_C"]
    W1 = TENSHU_LEVELS[0][0] + 2.4
    x_start = tx + W1 / 2 - 0.5
    x_end = LAYOUT["HON_X1"] - 16.0
    depth, wh = 6.2, 3.4
    cx, cy, ln = (x_start + x_end) / 2, 0.6 + depth / 2, x_end - x_start
    new_obj("Nagaya_wall", mesh("nagaya_wall", lambda bm: bm_box(bm, ln, depth, wh, c=(0, 0, 0)), ["Shikkui"]), c, (cx, cy, hz))
    # 腰の高さの小窓（狭間・窓。推測）
    win = window_mesh()
    nwin = int(ln / 9.0)
    for j in range(nwin):
        x = x_start + (j + 0.5) * ln / nwin
        new_obj("Nagaya_win%02d" % j, win, c, (x, cy - depth / 2 - 0.02, hz + wh * 0.58), (0, 0, 0), (0.75, 1, 0.7))
    roof_set("Nagaya", c, cx, cy, hz + wh, ln + 2.6, depth + 2.6, ln - 2.0, 0.6, 2.4, 0.35, curve=1.4, ridge=True)
    # 隅櫓（二重櫓）
    kx, ky = LAYOUT["HON_X1"] - 8.0, 6.0
    lv = [(12.0, 10.5, 4.0, 1.9, 1.9), (9.0, 7.8, 3.4, 2.6, 1.8)]
    z = hz
    for i, (w, d, h, rh, o) in enumerate(lv):
        p = "Yagura%d" % i
        new_obj(p + "_wall", mesh(p + "_wall", lambda bm, w=w, d=d, h=h: bm_box(bm, w, d, h + 0.3), ["Shikkui"]), c, (kx, ky, z))
        for side, ln_, rot in (("S", w, 0.0), ("W", d, -math.pi / 2)):
            for j in range(2):
                u = (j + 0.5) / 2 - 0.5
                pos = (kx + u * ln_, ky - d / 2 - 0.02) if side == "S" else (kx - w / 2 - 0.02, ky - u * ln_)
                new_obj("%s_win%s%d" % (p, side, j), win, c, (*pos, z + h * 0.56), (0, 0, rot), (0.8, 1, 0.8))
        top = i == len(lv) - 1
        w1, d1 = (lv[i + 1][0] + 0.6, lv[i + 1][1] + 0.6) if not top else (w * 0.5, 0.5)
        roof_set(p, c, kx, ky, z + h, w + 2 * o, d + 2 * o, w1, d1, rh, 0.6, ridge=top)
        z += h + rh
    # 土塀（天守台の西から南西隅まで）
    x_w0, x_w1 = LAYOUT["HON_X0"] + 1.5, tx - W1 / 2 + 0.5
    ln_w = x_w1 - x_w0

    def dobei(bm):
        bm_box(bm, ln_w, 0.6, 2.3, c=(0, 0, 0))
    new_obj("Dobei", mesh("dobei", dobei, ["Shikkui"]), c, ((x_w0 + x_w1) / 2, 1.2, hz))

    def dobei_roof(bm):
        bm_prism(bm, 1.6, ln_w, 0.55, z0=0.0, over=0.0)
        bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Z'))
    new_obj("Dobei_roof", mesh("dobei_roof", dobei_roof, ["Akagawara"]), c, ((x_w0 + x_w1) / 2, 1.2, hz + 2.3))


def leafy(ob, strength, size):
    """葉の塊の輪郭をもこもこさせる（雲模様のテクスチャで変位）。"""
    name = PREFIX + "Leafy%.1f" % size
    tex = bpy.data.textures.get(name) or bpy.data.textures.new(name, 'CLOUDS')
    tex.noise_depth = 2
    md = ob.modifiers.new("Leafy", 'DISPLACE')
    md.texture = tex
    md.texture_coords = 'GLOBAL'
    md.strength = strength
    md.mid_level = 0.5
    tex.noise_scale = size * 0.1


def build_pines():
    """本丸の松（【推測】本数・位置）。傾いた幹と、横に広がる葉の層（黒松の樹形）。"""
    r = random.Random(CFG["SEED"] + 11)
    c = COL["buildings"]
    variants = []
    for v in range(4):
        rv = random.Random(500 + v)
        h = rv.uniform(9, 14)
        lean = Vector((rv.uniform(-2.0, 2.0), rv.uniform(-2.0, 2.0), 0))
        pads = []
        npad = rv.randint(10, 14)
        for k in range(npad):
            t = 0.38 + 0.62 * k / (npad - 1)
            spread = 3.8 * (1.1 - t)
            ctr = lean * t + Vector((rv.uniform(-spread, spread), rv.uniform(-spread, spread), h * t + rv.uniform(-0.6, 0.6)))
            pads.append((ctr, rv.uniform(1.2, 2.4) * (1.15 - 0.35 * t)))

        def trunk(bm, lean=lean, h=h, pads=pads):
            prev = Vector((0, 0, 0))
            for k in range(1, 5):
                t = k / 4
                p = lean * t + Vector((0, 0, h * t)) + Vector((math.sin(k * 2.1), math.cos(k * 1.7), 0)) * 0.4
                bm_beam(bm, prev, p, 0.42 * (1.1 - 0.5 * t), True, 6)
                prev = p
            for ctr, rad in pads:                       # 枝
                base = lean * (ctr.z / h) + Vector((0, 0, ctr.z - 0.6))
                bm_beam(bm, base, ctr, 0.12, True, 5)

        def foliage(bm, pads=pads):
            for ctr, rad in pads:
                bm_ico(bm, rad, tuple(ctr), (1.6, 1.3, 0.5), sub=3)
        variants.append(multi_mesh("pine%d" % v, [(trunk, "Bark"), (foliage, "PineLeaf")]))
    tx, ty = LAYOUT["TENSHU_C"]

    def free(x, y):
        if abs(x - tx) < 19 and abs(y - ty) < 17:
            return False
        return all(abs(x - gx) > gw / 2 + 5 or abs(y - gy) > gd / 2 + 5 for gx, gy, gw, gd, _h in GOTEN)
    for k in range(12):
        for _ in range(40):
            x = r.uniform(LAYOUT["HON_X0"] + 10, LAYOUT["HON_X1"] - 10)
            y = r.uniform(14, 160)
            if free(x, y):
                break
        ob = new_obj("Pine%02d" % k, variants[k % 4], c, (x, y, LAYOUT["HON_Z"]), (0, 0, r.uniform(0, 6.28)), (1, 1, r.uniform(0.85, 1.2)))
        leafy(ob, 1.2, 1.0)


# 本丸御殿：【資料】江戸時代の本丸には藩主の御殿があった
#           【推測】棟の数・大きさ・配置・屋根（赤瓦とした）。(中心x, 中心y, 幅, 奥行, 壁の高さ)
GOTEN = [
    (-48.0, 58.0, 40.0, 22.0, 4.6),
    (6.0, 52.0, 30.0, 18.0, 4.4),
    (-98.0, 66.0, 28.0, 16.0, 4.2),
    (38.0, 92.0, 34.0, 20.0, 4.4),
    (-22.0, 102.0, 26.0, 14.0, 4.0),
    (-72.0, 116.0, 24.0, 14.0, 4.0),
    (-120.0, 104.0, 22.0, 13.0, 4.0),
    (78.0, 60.0, 22.0, 13.0, 4.0),
]


def build_goten():
    c = COL["buildings"]
    hz = LAYOUT["HON_Z"]
    for k, (x, y, w, d, h) in enumerate(GOTEN):
        p = "Goten%d" % k
        new_obj(p + "_wall", mesh(p + "_wall", lambda bm, w=w, d=d, h=h: bm_box(bm, w, d, h + 0.3), ["WoodDark"]), c, (x, y, hz))
        o = 2.4
        rh = d * 0.36
        roof_set(p, c, x, y, hz + h, w + 2 * o, d + 2 * o, max(1.0, w - d), 0.5, rh, 0.3, curve=1.25, ridge=True)
    # 御殿どうしをつなぐ渡り廊下
    for (a, b) in ((0, 1), (0, 2), (0, 4), (1, 3), (4, 5), (5, 6), (1, 7)):
        xa, ya = GOTEN[a][0], GOTEN[a][1]
        xb, yb = GOTEN[b][0], GOTEN[b][1]
        ln = math.hypot(xb - xa, yb - ya)
        ang = math.atan2(yb - ya, xb - xa)
        p = "Watari%d_%d" % (a, b)

        def body(bm, ln=ln):
            bm_box(bm, ln, 3.2, 3.0)

        def roof(bm, ln=ln):
            bm_prism(bm, 4.6, ln, 1.4, z0=3.0)
            bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Z'))
        new_obj(p, multi_mesh(p, [(body, "WoodDark"), (roof, "Akagawara")]), c,
                ((xa + xb) / 2, (ya + yb) / 2, hz), (0, 0, ang))


def build_fog():
    if not CFG["USE_FOG"]:
        return
    ox0, ox1, oy0, oy1 = LAYOUT["MOAT_OUT"]
    size_x, size_y = 6000.0, 6000.0           # 地平線まで霧とかすみが続く大きさ
    new_obj("Fog", mesh("fog", lambda bm: bm_box(bm, size_x, size_y, 70.0, c=(0, 2000.0, -1.0)), ["Fog"]), COL["env"])


def build_birds():
    """霧の中を横切るカラス（シルエット）。羽ばたきは翼の回転を繰り返す。"""
    simple_mat("Crow", (0.012, 0.012, 0.014), 0.6, 0)
    c = COL["buildings"]

    def body(bm):
        bm_ico(bm, 0.22, (0, 0, 0), (0.8, 2.0, 0.75), sub=2)
        bm_ico(bm, 0.12, (0, 0.42, 0.05), (1, 1.2, 1), sub=1)
        bm_beam(bm, (0, -0.4, 0), (0, -0.72, 0.02), 0.09)

    def wing(bm):
        vs = [bm.verts.new(v) for v in ((0, -0.12, 0), (0.55, -0.2, 0.02), (0.95, -0.05, 0), (0.55, 0.16, 0.01), (0, 0.16, 0))]
        bm.faces.new(vs)
    me_b = mesh("crow_body", body, ["Crow"], True)
    me_w = mesh("crow_wing", wing, ["Crow"])
    flights = [((-48.0, -66.0, 17.0), (-128.0, 6.0, 24.0), 0.0),
               ((-40.0, -58.0, 22.0), (-122.0, 14.0, 27.0), 9.0),
               ((-58.0, -72.0, 14.0), (-136.0, -2.0, 21.0), 17.0)]
    f0, f1 = CFG["FRAME_START"] - 20, CFG["FRAME_END"] + 10
    for k, (a, b, ph) in enumerate(flights):
        a, b = Vector(a), Vector(b)
        d = b - a
        ob = new_obj("Crow%d" % k, me_b, c, a, (0, 0, math.atan2(d.y, d.x) - math.pi / 2), (1.1, 1.1, 1.1))
        for f, t in ((f0, 0.0), (f1, 1.0)):
            ob.location = a.lerp(b, t)
            ob.keyframe_insert("location", frame=f)
        for fc in fcurves_of(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
        for side in (-1, 1):
            w = new_obj("Crow%d_wing%+d" % (k, side), me_w, c, (0, 0, 0), (0, 0, 0), (side, 1, 1))
            w.parent = ob
            for f, ang in ((1 + ph, 0.55), (4 + ph, -0.45), (7 + ph, 0.55)):
                w.rotation_euler = (0, -side * ang, 0)
                w.keyframe_insert("rotation_euler", frame=f)
            for fc in fcurves_of(w):
                fc.modifiers.new('CYCLES')


# =============================================================================
# 9. カメラ
# =============================================================================
def build_camera():
    c = COL["camera"]
    cd = bpy.data.cameras.new(PREFIX + "Camera")
    cd.sensor_fit = 'HORIZONTAL'
    cd.sensor_width = 36.0
    cd.clip_start, cd.clip_end = 0.3, 60000.0
    cam = new_obj("Camera", cd, c)
    tgt = new_obj("CameraTarget", None, c)
    tgt.empty_display_size = 2.0
    con = cam.constraints.new('TRACK_TO')
    con.target = tgt
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    cd.dof.use_dof = CFG["USE_DOF"]
    cd.dof.aperture_blades = 7
    cd.dof.aperture_ratio = 1.25             # わずかに縦長のボケ（アナモフィックレンズ風）
    for f, pos, look, lens, fstop in CAM_KEYS:
        cam.location = pos
        tgt.location = look
        cd.lens = lens
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = (Vector(look) - Vector(pos)).length
        cam.keyframe_insert("location", frame=f)
        tgt.keyframe_insert("location", frame=f)
        cd.keyframe_insert("lens", frame=f)
        cd.dof.keyframe_insert("aperture_fstop", frame=f)
        cd.dof.keyframe_insert("focus_distance", frame=f)
    # クレーン／ドローンらしい、ごくわずかな揺れ
    for ob, strength in ((cam, 0.05), (tgt, 0.08)):
        for fc in fcurves_of(ob):
            if fc.data_path == "location":
                mod = fc.modifiers.new('NOISE')
                mod.scale = 38.0
                mod.strength = strength
                mod.phase = 13.0 * fc.array_index + (7.0 if ob is tgt else 0.0)
    bpy.context.scene.camera = cam
    CAM["cam"] = cam


# =============================================================================
# 10. 描画設定・GPU・合成
# =============================================================================
def setup_device():
    """GPU があれば使う（OptiX → CUDA → HIP → oneAPI → Metal の順に探す）。"""
    sc = bpy.context.scene
    want = CFG["DEVICE"].upper()
    if want == "CPU":
        sc.cycles.device = 'CPU'
        log("描画デバイス：CPU（指定）")
        return "CPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        types = [i.identifier for i in prefs.bl_rna.properties["compute_device_type"].enum_items]
        for t in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            if t not in types:
                continue
            try:
                prefs.compute_device_type = t
                prefs.refresh_devices()
            except Exception:
                continue
            gpus = [d for d in prefs.devices if d.type == t]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == t
                sc.cycles.device = 'GPU'
                names = ", ".join(d.name for d in gpus)
                log("描画デバイス：GPU（%s）%s" % (t, names))
                return "GPU %s %s" % (t, names)
    except Exception as ex:
        log("GPU の確認に失敗：", ex)
    sc.cycles.device = 'CPU'
    log("描画デバイス：CPU（GPU が見つかりません）")
    return "CPU"


def script_dir():
    """このスクリプトのあるフォルダ。Blender の画面（テキストエディタ）から実行したときも探す。"""
    try:
        f = os.path.abspath(__file__)
        if os.path.isfile(f):
            return os.path.dirname(f)
    except NameError:
        pass
    for t in bpy.data.texts:
        if t.filepath and os.path.basename(t.filepath).startswith("aizu_wakamatsu_castle"):
            return os.path.dirname(bpy.path.abspath(t.filepath))
    if bpy.data.filepath:
        return os.path.dirname(bpy.data.filepath)
    return os.path.join(os.path.expanduser("~"), "aizu-castle")    # 例：C:\Users\名前\aizu-castle


def output_dir():
    if CFG["OUTPUT_DIR"]:
        return bpy.path.abspath(CFG["OUTPUT_DIR"])
    return os.path.join(script_dir(), "render", CFG["QUALITY"].lower())


def setup_render():
    sc = bpy.context.scene
    q = QUALITY_PRESETS[CFG["QUALITY"]]
    r = sc.render
    r.engine = 'CYCLES'
    STATE["device"] = setup_device()
    sc.frame_start, sc.frame_end = CFG["FRAME_START"], CFG["FRAME_END"]
    r.fps, r.fps_base = CFG["FPS"], 1.0
    r.resolution_x, r.resolution_y = q["res"]
    r.resolution_percentage = 100
    cy = sc.cycles
    cy.samples = q["samples"]
    cy.use_denoising = True
    for attr, val in (("use_adaptive_sampling", True), ("adaptive_threshold", q["noise"]),
                      ("adaptive_min_samples", 16),
                      ("max_bounces", q["bounces"]), ("diffuse_bounces", 3), ("glossy_bounces", 3),
                      ("transmission_bounces", 2), ("transparent_max_bounces", 8),
                      ("volume_bounces", q["vol_bounces"]), ("blur_glossy", 0.5),
                      ("caustics_reflective", False), ("caustics_refractive", False),
                      ("use_light_tree", True), ("denoiser", 'OPENIMAGEDENOISE'),
                      ("denoising_prefilter", 'ACCURATE'), ("denoising_input_passes", 'RGB_ALBEDO_NORMAL'),
                      ("volume_step_rate", 1.0), ("volume_max_steps", 1024)):
        if hasattr(cy, attr):
            try:
                setattr(cy, attr, val)
            except Exception:
                pass
    if STATE["device"].startswith("GPU") and hasattr(cy, "denoising_use_gpu"):
        cy.denoising_use_gpu = True
    r.use_motion_blur = q["blur"]
    if hasattr(r, "motion_blur_shutter"):
        r.motion_blur_shutter = 0.5           # シャッター角 180°（映画と同じブレ）
    if hasattr(r, "use_persistent_data"):
        r.use_persistent_data = True          # コマ間で BVH を使い回して速くする
    vs = sc.view_settings
    view = CFG["VIEW"]
    applied = False
    for cand in ([view] if view != "AUTO" else []) + ["AgX", "Filmic"]:
        try:
            vs.view_transform = cand
            applied = True
            break
        except Exception:
            continue
    if applied and vs.view_transform == "AgX":
        for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
            try:
                vs.look = look
                break
            except Exception:
                pass
    vs.exposure = CFG["EXPOSURE"]
    out = output_dir()
    os.makedirs(out, exist_ok=True)
    r.filepath = os.path.join(out, "aizu_kiri_")
    ims = r.image_settings
    if hasattr(ims, "media_type"):
        ims.media_type = 'IMAGE'
    if CFG["EXR"]:
        ims.file_format = 'OPEN_EXR_MULTILAYER'
        ims.color_depth = '16'
        for codec in ('DWAA', 'ZIP'):
            try:
                ims.exr_codec = codec
                break
            except Exception:
                pass
        vl = sc.view_layers[0]
        vl.use_pass_z = True
        vl.use_pass_mist = True
        for p in ("use_pass_volume_direct",):
            if hasattr(vl.cycles, p):
                setattr(vl.cycles, p, True)
    else:
        ims.file_format = 'PNG'
        ims.color_mode = 'RGB'
        ims.color_depth = '16' if q["bit16"] else '8'
    STATE["out"] = out


def setup_compositor():
    """光のにじみ（霧と瓦のハイライト）と、レンズのわずかな色ずれ・歪み。4.x と 5.x の両対応。"""
    if not CFG["USE_COMPOSITOR"]:
        return
    sc = bpy.context.scene
    try:
        if hasattr(sc, "compositing_node_group"):          # 5.x
            nt = bpy.data.node_groups.new(PREFIX + "Compositor", "CompositorNodeTree")
            nt.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
            out_sock = nt.nodes.new("NodeGroupOutput").inputs[0]
            sc.compositing_node_group = nt
        else:                                              # 4.x
            sc.use_nodes = True
            nt = sc.node_tree
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            out_sock = nt.nodes.new("CompositorNodeComposite").inputs["Image"]
        rl = nt.nodes.new("CompositorNodeRLayers")
        gl = nt.nodes.new("CompositorNodeGlare")
        if "Type" in gl.inputs:
            gl.inputs["Type"].default_value = "Bloom"
            for name, val in (("Threshold", 0.9), ("Strength", 0.22), ("Size", 0.6), ("Saturation", 0.9)):
                if name in gl.inputs:
                    gl.inputs[name].default_value = val
        else:
            gl.glare_type = 'FOG_GLOW'
            gl.threshold = 0.9
            gl.mix = -0.78
            gl.size = 8
        nt.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ld = nt.nodes.new("CompositorNodeLensdist")
        for name, val in (("Distortion", -0.012), ("Dispersion", 0.006)):
            if name in ld.inputs:
                ld.inputs[name].default_value = val
        for prop in ("use_fit",):
            if hasattr(ld, prop):
                setattr(ld, prop, True)
        if "Fit" in ld.inputs:
            ld.inputs["Fit"].default_value = True
        nt.links.new(gl.outputs["Image"], ld.inputs["Image"])
        nt.links.new(ld.outputs["Image"], out_sock)
        sc.render.use_compositing = True
    except Exception as ex:
        log("合成の設定をスキップ：", ex)


def write_notes():
    """考証メモ（資料で確認できたこと／推測）をシーンのテキストとして残す。"""
    t = bpy.data.texts.new(PREFIX + "考証メモ")
    lines = ["会津若松城（鶴ヶ城）慶応四年（1868）秋 ― 考証メモ", "",
             "【資料で確認できたこと】",
             "・天守は外観五層。寛永16年（1639）に五層へ改築とされる（城主は加藤明成とも加藤嘉明とも）",
             "・壁は白亜（白漆喰）、屋根は鉄分を含む釉薬の赤瓦（採用は1643年説・1648年説）",
             "・石垣は野面積み（蒲生氏郷の時代のものが残るとされる）",
             "・籠城戦は慶応4年8月23日（新暦1868年10月8日）から。このショットはその前の朝",
             "・天守は明治7年（1874）に取り壊され、現在の天守は昭和40年（1965）の再建",
             "", "【推測で作った部分】"]
    lines += ["・%s：%s" % a for a in ASSUMPTIONS]
    t.write("\n".join(lines) + "\n")


def timing_handlers():
    def pre(scene, *args):
        STATE["t0"] = time.time()

    def post(scene, *args):
        dt = time.time() - STATE.get("t0", time.time())
        STATE["times"].append((scene.frame_current, dt))
        try:
            with open(os.path.join(STATE["out"], "timing.csv"), "a", encoding="utf-8") as f:
                f.write("%d,%.2f,%s\n" % (scene.frame_current, dt, STATE.get("device", "")))
        except Exception:
            pass
        log("フレーム %d：%.1f 秒" % (scene.frame_current, dt))
    for h in (bpy.app.handlers.render_pre, bpy.app.handlers.render_post):
        for fn in list(h):
            if getattr(fn, "__name__", "") in ("pre", "post") and getattr(fn, "__module__", "") == __name__:
                h.remove(fn)
    bpy.app.handlers.render_pre.append(pre)
    bpy.app.handlers.render_post.append(post)


# =============================================================================
# 11. 実行
# =============================================================================
def build():
    t0 = time.time()
    if np is None:
        raise RuntimeError("numpy が見つかりません（Blender 同梱の Python で実行してください）")
    cleanup()
    root = coll(ROOT_NAME)
    for key, name in (("env", "地形・空・霧"), ("ishigaki", "石垣"), ("tenshu", "天守"),
                      ("buildings", "走長屋・櫓・塀・松"), ("camera", "カメラ")):
        COL[key] = coll(PREFIX + name, root)
    build_materials()
    az, el = sun_for_shot()
    build_world(az, el)
    build_sun(az, el)
    build_terrain()
    build_mountains()
    build_far_trees_and_town()
    build_ishigaki()
    build_tenshu()
    build_hashiri_nagaya()
    build_goten()
    build_pines()
    build_birds()
    build_fog()
    build_camera()
    setup_render()
    setup_compositor()
    write_notes()
    timing_handlers()
    bpy.context.scene.frame_set(CFG["FRAME_START"])
    log("シーン生成：%.1f 秒（%s・%d×%d・%d コマ）" % (time.time() - t0, CFG["QUALITY"],
        *QUALITY_PRESETS[CFG["QUALITY"]]["res"], CFG["FRAME_END"] - CFG["FRAME_START"] + 1))
    log("出力先：", STATE["out"])


def benchmark():
    """最初・中間・最後の 3 コマを描いて、1 コマの時間と全体の見込みを出す（4K の前に必ず）。"""
    sc = bpy.context.scene
    frames = [sc.frame_start, (sc.frame_start + sc.frame_end) // 2, sc.frame_end]
    base = sc.render.filepath
    times = []
    for f in frames:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(STATE["out"], "benchmark_%04d" % f)
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        times.append(time.time() - t0)
    sc.render.filepath = base
    avg = sum(times) / len(times)
    n = sc.frame_end - sc.frame_start + 1
    msg = ("ベンチマーク（%s・%s）：1 コマ平均 %.1f 秒（%s）→ %d コマで約 %.1f 時間"
           % (CFG["QUALITY"], STATE.get("device", ""), avg, ", ".join("%.1f" % t for t in times), n, avg * n / 3600))
    log(msg)
    with open(os.path.join(STATE["out"], "benchmark.txt"), "w", encoding="utf-8") as fh:
        fh.write(msg + "\n")
    return avg


def parse_cli():
    if "--" not in sys.argv:
        return {}
    a = sys.argv[sys.argv.index("--") + 1:]
    opts = {}
    i = 0
    while i < len(a):
        k = a[i]
        if k in ("--render", "--benchmark", "--exr"):
            opts[k[2:]] = True
        elif k in ("--quality", "--frames", "--out", "--device", "--save") and i + 1 < len(a):
            opts[k[2:]] = a[i + 1]
            i += 1
        i += 1
    if "quality" in opts:
        CFG["QUALITY"] = opts["quality"].upper()
    if "device" in opts:
        CFG["DEVICE"] = opts["device"].upper()
    if "out" in opts:
        CFG["OUTPUT_DIR"] = opts["out"]
    if opts.get("exr"):
        CFG["EXR"] = True
    if "frames" in opts:
        s, _, e = opts["frames"].partition("-")
        CFG["FRAME_START"], CFG["FRAME_END"] = int(s), int(e or s)
    return opts


def main():
    opts = parse_cli()
    build()
    if opts.get("save"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(opts["save"]))
        log("保存：", opts["save"])
    if opts.get("benchmark"):
        benchmark()
    if opts.get("render"):
        bpy.ops.render.render(animation=True)
        if STATE["times"]:
            avg = sum(t for _, t in STATE["times"]) / len(STATE["times"])
            log("描画完了：%d コマ、平均 %.1f 秒／コマ" % (len(STATE["times"]), avg))


if __name__ == "__main__":
    main()
