# -*- coding: utf-8 -*-
"""
坨罗山高级中学官网 · 图片生成器
================================
用 Pillow 生成「能画的部分」（画不出的真实照片请自行换图）：
  1) 素材/banner/banner.jpg          首图横幅：淡紫粉天空 + 云 + 白鸽 + 红丝带
  2) 素材/banner/strip-values.jpg    社会主义核心价值观通栏：红金书法 + 24 字
  3) 素材/banner/strip-study.jpg     学习强国通栏：红金通栏

画法：所有图按 SS 倍超采样绘制，最后 LANCZOS 缩回目标尺寸 —— 边缘才干净。

用法：  python gen_images.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "素材", "banner")
os.makedirs(OUT, exist_ok=True)

SS = 2  # 超采样倍数

FONTS = {
    "hei":  r"C:\Windows\Fonts\simhei.ttf",
    "kai":  r"C:\Windows\Fonts\simkai.ttf",
    "song": r"C:\Windows\Fonts\simsun.ttc",
    "yh":   r"C:\Windows\Fonts\msyh.ttc",
    "yhbd": r"C:\Windows\Fonts\msyhbd.ttc",
    "fang": r"C:\Windows\Fonts\simfang.ttf",
}


def font(name, size):
    return ImageFont.truetype(FONTS[name], size)


# ---------------------------------------------------------------- 基础工具
def norm01(a):
    """把数组线性拉回 0..1，避免梯度对比不够。"""
    lo, hi = float(a.min()), float(a.max())
    return (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)


def vgrad(h, w, stops):
    """纵向多段渐变。stops = [(pos0..1, (r,g,b)), ...]，按位置排序。"""
    t = np.linspace(0.0, 1.0, h)[:, None]
    col = np.zeros((h, 1, 3), dtype=np.float32)
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        m = (t >= p0) & (t <= p1)
        if not m.any():
            continue
        k = np.clip((t - p0) / max(p1 - p0, 1e-6), 0, 1)[:, :, None]
        c0a = np.float32(c0)[None, None, :]
        c1a = np.float32(c1)[None, None, :]
        val = c0a + (c1a - c0a) * k
        col = np.where(m[:, :, None], val, col)
    col = np.where((t < stops[0][0])[:, :, None], np.float32(stops[0][1])[None, None, :], col)
    col = np.where((t > stops[-1][0])[:, :, None], np.float32(stops[-1][1])[None, None, :], col)
    return np.repeat(col, w, axis=1)


def to_img(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def to_arr(img):
    return np.asarray(img).astype(np.float32)


def blur_img(img, r):
    return img.filter(ImageFilter.GaussianBlur(r))


def smoothstep(a, b, x):
    t = np.clip((x - a) / max(b - a, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def fill_from_curve(size, xs, ys, color, alpha=255):
    """把一条折线以下的区域填成 color（透明底 RGBA 图层）。"""
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    pts = list(zip(xs, ys)) + [(w - 1, h - 1), (0, h - 1)]
    d.polygon(pts, fill=color + (alpha,))
    return layer


def add(dst, layer, pos=None):
    """RGBA 图层叠加到 RGB 图；pos 给了就在该位置贴（默认整幅 alpha_composite）。"""
    base = dst.convert("RGBA")
    if pos is None:
        base.alpha_composite(layer)
    else:
        base.alpha_composite(layer, dest=(int(pos[0]), int(pos[1])))
    return base.convert("RGB")


def screen(base, layer, opacity=1.0):
    """screen 混合，用来做柔光/发光。"""
    b = to_arr(base)
    l = to_arr(layer.convert("RGB")) * opacity
    out = 255.0 - (255.0 - b) * (255.0 - l) / 255.0
    return to_img(out)


def noise_field(shape, cells=4, seed=1, smooth=True):
    """低分辨率随机场，放大成平滑噪声（用于云/褶皱）。"""
    rng = np.random.default_rng(seed)
    h, w = shape
    small = rng.random((max(cells, 2), max(cells, 2))).astype(np.float32)
    im = Image.fromarray((small * 255).astype(np.uint8), "L").resize((w, h), Image.BICUBIC)
    if smooth:
        im = im.filter(ImageFilter.GaussianBlur(max(w, h) / 130.0))
    return to_arr(im) / 255.0


# ================================================================ 1. 首图横幅
def sky_base(W, H):
    """淡紫粉天空：底部暖白霞光，中部粉，顶部淡紫蓝。"""
    stops = [
        (0.00, (150, 132, 208)),   # 顶部淡紫
        (0.18, (196, 172, 228)),
        (0.38, (240, 199, 218)),   # 粉
        (0.62, (253, 226, 220)),
        (0.82, (255, 246, 232)),   # 暖近白
        (1.00, (255, 251, 240)),
    ]
    arr = vgrad(H, W, stops)
    # 左右轻微冷暖差：左侧偏紫、右侧偏粉
    x = np.linspace(0, 1, W)[None, :, None]
    arr = arr + np.concatenate([-14 * x, -6 * x, 4 * x], axis=2)
    return arr


def draw_scene(W, H, base_frac=0.905, alpha_scale=1.0):
    """底部远景：树影 + 校园建筑剪影 + 旗杆，压住画面下缘。"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    base = int(H * base_frac)

    def A(a):
        return int(max(0, min(255, a * alpha_scale)))

    # 树林（一排圆弧，高低错落）
    rng = np.random.default_rng(7)
    for i in range(70):
        x = int(rng.random() * W)
        r = int(H * (0.035 + rng.random() * 0.045))
        y = base + int(r * 0.35)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(196, 66, 60, A(120)))

    # 主楼群：中间一栋带塔尖，两侧矮楼
    def block(x0, x1, top, color, alpha=235):
        d.rectangle([x0, top, x1, H], fill=color + (A(alpha),))
        # 窗（用小横线暗示）
        n = max(int((x1 - x0) / (H * 0.052)), 1)
        for k in range(n):
            wx = x0 + (k + 0.5) * (x1 - x0) / n
            d.line([wx - H * 0.012, top + H * 0.06, wx + H * 0.012, top + H * 0.06],
                   fill=(255, 232, 214, A(70)), width=max(1, int(H * 0.012)))

    mid = W // 2
    block(mid - int(W * 0.075), mid + int(W * 0.075), int(H * 0.735), (176, 46, 44), 245)
    d.polygon([(mid - int(W * 0.080), int(H * 0.735)),
               (mid, int(H * 0.665)),
               (mid + int(W * 0.080), int(H * 0.735))], fill=(166, 40, 38, A(245)))
    block(mid - int(W * 0.185), mid - int(W * 0.082), int(H * 0.800), (188, 54, 50), 225)
    block(mid + int(W * 0.082), mid + int(W * 0.185), int(H * 0.800), (188, 54, 50), 225)
    block(int(W * 0.055), mid - int(W * 0.190), int(H * 0.858), (200, 66, 60), 200)
    block(mid + int(W * 0.190), int(W * 0.945), int(H * 0.858), (200, 66, 60), 200)

    # 旗杆 + 旗
    px = int(W * 0.815)
    d.line([px, int(H * 0.60), px, base + int(H * 0.02)], fill=(172, 44, 42, A(235)),
           width=max(2, int(H * 0.010)))
    d.polygon([(px, int(H * 0.605)), (px + int(W * 0.026), int(H * 0.632)),
               (px, int(H * 0.660))], fill=(214, 58, 52, A(240)))

    # 地面
    d.rectangle([0, base, W, H], fill=(168, 44, 42, A(225)))
    return layer


def draw_dove(size, alpha=235, tone=(255, 255, 255)):
    """海鸥/白鸽剪影：每只翅膀用「下缘 + 上缘」两条贝塞尔曲线夹出的实心尖翼。"""
    box = int(size)
    im = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = box / 100.0
    col = tone + (alpha,)

    def bez(p0, p1, p2, n=40):
        t = np.linspace(0, 1, n)[:, None]
        return (1 - t) ** 2 * np.array(p0) + 2 * (1 - t) * t * np.array(p1) + t ** 2 * np.array(p2)

    def wing(sign):
        root_top = (50 * s, 33 * s)
        ctrl_up = (50 * s + sign * 25 * s, 8 * s)
        tip = (50 * s + sign * 48 * s, 3 * s)
        ctrl_low = (50 * s + sign * 24 * s, 25 * s)
        root_low = (50 * s + sign * 2 * s, 50 * s)
        up = bez(root_top, ctrl_up, tip)
        low = bez(tip, ctrl_low, root_low)
        d.polygon([tuple(p) for p in up] + [tuple(p) for p in low][1:], fill=col)
    wing(-1)
    wing(1)

    # 身体：细长椭圆，和双翼根部重叠
    d.ellipse([50 * s - 20 * s, 44 * s, 50 * s + 6 * s, 59 * s], fill=col)
    # 尾
    d.polygon([(50 * s - 14 * s, 46 * s), (50 * s - 46 * s, 53 * s),
               (50 * s - 44 * s, 58 * s), (50 * s - 13 * s, 58 * s)], fill=col)
    # 头 + 喙
    d.polygon([(50 * s + 5 * s, 37 * s), (50 * s + 14 * s, 33 * s),
               (50 * s + 21 * s, 36 * s), (50 * s + 33 * s, 40 * s),
               (50 * s + 21 * s, 44 * s), (50 * s + 13 * s, 47 * s),
               (50 * s + 4 * s, 45 * s)], fill=col)

    im = im.filter(ImageFilter.GaussianBlur(box / 260.0))
    return im


def draw_bird_mark(size, stroke_ratio=0.115, alpha=240, tone=(255, 255, 255)):
    """远处的飞鸟标记：两笔柔和的外张弧线，小尺寸下最像鸟。"""
    box = int(size)
    im = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    W = box
    H = box
    lw = max(2, int(box * stroke_ratio))
    col = tone + (alpha,)

    def arc(x0, y0, x1, y1, x2, y2, n=48):
        t = np.linspace(0, 1, n)[:, None]
        p0 = np.array([x0, y0], dtype=np.float64)
        p1 = np.array([x1, y1], dtype=np.float64)
        p2 = np.array([x2, y2], dtype=np.float64)
        pts = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2
        return [tuple(p) for p in pts]

    # 左翼：从中点向左上方划出
    d.line(arc(W * 0.50, H * 0.62, W * 0.30, H * 0.10, W * 0.03, H * 0.30),
           fill=col, width=lw, joint="curve")
    # 右翼
    d.line(arc(W * 0.50, H * 0.62, W * 0.70, H * 0.10, W * 0.97, H * 0.30),
           fill=col, width=lw, joint="curve")

    im = im.filter(ImageFilter.GaussianBlur(box / 200.0))
    return im


def dove(W, H, x, y, s, angle=0.0, alpha=235):
    im = draw_dove(s * 1.65, alpha=alpha)
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC)
    return im, (int(x - im.size[0] / 2), int(y - im.size[1] / 2))


def cloud_blob(W, H, seed, cx, cy, width, height, alpha=0.85, puffs=7):
    """一朵由若干圆丘叠出来的云。cx/cy/width/height 为归一化坐标（0..1）。"""
    layer = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(layer)
    rng = np.random.default_rng(seed)
    x0 = cx * W
    y0 = cy * H
    bw = width * W
    bh = height * H
    for i in range(puffs):
        # 沿水平轴铺开，中间高、两端矮，宽度随机
        t = (i + 0.5) / puffs
        px = x0 + (t - 0.5) * bw + rng.normal(0, bw * 0.035)
        hump = np.sin(np.pi * min(max(t, 0), 1)) ** 0.75
        ry = bh * (0.30 + 0.70 * hump) * (0.75 + rng.random() * 0.5)
        rx = ry * (1.5 + rng.random() * 1.3)
        py = y0 + (1 - hump) * bh * 0.55 + rng.normal(0, bh * 0.05)
        d.ellipse([px - rx, py - ry, px + rx, py + ry], fill=255)
    layer = layer.filter(ImageFilter.GaussianBlur(min(W, H) * 0.012))
    a = np.asarray(layer).astype(np.float32) / 255.0
    return np.clip(a, 0, 1) * alpha


def ribbon(W, H):
    """红丝带：顺着画面底缘横贯的一条波浪缎带，左端翘起、右端上挑，带折面与柔光。"""
    xs = np.linspace(0, W - 1, W)
    t = xs / (W - 1.0)

    def wave(k, amp, phase):
        return amp * np.sin(2 * np.pi * (k * t + phase))

    # 上边缘：整体在画面下三分之一，左端高、右端更高，中间下沉
    edge = (H * 0.775
            - H * 0.150 * (1 - smoothstep(0.0, 0.30, t))          # 左端翘起
            + H * 0.095 * smoothstep(0.30, 0.62, t)               # 中段下沉
            - H * 0.140 * smoothstep(0.62, 1.0, t)                # 右端上挑
            + wave(1.6, H * 0.030, 0.15)
            + wave(3.1, H * 0.018, 0.62))
    edge = np.clip(edge, H * 0.22, H * 0.88)

    # 折面：沿边缘的锯齿位移，制造缎带翻转感
    surf = np.clip(edge + wave(2.4, H * 0.028, 0.30) * np.abs(np.sin(2 * np.pi * (2.4 * t + 0.3))),
                   H * 0.20, H * 0.90)

    shadow = fill_from_curve((W, H), xs, np.clip(surf + H * 0.030, 0, H - 1), (116, 12, 18), 120)
    shadow = shadow.filter(ImageFilter.GaussianBlur(H * 0.030))

    front = fill_from_curve((W, H), xs, surf, (206, 42, 40), 255)
    hi = fill_from_curve((W, H), xs, np.clip(surf + H * 0.010, 0, H - 1), (238, 108, 86), 155)
    hi = hi.filter(ImageFilter.GaussianBlur(H * 0.013))
    crease = fill_from_curve((W, H), xs, np.clip(surf + H * 0.062, 0, H - 1), (152, 22, 28), 115)
    crease = crease.filter(ImageFilter.GaussianBlur(H * 0.024))
    # 下方再叠一层更深的红，让缎带有厚度
    deep = fill_from_curve((W, H), xs, np.clip(surf + H * 0.130, 0, H - 1), (176, 30, 32), 190)
    deep = deep.filter(ImageFilter.GaussianBlur(H * 0.020))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for l in (shadow, deep, crease, front, hi):
        layer.alpha_composite(l)
    return layer


def ribbon_glow(W, H, layer):
    """丝带外发光：把丝带模糊后 screen 上去。"""
    glow = layer.filter(ImageFilter.GaussianBlur(H * 0.06))
    a = to_arr(glow)[:, :, 3:4] / 255.0
    rgb = to_arr(glow)[:, :, :3]
    out = Image.new("RGB", (W, H), (0, 0, 0))
    out = to_img(rgb * a * 0.55)
    return out


def save_out(img, name, preview_dir=None):
    """存图。preview_dir 给了就存 PNG 预览（方便迭代看图），否则存正式 jpg。"""
    if preview_dir:
        os.makedirs(preview_dir, exist_ok=True)
        p = os.path.join(preview_dir, os.path.splitext(name)[0] + ".png")
        img.save(p)
    else:
        os.makedirs(OUT, exist_ok=True)
        p = os.path.join(OUT, name)
        img.save(p, quality=93, subsampling=1)
    print("saved", p, img.size)
    return p


def make_banner(W=1920, H=420, preview_dir=None):
    w, h = W * SS, H * SS
    sky = to_img(sky_base(w, h))

    # 霞光：左上偏紫、中部暖白
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w * 0.62, h * 1.06
    r = np.sqrt(((xx - cx) / (w * 0.62)) ** 2 + ((yy - cy) / (h * 1.25)) ** 2)
    glow = np.clip(1.0 - r, 0, 1) ** 2.1
    glow = np.asarray(Image.fromarray((glow * 255).astype(np.uint8), "L")
                      .filter(ImageFilter.GaussianBlur(w / 90.0))).astype(np.float32) / 255.0
    a = to_arr(sky)
    warm = np.array([255, 238, 214], dtype=np.float32)[None, None, :]
    a = a + (warm - a) * (glow[:, :, None] * 0.85)
    sky = to_img(a)

    # 云层：一朵朵独立的积云，用最大值叠加，留出中间天空
    cloud_layer = np.zeros((h, w), dtype=np.float32)
    blobs = [
        # seed, cx,    cy,    width, height, alpha, puffs
        (3,  -0.02,  0.10,  0.30,  0.16,  0.80, 7),
        (11,  0.13,  0.02,  0.22,  0.12,  0.75, 6),
        (23,  0.33,  0.14,  0.26,  0.13,  0.62, 6),
        (31,  0.52,  0.04,  0.20,  0.11,  0.70, 5),
        (47,  0.68,  0.16,  0.30,  0.15,  0.80, 7),
        (59,  0.86,  0.06,  0.24,  0.13,  0.72, 6),
        (71,  0.97,  0.22,  0.22,  0.12,  0.65, 5),
        (83,  0.24,  0.30,  0.34,  0.12,  0.45, 6),
        (97,  0.75,  0.36,  0.36,  0.12,  0.42, 6),
    ]
    for seed, cx_, cy_, bw, bh, al, pf in blobs:
        cloud_layer = np.maximum(cloud_layer, cloud_blob(w, h, seed, cx_, cy_, bw, bh, al, pf))
    cl = np.clip(cloud_layer, 0, 1)
    a = to_arr(sky)
    white = np.array([255, 252, 250], dtype=np.float32)[None, None, :]
    a = a + (white - a) * cl[:, :, None]
    sky = to_img(a)

    # 远景校园（压在下缘，丝带掀起来以后露出来）+ 丝带
    scene = draw_scene(w, h, base_frac=0.880, alpha_scale=0.95)
    scene = scene.filter(ImageFilter.GaussianBlur(h * 0.0018))
    sky = add(sky, scene)

    rb = ribbon(w, h)
    sky = screen(sky, ribbon_glow(w, h, rb))
    sky = add(sky, rb)

    # 远处的飞鸟（一小群，避开中间校名与底部丝带）
    for (dx, dy, ds, al) in [(w * 0.085, h * 0.175, h * 0.150, 235),
                             (w * 0.150, h * 0.095, h * 0.105, 200),
                             (w * 0.205, h * 0.235, h * 0.085, 175),
                             (w * 0.115, h * 0.330, h * 0.070, 150)]:
        bm = draw_bird_mark(ds, alpha=al)
        sky = add(sky, bm, (int(dx - bm.size[0] / 2), int(dy - bm.size[1] / 2)))

    # 收尾：轻噪点 + 缩回目标尺寸
    a = to_arr(sky)
    rng = np.random.default_rng(5)
    a = a + rng.normal(0, 1.5, a.shape)
    a = np.clip(a, 0, 255)
    out = to_img(a).resize((W, H), Image.LANCZOS)
    return save_out(out, "banner.jpg", preview_dir)


# ============================================== 2. 社会主义核心价值观通栏
def red_cloth(W, H, seed=2, deep=(138, 16, 20), mid=(198, 30, 28), warm=(232, 74, 52)):
    """红绸底：径向明暗 + 斜向褶皱 + 布纹噪点。"""
    yy, xx = np.mgrid[0:H, 0:W]
    # 径向：中心亮、四角暗
    nx = (xx - W * 0.5) / (W * 0.5)
    ny = (yy - H * 0.5) / (H * 0.5)
    r = np.sqrt((nx * 0.85) ** 2 + (ny * 0.75) ** 2)
    base = np.clip(1.0 - r * 0.72, 0.18, 1.0)
    base = 0.35 + 0.65 * base

    arr = np.zeros((H, W, 3), dtype=np.float32)
    for ch in range(3):
        arr[:, :, ch] = deep[ch] + (mid[ch] - deep[ch]) * base

    # 斜向褶皱光带
    fold = np.sin((xx * 0.010 + yy * 0.026) + 0.8 * np.sin(xx * 0.0032))
    fold = (fold + 1) / 2
    fsm = np.asarray(Image.fromarray((fold * 255).astype(np.uint8), "L")
                     .filter(ImageFilter.GaussianBlur(W / 130.0))).astype(np.float32) / 255.0
    arr = arr + (np.array(warm, dtype=np.float32)[None, None, :] - arr) * (fsm[:, :, None] * 0.30)

    # 布纹
    rng = np.random.default_rng(seed)
    arr = arr + rng.normal(0, 4.0, arr.shape)
    # 暖色高光（左上）
    y2, x2 = np.mgrid[0:H, 0:W]
    hl = np.clip(1.0 - np.sqrt(((x2 - W * 0.22) / (W * 0.55)) ** 2 +
                               ((y2 - H * 0.15) / (H * 0.75)) ** 2), 0, 1) ** 2
    arr = arr + (np.array([255, 170, 120], dtype=np.float32)[None, None, :] - arr) * (hl[:, :, None] * 0.22)
    return arr


def gold_text(img, xy, text, fnt, anchor="mm", spread=2.6):
    """金色渐变艺术字：高光 + 主金 + 深棕描边阴影（直接画在 img 上）。"""
    x, y = xy
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # 1) 外发光（暖红）：只画一层，靠模糊扩散
    d.text((x, y), text, font=fnt, anchor=anchor, fill=(255, 118, 58, 78))
    layer = layer.filter(ImageFilter.GaussianBlur(spread))
    base = add(img, layer)

    # 2) 深棕描边（加深轮廓，字更立体）
    d2 = ImageDraw.Draw(base)
    for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
        d2.text((x + ox, y + oy), text, font=fnt, anchor=anchor, fill=(112, 20, 12))

    # 3) 金色主体：用遮罩做纵向渐变
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).text((x, y), text, font=fnt, anchor=anchor, fill=255)
    m = np.asarray(mask).astype(np.float32) / 255.0

    W, H = base.size
    g = np.linspace(0, 1, H)[:, None, None]
    # 金：顶部亮到发白，中部正金，底部深金
    c_top = np.float32([255, 249, 222])[None, None, :]
    c_mid = np.float32([247, 205, 96])[None, None, :]
    c_bot = np.float32([214, 145, 42])[None, None, :]
    k1 = np.clip(g / 0.35, 0, 1)
    k2 = np.clip((g - 0.35) / 0.65, 0, 1)
    gold = c_top + (c_mid - c_top) * k1
    gold = gold + (c_bot - gold) * k2
    gold = np.broadcast_to(gold, (H, W, 3)).astype(np.float32)

    # 内部高光条：让金面有反光
    sheen = (np.exp(-((g - 0.30) ** 2) / (2 * 0.055 ** 2)) * 0.55)
    gold = gold + (255.0 - gold) * np.broadcast_to(sheen, (H, W, 1))

    a = to_arr(base)
    a = a * (1 - m[:, :, None]) + gold * m[:, :, None]
    return to_img(a)


def ink_bbox(fnt, text):
    """量出文字真实渲染出来的像素包围盒（textbbox 对中文有时不准，这里直接渲染再取 bbox）。"""
    pad = 40
    w = max(int(fnt.getlength(text)) + pad * 2, 8)
    asc, desc = fnt.getmetrics()
    h = asc + desc + pad * 2
    probe = Image.new("L", (w, h), 0)
    ImageDraw.Draw(probe).text((pad, pad), text, font=fnt, fill=255)
    bb = probe.getbbox()
    if bb is None:
        return (0, 0, 0, 0)
    return (bb[0] - pad, bb[1] - pad, bb[2] - pad, bb[3] - pad)


def draw_values(img, ss_h):
    """画 24 字三组：组名 + 四字，白色粗体，带淡阴影，整体居中不溢出。"""
    d = ImageDraw.Draw(img, "RGBA")
    W = img.size[0]
    # 组与组之间 / 组名与内容之间（按画布高度取比例，后面还会按实际宽度微调）
    gap_group = ss_h * 0.150
    gap_word = ss_h * 0.048
    f_label = font("hei", int(ss_h * 0.112))
    f_val = font("hei", int(ss_h * 0.118))

    groups = [("国家", "富强  民主  文明  和谐"),
              ("社会", "自由  平等  公正  法治"),
              ("公民", "爱国  敬业  诚信  友善")]

    def layout(fa, fb, gw, gg):
        ms = []
        for name, vals in groups:
            nb = ink_bbox(fa, name)
            vb = ink_bbox(fb, vals)
            ms.append((name, vals, nb[2] - nb[0], vb[2] - vb[0]))
        tot = sum(nw + gw + vw for _, _, nw, vw in ms) + gg * (len(groups) - 1)
        return ms, tot

    metrics, total = layout(f_label, f_val, gap_word, gap_group)
    # 留出画布宽度 6% 的左右边距；超了就整体等比缩小
    maxw = W * 0.88
    if total > maxw:
        k = maxw / total
        f_label = font("hei", max(int(ss_h * 0.112 * k), 12))
        f_val = font("hei", max(int(ss_h * 0.118 * k), 12))
        gap_group *= k
        gap_word *= k
        metrics, total = layout(f_label, f_val, gap_word, gap_group)

    x = (W - total) / 2.0
    line_cy = int(ss_h * 0.755)
    # 组与组之间的细竖线
    sep_xs = []
    for i, (name, vals, nw, vw) in enumerate(metrics):
        nb = ink_bbox(f_label, name)
        d.text((x - nb[0], line_cy), name, font=f_label, anchor="lm", fill=(255, 255, 255, 255))
        tx = x + nw + gap_word
        vb = ink_bbox(f_val, vals)
        d.text((tx - vb[0] + 2, line_cy + 2), vals, font=f_val, anchor="lm", fill=(104, 12, 16, 135))
        d.text((tx - vb[0], line_cy), vals, font=f_val, anchor="lm", fill=(255, 255, 255, 255))
        x += nw + gap_word + vw
        if i < len(metrics) - 1:
            sep_xs.append(x + gap_group / 2)
            x += gap_group

    for sx in sep_xs:
        d.line([(sx, line_cy - ss_h * 0.055), (sx, line_cy + ss_h * 0.055)],
               fill=(255, 226, 170, 90), width=max(1, int(ss_h * 0.006)))


def make_values_strip(W=1920, H=360, preview_dir=None):
    ss_w, ss_h = W * SS, H * SS
    arr = red_cloth(ss_w, ss_h, seed=17)
    img = to_img(arr)

    # 四角压暗 + 金色细边框
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, 0, ss_w - 1, ss_h - 1], outline=(255, 214, 130, 46), width=max(2, ss_h // 150))
    d.rectangle([ss_h // 90, ss_h // 90, ss_w - ss_h // 90, ss_h - ss_h // 90],
                outline=(120, 12, 16, 90), width=max(1, ss_h // 260))

    # 主标题（书法体）
    title = "“社会主义核心价值观”"
    f_title = font("kai", int(ss_h * 0.335))
    img = gold_text(img, (ss_w // 2, int(ss_h * 0.325)), title, f_title, spread=ss_h * 0.010)

    # 白鸽点缀（左上）
    dv, pos = dove(ss_w, ss_h, ss_w * 0.055, ss_h * 0.34, ss_h * 0.115, -10, 120)
    img = add(img, dv)

    # ---------- 24 字三组 ----------
    draw_values(img, ss_h)
    d = ImageDraw.Draw(img, "RGBA")

    # 左下角五颗黄星（一大四小，弧形）
    star_cx, star_cy = ss_w * 0.035, ss_h * 0.845
    def star(cx, cy, r, fill):
        pts = []
        for i in range(10):
            ang = -np.pi / 2 + i * np.pi / 5
            rr = r if i % 2 == 0 else r * 0.40
            pts.append((cx + rr * np.cos(ang), cy + rr * np.sin(ang)))
        d.polygon(pts, fill=fill)
    star(star_cx, star_cy, ss_h * 0.062, (255, 226, 96, 245))
    for i, (ox, oy) in enumerate([(0.075, -0.030), (0.105, 0.008), (0.098, 0.055), (0.062, 0.078)]):
        star(star_cx + ss_w * ox, star_cy + ss_h * oy, ss_h * 0.020, (255, 226, 96, 235))

    out = img.resize((W, H), Image.LANCZOS)
    return save_out(out, "strip-values.jpg", preview_dir)


# ==================================================== 3. 学习强国通栏
def make_study_strip(W=1920, H=300, preview_dir=None):
    ss_w, ss_h = W * SS, H * SS
    # 红金底：偏亮红，中间暖
    arr = red_cloth(ss_w, ss_h, seed=41, deep=(146, 12, 16), mid=(208, 28, 24), warm=(240, 88, 56))
    # 中央横向暖光带（给 logo 留位）
    yy, xx = np.mgrid[0:ss_h, 0:ss_w]
    band = np.exp(-((yy - ss_h * 0.5) ** 2) / (2 * (ss_h * 0.42) ** 2))
    arr = arr + (np.array([255, 150, 90], dtype=np.float32)[None, None, :] - arr) * (band[:, :, None] * 0.18)
    img = to_img(arr)

    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, 0, ss_w - 1, ss_h - 1], outline=(255, 216, 140, 40), width=max(2, ss_h // 140))
    # 左侧留白给「学习强国」标准 logo，右侧放标语（标语用 HTML 更好换）
    d.rectangle([ss_h * 0.10, ss_h * 0.16, ss_h * 0.10 + ss_h * 1.55, ss_h * 0.84],
                outline=(255, 214, 150, 36), width=max(1, ss_h // 300))

    # 主标题：学习强国（书法体，金色）
    f = font("kai", int(ss_h * 0.335))
    img = gold_text(img, (int(ss_h * 0.10 + ss_h * 1.55 / 2), int(ss_h * 0.50)), "学习强国", f,
                    spread=ss_h * 0.012)

    # 底部小字（类似 xuexi.cn 的位置）
    d = ImageDraw.Draw(img)
    f2 = font("yh", int(ss_h * 0.085))
    d.text((int(ss_h * 0.10 + ss_h * 1.55 / 2), int(ss_h * 0.795)), "中共中央宣传部",
           font=f2, anchor="mm", fill=(255, 236, 206, 215))

    out = img.resize((W, H), Image.LANCZOS)
    return save_out(out, "strip-study.jpg", preview_dir)


if __name__ == "__main__":
    import sys
    # 用法：  python gen_images.py            存正式 jpg 到 素材/banner/
    #         python gen_images.py --preview DIR   存 PNG 到 DIR（看图迭代用）
    if "--preview" in sys.argv:
        pdir = sys.argv[sys.argv.index("--preview") + 1]
    else:
        pdir = None
    make_banner(preview_dir=pdir)
    make_values_strip(preview_dir=pdir)
    make_study_strip(preview_dir=pdir)
    if "--dove" in sys.argv:
        # 单独把鸽子放大成一张图，方便检查形状
        zoom = Image.new("RGB", (900, 600), (176, 150, 220))
        big = draw_dove(520, alpha=255)
        zoom.paste(big, (190, 40), big)
        p = os.path.join(pdir or OUT, "_dove-zoom.png")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        zoom.save(p)
        print("saved", p)
    print("done ->", pdir or OUT)
