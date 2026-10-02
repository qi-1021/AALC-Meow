#!/usr/bin/env python3
"""按官方 AALC 的图像管线重新导出全部模板到 720p 基准。

严格复刻 upstream/aalc 的顺序（utils/image_utils.py）:
  load_image()  ->  整张 2560x1440 按 win_size/1440 用 INTER_AREA 缩放
                ->  get_bbox() 在缩放后的图上取有效区域
官方在 win_size=720（即本项目控制器的截图短边）时等价于：
  2560x1440 --INTER_AREA x0.5--> 1280x720 --get_bbox--> crop

用法:
  python3 scripts/regen_templates.py --check     # 只审计，不写文件
  python3 scripts/regen_templates.py --apply     # 写回 assets/resource/image
"""
import os, sys, glob, json, argparse
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

UP = 'upstream/aalc/assets/images/default'
OUR = 'assets/resource/image'
TARGET_SHORT = 720
REF_SHORT = 1440
SCALE = TARGET_SHORT / REF_SHORT          # 0.5
SEARCH_ORDER = ('share', 'zh_cn', 'en')    # 官方 load_image 的查找顺序

# 显式路径映射：解决 AALC-Meow 与官方命名微小差异的模板（如 enkephalin_confirm_assets -> confirm.png）
EXPLICIT_SOURCE_MAP = {
    'enkephalin/confirm.png': 'upstream/aalc/assets/images/default/share/enkephalin/enkephalin_confirm_assets.png',
    'enkephalin/cancel.png': 'upstream/aalc/assets/images/default/share/enkephalin/enkephalin_cancel_assets.png',
    'mail/confirm.png': 'upstream/aalc/assets/images/default/share/mail/get_mail_prize_confirm.png',
    'mirror/to_window_forfeit_confirm.png': 'upstream/aalc/assets/images/default/share/mirror/road_in_mir/towindow&forfeit_confirm_assets.png',
    'pass/missions.png': 'upstream/aalc/assets/images/default/zh_cn/pass/pass_missions_assets.png',
    'story/skip_confirm.png': 'upstream/aalc/assets/images/default/share/scenes/story_skip_confirm_assets.png',
    'battle/win_rate.png': 'upstream/aalc/assets/images/default/share/battle/win_rate_assets.png',
    'battle/gear_right.png': 'upstream/aalc/assets/images/default/share/battle/gear_right.png',
}

# 彻底拔除真机 1080p 历史截图保留列表，统一对齐 720p（0.5x）黄金基准
KEEP_REAL_SCREENSHOT = set()


def official_get_bbox(arr, threshold=0):
    """复刻 ImageUtils.get_bbox"""
    if arr.ndim == 3 and arr.shape[2] >= 3:
        arr = np.max(arr[:, :, :3], axis=2)
    elif arr.ndim == 3:
        arr = arr[:, :, 0]
    x = np.where(np.max(arr, axis=0) > threshold)[0]
    if len(x) == 0:
        return None
    y = np.where(np.max(arr, axis=1) > threshold)[0]
    if len(y) == 0:
        return None
    return int(x[0]), int(y[0]), int(x[-1] + 1), int(y[-1] + 1)


def find_official(rel):
    """按 load_image 的顺序定位官方源文件"""
    if rel in EXPLICIT_SOURCE_MAP:
        src = EXPLICIT_SOURCE_MAP[rel]
        if os.path.exists(src):
            return src
    for sub in SEARCH_ORDER:
        p = f'{UP}/{sub}/{rel}'
        if os.path.exists(p):
            return p
    # 回退：按纯文件名在官方树里找
    base = os.path.basename(rel)[:-4]
    for suf in ('_assets', '_bbox'):
        if base.endswith(suf):
            base = base[:-len(suf)]
            break
    for sub in SEARCH_ORDER:
        for pat in (f'{UP}/{sub}/**/{base}_assets.png', f'{UP}/{sub}/**/{base}.png'):
            hits = sorted(glob.glob(pat, recursive=True))
            if hits:
                return hits[0]
    return None


def derive(up_path):
    """官方 2560x1440 -> 0.5 缩放 -> get_bbox -> crop，返回 RGBA ndarray

    官方用 cv2.INTER_AREA 缩放；2560->1280 正好 0.5，PIL 的 BOX 滤波
    等价于 2x2 均值，与 INTER_AREA 一致。
    """
    img = Image.open(up_path).convert('RGBA')
    w, h = img.size
    nw, nh = int(round(w * SCALE)), int(round(h * SCALE))
    arr = np.array(img.resize((nw, nh), Image.BOX))
    bb = official_get_bbox(arr)
    if bb is None:
        return None
    x1, y1, x2, y2 = bb
    return arr[y1:y2, x1:x2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    ours = sorted(glob.glob(f'{OUR}/**/*.png', recursive=True))
    stats = {'ok': 0, 'fixed': 0, 'kept': 0, 'no_source': 0, 'empty': 0}
    fixed, no_source, kept, ok = [], [], [], []

    for p in ours:
        rel = os.path.relpath(p, OUR)
        if rel in KEEP_REAL_SCREENSHOT:
            kept.append(rel)
            stats['kept'] += 1
            continue
        src = find_official(rel)
        if not src:
            no_source.append(rel)
            stats['no_source'] += 1
            continue
        crop = derive(src)
        if crop is None or crop.size == 0:
            no_source.append(rel + '  (官方源无有效像素)')
            stats['empty'] += 1
            continue
        cur = Image.open(p)
        same = cur.size == (crop.shape[1], crop.shape[0])
        if same:
            ok.append(rel)
            stats['ok'] += 1
        else:
            fixed.append((rel, cur.size, (crop.shape[1], crop.shape[0])))
            stats['fixed'] += 1
            if args.apply:
                Image.fromarray(crop).save(p)

    print(f"总计 {len(ours)} 张")
    print(f"  尺寸已正确      : {stats['ok']}")
    print(f"  需重导(已{'写回' if args.apply else '待写回'}) : {stats['fixed']}")
    print(f"  有意保留真机截图: {stats['kept']}  {sorted(KEEP_REAL_SCREENSHOT)}")
    print(f"  官方无源(自造)  : {stats['no_source']}")
    print()
    if fixed:
        print("=== 比例被修正的模板（前 40）===")
        for rel, old, new in fixed[:40]:
            print(f"  {rel}: {old[0]}x{old[1]} -> {new[0]}x{new[1]}")
    print()
    print("=== 无官方源、需人工判定是否为自造/来自 AALC_Python ===")
    for rel in no_source:
        print("  ", rel)
    json.dump({'fixed': fixed, 'no_source': no_source, 'kept': kept, 'ok': ok},
              open('/tmp/regen_report.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
