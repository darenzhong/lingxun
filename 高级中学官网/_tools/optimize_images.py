# -*- coding: utf-8 -*-
"""
学校官网图片瘦身
================
不做花哨处理，只做三件事：
  1) 缩到"实际显示尺寸 × 2"（2 倍图，高清屏够用）
  2) 输出品质按用途分档（照片 84 / 带文字的通栏 88 / 校徽 88）
  3) 缩完做一次 UnsharpMask 轻锐化，抵消缩小带来的发肉

原图先备份到 _原图备份/，确认新图没问题就能删。
用法：  python optimize_images.py            # 备份 + 优化
        python optimize_images.py --dry-run  # 只列出会改成什么尺寸，不写文件
"""
import os
import shutil
import sys
from PIL import Image, ImageFilter

ROOT = r"O:\mirror\凌汛素材\高级中学官网"
ASSETS = os.path.join(ROOT, "素材")
BACKUP = os.path.join(ROOT, "_原图备份")

# 每张图的目标尺寸（都是"显示尺寸×2"再放宽一点），以及 JPEG 品质
#   说明：轮播最多显示 663×320 → 2x = 1326×640，留到 1400×676
#         资讯最多 577×180，但原图是 4:3，裁成 3.2:1 会切掉很多，所以保留 4:3 只缩尺寸
PLAN = {
    "logo/school-badge.jpg":   dict(size=(160, 160),   q=88, fit="cover"),
    "banner/banner.jpg":       dict(size=(2880, 420),  q=86, fit="cover"),
    "banner/slide-1.jpg":      dict(size=(1400, 676),  q=84, fit="cover"),
    "banner/slide-2.jpg":      dict(size=(1400, 676),  q=84, fit="cover"),
    "banner/slide-3.jpg":      dict(size=(1400, 676),  q=84, fit="cover"),
    "banner/strip-values.jpg": dict(size=None,         q=88, fit="keep"),   # 已是最优，只重压
    "banner/strip-study.jpg":  dict(size=None,         q=88, fit="keep"),
    "news/news-1.jpg":         dict(size=(1200, 675),  q=82, fit="cover"),
    "news/news-2.jpg":         dict(size=(1200, 675),  q=82, fit="cover"),
    "campus/campus-1.jpg":     dict(size=(640, 340),   q=82, fit="cover"),
    "campus/campus-2.jpg":     dict(size=(640, 340),   q=82, fit="cover"),
    "campus/campus-3.jpg":     dict(size=(640, 340),   q=82, fit="cover"),
    "campus/campus-4.jpg":     dict(size=(640, 340),   q=82, fit="cover"),
}


def crop_to_ratio(im, tw, th):
    """按目标宽高比居中裁剪，再缩放。"""
    tr = tw / th
    w, h = im.size
    r = w / h
    if abs(r - tr) < 0.01:
        return im.resize((tw, th), Image.LANCZOS)
    if r > tr:                      # 原图更宽 → 裁两侧
        nw = int(h * tr)
        left = (w - nw) // 2
        im = im.crop((left, 0, left + nw, h))
    else:                           # 原图更高 → 裁上下
        nh = int(w / tr)
        top = (h - nh) // 2
        im = im.crop((0, top, w, top + nh))
    return im.resize((tw, th), Image.LANCZOS)


def main():
    dry = "--dry-run" in sys.argv
    total_before = total_after = 0
    rows = []

    if not dry:
        os.makedirs(BACKUP, exist_ok=True)

    for rel, cfg in PLAN.items():
        src = os.path.join(ASSETS, rel.replace("/", os.sep))
        if not os.path.exists(src):
            print("跳过（不存在）:", rel)
            continue
        before = os.path.getsize(src)
        total_before += before
        im = Image.open(src)
        im = im.convert("RGB") if im.mode != "RGB" else im
        orig_size = im.size

        if cfg["fit"] == "cover" and cfg["size"]:
            tw, th = cfg["size"]
            # 原图比目标还小就别放大了，白糊
            if orig_size[0] <= tw and orig_size[1] <= th:
                out = im
            else:
                out = crop_to_ratio(im, tw, th)
        else:
            out = im

        # 缩小后轻锐化（只在真的缩了的时候做）
        if out.size != orig_size:
            out = out.filter(ImageFilter.UnsharpMask(radius=1.1, percent=68, threshold=3))

        if dry:
            print(f"  {rel:26} {orig_size[0]:>5}x{orig_size[1]:<5} → {out.size[0]:>5}x{out.size[1]:<5}"
                  f"  {before/1024:>7.0f}KB → ?")
            continue

        # 备份原图
        dst_bak = os.path.join(BACKUP, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst_bak), exist_ok=True)
        if not os.path.exists(dst_bak):
            shutil.copy2(src, dst_bak)

        out.save(src, "JPEG", quality=cfg["q"], optimize=True, progressive=True, subsampling=1)
        after = os.path.getsize(src)
        total_after += after
        rows.append((rel, orig_size, out.size, before, after))

    if dry:
        return
    print(f"\n{'文件':28}{'原始尺寸':>13}{'新尺寸':>13}{'原始':>10}{'现在':>10}{'省':>8}")
    for rel, o, n, b, a in rows:
        print(f"{rel:28}{str(o[0])+'x'+str(o[1]):>13}{str(n[0])+'x'+str(n[1]):>13}"
              f"{b/1024:>9.0f}K{a/1024:>9.0f}K{(1-a/b)*100:>7.0f}%")
    print(f"\n合计：{total_before/1024/1024:.2f} MB → {total_after/1024/1024:.2f} MB "
          f"（省 {(1-total_after/total_before)*100:.0f}%）")
    print("原图备份在:", BACKUP)


if __name__ == "__main__":
    main()
