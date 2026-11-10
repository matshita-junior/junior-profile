# -*- coding: utf-8 -*-
# =============================================================================
#  豊臣大坂城、夜明けから日没までに立ち上がる
#  Toyotomi Osaka Castle - a dawn-to-dusk construction timelapse
# -----------------------------------------------------------------------------
#  対応バージョン : Blender 4.2 LTS / 4.5 LTS / 5.x（4.2.23・4.5.15・5.2.3 で動作確認）
#  外部アセット   : 不要（すべて手続き生成）。後から差し替えやすい構造にしてある。
#
#  使い方
#    1. Blender を起動し、上部タブの「Scripting」を開く
#    2. テキストエディタで［開く］からこのファイルを選ぶ（または新規に貼り付け）
#    3. 下の CFG（ユーザー設定）を必要に応じて書き換える
#    4. ▶（スクリプト実行 / Alt+P）。生成には数十秒かかる
#    5. 3D ビューでテンキー 0（カメラ視点）→ Space で再生
#    6. ［レンダー］→［アニメーションレンダリング］（Ctrl+F12）で書き出し
#
#  構成（目次）
#    0. ユーザー設定 / タイムライン / 配置 / 時刻・カメラのキー表
#    1. 汎用ユーティリティ（コレクション、メッシュ生成、キーフレーム）
#    2. マテリアル（建設用マスク付き）
#    3. 建設アニメーション・スケジューラー（b_start などのカスタムプロパティ）
#    4. 差し替え用アセット（作業員・牛車・町家・松・鯱）
#    5. 環境（空・太陽・地形・堀・水・山並み・朝霧・雲・木）
#    6. 縄張り・石垣
#    7. 本丸（塀・櫓・門・橋・御殿・旗）
#    8. 天守
#    9. 普請場（足場・丸太・石材・クレーン）
#   10. 人と町（作業員・牛車・城下町）
#   11. カメラ・きらめき・テロップ
#   12. レンダー設定・コンポジター
#   13. main()
# =============================================================================

import bpy
import bmesh
import math
import os
import random
import time
from mathutils import Euler, Matrix, Vector
from mathutils import noise as mnoise

# =============================================================================
# 0. ユーザー設定（基本的にここだけ触れば調整できます）
# =============================================================================
CFG = {
    # --- レンダリング --------------------------------------------------------
    "ENGINE": "EEVEE",        # "EEVEE"（速い・GPU 推奨） / "CYCLES"（高品質・遅い）
    "QUALITY": "PREVIEW",     # "PREVIEW"（解像度50%・低サンプル） / "FINAL"
    "ASPECT": "16:9",         # "16:9"（YouTube） / "9:16"（ショート・リール・TikTok）
    "OUTPUT_PATH": "//render/toyotomi_osaka_",   # 「//」は .blend ファイルと同じ場所
    "OUTPUT_VIDEO": False,    # False = PNG 連番（推奨：途中から再開できる） / True = MP4
    # --- タイミング ----------------------------------------------------------
    "FPS": 30,
    "FRAME_START": 1,
    "FRAME_END": 900,         # 30fps x 30秒
    # --- 生成量（減らすと軽くなる） -------------------------------------------
    "SEED": 1583,             # 乱数シード。変えると作業員や石の配置が変わる
    "WORKERS": 160,           # 作業員の数
    "OXCARTS": 6,             # 牛車の数
    "TOWN_HOUSES": 130,       # 城下町の家の数
    "TREES": 70,              # 松の数
    # --- 演出の ON / OFF ----------------------------------------------------
    "USE_FOG": True,          # 朝霧（ボリューム）。Cycles では重いので注意
    "USE_CLOUDS": True,       # 流れる雲（タイムラプス感と雲の影）
    "USE_TITLES": True,       # タイトル・章テロップ（日本語フォントが必要）
    "USE_GLARE": True,        # コンポジターのグレア（金のきらめきを強調）
    "USE_DOF": False,         # 被写界深度（テロップもボケるので既定は OFF）
    # --- 差し替え用パス（空なら手続き生成のものを使う） ------------------------
    "FONT_PATH": "",          # 例 "C:/Windows/Fonts/yumindb.ttf"。空なら自動検出
    "HDRI_PATH": "",          # 例 "C:/hdri/sunset.exr"。指定すると空を HDRI に置き換え
    "TEXTURES": {             # 例 "kawara": "C:/tex/kawara_basecolor.png"
        "kawara": "", "ishigaki": "", "kuro": "", "shikkui": "", "wood": "", "ground": "",
    },
    # --- 実行モード ----------------------------------------------------------
    "MODE": "FULL",           # "FULL" = 全部作り直す / "ANIM_ONLY" = 建設アニメだけ再適用
}
# 外部（テスト用スクリプトなど）から上書きしたい場合は TS_OVERRIDES を定義しておく
CFG.update(globals().get("TS_OVERRIDES", {}))

# --- テロップの文言 -----------------------------------------------------------
TITLES = {
    "main": (8, 112, "豊臣大坂城", "夜明けから日没までに立ち上がる"),
    "chapters": [
        (40, 148, "明け六つ ― 縄張り・普請はじめ"),
        (165, 296, "朝 ― 石垣を積み、堀を穿つ"),
        (315, 496, "昼 ― 本丸に門・塀・櫓"),
        (515, 745, "午後 ― 天守、立ち上がる"),
        (762, 818, "暮れ六つ ― 黒と金の威容"),
    ],
    "end": (826, 900, "豊臣大坂城", "天正十一年（一五八三）築城開始 ／ 天守は天正十三年（一五八五）頃に完成"),
}

# --- タイムライン（フレーム） --------------------------------------------------
PH = {
    "DAWN":    (1, 150),     # 夜明け：更地・縄張り・朝霧・作業開始
    "WALLS":   (150, 300),   # 朝　　：石垣と堀
    "HONMARU": (300, 500),   # 昼　　：門・塀・櫓・本丸御殿
    "TENSHU":  (500, 750),   # 午後　：天守が下から上へ
    "FINALE":  (750, 901),   # 夕方　：完成と威容
}
TENSHU_LEVEL_START = 520     # 天守一重目の開始フレーム（天守台は 500〜535）
TENSHU_LEVEL_STEP = 40       # 一重あたりのフレーム数

# --- 城の配置（単位 m。+X=東, +Y=北, +Z=上） ----------------------------------
L = {
    "HON_W": 180.0, "HON_D": 150.0, "HON_Z": 10.0,     # 本丸（下段）の上面
    "MOAT_Z": -6.0, "WATER_Z": -2.2,                   # 堀底と水面
    "MOAT_W": 280.0, "MOAT_D": 250.0,                  # 堀の外形
    "BATTER": 5.0,                                     # 本丸石垣の法（上下の水平差）
    "TSUME_C": (20.0, 12.0), "TSUME_W": 90.0, "TSUME_D": 75.0, "TSUME_Z": 16.0,  # 詰ノ丸（上段）
    "TENSHU_C": (45.0, 31.0),                          # 天守の中心（史実に倣い本丸の北東寄り）
    "TENSHUDAI_W": 28.0, "TENSHUDAI_D": 24.0, "TENSHUDAI_Z": 27.0,
}

# 天守の各重：壁の幅・奥行・高さ、屋根の高さ、軒の出、千鳥破風を付ける面
TENSHU_LEVELS = [
    (24.0, 20.0, 5.6, 2.4, 3.2, ()),
    (20.5, 16.5, 4.6, 2.3, 3.0, ("S", "N")),
    (17.0, 13.5, 4.3, 2.2, 2.8, ("E", "W")),
    (13.5, 10.5, 4.0, 2.1, 2.6, ("S", "N")),
    (10.0, 8.0, 4.4, 5.2, 2.6, ()),          # 最上重（望楼・金の装飾）
]

# --- 時刻のキー表（ここを書き換えると 1 日の光が変わる） -----------------------
# 太陽: (フレーム, 方位[北=0 東=90 南=180 西=270], 高度[度], 色, 強さ, 光源の角度[度])
SUN_KEYS = [
    (1,   68, -1.0, (1.00, 0.42, 0.18), 1.0, 4.0),
    (60,  74,  4.0, (1.00, 0.55, 0.30), 2.2, 3.0),
    (150, 92, 16.0, (1.00, 0.78, 0.56), 3.4, 2.0),
    (300, 125, 42.0, (1.00, 0.93, 0.84), 4.3, 1.2),
    (420, 175, 63.0, (1.00, 0.97, 0.93), 4.6, 1.0),
    (520, 215, 52.0, (1.00, 0.95, 0.87), 4.4, 1.0),
    (650, 245, 30.0, (1.00, 0.86, 0.64), 3.9, 1.5),
    (750, 258, 15.0, (1.00, 0.70, 0.40), 3.4, 2.0),
    (850, 265, 6.0,  (1.00, 0.52, 0.22), 2.8, 2.5),
    (900, 268, 2.5,  (1.00, 0.43, 0.17), 2.2, 3.0),
]
# 空: (フレーム, 天頂の色, 太陽側の地平線, 反対側の地平線, 空の明るさ)
SKY_KEYS = [
    (1,   (0.05, 0.09, 0.22), (0.95, 0.45, 0.22), (0.25, 0.26, 0.40), 0.85),
    (60,  (0.07, 0.13, 0.30),  (1.00, 0.55, 0.28), (0.35, 0.36, 0.50), 0.75),
    (150, (0.14, 0.27, 0.55),  (0.98, 0.75, 0.55), (0.55, 0.62, 0.75), 0.95),
    (300, (0.17, 0.36, 0.75),  (0.80, 0.86, 0.95), (0.70, 0.80, 0.92), 1.05),
    (520, (0.16, 0.35, 0.76),  (0.82, 0.86, 0.93), (0.72, 0.80, 0.92), 1.05),
    (680, (0.14, 0.28, 0.60),  (1.00, 0.80, 0.55), (0.62, 0.66, 0.80), 0.95),
    (800, (0.10, 0.14, 0.36),  (1.00, 0.55, 0.22), (0.45, 0.35, 0.50), 0.80),
    (900, (0.06, 0.07, 0.22),  (0.95, 0.38, 0.14), (0.32, 0.24, 0.40), 0.60),
]
FOG_KEYS = [(1, 0.016), (80, 0.012), (150, 0.007), (220, 0.0025), (300, 0.0006),
            (650, 0.0004), (800, 0.0007), (900, 0.0010)]      # 地表付近の霧の濃さ（夕方は薄く：低い太陽が霧で弱まるため）
GOLD_GLOW_KEYS = [(1, 0.0), (745, 0.0), (800, 0.35), (860, 0.7), (900, 0.55)]  # 夕景で金が自ら輝く量
# 露出（実際のタイムラプス撮影のように、暗い朝夕は明るく・昼は絞る）
EXPOSURE_KEYS = [(1, 0.7), (80, 0.3), (160, -0.2), (300, -0.55), (560, -0.55), (700, -0.35),
                 (790, 0.0), (900, 0.45)]

# カメラ: (フレーム, 注視点, 方位[注視点から見たカメラの向き 南=180], 距離, カメラ高さ, 焦点距離mm)
CAM_KEYS = [
    (1,   (0, -128, 2.5), 192, 44, 1.8, 24),     # 地面すれすれ：杭と縄、作業員
    (100, (0, -118, 4.0), 188, 52, 3.5, 24),
    (160, (0, -85, 8.0),  182, 95, 11, 26),      # ゆっくり上昇
    (240, (0, -30, 6.0),  165, 165, 34, 28),     # 石垣と堀
    (310, (0, 0, 6.0),    150, 215, 58, 30),
    (410, (10, 5, 10),    132, 255, 118, 32),    # 俯瞰：本丸の全体像
    (490, (30, 20, 18),   140, 195, 88, 35),
    (570, (45, 31, 30),   165, 108, 30, 32),     # 天守へ寄る
    (650, (45, 31, 38),   200, 92, 20, 30),      # 回り込みながら見上げる
    (720, (45, 31, 46),   226, 104, 38, 32),
    (770, (40, 28, 42),   244, 135, 40, 35),
    (835, (25, 15, 28),   250, 232, 22, 35),     # 堀の水面越しに（映り込み）
    (900, (15, 5, 22),    252, 385, 95, 35),     # 引きのワイド：城・堀・町
]

PREFIX = "TS_"                       # 生成物の名前の接頭辞（作り直し時の削除に使う）
ROOT_NAME = "TS_豊臣大坂城"
BV = bpy.app.version
RNG = random.Random(CFG["SEED"])
MAT = {}        # マテリアル辞書  key -> Material
ASSET = {}      # 差し替え用アセット  key -> Collection
COL = {}        # 生成先コレクション
CAM = {}        # カメラ関連
GLINTS = []     # きらめきの予定 (フレーム, 位置, 大きさ)
_MESH = {}      # 共有メッシュのキャッシュ
MASK_GROUP = None


def log(*args):
    print("[豊臣大坂城]", *args)


def clamp(x, a, b):
    return max(a, min(b, x))


def lerp(a, b, t):
    return a + (b - a) * t


# =============================================================================
# 1. 汎用ユーティリティ
# =============================================================================
def coll(name, parent=None):
    """コレクションを取得（なければ作成）して親にリンクする。"""
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
    parent = parent if parent is not None else bpy.context.scene.collection
    if c.name not in parent.children:
        parent.children.link(c)
    return c


def find_layer_collection(lc, name):
    if lc.collection.name == name:
        return lc
    for ch in lc.children:
        r = find_layer_collection(ch, name)
        if r:
            return r
    return None


def cleanup():
    """以前このスクリプトが作ったもの（TS_ で始まるもの）だけを削除する。"""
    sc = bpy.context.scene
    if sc.world and sc.world.name.startswith(PREFIX):
        sc.world = None
    cng = getattr(sc, "compositing_node_group", None)      # 5.x のコンポジター
    if cng is not None and cng.name.startswith(PREFIX):
        sc.compositing_node_group = None
    root = bpy.data.collections.get(ROOT_NAME)
    if root:
        obs = list(root.all_objects)
        if hasattr(bpy.data, "batch_remove"):
            bpy.data.batch_remove(obs)
        else:
            for ob in obs:
                bpy.data.objects.remove(ob, do_unlink=True)

        def rm(c):
            for ch in list(c.children):
                rm(ch)
            bpy.data.collections.remove(c)
        rm(root)
    for ob in list(bpy.data.objects):
        if ob.name.startswith(PREFIX):
            bpy.data.objects.remove(ob, do_unlink=True)
    for data in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras,
                 bpy.data.lights, bpy.data.node_groups, bpy.data.worlds, bpy.data.collections):
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


def new_empty(name, col, loc=(0, 0, 0), size=1.0, kind="PLAIN_AXES"):
    ob = new_obj(name, None, col, loc)
    ob.empty_display_type = kind
    ob.empty_display_size = size
    return ob


def instance(name, asset_coll, col, loc, rot_z=0.0, scale=1.0):
    """アセット（コレクション）をインスタンス配置する。中身を差し替えると全部が変わる。"""
    e = new_obj(name, None, col, loc, (0, 0, rot_z), (scale, scale, scale))
    e.instance_type = 'COLLECTION'
    e.instance_collection = asset_coll
    e.empty_display_size = 0.6
    return e


def parent_to(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = Matrix.Identity(4)


def no_shadow(ob):
    """テロップやきらめき等、影や映り込みに出したくないもの。"""
    for attr in ("visible_shadow", "visible_glossy", "visible_diffuse", "visible_transmission",
                 "visible_volume_scatter"):
        if hasattr(ob, attr):
            setattr(ob, attr, False)


def add_solidify(ob, t, offset=-1.0):
    m = ob.modifiers.new("Solidify", 'SOLIDIFY')
    m.thickness = t
    m.offset = offset
    return m


# ---- bmesh の基本形状 -------------------------------------------------------
def bm_box(bm, sx, sy, sz, c=(0, 0, 0), base=True, rot_z=0.0):
    """箱。base=True なら c が底面の中心。"""
    m = (Matrix.Translation((c[0], c[1], c[2] + (sz / 2 if base else 0)))
         @ Matrix.Rotation(rot_z, 4, 'Z') @ Matrix.Diagonal((sx, sy, sz, 1.0)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)


def bm_cyl(bm, r1, r2, h, seg=8, c=(0, 0, 0), axis='Z', base=True):
    """円柱/円錐。axis 方向に伸びる。base=True なら c が端面の中心。"""
    m = Matrix.Translation((0, 0, h / 2 if base else 0))
    if axis == 'X':
        m = Matrix.Rotation(math.pi / 2, 4, 'Y') @ m
    elif axis == 'Y':
        m = Matrix.Rotation(-math.pi / 2, 4, 'X') @ m
    m = Matrix.Translation(c) @ m
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r1, radius2=r2, depth=h, matrix=m)


def bm_sphere(bm, r, c=(0, 0, 0), scl=(1, 1, 1), u=12, v=8, rot=(0, 0, 0)):
    m = (Matrix.Translation(c) @ Euler(rot).to_matrix().to_4x4()
         @ Matrix.Diagonal((scl[0], scl[1], scl[2], 1.0)))
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r, matrix=m)


def bm_ico(bm, r, c=(0, 0, 0), scl=(1, 1, 1), sub=2):
    m = Matrix.Translation(c) @ Matrix.Diagonal((scl[0], scl[1], scl[2], 1.0))
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r, matrix=m)


def bm_beam(bm, p0, p1, t, cyl=False, seg=6):
    """p0 から p1 へ向かう角材（cyl=True なら丸太）。縄・腕・足場の材などに使う。"""
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


def bm_loft(bm, rings, cap_top=False, cap_bottom=False, sides=(0, 1, 2, 3), flip=False):
    """長方形のリングを下から順につないで側面を張る（石垣・壁・天守台）。
    rings : [(幅, 奥行, z), ...] または [(幅, 奥行, z, cx, cy), ...]
    sides : 張る辺（0=南, 1=東, 2=北, 3=西）。石垣を辺ごとに分けて時間差で積むのに使う
    flip  : True で法線を内向きに（堀の外側の石垣など）"""
    loops = []
    for r in rings:
        w, d, z = r[0], r[1], r[2]
        cx, cy = (r[3], r[4]) if len(r) > 3 else (0.0, 0.0)
        loops.append([bm.verts.new((cx + sx * w / 2, cy + sy * d / 2, z))
                      for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for a, b in zip(loops, loops[1:]):
        for i in sides:
            j = (i + 1) % 4
            q = (a[i], a[j], b[j], b[i])
            bm.faces.new(q[::-1] if flip else q)
    if cap_top:
        bm.faces.new(loops[-1][::-1] if flip else loops[-1])
    if cap_bottom:
        bm.faces.new(loops[0] if flip else loops[0][::-1])
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')


def rect_ring(w, d, seg):
    """長方形の外周を反時計回りに seg 分割した点列。cf = 隅への近さ（隅=1, 辺の中央=0）"""
    corners = [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]
    pts = []
    for s in range(4):
        (x0, y0), (x1, y1) = corners[s], corners[(s + 1) % 4]
        for k in range(seg):
            u = k / seg
            pts.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, abs(2 * u - 1) ** 4))
    return pts


def bm_jroof(bm, w0, d0, w1, d1, h, rings=6, seg=8, curve=1.7, lift=0.7, flare=0.04,
             t_end=1.0, zoff=0.0, cap=True):
    """反りのある和風の屋根（寄棟・入母屋風）。原点は軒先の高さ。
    w0,d0=軒先の大きさ / w1,d1=上端（上の重の壁、または棟）/ h=屋根の高さ
    curve=反りの強さ（1より大きいと軒先が緩く棟側が急になる）/ lift=隅の反り上がり
    t_end<1 にすると軒先の帯だけを作る（金箔瓦の帯に使う）"""
    loops = []
    for r in range(rings + 1):
        t = t_end * r / rings
        w = lerp(w0, w1, t)
        d = lerp(d0, d1, t)
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


def bm_prism(bm, w, length, h, z0=0.0, c=(0, 0)):
    """切妻屋根（三角柱）。棟は Y 方向。町家・塀の屋根・高麗門に使う。"""
    vs = []
    for y in (-length / 2, length / 2):
        vs.append([bm.verts.new((c[0] - w / 2, c[1] + y, z0)),
                   bm.verts.new((c[0] + w / 2, c[1] + y, z0)),
                   bm.verts.new((c[0], c[1] + y, z0 + h))])
    a, b = vs
    bm.faces.new((a[0], a[2], b[2], b[0]))   # 西の斜面
    bm.faces.new((a[1], b[1], b[2], a[2]))   # 東の斜面
    bm.faces.new((a[0], a[1], a[2]))         # 南の妻
    bm.faces.new((b[2], b[1], b[0]))         # 北の妻
    bm.faces.new((a[0], b[0], b[1], a[1]))   # 底


def bm_rough_stone(bm, size, seed):
    """不揃いな石（箱の頂点をランダムにずらす）。"""
    r = random.Random(seed)
    m = Matrix.Diagonal((size * r.uniform(0.9, 1.5), size * r.uniform(0.7, 1.1),
                         size * r.uniform(0.55, 0.8), 1.0))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    for v in res["verts"]:
        v.co += Vector((r.uniform(-0.12, 0.12), r.uniform(-0.12, 0.12), r.uniform(-0.1, 0.1))) * size
    bmesh.ops.subdivide_edges(bm, edges=list({e for v in res["verts"] for e in v.link_edges}),
                              cuts=1, use_grid_fill=True)
    for v in bm.verts:
        v.co += Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))) * size * 0.05


def mesh(name, fn, mats, smooth=False):
    """1種類のマテリアルのメッシュ（同名ならキャッシュを共有＝リンク複製で軽い）。"""
    key = PREFIX + name
    if key in _MESH:
        return _MESH[key]
    bm = bmesh.new()
    fn(bm)
    if smooth:
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
    """複数マテリアルを1メッシュに。parts = [(関数(bm), マテリアルキー[, スムーズ]), ...]"""
    key = PREFIX + name
    if key in _MESH:
        return _MESH[key]
    bm = bmesh.new()
    keys = []
    for part in parts:
        fn, mk = part[0], part[1]
        smooth = part[2] if len(part) > 2 else False
        if mk not in keys:
            keys.append(mk)
        n0 = len(bm.faces)
        fn(bm)
        bm.faces.ensure_lookup_table()
        for i in range(n0, len(bm.faces)):
            bm.faces[i].material_index = keys.index(mk)
            bm.faces[i].smooth = smooth
    me = bpy.data.meshes.new(key)
    bm.to_mesh(me)
    bm.free()
    for k in keys:
        me.materials.append(MAT[k])
    _MESH[key] = me
    return me


# ---- アニメーション補助 -----------------------------------------------------
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


def set_interp(id_data, kind="LINEAR", contains=None):
    for fc in fcurves_of(id_data):
        if contains and contains not in fc.data_path:
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = kind


def key_prop(ob, prop, value, frame):
    """カスタムプロパティ（マテリアルが読む b_transp など）にキーを打つ。"""
    ob[prop] = float(value)
    ob.keyframe_insert('["%s"]' % prop, frame=frame)


def key_hide(ob, hidden, frame):
    ob.hide_render = hidden
    ob.hide_viewport = hidden
    ob.keyframe_insert("hide_render", frame=frame)
    ob.keyframe_insert("hide_viewport", frame=frame)


def key_socket(sock, value, frame):
    sock.default_value = value
    sock.keyframe_insert("default_value", frame=frame)


def phase_at(f):
    for name, (a, b) in PH.items():
        if a <= f < b:
            return name
    return "FINALE"


# =============================================================================
# 2. マテリアル
#    すべての建物マテリアルに「建設マスク」を組み込む。オブジェクトのカスタムプロパティ
#      b_transp    : 0=不透明 → 1=透明（フェード）
#      b_reveal_on : 1 のとき b_reveal_z より上を隠す（下から積み上がる表現）
#      b_reveal_z  : 現在の積み上がり高さ（ワールド Z）
#      b_glint_v   : 金のきらめき（金箔マテリアルの発光）
#      band_z      : 漆喰マテリアルで、この高さより下を黒い腰板にする
#    を Attribute ノード（Object）で読む。差し替えモデルにも同じマテリアルを割り当てれば
#    同じ建設アニメーションが使える。
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
    """色のミックス（ShaderNodeMix / RGBA）。"""
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = 'RGBA'
    _in(nt, n.inputs[0], fac)
    _in(nt, n.inputs[6], a)
    _in(nt, n.inputs[7], b)
    return n.outputs[2]


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


def ATTR(nt, name):
    n = nt.nodes.new("ShaderNodeAttribute")
    n.attribute_type = 'OBJECT'
    n.attribute_name = name
    return n.outputs["Fac"]


def NOISE(nt, vec, scale, detail=4.0, rough=0.55):
    n = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(vec, n.inputs["Vector"])
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    return n.outputs["Fac"]


def COORD(nt, kind="Object"):
    return nt.nodes.new("ShaderNodeTexCoord").outputs[kind]


def POS(nt):
    return nt.nodes.new("ShaderNodeNewGeometry").outputs["Position"]


def BUMP(nt, height, strength, distance, bsdf):
    n = nt.nodes.new("ShaderNodeBump")
    n.inputs["Strength"].default_value = strength
    n.inputs["Distance"].default_value = distance
    nt.links.new(height, n.inputs["Height"])
    nt.links.new(n.outputs["Normal"], bsdf.inputs["Normal"])


def build_mask_group():
    """建設マスク（ノードグループ）。Visible = (1-b_transp) * (1 - b_reveal_on*(Z>b_reveal_z))"""
    ng = bpy.data.node_groups.new(PREFIX + "BuildMask", "ShaderNodeTree")
    ng.interface.new_socket(name="Z", in_out='INPUT', socket_type='NodeSocketFloat')
    ng.interface.new_socket(name="Visible", in_out='OUTPUT', socket_type='NodeSocketFloat')
    gi = ng.nodes.new("NodeGroupInput")
    go = ng.nodes.new("NodeGroupOutput")
    above = MATH(ng, 'GREATER_THAN', gi.outputs["Z"], ATTR(ng, "b_reveal_z"))
    hidden = MATH(ng, 'MULTIPLY', above, ATTR(ng, "b_reveal_on"))
    vis = MATH(ng, 'MULTIPLY', MATH(ng, 'SUBTRACT', 1.0, hidden),
               MATH(ng, 'SUBTRACT', 1.0, ATTR(ng, "b_transp")), clamp_=True)
    ng.links.new(vis, go.inputs["Visible"])
    return ng


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


def finish(m, nt, shader, z=None):
    """建設マスクを通して出力につなぎ、EEVEE の透過設定をする。"""
    out = nt.nodes.get("Material Output") or nt.nodes.new("ShaderNodeOutputMaterial")
    if z is None:
        z = SEP(nt, POS(nt))["Z"]
    g = nt.nodes.new("ShaderNodeGroup")
    g.node_tree = MASK_GROUP
    nt.links.new(z, g.inputs["Z"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(g.outputs["Visible"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(shader, mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    for attr, val in (("surface_render_method", 'DITHERED'), ("blend_method", 'HASHED'),
                      ("use_transparent_shadow", True), ("shadow_method", 'HASHED')):
        if hasattr(m, attr):
            try:
                setattr(m, attr, val)
            except Exception:
                pass


def tex_override(nt, key, b, scale=0.25):
    """CFG["TEXTURES"][key] に画像があれば、ボックス投影でベースカラーに使う。"""
    path = CFG["TEXTURES"].get(key, "")
    if not path:
        return False
    path = bpy.path.abspath(path)
    if not os.path.exists(path):
        log("テクスチャが見つかりません:", path)
        return False
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(path, check_existing=True)
    t.projection = 'BOX'
    t.projection_blend = 0.25
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(COORD(nt), mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return True


def simple_mat(key, color, rough=0.6, var=0.15, scale=2.0, metal=0.0):
    """単色＋ノイズのムラ。"""
    m, nt, b = new_mat(key, color, rough, metal)
    if var > 0:
        n = NOISE(nt, COORD(nt), scale)
        dark = tuple(c * (1 - var) for c in color)
        light = tuple(min(1.0, c * (1 + var)) for c in color)
        nt.links.new(MIXC(nt, n, dark, light), b.inputs["Base Color"])
    finish(m, nt, b.outputs[0])
    return m


def build_materials():
    global MASK_GROUP
    MASK_GROUP = build_mask_group()

    # --- 黒漆（天守の壁）：横板（下見板）の凹凸＋クリアコートのつや -------------
    m, nt, b = new_mat("KuroUrushi", (0.010, 0.010, 0.012), 0.32)
    b.inputs["Coat Weight"].default_value = 0.6
    b.inputs["Coat Roughness"].default_value = 0.07
    z = SEP(nt, POS(nt))["Z"]
    boards = MATH(nt, 'ABSOLUTE', MATH(nt, 'SINE', MATH(nt, 'MULTIPLY', z, 2 * math.pi / 0.33)))
    BUMP(nt, boards, 0.25, 0.03, b)
    tex_override(nt, "kuro", b)
    finish(m, nt, b.outputs[0])

    # --- 金箔：ラフネスのムラ＋きらめき発光（b_glint_v）＋夕景の発光（GoldGlow） ---
    m, nt, b = new_mat("Kinpaku", (1.0, 0.70, 0.28), 0.2, 1.0)
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 3.5
    nt.links.new(COORD(nt), vor.inputs["Vector"])
    nt.links.new(MAPR(nt, vor.outputs["Distance"], 0.0, 1.0, 0.12, 0.30), b.inputs["Roughness"])
    glow = nt.nodes.new("ShaderNodeValue")
    glow.name = glow.label = "GoldGlow"
    glow.outputs[0].default_value = 0.0
    em = MATH(nt, 'ADD', MATH(nt, 'MULTIPLY', ATTR(nt, "b_glint_v"), 14.0), glow.outputs[0])
    b.inputs["Emission Color"].default_value = (1.0, 0.62, 0.22, 1.0)
    nt.links.new(em, b.inputs["Emission Strength"])
    finish(m, nt, b.outputs[0])

    # --- 瓦（いぶし瓦）：面の向きで丸瓦の列方向を切り替える ---------------------
    m, nt, b = new_mat("Kawara", (0.055, 0.06, 0.07), 0.38, 0.35)
    p = SEP(nt, POS(nt))
    nrm = SEP(nt, nt.nodes.new("ShaderNodeNewGeometry").outputs["Normal"])
    east_west = MATH(nt, 'GREATER_THAN', MATH(nt, 'ABSOLUTE', nrm["X"]), MATH(nt, 'ABSOLUTE', nrm["Y"]))
    coord = MATH(nt, 'ADD', MATH(nt, 'MULTIPLY', p["X"], MATH(nt, 'SUBTRACT', 1.0, east_west)),
                 MATH(nt, 'MULTIPLY', p["Y"], east_west))
    rows = MATH(nt, 'POWER', MATH(nt, 'ABSOLUTE', MATH(nt, 'SINE', MATH(nt, 'MULTIPLY', coord, 2 * math.pi / 0.36))), 0.6)
    course = MATH(nt, 'ABSOLUTE', MATH(nt, 'SINE', MATH(nt, 'MULTIPLY', p["Z"], 2 * math.pi / 0.30)))
    BUMP(nt, MATH(nt, 'ADD', rows, MATH(nt, 'MULTIPLY', course, 0.3)), 0.5, 0.08, b)
    if not tex_override(nt, "kawara", b):
        nt.links.new(MIXC(nt, NOISE(nt, COORD(nt), 0.8), (0.05, 0.055, 0.065), (0.085, 0.09, 0.10)),
                     b.inputs["Base Color"])
    finish(m, nt, b.outputs[0])

    # --- 石垣（野面積み）：ボロノイの各セルを1つの石に。石の中心高さで積み上げる ---
    m, nt, b = new_mat("Ishigaki", (0.4, 0.38, 0.35), 0.85)
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = 'MULTIPLY'
    nt.links.new(COORD(nt), sc.inputs[0])
    sc.inputs[1].default_value = (0.55, 0.55, 0.85)      # 横長の石（約1.8m x 1.2m）
    v1 = nt.nodes.new("ShaderNodeTexVoronoi")
    v1.inputs["Scale"].default_value = 1.0
    v1.inputs["Randomness"].default_value = 0.85
    nt.links.new(sc.outputs[0], v1.inputs["Vector"])
    v2 = nt.nodes.new("ShaderNodeTexVoronoi")
    v2.feature = 'DISTANCE_TO_EDGE'
    v2.inputs["Scale"].default_value = 1.0
    v2.inputs["Randomness"].default_value = 0.85
    nt.links.new(sc.outputs[0], v2.inputs["Vector"])
    joint = MAPR(nt, v2.outputs["Distance"], 0.0, 0.07)               # 0 = 目地
    cell = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(v1.outputs["Color"], cell.inputs[0])
    stone = MIXC(nt, cell.outputs[0], (0.30, 0.29, 0.27), (0.50, 0.48, 0.44))
    stone = MIXC(nt, MATH(nt, 'MULTIPLY', cell.outputs[1], 0.5), stone, (0.42, 0.34, 0.26))
    detail = NOISE(nt, COORD(nt), 4.0)
    stone = MIXC(nt, MATH(nt, 'MULTIPLY', detail, 0.35), stone, (0.2, 0.2, 0.19))
    if not tex_override(nt, "ishigaki", b):
        nt.links.new(MIXC(nt, joint, (0.05, 0.05, 0.045), stone), b.inputs["Base Color"])
    BUMP(nt, MATH(nt, 'ADD', MATH(nt, 'POWER', joint, 0.5), MATH(nt, 'MULTIPLY', detail, 0.25)), 0.6, 0.15, b)
    cz = MATH(nt, 'ADD', MATH(nt, 'DIVIDE', SEP(nt, v1.outputs["Position"])["Z"], 0.85),
              MATH(nt, 'MULTIPLY', cell.outputs[1], 0.6))
    finish(m, nt, b.outputs[0], z=cz)

    # --- 漆喰＋黒い腰板（塀・櫓・御殿・町家）。band_z より下が黒 ----------------
    m, nt, b = new_mat("Shikkui", (0.8, 0.78, 0.72), 0.7)
    lower = MATH(nt, 'LESS_THAN', SEP(nt, COORD(nt))["Z"], ATTR(nt, "band_z"))
    white = MIXC(nt, NOISE(nt, COORD(nt), 1.5), (0.74, 0.72, 0.66), (0.84, 0.82, 0.76))
    if not tex_override(nt, "shikkui", b):
        nt.links.new(MIXC(nt, lower, white, (0.016, 0.015, 0.016)), b.inputs["Base Color"])
    nt.links.new(MATH(nt, 'SUBTRACT', 0.72, MATH(nt, 'MULTIPLY', lower, 0.35)), b.inputs["Roughness"])
    finish(m, nt, b.outputs[0])

    # --- 地面：中心ほど土（普請場）、外は草地 ----------------------------------
    m, nt, b = new_mat("Ground", (0.2, 0.2, 0.1), 0.92)
    p = SEP(nt, POS(nt))
    cxy = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(p["X"], cxy.inputs[0])
    nt.links.new(p["Y"], cxy.inputs[1])
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = 'LENGTH'
    nt.links.new(cxy.outputs[0], ln.inputs[0])
    n_big = NOISE(nt, POS(nt), 0.015, 5)
    t = MAPR(nt, MATH(nt, 'ADD', ln.outputs["Value"], MATH(nt, 'MULTIPLY', n_big, 90.0)), 260.0, 360.0)
    grass = MIXC(nt, NOISE(nt, POS(nt), 0.05, 4), (0.09, 0.15, 0.05), (0.18, 0.22, 0.08))
    dirt = MIXC(nt, NOISE(nt, POS(nt), 0.2, 3), (0.28, 0.21, 0.14), (0.38, 0.30, 0.20))
    if not tex_override(nt, "ground", b, 0.05):
        nt.links.new(MIXC(nt, t, dirt, grass), b.inputs["Base Color"])
    finish(m, nt, b.outputs[0])

    # --- 水（堀）：4D ノイズを時間で動かしてさざ波 -----------------------------
    m, nt, b = new_mat("Water", (0.012, 0.045, 0.05), 0.04)
    b.inputs["IOR"].default_value = 1.33
    wn = nt.nodes.new("ShaderNodeTexNoise")
    wn.name = "WaterNoise"
    wn.noise_dimensions = '4D'
    wn.inputs["Scale"].default_value = 0.35
    wn.inputs["Detail"].default_value = 3.0
    nt.links.new(COORD(nt), wn.inputs["Vector"])
    BUMP(nt, wn.outputs["Fac"], 0.12, 0.2, b)
    finish(m, nt, b.outputs[0])

    # --- 単色系 ---------------------------------------------------------------
    simple_mat("Noji", (0.36, 0.24, 0.13), 0.8)            # 屋根の下地（野地板）
    simple_mat("Wood", (0.40, 0.28, 0.16), 0.75, 0.25, 6)  # 白木（足場・丸太・柱）
    simple_mat("WoodDark", (0.09, 0.06, 0.04), 0.6)        # 古材・門・橋
    simple_mat("Rope", (0.72, 0.62, 0.40), 0.9)            # 縄
    simple_mat("Hiwada", (0.20, 0.09, 0.05), 0.88, 0.2, 3) # 檜皮葺（御殿の屋根）
    simple_mat("Ita", (0.20, 0.17, 0.13), 0.85)            # 板葺（町家の屋根）
    simple_mat("Earth", (0.30, 0.22, 0.14), 0.95, 0.2, 0.3)  # 盛り土・掘削前の地面
    simple_mat("Gravel", (0.36, 0.33, 0.28), 0.95, 0.12, 0.4)  # 本丸の地面
    simple_mat("Road", (0.44, 0.36, 0.26), 0.95, 0.1, 0.3)
    # 遠山：空気遠近法として、空の色（Haze）を発光で混ぜる
    m, nt, b = new_mat("Mountain", (0.10, 0.13, 0.18), 1.0)
    haze = nt.nodes.new("ShaderNodeRGB")
    haze.name = "Haze"
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(haze.outputs[0], em.inputs["Color"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.6
    nt.links.new(b.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    finish(m, nt, mix.outputs[0])
    simple_mat("Pine", (0.03, 0.09, 0.035), 0.9, 0.2, 1.5)
    simple_mat("Skin", (0.62, 0.45, 0.32), 0.6, 0)
    simple_mat("Indigo", (0.04, 0.07, 0.16), 0.8, 0)       # 藍の着物
    simple_mat("Brown", (0.22, 0.14, 0.08), 0.8, 0)        # 茶の着物
    simple_mat("WhiteCloth", (0.85, 0.83, 0.77), 0.8, 0)   # 白い着物・幟
    simple_mat("Straw", (0.72, 0.60, 0.35), 0.85, 0)       # 陣笠・角
    simple_mat("Ox", (0.08, 0.05, 0.035), 0.7, 0)
    simple_mat("Pane", (0.02, 0.018, 0.016), 0.5, 0)       # 窓の奥

    # 雲（少し発光させて陰を青く柔らかく）
    m, nt, b = new_mat("Cloud", (0.92, 0.92, 0.95), 1.0)
    b.inputs["Emission Color"].default_value = (0.55, 0.65, 0.85, 1.0)
    b.inputs["Emission Strength"].default_value = 0.12
    finish(m, nt, b.outputs[0])

    # 発光（きらめき・テロップ）
    for key, col, strength in (("Glint", (1.0, 0.92, 0.75), 60.0), ("TitleWhite", (0.98, 0.94, 0.86), 3.0),
                               ("TitleGold", (1.0, 0.72, 0.32), 3.0), ("TitleShadow", (0.0, 0.0, 0.0), 1.0)):
        m = bpy.data.materials.new(PREFIX + key)
        if hasattr(m, "use_nodes") and not m.use_nodes:
            m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            if n.type != 'OUTPUT_MATERIAL':
                nt.nodes.remove(n)
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = (*col, 1.0)
        e.inputs["Strength"].default_value = strength
        finish(m, nt, e.outputs[0])
        MAT[key] = m

    # 朝霧（ボリューム）：地表ほど濃い。FogDensity をキーで薄くしていく
    m = bpy.data.materials.new(PREFIX + "Fog")
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.86, 0.88, 0.92, 1.0)
    vol.inputs["Anisotropy"].default_value = 0.35
    fall = MATH(nt, 'POWER', MAPR(nt, SEP(nt, POS(nt))["Z"], 0.0, 22.0, 1.0, 0.0), 2.0)
    dens_v = nt.nodes.new("ShaderNodeValue")
    dens_v.name = dens_v.label = "FogDensity"
    dens = MATH(nt, 'ADD', MATH(nt, 'MULTIPLY', fall, dens_v.outputs[0]), 0.00012)
    nt.links.new(dens, vol.inputs["Density"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    MAT["Fog"] = m


# =============================================================================
# 3. 建設アニメーション・スケジューラー
#    オブジェクトにカスタムプロパティで「いつ・どう現れるか」を書いておき、
#    apply_build() がキーフレームに変換する。差し替えモデルもプロパティを付ければ動く。
#      b_start  : 出現開始フレーム     b_dur : 出現にかけるフレーム数
#      b_mode   : grow（底から伸びる）/ pop（弾んで出る）/ drop（上から降りる）/
#                 rise（下からせり上がる）/ fade（透明→不透明）/
#                 reveal（下から積み上がる。マテリアルのマスクを使う）/ none
#      b_axis   : grow の方向 "X" "Y" "Z"     b_dz : drop / rise の移動量
#      b_end    : 消える（資材が使われる）フレーム    b_end_mode : shrink / sink / fade / none
#      b_glint  : このフレームで金がきらめく
# =============================================================================
def sched(ob, start, dur=12, mode="grow", end=None, end_dur=8, end_mode="shrink", **kw):
    ob["b_start"] = float(start)
    ob["b_dur"] = float(dur)
    ob["b_mode"] = mode
    if end is not None:
        ob["b_end"] = float(end)
        ob["b_end_dur"] = float(end_dur)
        ob["b_end_mode"] = end_mode
    for k, v in kw.items():
        ob["b_" + k] = v
    return ob


def world_z_bounds(ob):
    M = Matrix.LocRotScale(Vector(ob["b_loc"]), Euler(ob["b_rot"]), Vector(ob["b_scl"]))
    if ob.parent:
        M = ob.parent.matrix_world @ M
    if ob.type == 'MESH' and len(ob.data.vertices):
        zs = [(M @ v.co).z for v in ob.data.vertices]
        return min(zs), max(zs)
    return M.translation.z, M.translation.z + 10.0


def apply_build(ob):
    if "b_start" not in ob:
        return
    if "b_loc" not in ob:      # 完成時のトランスフォームを保存（ANIM_ONLY で復元に使う）
        ob["b_loc"] = list(ob.location)
        ob["b_rot"] = list(ob.rotation_euler)
        ob["b_scl"] = list(ob.scale)
    loc, scl = Vector(ob["b_loc"]), Vector(ob["b_scl"])
    ob.location, ob.rotation_euler, ob.scale = loc, Euler(ob["b_rot"]), scl
    f0 = CFG["FRAME_START"]
    s = float(ob["b_start"])
    d = max(1.0, float(ob.get("b_dur", 12)))
    mode = ob.get("b_mode", "grow")
    # 縮小は 0.02 まで。極端に小さい（0.0001 など）とバンプ計算が NaN になり、
    # デノイズやグレアで画面全体が白飛びするため、極小の瞬間は非表示にしておく
    tiny = 0.02
    ob["b_transp"] = 0.0

    # 可視性：出現前は非表示（レンダー・ビューポートとも）
    show = s + 1 if mode in ("grow", "pop") else s
    if show > f0:
        key_hide(ob, True, f0)
    key_hide(ob, False, max(f0, show))

    if mode == "grow":
        ax = "XYZ".index(ob.get("b_axis", "Z"))
        s0 = scl.copy()
        s0[ax] *= tiny
        ob.scale = s0
        ob.keyframe_insert("scale", frame=s)
        ob.scale = scl
        ob.keyframe_insert("scale", frame=s + d)
    elif mode == "pop":
        for fr, k in ((s, tiny), (s + d * 0.65, 1.12), (s + d, 1.0)):
            ob.scale = scl * k
            ob.keyframe_insert("scale", frame=fr)
    elif mode in ("drop", "rise"):
        dz = float(ob.get("b_dz", 6.0)) * (1 if mode == "drop" else -1)
        ob.location = loc + Vector((0, 0, dz))
        ob.keyframe_insert("location", index=2, frame=s)
        ob.location = loc
        ob.keyframe_insert("location", index=2, frame=s + d)
        key_prop(ob, "b_transp", 1.0, s)
        key_prop(ob, "b_transp", 0.0, s + d * 0.6)
    elif mode == "fade":
        key_prop(ob, "b_transp", 1.0, s)
        key_prop(ob, "b_transp", 0.0, s + d)
    elif mode == "reveal":
        zmin, zmax = world_z_bounds(ob)
        ob["b_reveal_on"] = 1.0
        key_prop(ob, "b_reveal_z", zmin - 0.8, s)
        key_prop(ob, "b_reveal_z", zmax + 1.5, s + d)

    e = ob.get("b_end", None)
    if e is not None:
        e = float(e)
        ed = float(ob.get("b_end_dur", 8))
        em = ob.get("b_end_mode", "shrink")
        if em == "shrink":
            ob.scale = scl
            ob.keyframe_insert("scale", frame=e - ed)
            ob.scale = scl * tiny
            ob.keyframe_insert("scale", frame=e)
        elif em == "sink":
            dz = float(ob.get("b_end_dz", 8.0))
            ob.location = loc
            ob.keyframe_insert("location", index=2, frame=e - ed)
            ob.location = loc - Vector((0, 0, dz))
            ob.keyframe_insert("location", index=2, frame=e)
        elif em == "fade":
            key_prop(ob, "b_transp", 0.0, e - ed)
            key_prop(ob, "b_transp", 1.0, e)
        key_hide(ob, True, e if em == "shrink" else e + 1)

    g = ob.get("b_glint", None)
    if g is not None:      # 金のきらめき（発光のパルス）
        key_prop(ob, "b_glint_v", 0.0, g - 3)
        key_prop(ob, "b_glint_v", 1.0, g + 1)
        key_prop(ob, "b_glint_v", 0.0, g + 14)

    # 静止状態（キーのないフレーム外で見たとき）は完成形にしておく
    ob.location, ob.scale = loc, scl
    ob.hide_render = ob.hide_viewport = False


def apply_all_builds():
    n = 0
    for ob in bpy.data.objects:
        if "b_start" in ob:
            apply_build(ob)
            n += 1
    log("建設アニメーションを適用:", n, "オブジェクト")


def reapply_animations():
    """ANIM_ONLY モード：b_start を持つオブジェクトのアニメだけ作り直す。
    差し替えモデルに b_start 等を付けたあとに使う。"""
    for ob in bpy.data.objects:
        if "b_start" in ob:
            ob.animation_data_clear()
            if "b_loc" in ob:
                ob.location, ob.rotation_euler, ob.scale = ob["b_loc"], ob["b_rot"], ob["b_scl"]
    apply_all_builds()


def auto_schedule_by_height(objects, f_start, f_end, mode="reveal", dur=10):
    """差し替えた高品質モデル用：低い部品から順に現れるよう b_start を自動で振る。
    例: auto_schedule_by_height(bpy.data.collections["MyTenshu"].objects, 520, 725)"""
    objs = [o for o in objects if o.type in ('MESH', 'EMPTY', 'CURVE')]
    objs.sort(key=lambda o: o.matrix_world.translation.z)
    for i, o in enumerate(objs):
        sched(o, lerp(f_start, f_end - dur, i / max(1, len(objs) - 1)), dur, mode)


# =============================================================================
# 4. 差し替え用アセット（非表示の 99_ASSETS コレクションに置き、インスタンスで配置）
#    各アセットは原点 = 足元/地面、正面 = +Y 向き。中身を高品質モデルに入れ替えれば
#    シーン中のすべてのインスタンスが自動で置き換わる。
# =============================================================================
def make_asset(key, parts, props=None):
    c = bpy.data.collections.new(PREFIX + "ASSET_" + key)
    COL["assets"].children.link(c)
    ob = bpy.data.objects.new(PREFIX + "asset_" + key, multi_mesh("asset_" + key, parts))
    c.objects.link(ob)
    for k, v in (props or {}).items():
        ob[k] = v
    ASSET[key] = c
    return c


def worker_parts(cloth, carry=None, off=(0, 0, 0), s=1.0):
    """簡易的な人型（身長約1.7m）。carry = "log"（丸太を担ぐ）/ "stone"（石を背負う）"""
    ox, oy, oz = off

    def P(x, y, z):
        return (ox + x * s, oy + y * s, oz + z * s)
    parts = [
        (lambda bm: bm_cyl(bm, 0.075 * s, 0.07 * s, 0.62 * s, 6, c=P(-0.09, 0, 0)), "Brown"),
        (lambda bm: bm_cyl(bm, 0.075 * s, 0.07 * s, 0.62 * s, 6, c=P(0.09, 0, 0)), "Brown"),
        (lambda bm: bm_cyl(bm, 0.25 * s, 0.17 * s, 0.84 * s, 8, c=P(0, 0, 0.56)), cloth),
        (lambda bm: bm_beam(bm, P(-0.22, 0, 1.36), P(-0.31, 0.14, 0.84), 0.05 * s, True), cloth),
        (lambda bm: bm_beam(bm, P(0.22, 0, 1.36), P(0.31, 0.14, 0.84), 0.05 * s, True), cloth),
        (lambda bm: bm_sphere(bm, 0.115 * s, c=P(0, 0.01, 1.53)), "Skin", True),
        (lambda bm: bm_cyl(bm, 0.28 * s, 0.02 * s, 0.13 * s, 10, c=P(0, 0, 1.6)), "Straw"),
    ]
    if carry == "log":
        parts.append((lambda bm: bm_cyl(bm, 0.11 * s, 0.11 * s, 2.6 * s, 8, c=P(-1.3, 0.05, 1.46), axis='X'), "Wood"))
    if carry == "stone":
        parts.append((lambda bm: bm_box(bm, 0.5 * s, 0.4 * s, 0.42 * s, c=P(0, -0.3, 0.95)), "Gravel"))
    return parts


def build_assets():
    # 作業員 4種（藍・茶・丸太担ぎ・石背負い）
    make_asset("worker_a", worker_parts("Indigo"))
    make_asset("worker_b", worker_parts("Brown"))
    make_asset("worker_c", worker_parts("WhiteCloth", carry="log"))
    make_asset("worker_d", worker_parts("Indigo", carry="stone"))

    # 牛車（牛・荷車・石材・牛飼い）。正面 +Y
    cart = [
        (lambda bm: bm_sphere(bm, 1.0, c=(0, 1.4, 1.05), scl=(0.55, 1.05, 0.55)), "Ox", True),
        (lambda bm: bm_sphere(bm, 0.32, c=(0, 2.55, 1.15), scl=(0.85, 1.2, 0.9)), "Ox", True),
        (lambda bm: bm_beam(bm, (-0.18, 2.6, 1.38), (-0.42, 2.55, 1.58), 0.05, True), "Straw"),
        (lambda bm: bm_beam(bm, (0.18, 2.6, 1.38), (0.42, 2.55, 1.58), 0.05, True), "Straw"),
        (lambda bm: bm_beam(bm, (-0.6, 2.15, 1.45), (0.6, 2.15, 1.45), 0.09), "Wood"),
        (lambda bm: bm_beam(bm, (-0.5, 2.15, 1.35), (-0.5, -0.2, 0.95), 0.07), "Wood"),
        (lambda bm: bm_beam(bm, (0.5, 2.15, 1.35), (0.5, -0.2, 0.95), 0.07), "Wood"),
        (lambda bm: bm_box(bm, 1.6, 2.4, 0.22, c=(0, -0.9, 0.82)), "Wood"),
        (lambda bm: bm_box(bm, 0.08, 2.4, 0.4, c=(-0.78, -0.9, 1.0)), "Wood"),
        (lambda bm: bm_box(bm, 0.08, 2.4, 0.4, c=(0.78, -0.9, 1.0)), "Wood"),
        (lambda bm: bm_cyl(bm, 0.62, 0.62, 0.12, 14, c=(-0.88, -0.9, 0.62), axis='X', base=False), "WoodDark"),
        (lambda bm: bm_cyl(bm, 0.62, 0.62, 0.12, 14, c=(0.88, -0.9, 0.62), axis='X', base=False), "WoodDark"),
        (lambda bm: [bm_box(bm, 0.75, 0.7, 0.55, c=(-0.3, -0.4, 1.04)),
                     bm_box(bm, 0.65, 0.8, 0.5, c=(0.32, -1.25, 1.04)),
                     bm_box(bm, 0.6, 0.55, 0.45, c=(0.0, -1.0, 1.55))], "Gravel"),
    ]
    for legy in (0.8, 2.0):          # 牛の脚
        for lx in (-0.3, 0.3):
            cart.append((lambda bm, lx=lx, legy=legy: bm_cyl(bm, 0.11, 0.09, 0.78, 6, c=(lx, legy, 0)), "Ox"))
    cart += worker_parts("Brown", off=(1.05, 2.3, 0))
    make_asset("oxcart", cart)

    # 町家 2種（板葺の切妻屋根、黒い腰板＋土壁）。正面 -Y が通り側
    make_asset("machiya_a", [
        (lambda bm: bm_box(bm, 7.0, 9.0, 3.4), "Shikkui"),
        (lambda bm: bm_prism(bm, 8.4, 10.2, 1.9, z0=3.4), "Ita"),
        (lambda bm: bm_box(bm, 7.6, 1.3, 0.12, c=(0, -5.0, 2.4)), "Ita"),
    ], props={"band_z": 1.3})
    make_asset("machiya_b", [
        (lambda bm: bm_box(bm, 6.0, 10.0, 4.6), "Shikkui"),
        (lambda bm: bm_prism(bm, 7.2, 11.0, 2.0, z0=4.6), "Ita"),
        (lambda bm: bm_box(bm, 6.6, 1.2, 0.12, c=(0, -5.4, 2.6)), "Ita"),
        (lambda bm: bm_box(bm, 3.6, 0.1, 0.6, c=(0, -5.02, 3.4)), "Pane"),
    ], props={"band_z": 1.6})

    # 松
    make_asset("pine", [
        (lambda bm: bm_cyl(bm, 0.32, 0.18, 7.8, 7), "WoodDark"),
        (lambda bm: [bm_ico(bm, 2.6, c=(0.6, 0.2, 5.2), scl=(1.35, 1.0, 0.42)),
                     bm_ico(bm, 2.3, c=(-0.8, 0.5, 6.4), scl=(1.3, 1.0, 0.45)),
                     bm_ico(bm, 1.9, c=(0.3, -0.6, 7.4), scl=(1.25, 1.0, 0.45)),
                     bm_ico(bm, 1.3, c=(0.0, 0.2, 8.3), scl=(1.2, 1.0, 0.5))], "Pine", True),
    ])

    # 金の鯱（頭が +X、尾が上に反る）。高さ約2.6m
    make_asset("shachi", [
        (lambda bm: bm_box(bm, 0.6, 0.5, 0.25), "Kinpaku"),
        (lambda bm: bm_sphere(bm, 1.0, c=(0.0, 0, 1.05), scl=(0.38, 0.30, 0.95), rot=(0, -0.35, 0), u=16, v=10), "Kinpaku", True),
        (lambda bm: bm_sphere(bm, 0.42, c=(0.32, 0, 0.45), scl=(1.25, 0.85, 0.75), u=14, v=8), "Kinpaku", True),
        (lambda bm: bm_sphere(bm, 1.0, c=(-0.25, 0, 2.15), scl=(0.12, 0.55, 0.38), u=12, v=8), "Kinpaku", True),
        (lambda bm: bm_sphere(bm, 1.0, c=(0.05, 0.3, 1.0), scl=(0.3, 0.05, 0.2)), "Kinpaku", True),
        (lambda bm: bm_sphere(bm, 1.0, c=(0.05, -0.3, 1.0), scl=(0.3, 0.05, 0.2)), "Kinpaku", True),
    ])

    # アセット置き場はビューレイヤーから除外（インスタンスだけが描画される）
    lc = find_layer_collection(bpy.context.view_layer.layer_collection, COL["assets"].name)
    if lc:
        lc.exclude = True


# =============================================================================
# 5. 環境（空・太陽・地形・堀・水・山並み・朝霧・雲・木）
# =============================================================================
def sun_dir(az, el):
    """太陽の方向ベクトル（方位: 北=0, 東=90）。"""
    a, e = math.radians(az), math.radians(el)
    return Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))


def build_world():
    """空：天頂色・地平線（太陽側/反対側）・太陽のにじみをキーで変化させるグラデーション。
    HDRI_PATH を指定すると環境テクスチャに置き換わる（太陽ライトはそのまま）。"""
    w = bpy.data.worlds.new(PREFIX + "World")
    if hasattr(w, "use_nodes") and not w.use_nodes:
        w.use_nodes = True
    bpy.context.scene.world = w
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    hdri = bpy.path.abspath(CFG["HDRI_PATH"]) if CFG["HDRI_PATH"] else ""
    if hdri and os.path.exists(hdri):
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdri, check_existing=True)
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
        for f, *_rest, strength in SKY_KEYS:
            key_socket(bg.inputs["Strength"], strength, f)
        return
    dirn = nt.nodes.new("ShaderNodeVectorMath")
    dirn.operation = 'NORMALIZE'
    nt.links.new(COORD(nt, "Generated"), dirn.inputs[0])
    d = dirn.outputs["Vector"]
    dz = SEP(nt, d)["Z"]
    sd = nt.nodes.new("ShaderNodeCombineXYZ")
    sd.name = "SunDir"
    # キー間の補間で長さが 1 からずれるので正規化する（ずれたまま 2000 乗すると発散する）
    sdn = nt.nodes.new("ShaderNodeVectorMath")
    sdn.operation = 'NORMALIZE'
    nt.links.new(sd.outputs[0], sdn.inputs[0])
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = 'DOT_PRODUCT'
    nt.links.new(d, dot.inputs[0])
    nt.links.new(sdn.outputs[0], dot.inputs[1])
    cos_sun = MATH(nt, 'MINIMUM', dot.outputs["Value"], 1.0)
    zen = nt.nodes.new("ShaderNodeRGB"); zen.name = "Zenith"
    hs = nt.nodes.new("ShaderNodeRGB"); hs.name = "HorizonSun"
    ha = nt.nodes.new("ShaderNodeRGB"); ha.name = "HorizonAnti"
    sc_ = nt.nodes.new("ShaderNodeRGB"); sc_.name = "SunColor"
    toward = MATH(nt, 'POWER', MAPR(nt, cos_sun, -1.0, 1.0), 2.0)
    horizon = MIXC(nt, toward, ha.outputs[0], hs.outputs[0])
    up = MATH(nt, 'POWER', MAPR(nt, dz, -0.02, 0.5), 0.6)
    sky = MIXC(nt, up, horizon, zen.outputs[0])
    pos = MATH(nt, 'MAXIMUM', cos_sun, 0.0)
    glow = MATH(nt, 'ADD', MATH(nt, 'MULTIPLY', MATH(nt, 'POWER', pos, 6.0), 0.9),
                MATH(nt, 'MULTIPLY', MATH(nt, 'POWER', pos, 2000.0), 30.0))
    glow_c = nt.nodes.new("ShaderNodeMix")
    glow_c.data_type = 'RGBA'
    glow_c.blend_type = 'MULTIPLY'
    glow_c.inputs[0].default_value = 1.0
    nt.links.new(sc_.outputs[0], glow_c.inputs[6])
    cc = nt.nodes.new("ShaderNodeCombineColor")
    for i in range(3):
        nt.links.new(glow, cc.inputs[i])
    nt.links.new(cc.outputs[0], glow_c.inputs[7])
    add = nt.nodes.new("ShaderNodeMix")
    add.data_type = 'RGBA'
    add.blend_type = 'ADD'
    add.inputs[0].default_value = 1.0
    nt.links.new(sky, add.inputs[6])
    nt.links.new(glow_c.outputs[2], add.inputs[7])
    ground = MIXC(nt, MAPR(nt, dz, -0.08, 0.0), (0.05, 0.05, 0.045), add.outputs[2])
    nt.links.new(ground, bg.inputs["Color"])

    for f, z, hsun, hanti, strength in SKY_KEYS:
        key_socket(zen.outputs[0], (*z, 1.0), f)
        key_socket(hs.outputs[0], (*hsun, 1.0), f)
        key_socket(ha.outputs[0], (*hanti, 1.0), f)
        key_socket(bg.inputs["Strength"], strength, f)
    for f, az, el, col, *_ in SUN_KEYS:
        v = sun_dir(az, el)
        for i in range(3):
            key_socket(sd.inputs[i], v[i], f)
        key_socket(sc_.outputs[0], (*col, 1.0), f)


def build_sun():
    ld = bpy.data.lights.new(PREFIX + "Sun", 'SUN')
    ob = new_obj("Sun", ld, COL["env"])
    for f, az, el, col, energy, angle in SUN_KEYS:
        # 太陽ライトは -Z 方向に光る。X 回転 = 90°-高度、Z 回転 = 180°-方位
        ob.rotation_euler = (math.radians(90 - max(el, 0.5)), 0.0, math.radians(180 - az))
        ob.keyframe_insert("rotation_euler", frame=f)
        ld.color = col
        ld.energy = energy
        ld.angle = math.radians(angle)
        for p in ("color", "energy", "angle"):
            ld.keyframe_insert(p, frame=f)
    if hasattr(ld, "use_contact_shadow"):
        ld.use_contact_shadow = True
    CAM["sun"] = ob


def build_terrain():
    c = COL["env"]
    ow, od, R = L["MOAT_W"], L["MOAT_D"], 4000.0
    hw, hd, hz, mz, B = L["HON_W"], L["HON_D"], L["HON_Z"], L["MOAT_Z"], L["BATTER"]

    def ground(bm):     # 外側の地面（堀の外形の穴あき）
        o = [bm.verts.new((x, y, 0)) for x, y in ((-R, -R), (R, -R), (R, R), (-R, R))]
        i_ = [bm.verts.new((x, y, 0)) for x, y in ((-ow / 2, -od / 2), (ow / 2, -od / 2), (ow / 2, od / 2), (-ow / 2, od / 2))]
        for k in range(4):
            j = (k + 1) % 4
            bm.faces.new((o[k], o[j], i_[j], i_[k]))
    new_obj("Ground", mesh("ground", ground, ["Ground"]), c)
    new_obj("MoatBottom", mesh("moat_bottom", lambda bm: bm_box(bm, ow, od, 0.1, c=(0, 0, mz - 0.1)), ["Earth"]), c)
    # 本丸・詰ノ丸の上面（砂利）
    new_obj("HonmaruTop", mesh("hon_top", lambda bm: bm_box(bm, hw, hd, 0.2, c=(0, 0, hz - 0.2)), ["Gravel"]), c)
    tx, ty = L["TSUME_C"]
    tw, td, tz = L["TSUME_W"], L["TSUME_D"], L["TSUME_Z"]
    new_obj("TsumeTop", mesh("tsume_top", lambda bm: bm_box(bm, tw, td, 0.2, c=(tx, ty, tz - 0.2)), ["Gravel"]), c)
    # 盛り土（石垣ができる前の台地の斜面）
    # 石垣と同じ反りの断面で、1.2m 内側に作る（直線だと中ほどで石垣の外にはみ出す）
    mrings = [(w_ - 1.2, d_ - 1.2, z_) for (w_, d_, z_, _x, _y) in ishigaki_rings(hw, hd, mz, hz - 0.05, B)]
    new_obj("Mound", mesh("mound", lambda bm: bm_loft(bm, mrings), ["Earth"]), c)   # 石垣の内側の土（残しておく）
    trings = [(w_ - 1.0, d_ - 1.0, z_, x_, y_) for (w_, d_, z_, x_, y_) in ishigaki_rings(tw, td, hz - 0.3, tz - 0.05, 2.2, tx, ty, n=4)]
    new_obj("TsumeMound", mesh("tsume_mound", lambda bm: bm_loft(bm, trings), ["Earth"]), c)
    # 掘る前の地面（堀の範囲を覆うフタ）。4辺に分けて順に沈め、掘削を表現する
    ib_w, ib_d = hw + 2 * B - 1.2, hd + 2 * B - 1.2
    o = [(-ow / 2, -od / 2), (ow / 2, -od / 2), (ow / 2, od / 2), (-ow / 2, od / 2)]
    i_ = [(-ib_w / 2, -ib_d / 2), (ib_w / 2, -ib_d / 2), (ib_w / 2, ib_d / 2), (-ib_w / 2, ib_d / 2)]
    for k, start in enumerate((150, 165, 180, 195)):
        j = (k + 1) % 4

        def cover(bm, k=k, j=j):
            vs = [bm.verts.new((*p, 0.03)) for p in (o[k], o[j], i_[j], i_[k])]
            bm.faces.new(vs)
        cv = new_obj("MoatCover%d" % k, mesh("moat_cover%d" % k, cover, ["Earth"]), c)
        sched(cv, 1, 1, "none", end=start + 50, end_dur=50, end_mode="sink", end_dz=6.5)
    # 水面：掘り終わった堀に水が満ちていく
    water = new_obj("Water", mesh("water", lambda bm: bm_box(bm, ow - 1, od - 1, 0.05, c=(0, 0, L["WATER_Z"] - 0.05)), ["Water"]), c)
    sched(water, 235, 65, "rise", dz=4.2)
    # 道（南の街道と西の城下へ向かう道）
    for name, sx, sy, cx_, cy_ in (("RoadS", 10, 1400, 0, -125 - 700), ("RoadW", 900, 9, -450, -200)):
        new_obj(name, mesh(name, lambda bm, sx=sx, sy=sy, cx_=cx_, cy_=cy_: bm_box(bm, sx, sy, 0.06, c=(cx_, cy_, 0)), ["Road"]), c)


def build_mountains():
    """遠景の山並み（全周）。東（生駒山地の方向）を高く、西（大阪湾の方向）を低く。"""
    def fn(bm):
        segs = 240
        first = prev = None
        for k in range(segs):
            a = 2 * math.pi * k / segs
            r = 5200 + 500 * math.sin(k * 0.23)
            x, y = math.sin(a) * r, math.cos(a) * r
            east = 0.5 + 0.5 * math.sin(a)                 # 東=1, 西=0
            n = 0.5 + 0.5 * mnoise.noise(Vector((math.cos(a) * 3.0, math.sin(a) * 3.0, 1.7)))
            hgt = 20 + (60 + 260 * n) * (0.25 + 0.75 * east)
            pair = (bm.verts.new((x, y, -40)), bm.verts.new((x * 1.02, y * 1.02, hgt)))
            if prev:
                bm.faces.new((prev[0], pair[0], pair[1], prev[1]))
            else:
                first = pair
            prev = pair
        bm.faces.new((prev[0], first[0], first[1], prev[1]))
    new_obj("Mountains", mesh("mountains", fn, ["Mountain"]), COL["env"])


def build_fog():
    if not CFG["USE_FOG"]:
        return
    fog = new_obj("Fog", mesh("fog", lambda bm: bm_box(bm, 1500, 1500, 60, c=(0, -100, -8)), ["Fog"]), COL["env"])
    node = MAT["Fog"].node_tree.nodes["FogDensity"]
    for f, v in FOG_KEYS:
        key_socket(node.outputs[0], v, f)


def build_clouds():
    """流れる雲。速く流すとタイムラプスらしくなり、地面を雲の影が走る。"""
    if not CFG["USE_CLOUDS"]:
        return
    r = random.Random(CFG["SEED"] + 7)
    for i in range(12):
        def fn(bm, i=i):
            rr = random.Random(i * 31 + 5)
            for k in range(rr.randint(5, 9)):
                bm_ico(bm, rr.uniform(28, 60), c=(rr.uniform(-90, 90), rr.uniform(-50, 50), rr.uniform(-8, 14)),
                       scl=(1.3, 1.0, 0.5), sub=2)
        x0 = r.uniform(-1900, 700)
        ob = new_obj("Cloud%02d" % i, mesh("cloud%02d" % i, fn, ["Cloud"], smooth=True), COL["env"],
                     (x0, r.uniform(-1400, 1400), r.uniform(280, 460)))
        ob.keyframe_insert("location", index=0, frame=CFG["FRAME_START"])
        ob.location.x = x0 + 1100
        ob.keyframe_insert("location", index=0, frame=CFG["FRAME_END"])
        set_interp(ob, "LINEAR")


def near_camera_path(p, dist):
    for q in CAM.get("path", []):
        if (Vector((p[0], p[1])) - Vector((q[0], q[1]))).length < dist and q[2] < 40:
            return True
    return False


def build_trees():
    r = random.Random(CFG["SEED"] + 11)
    n, tries = 0, 0
    while n < CFG["TREES"] and tries < 5000:
        tries += 1
        a = r.uniform(0, 2 * math.pi)
        d = r.uniform(170, 650)
        x, y = math.sin(a) * d, math.cos(a) * d
        if abs(x) < 160 and abs(y) < 145:                 # 堀の内側
            continue
        if abs(x) < 25 and y < -120:                      # 南の街道
            continue
        if x < -185 and -260 < y < 210:                   # 西の城下町
            continue
        if -20 > y > -190 and -120 < x < 120:             # 南の普請場
            continue
        if near_camera_path((x, y), 30):
            continue
        instance("Pine%02d" % n, ASSET["pine"], COL["env"], (x, y, 0), r.uniform(0, 6.28), r.uniform(0.8, 1.4))
        n += 1


# =============================================================================
# 6. 縄張り・石垣
# =============================================================================
def loop_points(w, d, cx, cy, spacing):
    """長方形の外周を spacing ごとにたどる点列（反時計回り、南西の角から）。"""
    corners = [(cx - w / 2, cy - d / 2), (cx + w / 2, cy - d / 2), (cx + w / 2, cy + d / 2), (cx - w / 2, cy + d / 2)]
    pts = []
    for s in range(4):
        (x0, y0), (x1, y1) = corners[s], corners[(s + 1) % 4]
        ln = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(round(ln / spacing)))
        for k in range(n):
            pts.append((lerp(x0, x1, k / n), lerp(y0, y1, k / n)))
    return pts


def build_nawabari():
    """縄張り：木杭を打ち、縄を張る。石垣ができるにつれて消える。"""
    c = COL["nawabari"]
    hw, hd, hz = L["HON_W"], L["HON_D"], L["HON_Z"]
    tx, ty = L["TSUME_C"]
    kx, ky = L["TENSHU_C"]
    loops = [  # (幅, 奥行, cx, cy, z, 間隔, 開始, 終了, 消える範囲)
        (L["MOAT_W"] + 2, L["MOAT_D"] + 2, 0, 0, 0.0, 12, 12, 110, (150, 260)),
        (hw - 1, hd - 1, 0, 0, hz, 10, 20, 120, (165, 290)),
        (L["TSUME_W"] - 1, L["TSUME_D"] - 1, tx, ty, L["TSUME_Z"], 8, 40, 125, (250, 300)),
        (L["TENSHUDAI_W"] + 6, L["TENSHUDAI_D"] + 6, kx, ky, L["TSUME_Z"], 6, 60, 130, (500, 520)),
    ]
    stake = mesh("stake", lambda bm: bm_cyl(bm, 0.07, 0.05, 1.1, 6), ["Wood"])
    r = random.Random(CFG["SEED"] + 3)
    for li, (w, d, cx, cy, z, sp, f0, f1, (v0, v1)) in enumerate(loops):
        pts = loop_points(w, d, cx, cy, sp)
        for k, (x, y) in enumerate(pts):
            fs = lerp(f0, f1, k / len(pts))
            ve = r.uniform(v0, v1)
            st = new_obj("Stake%d_%03d" % (li, k), stake, c, (x, y, z - 0.25))
            sched(st, fs, 4, "pop", end=ve, end_dur=6)
            x2, y2 = pts[(k + 1) % len(pts)]
            ln = math.hypot(x2 - x, y2 - y)
            rope = mesh("rope_%.1f" % ln, lambda bm, ln=ln: bm_beam(bm, (0, 0, 0), (ln, 0, 0), 0.06), ["Rope"])
            ro = new_obj("Rope%d_%03d" % (li, k), rope, c, (x, y, z + 0.55), (0, 0, math.atan2(y2 - y, x2 - x)))
            sched(ro, fs + 4, 6, "grow", end=ve, end_dur=6, axis="X")


def ishigaki_rings(w_top, d_top, z_bot, z_top, batter, cx=0.0, cy=0.0, n=6, concave=1.6):
    """石垣の断面リング。下ほど緩く上ほど急な「扇の勾配」風の反り。"""
    rings = []
    for i in range(n + 1):
        t = i / n
        inset = batter * (1 - (1 - t) ** concave)
        rings.append((w_top + 2 * batter - 2 * inset, d_top + 2 * batter - 2 * inset, lerp(z_bot, z_top, t), cx, cy))
    return rings


def build_ishigaki():
    c = COL["ishigaki"]
    hw, hd, hz, mz, B = L["HON_W"], L["HON_D"], L["HON_Z"], L["MOAT_Z"], L["BATTER"]
    ow, od = L["MOAT_W"], L["MOAT_D"]
    tx, ty = L["TSUME_C"]
    kx, ky = L["TENSHU_C"]
    sides = "SENW"
    # 本丸の石垣（堀底から本丸上面まで）
    rings = ishigaki_rings(hw, hd, mz - 0.3, hz, B)
    for k, (start, dur) in enumerate(((160, 110), (172, 108), (184, 106), (196, 102))):
        ob = new_obj("Ishigaki_Hon_" + sides[k], mesh("ish_hon%d" % k, lambda bm, k=k: bm_loft(bm, rings, sides=(k,)), ["Ishigaki"]), c)
        sched(ob, start, dur, "reveal")
    # 堀の外側の石垣（内向き）
    orings = [(ow - 3.6, od - 3.6, mz - 0.3), (ow - 1.2, od - 1.2, -2.0), (ow, od, 0.05)]
    for k, (start, dur) in enumerate(((175, 70), (190, 65), (205, 65), (220, 65))):
        ob = new_obj("Ishigaki_Moat_" + sides[k], mesh("ish_moat%d" % k, lambda bm, k=k: bm_loft(bm, orings, sides=(k,), flip=True), ["Ishigaki"]), c)
        sched(ob, start, dur, "reveal")
    # 詰ノ丸の石垣
    trings = ishigaki_rings(L["TSUME_W"], L["TSUME_D"], hz - 0.3, L["TSUME_Z"], 2.2, tx, ty, n=4)
    for k in range(4):
        ob = new_obj("Ishigaki_Tsume_" + sides[k], mesh("ish_tsume%d" % k, lambda bm, k=k: bm_loft(bm, trings, sides=(k,)), ["Ishigaki"]), c)
        sched(ob, 250 + k * 8, 55, "reveal")
    # 天守台（午後の最初に積む）
    drings = ishigaki_rings(L["TENSHUDAI_W"], L["TENSHUDAI_D"], L["TSUME_Z"] - 0.2, L["TENSHUDAI_Z"], 2.8, kx, ky)
    ob = new_obj("Tenshudai", mesh("tenshudai", lambda bm: bm_loft(bm, drings, cap_top=True), ["Ishigaki"]), c)
    sched(ob, 500, 36, "reveal")


# =============================================================================
# 7. 本丸（塀・櫓・門・橋・御殿・旗）
# =============================================================================
def jroof_set(name, col, cx, cy, z, w0, d0, w1, d1, h, start, roof_mat="Kawara", lift=0.6,
              gold=True, onigawara=True, glint=None, solid=0.35):
    """屋根＋金の軒先＋金の鬼瓦をまとめて作る。"""
    objs = []
    me = mesh("%s_roof" % name, lambda bm: bm_jroof(bm, w0, d0, w1, d1, h, lift=lift), [roof_mat])
    r = new_obj(name + "_roof", me, col, (cx, cy, z))
    add_solidify(r, solid)
    sched(r, start, 8, "drop", dz=5.0)
    objs.append(r)
    if gold:
        me = mesh("%s_eave" % name, lambda bm: bm_jroof(bm, w0 + 0.12, d0 + 0.12, w1, d1, h, lift=lift, t_end=0.1,
                                                         zoff=0.1, cap=False), ["Kinpaku"])
        g = new_obj(name + "_eave", me, col, (cx, cy, z))
        sched(g, start + 9, 4, "pop", glint=glint if glint else start + 11)
        objs.append(g)
    if onigawara:
        so = clamp(0.12 + 0.012 * w0, 0.18, 0.45)    # 屋根の大きさに合わせた鬼瓦の大きさ

        def oni(bm):
            for sx in (-1, 1):
                for sy in (-1, 1):
                    bm_box(bm, so, so, so * 1.3, c=(sx * w0 / 2 * 1.04, sy * d0 / 2 * 1.04, lift - 0.1), rot_z=math.pi / 4)
        o = new_obj(name + "_oni", mesh("%s_oni" % name, oni, ["Kinpaku"]), col, (cx, cy, z))
        sched(o, start + 10, 4, "pop", glint=glint if glint else start + 12)
        objs.append(o)
    return objs


def build_dobei_line(col, pts, z, start, step, prefix):
    """塀（黒い腰板＋白壁＋瓦の笠）を区間ごとに伸ばす。pts = [(x0,y0,x1,y1), ...]"""
    f = start
    for k, (x0, y0, x1, y1) in enumerate(pts):
        ln = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        key = "%.1f" % ln
        wall = mesh("dobei_" + key, lambda bm, ln=ln: bm_box(bm, ln, 0.7, 2.4, c=(ln / 2, 0, 0)), ["Shikkui"])
        w = new_obj("%s_wall%02d" % (prefix, k), wall, col, (x0, y0, z), (0, 0, ang))
        w["band_z"] = 1.0
        sched(w, f, 10, "grow", axis="X")

        def cap(bm, ln=ln):
            bm_prism(bm, 1.5, ln + 0.3, 0.55, z0=2.4, c=(0, 0))
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Z'))
            bmesh.ops.translate(bm, verts=bm.verts, vec=(ln / 2, 0, 0))
        cp = new_obj("%s_cap%02d" % (prefix, k), mesh("dobei_cap_" + key, cap, ["Kawara"]), col, (x0, y0, z), (0, 0, ang))
        sched(cp, f + 5, 8, "grow", axis="X")
        f += step


def perimeter_spans(x0, y0, x1, y1, corner, gaps=(), seg=18.0):
    """長方形の4辺を、角（櫓の場所）と gaps（門などの開口）を除いて seg 程度に分割。
    gaps は 関数(x, y) -> True なら、その区間に塀を作らない。"""
    sides = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    out = []
    for (ax, ay), (bx, by) in sides:
        ln = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / ln, (by - ay) / ln
        t = corner
        while t < ln - corner - 1.0:
            t2 = min(t + seg, ln - corner)
            px0, py0 = ax + ux * t, ay + uy * t
            px1, py1 = ax + ux * t2, ay + uy * t2
            mx, my = (px0 + px1) / 2, (py0 + py1) / 2
            if not any(g(mx, my) for g in gaps):
                out.append((px0, py0, px1, py1))
            t = t2
    return out


def make_yagura(name, col, cx, cy, z, w, d, start):
    """二重櫓：黒い腰板の白壁、反りのある瓦屋根、金の軒先。"""
    h0, rh0, h1, rh1 = 5.0, 2.0, 3.6, 2.8
    w1, d1 = w * 0.72, d * 0.72
    b0 = new_obj(name + "_b0", mesh("yag_b0_%.0f_%.0f" % (w, d), lambda bm: bm_box(bm, w, d, h0), ["Shikkui"]), col, (cx, cy, z))
    b0["band_z"] = 3.2
    sched(b0, start, 10, "reveal")
    jroof_set(name + "_r0", col, cx, cy, z + h0, w + 3.4, d + 3.4, w1 + 0.4, d1 + 0.4, rh0, start + 9, lift=0.5)
    b1 = new_obj(name + "_b1", mesh("yag_b1_%.0f_%.0f" % (w, d), lambda bm: bm_box(bm, w1, d1, h1), ["Shikkui"]), col, (cx, cy, z + h0 + rh0))
    b1["band_z"] = 1.8
    sched(b1, start + 16, 8, "reveal")
    zt = z + h0 + rh0 + h1
    jroof_set(name + "_r1", col, cx, cy, zt, w1 + 3.0, d1 + 3.0, w1 * 0.55, 0.4, rh1, start + 22, lift=0.6)
    ridge = new_obj(name + "_ridge", mesh("yag_ridge_%.0f" % w, lambda bm: bm_box(bm, w1 * 0.55 + 0.6, 0.6, 0.7), ["Kawara"]), col, (cx, cy, zt + rh1 - 0.2))
    sched(ridge, start + 30, 4, "pop")


def build_honmaru():
    c = COL["honmaru"]
    hw, hd, hz = L["HON_W"], L["HON_D"], L["HON_Z"]
    tx, ty = L["TSUME_C"]
    tw, td, tz = L["TSUME_W"], L["TSUME_D"], L["TSUME_Z"]
    kx, ky = L["TENSHU_C"]

    # --- 橋と高麗門・大手の櫓門（南） -------------------------------------------
    y_out, y_in = -L["MOAT_D"] / 2 - 0.5, -hd / 2 + 0.5
    blen = math.hypot(y_in - y_out, hz)
    bang = math.atan2(hz, y_in - y_out)

    def bridge(bm):      # 橋板と欄干（傾けて架ける）
        bm_box(bm, 7.0, blen, 0.5, c=(0, blen / 2, -0.5))
        for sx in (-1, 1):
            bm_box(bm, 0.25, blen, 1.0, c=(sx * 3.4, blen / 2, 0))
    br = new_obj("Bridge", mesh("bridge", bridge, ["WoodDark"]), c, (0, y_out, 0.0), (bang, 0, 0))
    sched(br, 306, 26, "grow", axis="Y")

    def piers(bm):       # 橋脚（垂直に立てる）
        for k in range(1, 5):
            yk, zk = lerp(y_out, y_in, k / 5), hz * k / 5 - 0.6
            for sx in (-1, 1):
                bm_box(bm, 0.5, 0.5, zk - L["MOAT_Z"], c=(sx * 2.8, yk, L["MOAT_Z"]))
    pr = new_obj("BridgePiers", mesh("bridge_piers", piers, ["WoodDark"]), c)
    sched(pr, 300, 10, "grow")

    def koraimon(bm):
        for sx in (-1, 1):
            bm_box(bm, 0.7, 0.7, 5.0, c=(sx * 3.2, 0, 0))
        bm_box(bm, 7.6, 0.6, 0.6, c=(0, 0, 4.2))
        bm_box(bm, 2.9, 0.25, 4.0, c=(-1.5, 0, 0))
        bm_box(bm, 2.9, 0.25, 4.0, c=(1.5, 0, 0))
    km = new_obj("KoraiMon", mesh("koraimon", koraimon, ["WoodDark"]), c, (0, y_out - 3.0, 0))
    sched(km, 322, 10, "rise", dz=5.0)

    def kr(bm):
        bm_prism(bm, 3.0, 9.6, 1.3, z0=4.8)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Z'))
    kmr = new_obj("KoraiMonRoof", mesh("koraimon_roof", kr, ["Kawara"]), c, (0, y_out - 3.0, 0))
    sched(kmr, 330, 8, "drop", dz=4.0)

    gy = -hd / 2 + 4.0
    def posts(bm):       # 門柱と冠木
        for sx in (-1, 1):
            bm_box(bm, 1.3, 1.3, 5.2, c=(sx * 4.6, 0, 0))
        bm_box(bm, 10.5, 1.2, 0.8, c=(0, 0, 4.6))
    gate_posts = new_obj("OteMon_posts", mesh("otemon_posts", posts, ["WoodDark"]), c, (0, gy, hz))
    sched(gate_posts, 335, 10, "grow")
    doors = new_obj("OteMon_doors", mesh("otemon_doors", lambda bm: [bm_box(bm, 4.0, 0.3, 4.4, c=(sx * 2.05, 0.2, 0)) for sx in (-1, 1)], ["KuroUrushi"]), c, (0, gy, hz))
    sched(doors, 345, 6, "pop")
    upper = new_obj("OteMon_upper", mesh("otemon_upper", lambda bm: bm_box(bm, 24.0, 8.0, 4.4), ["Shikkui"]), c, (0, gy, hz + 5.2))
    upper["band_z"] = 2.6
    sched(upper, 350, 12, "reveal")
    jroof_set("OteMon", c, 0, gy, hz + 9.6, 24 + 5.0, 8 + 5.0, 24 * 0.62, 0.5, 3.0, 362, lift=0.7)

    # --- 塀（本丸・詰ノ丸） -----------------------------------------------------
    inset = 2.0
    gate_gap = lambda x, y: abs(x) < 13 and y < 0
    spans = perimeter_spans(-hw / 2 + inset, -hd / 2 + inset, hw / 2 - inset, hd / 2 - inset, 9.0, gaps=(gate_gap,))
    build_dobei_line(c, spans, hz, 340, 3, "Dobei_Hon")
    x0, y0, x1, y1 = tx - tw / 2 + 1.5, ty - td / 2 + 1.5, tx + tw / 2 - 1.5, ty + td / 2 - 1.5
    tenshu_zone = lambda x, y: x > kx - 20 and y > ky - 18
    spans = perimeter_spans(x0, y0, x1, y1, 7.0, gaps=(tenshu_zone,), seg=15.0)
    build_dobei_line(c, spans, tz, 400, 4, "Dobei_Tsume")

    # --- 櫓 -----------------------------------------------------------------
    yag = [(-hw / 2 + 7, -hd / 2 + 7, hz, 12, 11), (hw / 2 - 7, -hd / 2 + 7, hz, 12, 11),
           (hw / 2 - 7, hd / 2 - 7, hz, 12, 11), (-hw / 2 + 7, hd / 2 - 7, hz, 12, 11),
           (-hw / 2 + 7, 5, hz, 10, 9), (hw / 2 - 7, -22, hz, 10, 9),
           (x0 + 4, y0 + 4, tz, 9, 8), (x1 - 4, y0 + 4, tz, 9, 8), (x0 + 4, y1 - 4, tz, 9, 8)]
    for k, (x, y, z, w, d) in enumerate(yag):
        make_yagura("Yagura%d" % k, c, x, y, z, w, d, 360 + k * 12)

    # --- 本丸御殿（檜皮葺風の屋根に金の棟飾り） ---------------------------------
    for k, (x, y, z, w, d, start) in enumerate(((-48, -42, hz, 50, 28, 420), (-55, 22, hz, 34, 26, 440), (2, 22, tz, 28, 20, 460))):
        b = new_obj("Goten%d" % k, mesh("goten_b%d" % k, lambda bm, w=w, d=d: bm_box(bm, w, d, 5.5), ["Shikkui"]), c, (x, y, z))
        b["band_z"] = 1.6
        sched(b, start, 12, "reveal")
        jroof_set("Goten%d" % k, c, x, y, z + 5.5, w + 5, d + 5, w * 0.6, 1.0, 7.0, start + 12, roof_mat="Hiwada", lift=0.9)

    # --- 幟（のぼり）と秀吉の千成瓢箪の馬印 -------------------------------------
    flags = [(x, -hd / 2 + 5.5) for x in (-70, -40, -18, 18, 40, 70)] + \
            [(-hw / 2 + 5.5, y) for y in (-40, -10, 25, 50)] + [(hw / 2 - 5.5, y) for y in (-48, 0, 40)] + \
            [(x, hd / 2 - 5.5) for x in (-60, -25, 10)]
    for k, (x, y) in enumerate(flags):
        make_flag("Nobori%02d" % k, c, (x, y, hz), 470 + k * 1.5, gold=(k % 3 == 0))
    make_gourd_standard(c, (-14, -64, hz), 770)


def make_flag(name, col, pos, start, gold=False):
    """幟：竿＋横木＋布（Wave モディファイアではためく）。"""
    root = new_empty(name, col, pos, 0.5)
    sched(root, start, 8, "pop")
    pole = new_obj(name + "_pole", mesh("flag_pole", lambda bm: [bm_cyl(bm, 0.07, 0.06, 7.6, 6),
                                                              bm_beam(bm, (0, 0, 7.35), (1.0, 0, 7.35), 0.06, True)], ["WoodDark"]), col)
    parent_to(pole, root)
    nx, nz = 10, 18
    me = bpy.data.meshes.new(PREFIX + name + "_cloth")
    verts = [(0.05 + 0.9 * i / nx, 0.0, 7.3 - 3.8 * j / nz) for j in range(nz + 1) for i in range(nx + 1)]
    faces = [(j * (nx + 1) + i, j * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i)
             for j in range(nz) for i in range(nx)]
    me.from_pydata(verts, [], faces)
    me.materials.append(MAT["Kinpaku" if gold else "WhiteCloth"])
    cloth = new_obj(name + "_cloth", me, col)
    parent_to(cloth, root)
    vg = cloth.vertex_groups.new(name="flutter")
    for idx, v in enumerate(verts):
        vg.add([idx], clamp((v[0] - 0.05) / 0.9, 0.0, 1.0), 'REPLACE')
    wave = cloth.modifiers.new("Wave", 'WAVE')
    wave.use_x, wave.use_y = True, False
    wave.use_normal = True
    wave.height, wave.width, wave.narrowness, wave.speed = 0.12, 0.8, 1.5, 0.15
    wave.time_offset = -RNG.uniform(0, 40)
    wave.vertex_group = "flutter"
    band = new_obj(name + "_band", mesh("flag_band", lambda bm: bm_box(bm, 0.95, 0.06, 0.35, c=(0.52, 0, 7.0)),
                                         ["WhiteCloth" if gold else "Kinpaku"]), col)
    parent_to(band, root)


def make_gourd_standard(col, pos, start):
    """秀吉の馬印「千成瓢箪」をイメージした金の瓢箪（完成の象徴）。"""
    def fn(bm):
        bm_sphere(bm, 0.55, c=(0, 0, 9.3), u=14, v=10)
        bm_sphere(bm, 0.38, c=(0, 0, 10.15), u=12, v=8)
        for k in range(8):
            a = k * math.pi / 4
            bm_sphere(bm, 0.2, c=(math.cos(a) * 0.9, math.sin(a) * 0.9, 8.4), u=8, v=6)
            bm_sphere(bm, 0.14, c=(math.cos(a) * 0.9, math.sin(a) * 0.9, 8.75), u=8, v=6)
    root = new_empty("Umajirushi", col, pos, 0.5)
    sched(root, start, 10, "pop")
    pole = new_obj("Umajirushi_pole", mesh("gourd_pole", lambda bm: bm_cyl(bm, 0.09, 0.07, 9.0, 6), ["KuroUrushi"]), col)
    parent_to(pole, root)
    g = new_obj("Umajirushi_gold", mesh("gourd", fn, ["Kinpaku"], smooth=True), col)
    parent_to(g, root)
    sched(g, start, 1, "none", glint=start + 6)
    GLINTS.append((860, Vector(pos) + Vector((0, 0, 10.0)), 2.2))


# =============================================================================
# 8. 天守（豊臣期：黒漆の壁・金箔瓦・金の鯱・外観五重）
#    各重の順番：床 → 足場 → 柱 → 梁 → 壁（下から） → 窓・金の帯 → 野地 → 瓦（下から）
#                → 千鳥破風 → 金の軒先・鬼瓦（きらめき）
# =============================================================================
def scaffold_mesh(name, w, d, h, sp=3.0):
    def fn(bm):
        pts = loop_points(w, d, 0, 0, sp)
        for (x, y) in pts:
            bm_cyl(bm, 0.09, 0.08, h + 1.0, 5, c=(x, y, -0.8))
        corners = [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]
        z = 2.0
        while z < h:
            for s in range(4):
                (x0, y0), (x1, y1) = corners[s], corners[(s + 1) % 4]
                bm_beam(bm, (x0, y0, z), (x1, y1, z), 0.12)
            z += 2.0
        for s in range(4):   # 筋交い
            (x0, y0), (x1, y1) = corners[s], corners[(s + 1) % 4]
            bm_beam(bm, (x0, y0, 0.2), (lerp(x0, x1, 0.35), lerp(y0, y1, 0.35), h - 0.2), 0.1)
            bm_beam(bm, (x1, y1, 0.2), (lerp(x1, x0, 0.35), lerp(y1, y0, 0.35), h - 0.2), 0.1)
    return mesh(name, fn, ["Wood"])


def window_mesh():
    def frame(bm):
        for (a, b) in (((-0.8, -0.65), (0.8, -0.65)), ((-0.8, 0.65), (0.8, 0.65)),
                       ((-0.8, -0.65), (-0.8, 0.65)), ((0.8, -0.65), (0.8, 0.65))):
            bm_beam(bm, (a[0], -0.12, a[1]), (b[0], -0.12, b[1]), 0.16)
        for k in (-0.4, 0.0, 0.4):     # 縦の格子
            bm_beam(bm, (k, -0.1, -0.6), (k, -0.1, 0.6), 0.06)
    return multi_mesh("tenshu_window", [
        (lambda bm: bm_box(bm, 1.6, 0.14, 1.3, c=(0, -0.05, 0), base=False), "Pane"),
        (frame, "Kinpaku"),
    ])


def hafu_mesh(gw, gh, depth):
    """千鳥破風：瓦の斜面＋黒い妻壁＋金の破風板と懸魚（げぎょ）。正面 -Y。"""
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
        bm_beam(bm, (-gw / 2 - 0.2, -0.08, -0.1), (0, -0.08, gh + 0.1), 0.35)
        bm_beam(bm, (gw / 2 + 0.2, -0.08, -0.1), (0, -0.08, gh + 0.1), 0.35)
        bm_box(bm, 0.7, 0.15, 0.9, c=(0, -0.12, gh - 1.1))
    return multi_mesh("hafu_%.1f_%.1f" % (gw, gh), [(slopes, "Kawara"), (gable_wall, "KuroUrushi"), (boards, "Kinpaku")])


def build_tenshu():
    c = COL["tenshu"]
    kx, ky = L["TENSHU_C"]
    z = L["TENSHUDAI_Z"]
    n = len(TENSHU_LEVELS)
    win = window_mesh()
    CAM["tenshu_edges"] = []
    for i, (w, d, h, rh, o, hafu) in enumerate(TENSHU_LEVELS):
        f = TENSHU_LEVEL_START + i * TENSHU_LEVEL_STEP
        top = i == n - 1
        p = "Tenshu%d" % i
        fl = new_obj(p + "_floor", mesh(p + "_floor", lambda bm, w=w, d=d: bm_box(bm, w + 0.6, d + 0.6, 0.45), ["WoodDark"]), c, (kx, ky, z))
        sched(fl, f, 5, "rise", dz=1.0)
        # 足場（その重のまわり）。完成後、上から順に外す
        sc = new_obj(p + "_scaffold", scaffold_mesh(p + "_scaffold", w + 2.6, d + 2.6, h - 0.3), COL["site"], (kx, ky, z))
        sched(sc, f, 8, "grow", end=742 + (n - 1 - i) * 4, end_dur=6)
        # 作業員が乗る足場のライン（作業員の配置に使う）
        CAM["tenshu_edges"].append([(f, f + 38), w + 1.9, d + 1.9, z + 0.5])
        # 柱
        pil = mesh(p + "_pillar", lambda bm, h=h: bm_box(bm, 0.42, 0.42, h - 0.45), ["Wood"])
        pts = loop_points(w - 0.6, d - 0.6, kx, ky, 2.6)
        for k, (x, y) in enumerate(pts):
            po = new_obj("%s_pillar%02d" % (p, k), pil, c, (x, y, z + 0.45))
            sched(po, f + 2 + 10 * k / len(pts), 6, "grow")
        beam = new_obj(p + "_beams", mesh(p + "_beams", lambda bm, w=w, d=d, h=h: bm_loft(bm, [(w - 0.2, d - 0.2, h - 0.5), (w - 0.2, d - 0.2, h - 0.1)]), ["Wood"]), c, (kx, ky, z))
        sched(beam, f + 12, 4, "pop")
        # 黒漆の壁（下から積み上がる）
        wall = new_obj(p + "_wall", mesh(p + "_wall", lambda bm, w=w, d=d, h=h: bm_loft(bm, [(w, d, 0.4), (w, d, h)]), ["KuroUrushi"]), c, (kx, ky, z))
        sched(wall, f + 14, 10, "reveal")
        # 金の長押（帯）
        bands = new_obj(p + "_bands", mesh(p + "_bands", lambda bm, w=w, d=d, h=h: [
            bm_loft(bm, [(w + 0.16, d + 0.16, h - 0.6), (w + 0.16, d + 0.16, h - 0.35)]),
            bm_loft(bm, [(w + 0.16, d + 0.16, 0.9), (w + 0.16, d + 0.16, 1.1)])], ["Kinpaku"]), c, (kx, ky, z))
        sched(bands, f + 22, 5, "pop")
        # 窓（金の枠）
        k = 0
        for side, ln, rot in (("S", w, 0.0), ("N", w, math.pi), ("E", d, math.pi / 2), ("W", d, -math.pi / 2)):
            nwin = max(2, int(ln / 4.6))
            for j in range(nwin):
                u = (j + 0.5) / nwin - 0.5
                if side == "S":
                    pos = (kx + u * ln, ky - d / 2 - 0.05)
                elif side == "N":
                    pos = (kx - u * ln, ky + d / 2 + 0.05)
                elif side == "E":
                    pos = (kx + w / 2 + 0.05, ky + u * ln)
                else:
                    pos = (kx - w / 2 - 0.05, ky - u * ln)
                wo = new_obj("%s_win%02d" % (p, k), win, c, (*pos, z + h * 0.55), (0, 0, rot))
                sched(wo, f + 22 + k * 0.3, 5, "pop")
                k += 1
        if top:
            # 最上重：金の障壁画パネルと金の高欄（廻縁）
            panels = new_obj(p + "_panels", mesh(p + "_panels", lambda bm, w=w, d=d, h=h: [
                bm_box(bm, w * 0.8, 0.1, h * 0.36, c=(0, -d / 2 - 0.06, h * 0.12)),
                bm_box(bm, w * 0.8, 0.1, h * 0.36, c=(0, d / 2 + 0.06, h * 0.12)),
                bm_box(bm, 0.1, d * 0.8, h * 0.36, c=(w / 2 + 0.06, 0, h * 0.12)),
                bm_box(bm, 0.1, d * 0.8, h * 0.36, c=(-w / 2 - 0.06, 0, h * 0.12))], ["Kinpaku"]), c, (kx, ky, z))
            sched(panels, f + 20, 6, "pop", glint=f + 24)

            def koran(bm, w=w, d=d):
                W, D = w + 2.6, d + 2.6
                cs = [(-W / 2, -D / 2), (W / 2, -D / 2), (W / 2, D / 2), (-W / 2, D / 2)]
                for s in range(4):
                    (x0, y0), (x1, y1) = cs[s], cs[(s + 1) % 4]
                    bm_beam(bm, (x0, y0, 1.05), (x1, y1, 1.05), 0.14)
                    bm_beam(bm, (x0, y0, 0.55), (x1, y1, 0.55), 0.08)
                for (x, y) in loop_points(W, D, 0, 0, 1.6):
                    bm_box(bm, 0.14, 0.14, 1.1, c=(x, y, 0))
            kr = new_obj(p + "_koran", mesh(p + "_koran", koran, ["Kinpaku"]), c, (kx, ky, z + 0.45))
            sched(kr, f + 6, 6, "pop", glint=f + 10)
            deck = new_obj(p + "_deck", mesh(p + "_deck", lambda bm, w=w, d=d: bm_box(bm, w + 2.8, d + 2.8, 0.35), ["KuroUrushi"]), c, (kx, ky, z + 0.1))
            sched(deck, f + 4, 5, "rise", dz=1.0)
        # 屋根：野地（下地）→ 瓦（下から葺く）→ 金の軒先・鬼瓦
        rz = z + h
        if not top:
            w1, d1 = TENSHU_LEVELS[i + 1][0] + 0.6, TENSHU_LEVELS[i + 1][1] + 0.6
        else:
            w1, d1 = w * 0.5, 0.5
        W0, D0 = w + 2 * o, d + 2 * o
        lift = 0.8 if not top else 1.0
        noji = new_obj(p + "_noji", mesh(p + "_noji", lambda bm, W0=W0, D0=D0, w1=w1, d1=d1, rh=rh, lift=lift: bm_jroof(bm, W0, D0, w1, d1, rh, lift=lift), ["Noji"]), c, (kx, ky, rz))
        add_solidify(noji, 0.4)
        sched(noji, f + 22, 6, "drop", dz=5.0)
        kawara = new_obj(p + "_kawara", mesh(p + "_kawara", lambda bm, W0=W0, D0=D0, w1=w1, d1=d1, rh=rh, lift=lift: bm_jroof(bm, W0 + 0.1, D0 + 0.1, w1, d1, rh, lift=lift, zoff=0.1), ["Kawara"]), c, (kx, ky, rz))
        add_solidify(kawara, 0.12)
        sched(kawara, f + 27, 9, "reveal")
        eave = new_obj(p + "_eave", mesh(p + "_eave", lambda bm, W0=W0, D0=D0, w1=w1, d1=d1, rh=rh, lift=lift: bm_jroof(bm, W0 + 0.22, D0 + 0.22, w1, d1, rh, lift=lift, t_end=0.1, zoff=0.2, cap=False), ["Kinpaku"]), c, (kx, ky, rz))
        sched(eave, f + 35, 4, "pop", glint=f + 37)

        def oni(bm, W0=W0, D0=D0, lift=lift):
            for sx in (-1, 1):
                for sy in (-1, 1):
                    bm_box(bm, 0.5, 0.5, 0.65, c=(sx * W0 / 2 * 1.04, sy * D0 / 2 * 1.04, lift - 0.05), rot_z=math.pi / 4)
        on = new_obj(p + "_oni", mesh(p + "_oni", oni, ["Kinpaku"]), c, (kx, ky, rz))
        sched(on, f + 35, 4, "pop", glint=f + 37)
        GLINTS.append((f + 37, Vector((kx + W0 / 2 * 1.04, ky - D0 / 2 * 1.04, rz + lift + 0.4)), 1.6 + i * 0.25))
        # 千鳥破風
        for side in hafu:
            sl = w if side in "SN" else d
            gw, gh = sl * 0.38, rh * 1.3 + 0.6
            R = (d / 2 if side in "SN" else w / 2) + o * 0.55
            pos, rot = {"S": ((kx, ky - R), 0.0), "N": ((kx, ky + R), math.pi),
                        "E": ((kx + R, ky), math.pi / 2), "W": ((kx - R, ky), -math.pi / 2)}[side]
            hf = new_obj("%s_hafu%s" % (p, side), hafu_mesh(gw, gh, 5.0), c, (*pos, rz + rh * 0.12), (0, 0, rot))
            sched(hf, f + 31, 6, "pop")
        z = rz + rh
    # 大棟と金の鯱
    w_top = TENSHU_LEVELS[-1][0]
    rl = w_top * 0.5
    ridge = new_obj("Tenshu_ridge", mesh("tenshu_ridge", lambda bm: bm_box(bm, rl + 1.0, 0.8, 0.9), ["Kawara"]), c, (kx, ky, z - 0.25))
    sched(ridge, 722, 4, "pop")
    for sx in (-1, 1):
        sh = instance("Shachi%+d" % sx, ASSET["shachi"], c, (kx + sx * (rl / 2 + 0.2), ky, z + 0.5), 0.0 if sx < 0 else math.pi)
        sched(sh, 728, 8, "pop")
    CAM["shachi"] = Vector((kx, ky, z + 2.0))
    for f_, dx, s_ in ((738, -1, 2.6), (742, 1, 2.6), (790, -1, 3.0), (812, 0, 2.2), (836, 1, 3.0), (878, -1, 2.4)):
        GLINTS.append((f_, Vector((kx + dx * (rl / 2 + 0.2), ky, z + 2.2)), s_))
    CAM["tenshu_top"] = z


# =============================================================================
# 9. 普請場（足場・丸太・石材・クレーン）
# =============================================================================
def build_site():
    c = COL["site"]
    hz, tz = L["HON_Z"], L["TSUME_Z"]
    r = random.Random(CFG["SEED"] + 21)
    # 石材の山：運び込まれて増え（夜明け）、石垣を積むにつれて減る（朝）
    stones = [mesh("stone%d" % v, lambda bm, v=v: bm_rough_stone(bm, 1.0, v), ["Ishigaki"]) for v in range(6)]
    piles = [((-14, -140, 0), 26, (1, 150), (165, 300)), ((-55, -150, 0), 22, (1, 150), (160, 290)),
             ((55, -152, 0), 22, (1, 150), (170, 300)), ((-160, -40, 0), 18, (20, 150), (190, 300)),
             ((160, 40, 0), 18, (20, 150), (190, 300)), ((-60, -55, hz), 16, (30, 150), (170, 300)),
             ((10, -14, tz), 20, (460, 500), (505, 545))]
    for pi, ((px, py, pz), cnt, (a0, a1), (v0, v1)) in enumerate(piles):
        for k in range(cnt):
            s = r.uniform(0.9, 2.1)
            ang = r.uniform(0, 2 * math.pi)
            rad = r.uniform(0, 6.0)
            layer = 0 if k < cnt * 0.6 else 1
            ob = new_obj("Stone%d_%02d" % (pi, k), stones[k % 6], c,
                         (px + math.cos(ang) * rad, py + math.sin(ang) * rad, pz + layer * 0.9 + 0.3 * s),
                         (0, 0, r.uniform(0, 6.28)), (s, s, s))
            start = a0 if (a0 == 1 and r.random() < 0.4) else r.uniform(a0, a1)
            sched(ob, start, 6, "pop", end=r.uniform(v0, v1), end_dur=5)
    # 丸太の山：昼〜午後に建物へ使われて減っていく
    logm = mesh("log", lambda bm: bm_cyl(bm, 0.24, 0.22, 8.0, 10, c=(-4.0, 0, 0), axis='X'), ["Wood"])
    for pi, (px, py, pz, yaw) in enumerate(((14, -146, 0, 0.3), (-110, -158, 0, -0.2), (110, -160, 0, 0.1),
                                            (-60, 40, hz, 1.2), (62, -50, hz, 0.0))):
        k = 0
        for layer, cnt in enumerate((5, 4, 3)):
            for j in range(cnt):
                off = (j - (cnt - 1) / 2) * 0.5
                lx, ly = -math.sin(yaw) * off, math.cos(yaw) * off
                ob = new_obj("Log%d_%02d" % (pi, k), logm, c, (px + lx, py + ly, pz + 0.24 + layer * 0.43), (0, 0, yaw))
                sched(ob, r.uniform(40, 200), 6, "pop", end=r.uniform(330, 720), end_dur=6)
                k += 1
    # 夜明けの仮設足場
    for k, (x, y, z, w, d, h) in enumerate(((-25, -137, 0, 8, 4, 5), (-70, -55, hz, 6, 6, 8), (70, -55, hz, 6, 6, 6))):
        ob = new_obj("TempScaffold%d" % k, scaffold_mesh("temp_scaffold%d" % k, w, d, h, 2.0), c, (x, y, z))
        sched(ob, 1, 1, "none", end=r.uniform(290, 320), end_dur=8)
    # 木製クレーン（旋回して石を吊る）
    make_crane("CraneA", c, (-30, -66, hz), (150, 300), -2.1, -1.0, 100, 312)
    make_crane("CraneB", c, (84, 20, hz), (160, 300), -0.5, 0.5, 110, 312)
    make_crane("CraneC", c, (0, -2, tz), (500, 730), 0.35, 1.2, 480, 745)


def make_crane(name, col, pos, active, a0, a1, appear, vanish):
    root = new_empty(name, col, pos, 1.0)
    sched(root, appear, 10, "pop", end=vanish, end_dur=8)
    parts = [
        new_obj(name + "_mast", mesh("crane_mast", lambda bm: bm_cyl(bm, 0.3, 0.24, 15.0, 8), ["Wood"]), col),
        new_obj(name + "_guys", mesh("crane_guys", lambda bm: [bm_beam(bm, (0, 0, 14.8), (sx * 7, sy * 7, 0), 0.05)
                                                              for sx in (-1, 1) for sy in (-1, 1)], ["Rope"]), col),
    ]
    for p_ in parts:
        parent_to(p_, root)
    pivot = new_empty(name + "_pivot", col, (0, 0, 14.5), 0.5)
    parent_to(pivot, root)
    jib = new_obj(name + "_jib", mesh("crane_jib", lambda bm: [bm_beam(bm, (-4, 0, 0), (13, 0, 0), 0.34, True, 8),
                                                              bm_box(bm, 1.4, 1.2, 1.2, c=(-3.8, 0, -1.2))], ["Wood"]), col)
    rope = new_obj(name + "_rope", mesh("crane_rope", lambda bm: bm_beam(bm, (12.8, 0, 0), (12.8, 0, -9.0), 0.05), ["Rope"]), col)
    stone = new_obj(name + "_stone", mesh("stone_big", lambda bm: bm_rough_stone(bm, 1.6, 99), ["Ishigaki"]), col, (12.8, 0, -9.8))
    for p_ in (jib, rope, stone):
        parent_to(p_, pivot)
    # 旋回：資材側 a0 → 石垣側 a1 → 戻る（36 フレーム周期）。石は運ぶ間だけ見える
    cyc = 36
    key_hide(stone, True, CFG["FRAME_START"])
    for f in range(active[0], active[1], cyc):
        for df, ang in ((0, a0), (14, a1), (18, a1), (32, a0)):
            pivot.rotation_euler.z = ang
            pivot.keyframe_insert("rotation_euler", index=2, frame=f + df)
        key_hide(stone, False, f)
        key_hide(stone, True, f + 17)
        stone.location.z = -9.8
        stone.keyframe_insert("location", index=2, frame=f)
        stone.location.z = -6.0
        stone.keyframe_insert("location", index=2, frame=f + 14)


# =============================================================================
# 10. 人と町（作業員・牛車・城下町）
# =============================================================================
def zones_for(f):
    """その時刻に作業員が働く場所 [(ゾーン, 重み), ...]。ゾーンは長方形 or 線分。"""
    hz, tz = L["HON_Z"], L["TSUME_Z"]
    R = lambda x0, x1, y0, y1, z: ("rect", x0, x1, y0, y1, z)
    SOUTH, EAST, WEST, NORTH = R(-90, 90, -178, -132, 0), R(146, 175, -110, 110, 0), R(-175, -146, -110, 110, 0), R(-110, 110, 131, 165, 0)
    HON_S, HON_W, HON_N, HON_E = R(-84, 84, -68, -30, hz), R(-84, -30, -30, 68, hz), R(-30, 84, 53, 68, hz), R(69, 84, -30, 53, hz)
    TSUME, TSUME_S = R(-21, 26, -21, 45, tz), R(26, 61, -21, 13, tz)
    TOWN = R(-420, -200, -230, 120, 0)
    ph = phase_at(f)
    if ph == "DAWN":
        return [(SOUTH, 5), (HON_S, 2), (HON_W, 1), (TSUME, 1), (EAST, 1), (WEST, 1)]
    if ph == "WALLS":
        return [(SOUTH, 3), (EAST, 2), (WEST, 2), (NORTH, 2), (HON_S, 2), (HON_W, 1), (HON_N, 1), (HON_E, 1), (TSUME, 1)]
    if ph == "HONMARU":
        return [(HON_S, 3), (HON_W, 3), (HON_N, 2), (HON_E, 2), (TSUME, 2), (SOUTH, 1)]
    if ph == "TENSHU":
        z = [(TSUME, 3), (TSUME_S, 3), (HON_S, 1), (HON_W, 1)]
        for (a, b), w, d, ez in CAM.get("tenshu_edges", []):
            if a <= f < b:
                kx, ky = L["TENSHU_C"]
                cs = [(kx - w / 2, ky - d / 2), (kx + w / 2, ky - d / 2), (kx + w / 2, ky + d / 2), (kx - w / 2, ky + d / 2)]
                for s in range(4):
                    z.append((("edge", cs[s], cs[(s + 1) % 4], ez, b), 1.2))   # b = 足場が使える最後
        return z
    return [(HON_S, 1), (SOUTH, 1), (TOWN, 3)]


def zone_point(z, r, near=None, reach=10.0):
    if z[0] == "rect":
        _, x0, x1, y0, y1, zz = z
        if near is not None:
            x = clamp(near.x + r.uniform(-reach, reach), x0, x1)
            y = clamp(near.y + r.uniform(-reach, reach), y0, y1)
        else:
            x, y = r.uniform(x0, x1), r.uniform(y0, y1)
        return Vector((x, y, zz))
    _, a, b, zz = z[:4]
    t = r.random()
    if near is not None:
        ab = Vector(b) - Vector(a)
        t0 = clamp((Vector((near.x, near.y)) - Vector(a)).dot(ab) / max(1e-6, ab.length_squared), 0, 1)
        t = clamp(t0 + r.uniform(-0.15, 0.15), 0, 1)
    return Vector((lerp(a[0], b[0], t), lerp(a[1], b[1], t), zz))


def weighted(items, r):
    tot = sum(w for _, w in items)
    x = r.uniform(0, tot)
    for it, w in items:
        x -= w
        if x <= 0:
            return it
    return items[-1][0]


def build_workers():
    """作業員：時間帯ごとの持ち場に現れ、短い移動と立ち止まりを繰り返す。
    タイムラプスらしく、人は現れては消える（ちらつく）。"""
    c = COL["life"]
    r = random.Random(CFG["SEED"] + 31)
    FE = CFG["FRAME_END"]
    p_vis = {"DAWN": 0.75, "WALLS": 0.95, "HONMARU": 0.9, "TENSHU": 0.85, "FINALE": 0.45}
    variants = [("worker_a", 4), ("worker_b", 4), ("worker_c", 1.5), ("worker_d", 1.5)]
    cam0 = Vector((-9.0, -171.0, 0))
    for i in range(CFG["WORKERS"]):
        e = instance("Worker%03d" % i, ASSET[weighted(variants, r)], c, (0, 0, -50), 0.0, r.uniform(0.93, 1.07))
        key_hide(e, True, CFG["FRAME_START"])
        f = int(10 + (r.random() ** 1.5) * 110)
        heading = r.uniform(0, 2 * math.pi)
        while f < FE - 6:
            if r.random() < p_vis[phase_at(f)]:
                zone = weighted(zones_for(f), r)
                end = min(FE, f + r.randint(30, 80))
                if zone[0] == "edge":           # 足場が外されたら降りる
                    end = min(end, int(zone[4]))
                p = zone_point(zone, r)
                if f < 160 and (p - cam0).xy.length < 7:
                    p.x += 9
                e.location = p
                e.keyframe_insert("location", frame=f)
                key_hide(e, False, f)
                t = f
                while t < end - 2:
                    q = zone_point(zone, r, near=p)
                    if f < 160 and (q - cam0).xy.length < 7:
                        q = p.copy()
                    dt = min(r.randint(5, 14), end - t)   # 区間の終わりを越えない
                    dv = q - p
                    if dv.xy.length > 0.3:
                        new_h = math.atan2(-dv.x, dv.y)
                        while new_h - heading > math.pi:
                            new_h -= 2 * math.pi
                        while new_h - heading < -math.pi:
                            new_h += 2 * math.pi
                        e.rotation_euler.z = heading
                        e.keyframe_insert("rotation_euler", index=2, frame=t)
                        heading = new_h
                        e.rotation_euler.z = heading
                        e.keyframe_insert("rotation_euler", index=2, frame=t + 2)
                    e.location = p
                    e.keyframe_insert("location", frame=t)
                    e.location = q
                    e.keyframe_insert("location", frame=t + dt)
                    p = q
                    t += dt + r.choice((0, 0, 2, 4, 8))
                key_hide(e, True, end)
                f = max(end, t) + 1 + r.randint(0, 14)
            else:
                f += r.randint(10, 30)


def build_oxcarts():
    """牛車：南の街道から石材を運び込んでは戻る（昼過ぎまで）。"""
    c = COL["life"]
    r = random.Random(CFG["SEED"] + 41)
    for i in range(CFG["OXCARTS"]):
        e = instance("OxCart%d" % i, ASSET["oxcart"], c, (0, -900, 0))
        side = 1 if i % 2 else -1
        dest = Vector((side * 9 + r.uniform(-3, 3), -150 + r.uniform(-5, 3), 0))
        lane_in, lane_out = Vector((-1.6, 0, 0)), Vector((1.6, 0, 0))
        t = 1 - i * (150 // max(1, CFG["OXCARTS"]))
        path = [(0, Vector((0, -900, 0)) + lane_in, 0.0), (50, Vector((0, -178, 0)) + lane_in, 0.0),
                (62, dest, math.atan2(-(dest.x), dest.y + 178)), (78, dest, math.atan2(-(dest.x), dest.y + 178)),
                (84, dest, math.pi), (96, Vector((0, -182, 0)) + lane_out, math.pi), (146, Vector((0, -900, 0)) + lane_out, math.pi)]
        while t < 560:
            for df, pos, hd in path:
                e.location = pos
                e.rotation_euler.z = hd
                e.keyframe_insert("location", frame=t + df)
                e.keyframe_insert("rotation_euler", index=2, frame=t + df)
            t += 150
        key_hide(e, False, CFG["FRAME_START"])
        key_hide(e, True, 562)


def build_town():
    """城下町：午後から夕方にかけて、城に近い通りから順に家が建つ。
    （のちに秀吉が整えた西の船場・南の上町をイメージした配置）"""
    c = COL["life"]
    r = random.Random(CFG["SEED"] + 51)
    spots = []
    for y in (-215, -150, -85, -20, 45, 110):
        for x in range(-206, -560, -11):
            for s in (-1, 1):
                spots.append((x + r.uniform(-1, 1), y + s * 9.5, 0.0 if s > 0 else math.pi))
    for y in range(-192, -480, -12):
        for s in (-1, 1):
            spots.append((s * 13.0, y + r.uniform(-1, 1), -math.pi / 2 if s > 0 else math.pi / 2))
    spots.sort(key=lambda p: math.hypot(p[0] + 60, p[1] + 60) + r.uniform(0, 25))
    spots = spots[:CFG["TOWN_HOUSES"]]
    for k, (x, y, rot) in enumerate(spots):
        e = instance("House%03d" % k, ASSET["machiya_a" if r.random() < 0.6 else "machiya_b"], c, (x, y, 0), rot, r.uniform(0.9, 1.15))
        sched(e, 590 + 270 * k / max(1, len(spots)), 10, "pop")
    for name, sx, sy, cx_, cy_ in [("Street%d" % k, 360, 7, -380, y) for k, y in enumerate((-215, -150, -85, -20, 45, 110))]:
        st = new_obj(name, mesh(name, lambda bm, sx=sx, sy=sy, cx_=cx_, cy_=cy_: bm_box(bm, sx, sy, 0.05, c=(cx_, cy_, 0)), ["Road"]), c)
        sched(st, 580, 30, "fade")


# =============================================================================
# 11. カメラ・きらめき・テロップ
# =============================================================================
def _cam_params(f):
    """CAM_KEYS を Catmull-Rom 風に補間して (位置, 注視点, 焦点距離) を返す。"""
    ks = CAM_KEYS
    if f <= ks[0][0]:
        i = 0
    elif f >= ks[-1][0]:
        i = len(ks) - 2
    else:
        i = max(j for j in range(len(ks) - 1) if ks[j][0] <= f)
    t = clamp((f - ks[i][0]) / (ks[i + 1][0] - ks[i][0]), 0.0, 1.0)

    def vals(k):
        fr, foc, az, dist, h, lens = k
        return [foc[0], foc[1], foc[2], az, dist, h, lens]

    def tangent(j, comp):
        if j <= 0 or j >= len(ks) - 1:
            return 0.0
        return (vals(ks[j + 1])[comp] - vals(ks[j - 1])[comp]) / (ks[j + 1][0] - ks[j - 1][0])
    out = []
    dt = ks[i + 1][0] - ks[i][0]
    for comp in range(7):
        p0, p1 = vals(ks[i])[comp], vals(ks[i + 1])[comp]
        m0, m1 = tangent(i, comp) * dt, tangent(i + 1, comp) * dt
        t2, t3 = t * t, t * t * t
        out.append((2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1)
    fx, fy, fz, az, dist, h, lens = out
    a = math.radians(az)
    pos = Vector((fx + math.sin(a) * dist, fy + math.cos(a) * dist, h))
    return pos, Vector((fx, fy, fz)), lens


def build_camera():
    c = COL["camlight"]
    cd = bpy.data.cameras.new(PREFIX + "Camera")
    cd.sensor_width = 36.0
    cd.clip_start, cd.clip_end = 0.1, 12000.0
    cam = new_obj("Camera", cd, c)
    target = new_empty("CameraTarget", c, (0, 0, 0), 2.0, "SPHERE")
    con = cam.constraints.new('TRACK_TO')
    con.target = target
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    path = []
    for f in range(CFG["FRAME_START"], CFG["FRAME_END"] + 1, 3):
        pos, foc, lens = _cam_params(f)
        cam.location = pos
        target.location = foc
        cd.lens = lens
        cam.keyframe_insert("location", frame=f)
        target.keyframe_insert("location", frame=f)
        cd.keyframe_insert("lens", frame=f)
        path.append(pos)
    if CFG["USE_DOF"]:
        cd.dof.use_dof = True
        cd.dof.focus_object = target
        cd.dof.aperture_fstop = 8.0
    bpy.context.scene.camera = cam
    CAM["cam"], CAM["data"], CAM["path"] = cam, cd, path


def star_mesh():
    def fn(bm):
        for rot, r1, r2 in ((0.0, 1.0, 0.07), (math.pi / 4, 0.45, 0.05)):
            n = 8
            center = bm.verts.new((0, 0, 0))
            ring = []
            for k in range(n):
                a = rot + k * 2 * math.pi / n
                rr = r1 if k % 2 == 0 else r2
                ring.append(bm.verts.new((math.cos(a) * rr, math.sin(a) * rr, 0.01 * (rot > 0))))
            for k in range(n):
                bm.faces.new((center, ring[k], ring[(k + 1) % n]))
    return mesh("glint_star", fn, ["Glint"])


def build_glints():
    """金のきらめき：カメラを向く星形の光（グレアと組み合わせると効果的）。"""
    c = COL["fx"]
    me = star_mesh()
    for k, (f, pos, size) in enumerate(GLINTS):
        g = new_obj("Glint%02d" % k, me, c, pos)
        no_shadow(g)
        con = g.constraints.new('TRACK_TO')
        con.target = CAM["cam"]
        con.track_axis = 'TRACK_Z'
        con.up_axis = 'UP_Y'
        key_hide(g, True, CFG["FRAME_START"])
        key_hide(g, False, f - 1)
        for df, s_, rz in ((-1, 0.02, 0.0), (3, size, 0.5), (10, 0.02, 1.0)):
            g.scale = (s_, s_, s_)
            g.rotation_euler.z = rz
            g.keyframe_insert("scale", frame=f + df)
            g.keyframe_insert("rotation_euler", index=2, frame=f + df)
        key_hide(g, True, f + 11)


FONT_CANDIDATES = [
    "C:/Windows/Fonts/yumindb.ttf", "C:/Windows/Fonts/YuMincho.ttc", "C:/Windows/Fonts/msmincho.ttc",
    "C:/Windows/Fonts/YuGothB.ttc", "C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/msgothic.ttc",
    "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc", "/System/Library/Fonts/Hiragino Mincho ProN.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", "/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def find_font():
    paths = [CFG["FONT_PATH"]] if CFG["FONT_PATH"] else []
    for p in paths + FONT_CANDIDATES:
        p = bpy.path.abspath(p)
        if p and os.path.exists(p):
            try:
                return bpy.data.fonts.load(p, check_existing=True)
            except Exception:
                continue
    return None


def build_titles():
    """テロップ：カメラの子にした板に文字を置き、焦点距離に応じて大きさを補正する。"""
    if not CFG["USE_TITLES"]:
        return
    font = find_font()
    if font is None:
        log("日本語フォントが見つからないためテロップを省略しました（CFG['FONT_PATH'] で指定可）")
        return
    c = COL["fx"]
    cam, cd = CAM["cam"], CAM["data"]
    rig = new_empty("TitleRig", c, (0, 0, -1.0), 0.05)
    parent_to(rig, cam)
    for i in range(3):   # 焦点距離が変わっても文字の大きさを一定に（単純な式なので自動実行不要）
        fc = rig.driver_add("scale", i)
        drv = fc.driver
        drv.type = 'SCRIPTED'
        drv.expression = "35.0/lens"
        v = drv.variables.new()
        v.name = "lens"
        v.type = 'SINGLE_PROP'
        v.targets[0].id_type = 'CAMERA'
        v.targets[0].id = cd
        v.targets[0].data_path = "lens"
    portrait = CFG["ASPECT"] == "9:16"
    fw = 36.0 / 35.0 * (9 / 16 if portrait else 1.0)
    fh = fw * (16 / 9 if portrait else 9 / 16)
    k = 1.7 if portrait else 1.0       # 縦型は画面の幅が狭いので文字を大きめに

    def text(name, body, size, x, y, f0, f1, mat="TitleWhite", align='CENTER'):
        for shadow in (True, False):
            cu = bpy.data.curves.new(PREFIX + name + ("_sh" if shadow else ""), 'FONT')
            cu.body = body
            cu.font = font
            cu.size = size
            cu.align_x = align
            cu.align_y = 'CENTER'
            cu.space_character = 1.05
            cu.materials.append(MAT["TitleShadow" if shadow else mat])
            ob = new_obj(name + ("_sh" if shadow else ""), cu, c)
            parent_to(ob, rig)
            ob.location = (x + (size * 0.04 if shadow else 0), y - (size * 0.04 if shadow else 0), -0.001 if shadow else 0.0)
            no_shadow(ob)
            key_hide(ob, True, CFG["FRAME_START"])
            key_hide(ob, False, f0)
            key_prop(ob, "b_transp", 1.0, f0)
            key_prop(ob, "b_transp", 0.35 if shadow else 0.0, f0 + 10)
            key_prop(ob, "b_transp", 0.35 if shadow else 0.0, f1 - 10)
            key_prop(ob, "b_transp", 1.0, f1)
            key_hide(ob, True, f1 + 1)

    f0, f1, main, sub = TITLES["main"]
    text("Title_main", main, fw * 0.085 * k, 0, fh * 0.07, f0, f1, "TitleGold")
    text("Title_sub", sub, fw * 0.032 * k, 0, -fh * 0.05, f0 + 10, f1)
    for i, (a, b, body) in enumerate(TITLES["chapters"]):
        text("Chapter%d" % i, body, fw * 0.024 * k, -fw / 2 + fw * 0.05, -fh / 2 + fh * 0.09, a, b, align='LEFT')
    f0, f1, main, sub = TITLES["end"]
    if portrait:
        sub = sub.replace(" ／ ", "\n")   # 縦型では2行に分ける
    text("End_main", main, fw * 0.07 * k, 0, fh * 0.33, f0, f1 + 10, "TitleGold")     # 城と重ならない上部
    text("End_sub", sub, fw * 0.02 * k, 0, fh * (0.25 if portrait else 0.235), f0 + 8, f1 + 10)


# =============================================================================
# 12. レンダー設定・コンポジター
# =============================================================================
def setup_render():
    sc = bpy.context.scene
    r = sc.render
    sc.frame_start, sc.frame_end = CFG["FRAME_START"], CFG["FRAME_END"]
    r.fps, r.fps_base = CFG["FPS"], 1.0
    rx, ry = (1080, 1920) if CFG["ASPECT"] == "9:16" else (1920, 1080)
    r.resolution_x, r.resolution_y = rx, ry
    final = CFG["QUALITY"] == "FINAL"
    r.resolution_percentage = 100 if final else 50
    if CFG["ENGINE"] == "CYCLES":
        r.engine = 'CYCLES'
        sc.cycles.samples = 128 if final else 24
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 6
        try:
            sc.cycles.use_adaptive_sampling = True
        except Exception:
            pass
    else:
        ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
        r.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in ids else 'BLENDER_EEVEE'
        ee = sc.eevee
        for attr, val in (("taa_render_samples", 64 if final else 16), ("use_raytracing", True),
                          ("use_ssr", True), ("use_gtao", True), ("use_shadows", True),
                          ("use_volumetric_shadows", True), ("volumetric_end", 1800.0),
                          ("volumetric_tile_size", '8' if final else '16'), ("use_bloom", False)):
            if hasattr(ee, attr):
                try:
                    setattr(ee, attr, val)
                except Exception:
                    pass
    vs = sc.view_settings
    try:
        vs.view_transform = 'AgX'
        for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
            try:
                vs.look = look
                break
            except Exception:
                pass
    except Exception:
        vs.view_transform = 'Filmic'
    vs.exposure = EXPOSURE_KEYS[0][1]
    r.use_motion_blur = False
    # Cycles の「永続データ」はオフ。表示/非表示の切り替えが続く長い連続レンダリングで、
    # オブジェクトごとのプロパティ（建設マスク）が食い違い、石垣が透ける現象を確認したため
    if hasattr(r, "use_persistent_data"):
        r.use_persistent_data = False
    r.filepath = CFG["OUTPUT_PATH"]
    ims = r.image_settings
    if CFG["OUTPUT_VIDEO"]:
        if hasattr(ims, "media_type"):
            ims.media_type = 'VIDEO'
        ims.file_format = 'FFMPEG'
        r.ffmpeg.format = 'MPEG4'
        r.ffmpeg.codec = 'H264'
        r.ffmpeg.constant_rate_factor = 'HIGH'
    else:
        if hasattr(ims, "media_type"):
            ims.media_type = 'IMAGE'
        ims.file_format = 'PNG'
        ims.color_mode = 'RGB'


def setup_compositor():
    """グレア（ブルーム）で金のハイライトをにじませる。4.x と 5.x で構造が違うので両対応。"""
    if not CFG["USE_GLARE"]:
        return
    sc = bpy.context.scene
    try:
        if hasattr(sc, "compositing_node_group"):          # 5.x
            ng = bpy.data.node_groups.new(PREFIX + "Compositor", "CompositorNodeTree")
            ng.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
            rl = ng.nodes.new("CompositorNodeRLayers")
            gl = ng.nodes.new("CompositorNodeGlare")
            out = ng.nodes.new("NodeGroupOutput")
            ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
            ng.links.new(gl.outputs["Image"], out.inputs[0])
            sc.compositing_node_group = ng
        else:                                              # 4.x
            sc.use_nodes = True
            nt = sc.node_tree
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            rl = nt.nodes.new("CompositorNodeRLayers")
            gl = nt.nodes.new("CompositorNodeGlare")
            comp = nt.nodes.new("CompositorNodeComposite")
            nt.links.new(rl.outputs["Image"], gl.inputs["Image"])
            nt.links.new(gl.outputs["Image"], comp.inputs["Image"])
        if "Type" in gl.inputs:
            gl.inputs["Type"].default_value = "Bloom"
        else:
            try:
                gl.glare_type = 'BLOOM'
            except Exception:
                gl.glare_type = 'FOG_GLOW'
        for name, val in (("Threshold", 1.4), ("Strength", 0.45), ("Size", 0.55)):
            if name in gl.inputs:
                gl.inputs[name].default_value = val
        if hasattr(gl, "threshold") and "Threshold" not in gl.inputs:
            gl.threshold = 1.4
            gl.mix = -0.55
            gl.size = 7
        sc.render.use_compositing = True
    except Exception as ex:
        log("コンポジターの設定をスキップ:", ex)


def key_material_values():
    """マテリアル内の時間変化（夕景の金の発光・水面のさざ波）。"""
    nt = MAT["Kinpaku"].node_tree
    for f, v in GOLD_GLOW_KEYS:
        key_socket(nt.nodes["GoldGlow"].outputs[0], v, f)
    hz = MAT["Mountain"].node_tree.nodes["Haze"]
    for f, _z, _hs, ha, strength in SKY_KEYS:
        key_socket(hz.outputs[0], (ha[0] * strength, ha[1] * strength, ha[2] * strength, 1.0), f)
    sc = bpy.context.scene
    for f, v in EXPOSURE_KEYS:
        sc.view_settings.exposure = v
        sc.view_settings.keyframe_insert("exposure", frame=f)
    wn = MAT["Water"].node_tree.nodes["WaterNoise"]
    key_socket(wn.inputs["W"], 0.0, CFG["FRAME_START"])
    key_socket(wn.inputs["W"], 14.0, CFG["FRAME_END"])
    set_interp(MAT["Water"].node_tree, "LINEAR")


# =============================================================================
# 13. main()
# =============================================================================
def main():
    t0 = time.time()
    log("Blender", ".".join(map(str, BV)), "で実行 / モード:", CFG["MODE"])
    if CFG["MODE"] == "ANIM_ONLY":
        reapply_animations()
        return
    cleanup()
    RNG.seed(CFG["SEED"])
    root = coll(ROOT_NAME)
    for key, name in (("env", "TS_00_環境"), ("nawabari", "TS_01_縄張り"), ("ishigaki", "TS_02_石垣"),
                      ("honmaru", "TS_03_本丸"), ("tenshu", "TS_04_天守"), ("site", "TS_05_普請場"),
                      ("life", "TS_06_人と町"), ("fx", "TS_07_演出"), ("camlight", "TS_08_カメラと光"),
                      ("assets", "TS_99_ASSETS_差し替え用")):
        COL[key] = coll(name, root)
    build_materials()
    build_assets()
    build_camera()          # 木や作業員がカメラの通り道を避けるため先に作る
    build_world()
    build_sun()
    build_terrain()
    build_mountains()
    build_fog()
    build_clouds()
    build_trees()
    build_nawabari()
    build_ishigaki()
    build_honmaru()
    build_tenshu()
    build_site()
    build_town()
    apply_all_builds()      # ここまでに sched() したものをキーフレームに変換
    build_workers()
    build_oxcarts()
    build_glints()
    build_titles()
    key_material_values()
    setup_render()
    setup_compositor()
    sc = bpy.context.scene
    sc.frame_set(760)
    log("完成: オブジェクト数 %d / %.1f 秒" % (len(root.all_objects), time.time() - t0))


if __name__ == "__main__":
    main()
