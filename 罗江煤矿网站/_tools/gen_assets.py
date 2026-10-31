# -*- coding: utf-8 -*-
r"""
罗江煤矿 · 企业网站素材生成
------------------------------------------------------------------
用法：  python 凌汛素材\罗江煤矿网站\_tools\gen_assets.py
输出：  凌汛素材\罗江煤矿网站\assets\
------------------------------------------------------------------
全部 PIL 手画，没有 AI 生图。
风格照 1999–2003 年那批国企网站：深蓝、灰、红，井架剪影，像素图标，
边缘要硬（先画小图再 NEAREST 放大），别做现代的圆角和阴影。
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
OUT = os.path.join(SITE, "assets")
os.makedirs(OUT, exist_ok=True)

# ── 那个年代的配色 ────────────────────────────────────────────
NAVY   = (0, 32, 80, 255)      # 主色：深蓝
NAVY_2 = (0, 51, 120, 255)
STEEL  = (86, 104, 132, 255)
GREY   = (192, 196, 200, 255)
GREY_2 = (128, 134, 140, 255)
WHITE  = (255, 255, 255, 255)
RED    = (200, 16, 24, 255)
RED_2  = (140, 8, 16, 255)
YELLOW = (255, 208, 0, 255)
BLACK  = (16, 16, 16, 255)


def font(size, bold=True):
    for c in ((r"C:\Windows\Fonts\simhei.ttf" if bold else r"C:\Windows\Fonts\simsun.ttc"),
              r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


def save(im, name):
    p = os.path.join(OUT, name)
    im.save(p)
    print("  %-18s %dx%d" % (name, im.size[0], im.size[1]))
    return p


def pixel(w, h, fn, scale=4):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), w, h)
    return im.resize((w * scale, h * scale), Image.NEAREST)


# ── 1. 顶部横幅：井架剪影 + 矿名 ──────────────────────────────
def banner():
    W, H = 780, 92
    im = Image.new("RGBA", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    # 竖向渐变（上面亮一点）
    for y in range(H):
        k = 1 - y / float(H)
        d.line([(0, y), (W, y)], fill=(int(NAVY[0] + 34 * k),
                                       int(NAVY[1] + 52 * k),
                                       int(NAVY[2] + 70 * k), 255))
    # 远处煤山
    d.polygon([(0, H), (0, 62), (120, 44), (250, 66), (360, 52), (470, 70), (W, 58), (W, H)],
              fill=(8, 24, 56, 255))
    # 井架剪影（右侧）
    bx = 600
    d.line([(bx, 84), (bx + 22, 16), (bx + 44, 84)], fill=(10, 26, 58, 255), width=4)
    for yy in (40, 54, 68):
        wdt = int((yy - 16) / 68.0 * 44)
        d.line([(bx + 22 - wdt // 2, yy), (bx + 22 + wdt // 2, yy)], fill=(10, 26, 58, 255), width=3)
    d.line([(bx + 22, 16), (bx + 22, 6)], fill=(10, 26, 58, 255), width=3)
    d.line([(bx - 16, 84), (bx + 60, 84)], fill=(10, 26, 58, 255), width=5)
    # 矿名
    d.text((26, 16), "罗江煤矿", font=font(44), fill=WHITE)
    d.text((30, 66), "L U O J I A N G   C O A L   M I N E", font=font(11, False), fill=(150, 176, 214, 255))
    # 右上角红方块（那个年代爱用的角标）
    d.rectangle([W - 132, 10, W - 118, 24], fill=RED)
    d.rectangle([W - 108, 10, W - 94, 24], fill=YELLOW)
    d.rectangle([W - 84, 10, W - 70, 24], fill=STEEL)
    d.rectangle([0, 0, W - 1, H - 1], outline=(0, 0, 0, 255), width=1)
    return save(im, "banner.png")


# ── 2. 井架图标 ───────────────────────────────────────────────
def jijia():
    def draw(d, w, h):
        d.line([(3, 30), (10, 1), (17, 30)], fill=STEEL, width=2)
        for y in (11, 18, 25):
            k = (y - 1) / 29.0
            half = int(k * 7)
            d.line([(10 - half, y), (10 + half, y)], fill=STEEL)
        d.line([(10, 1), (22, 8)], fill=STEEL)
        d.line([(0, 31), (21, 31)], fill=GREY_2, width=2)
        d.ellipse([19, 5, 27, 13], fill=RED)
    return save(pixel(28, 33, draw, 4), "jijia.png")


# ── 3. 矿车 ───────────────────────────────────────────────────
def cart():
    def draw(d, w, h):
        d.polygon([(2, 4), (26, 4), (23, 15), (5, 15)], fill=GREY_2, outline=BLACK)
        d.line([(2, 5), (26, 5)], fill=GREY)
        d.polygon([(6, 5), (11, 5), (10, 12), (7, 12)], fill=(40, 40, 40, 255))
        d.polygon([(13, 5), (18, 5), (17, 12), (14, 12)], fill=(40, 40, 40, 255))
        d.ellipse([3, 15, 9, 21], fill=(60, 60, 60, 255), outline=BLACK)
        d.ellipse([19, 15, 25, 21], fill=(60, 60, 60, 255), outline=BLACK)
    return save(pixel(28, 22, draw, 4), "cart.png")


# ── 4. 矿灯 ───────────────────────────────────────────────────
def lamp():
    def draw(d, w, h):
        d.ellipse([3, 2, 17, 12], fill=YELLOW, outline=GREY_2)
        d.ellipse([7, 5, 13, 9], fill=WHITE)
        d.rectangle([5, 12, 15, 20], fill=GREY_2, outline=BLACK)
        d.rectangle([6, 13, 14, 15], fill=GREY)
        d.line([(8, 20), (8, 25)], fill=STEEL, width=2)
        d.line([(12, 20), (12, 25)], fill=STEEL, width=2)
    return save(pixel(20, 27, draw, 4), "lamp.png")


# ── 5. 广播喇叭 ───────────────────────────────────────────────
def speaker():
    def draw(d, w, h):
        d.polygon([(2, 8), (8, 8), (15, 2), (15, 18), (8, 12), (2, 12)],
                  fill=GREY_2, outline=BLACK)
        # 声波
        for i, r in enumerate((5, 8, 11)):
            d.arc([15 - r + 6, 10 - r, 15 + r + 6, 10 + r], -55, 55, fill=STEEL)
    return save(pixel(30, 21, draw, 4), "speaker.png")


# ── 6. 红星（光荣榜用） ───────────────────────────────────────
def star():
    def draw(d, w, h):
        d.polygon([(8, 0), (10, 6), (16, 6), (11, 10), (13, 16),
                   (8, 12), (3, 16), (5, 10), (0, 6), (6, 6)],
                  fill=RED, outline=RED_2)
        d.point((8, 5), fill=YELLOW)
        d.point((7, 6), fill=YELLOW)
        d.point((9, 6), fill=YELLOW)
    return save(pixel(17, 17, draw, 4), "star.png")


# ── 7. 底纹：深色网格 ─────────────────────────────────────────
def bg_tile():
    S = 16
    im = Image.new("RGBA", (S, S), (244, 246, 248, 255))
    d = ImageDraw.Draw(im)
    d.line([(0, 0), (S - 1, 0)], fill=(226, 230, 236, 255))
    d.line([(0, 0), (0, S - 1)], fill=(226, 230, 236, 255))
    return save(im.resize((S * 4, S * 4), Image.NEAREST), "bg-tile.png")


# ── 8. 标题条：深蓝渐变，做成 2px 宽可横向平铺（红线由 CSS 加） ──
def titlebar():
    W, H = 2, 24
    im = Image.new("RGBA", (W, H), NAVY_2)
    d = ImageDraw.Draw(im)
    for y in range(H):
        k = 1 - y / float(H)
        d.line([(0, y), (W - 1, y)], fill=(int(NAVY_2[0] + 44 * k),
                                           int(NAVY_2[1] + 64 * k),
                                           int(NAVY_2[2] + 84 * k), 255))
    return save(im, "titlebar.png")


# ── 9. 计划生育标语横幅 ───────────────────────────────────────
def jhsy_banner():
    W, H = 780, 56
    im = Image.new("RGBA", (W, H), (196, 14, 22, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, H - 1], outline=YELLOW, width=3)
    d.rectangle([5, 5, W - 6, H - 6], outline=(255, 255, 255, 110), width=1)
    # 两头的花饰
    for x in (18, W - 34):
        d.rectangle([x, H // 2 - 9, x + 15, H // 2 + 9], fill=YELLOW, outline=None)
        d.rectangle([x + 4, H // 2 - 5, x + 11, H // 2 + 5], fill=(196, 14, 22, 255))
    d.text((W // 2, H // 2 + 1), "抓好计划生育　少生优生　幸福一生",
           font=font(30), fill=(255, 255, 255, 255), anchor="mm")
    return save(im, "jhsy-banner.png")


if __name__ == "__main__":
    print("生成到 " + OUT)
    banner()
    jijia()
    cart()
    lamp()
    speaker()
    star()
    bg_tile()
    titlebar()
    jhsy_banner()
    print("完成。")
