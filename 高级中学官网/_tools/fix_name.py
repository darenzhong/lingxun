# -*- coding: utf-8 -*-
r"""
把照片里烧进去的「陀螺山」改成「坨罗山」
=======================================
HTML 里的字好改，**照片里的字是像素，只能在图上重画**。

两张轮播图都是"整行横排文字"，做法统一：
  用周围底色把前两个字盖掉 → 按同样字号把「坨罗」画回原位

坐标是**量出来的**（不是猜的）：在原图上打坐标网格，肉眼读边界。
  slide-2  陀 x395~445  y198~238    白字 / 红横幅
  slide-3  陀 x390~440  y92~135     金字 / 深色LED屏

校徽是金属圆环 + 弧形排字，自动补底会留金红条纹，**没有硬做**，
单独列在 fix_badge 里（默认不跑，见文件末尾说明）。

用法：
  python fix_name.py            # 处理 slide-2 和 slide-3
  python fix_name.py --dry-run  # 只出预览图，不改原图
"""
import os
import shutil
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = r"O:\mirror\凌汛素材\高级中学官网\素材"
BACKUP = os.path.join(os.path.dirname(ROOT), "_文字原图")
TEMP = os.environ.get("TEMP", ".")
HEI = r"C:\Windows\Fonts\simhei.ttf"

# 每张图要改的地方：全部是原图像素坐标（在原图上打坐标网格量出来的）
JOBS = [
    dict(
        rel="banner/slide-2.jpg",
        # 前两个字所在的红布区域。注意横幅下沿 y≈242 就翻成白墙了，不能再往下扩
        erase=(391, 195, 497, 241),
        pitch=51.0,               # 字距
        center_y=217,             # 文字行垂直中心
        first_center_x=420,       # 第一个字的中心 x
        font_size=45,
        # 红布是竖向渐变的，给首尾两色，逐行插值，避免一块死红
        fill_top=(188, 32, 52),
        fill_bottom=(197, 24, 40),
        text=(252, 252, 252),     # 白字
        stroke=(150, 30, 42),     # 白字外面一圈淡红，跟原图一致
        stroke_w=2,
    ),
    dict(
        rel="banner/slide-3.jpg",
        erase=(386, 88, 498, 138),
        pitch=50.5,
        center_y=113,
        first_center_x=416,
        font_size=43,
        fill_top=(86, 26, 24),    # LED 屏深底（实测约 (88,28,26)）
        fill_bottom=(76, 30, 28),
        text=(253, 235, 140),     # 金字
        stroke=(120, 70, 20),
        stroke_w=1,
    ),
]


def run(job, dry=False):
    src = os.path.join(ROOT, job["rel"].replace("/", os.sep))
    if not dry:
        bak = os.path.join(BACKUP, job["rel"].replace("/", os.sep))
        os.makedirs(os.path.dirname(bak), exist_ok=True)
        if not os.path.exists(bak):
            shutil.copy2(src, bak)

    S = 5                                   # 超采样，边缘才干净
    im = Image.open(src).convert("RGB")
    big = im.resize((im.width * S, im.height * S), Image.LANCZOS)
    d = ImageDraw.Draw(big)

    # 1) 逐行渐变盖掉原来的两个字（红色横幅/屏幕本身都有竖向明暗，平涂会露馅）
    x0, y0, x1, y1 = [v * S for v in job["erase"]]
    top = job["fill_top"]
    bot = job["fill_bottom"]
    h = y1 - y0
    for yy in range(int(y0), int(y1) + 1):
        t = (yy - y0) / h if h else 0
        col = tuple(int(round(top[j] + (bot[j] - top[j]) * t)) for j in range(3))
        d.line([(x0, yy), (x1, yy)], fill=col)

    # 2) 画出「坨罗」
    f = ImageFont.truetype(HEI, int(job["font_size"] * S))
    for i, ch in enumerate("坨罗"):
        cx = (job["first_center_x"] + job["pitch"] * i) * S
        cy = job["center_y"] * S
        bb = d.textbbox((0, 0), ch, font=f)
        tx = cx - (bb[2] - bb[0]) / 2 - bb[0]
        ty = cy - (bb[3] - bb[1]) / 2 - bb[1]
        d.text((tx, ty), ch, font=f, fill=job["text"],
               stroke_width=job["stroke_w"] * S, stroke_fill=job["stroke"])

    out = big.resize(im.size, Image.LANCZOS)
    dst = os.path.join(ROOT, job["rel"].replace("/", os.sep))
    if not dry:
        out.save(dst, "JPEG", quality=88, optimize=True, progressive=True, subsampling=1)

    # 出一个放大预览，方便立刻检查
    tag = os.path.basename(job["rel"]).replace(".jpg", "")
    px0, py0, px1, py1 = job["erase"]
    prev = out.crop((max(0, px0 - 100), max(0, py0 - 45),
                     min(out.width, px1 + 220), min(out.height, py1 + 45)))
    prev = prev.resize((prev.width * 3, prev.height * 3), Image.LANCZOS)
    p = os.path.join(TEMP, f"verify-{tag}.png")
    prev.save(p)
    print(f"  {job['rel']}  → {'(dry-run)' if dry else dst}")
    print(f"     预览: {p}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    for job in JOBS:
        run(job, dry)
    print("\n完成。预览图在系统临时目录，看一眼确认。")
