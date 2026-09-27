#!/usr/bin/env python3
"""从官方 *_bbox.png 派生 MaaFramework 的 roi，写回 pipeline JSON。

官方 AALC 没有 roi 概念，它用「同位置的 *_bbox.png 模板」把匹配范围限定在
一个窗口内（ImageUtils.get_bbox）。本项目跑在 MaaFramework 上，同样的语义
用 roi 表达。roi 与模板同源，因此可自动推导，无需手填坐标。

官方流程（以 infinity_mirror 为例，mirror.py:156-164）:
    bbox = get_bbox(load_image(".../infinity_mirror_bbox.png"))
    bbox = (bbox[0]-70, bbox[1], bbox[2]+100, bbox[3])   # 官方手动外扩
    在该区域内 find_text / click_element

对应到本项目:
    roi = [x1, y1, w, h]   （已按 1280x720 归一化）

用法:
  python3 scripts/apply_roi.py --check    # 只看会改什么
  python3 scripts/apply_roi.py --apply    # 写回
"""
import os, sys, glob, json, argparse
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

UP = 'upstream/aalc/assets/images/default'
OUR_IMG = 'assets/resource/image'
SCALE = 720 / 1440
# 官方在部分 bbox 上做了手动外扩（mirror.py:157-162），这里复刻同样的外扩量
OFFICIAL_EXPAND = {
    'mirror/road_to_mir/infinity_mirror_bbox.png': (-70, 0, 100, 0),
}


def get_bbox(arr, threshold=0):
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


def roi_from_bbox(bbox_rel):
    """官方 *_bbox.png（2560x1440）-> 720p 的 [x, y, w, h]，带官方外扩量"""
    src = None
    for sub in ('share', 'zh_cn', 'en'):
        p = f'{UP}/{sub}/{bbox_rel}'
        if os.path.exists(p):
            src = p
            break
    if not src:
        return None
    img = Image.open(src).convert('RGBA')
    w, h = img.size
    arr = np.array(img.resize((int(round(w * SCALE)), int(round(h * SCALE))), Image.BOX))
    bb = get_bbox(arr)
    if bb is None:
        return None
    x1, y1, x2, y2 = bb
    lx, ty, rx, by = OFFICIAL_EXPAND.get(bbox_rel, (0, 0, 0, 0))
    x1 = max(0, x1 + lx)
    y1 = max(0, y1 + ty)
    x2 = min(arr.shape[1], x2 + rx)
    y2 = min(arr.shape[0], y2 + by)
    return [x1, y1, max(1, x2 - x1), max(1, y2 - y1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    # 我们工程里已存在的 bbox 模板（与官方同名）
    bboxes = sorted(glob.glob(f'{OUR_IMG}/**/*_bbox.png', recursive=True))
    bbox_rel = {os.path.relpath(p, OUR_IMG): p for p in bboxes}
    print(f"工程内 bbox 模板 {len(bbox_rel)} 张\n")

    applied, skipped = [], []
    for p in sorted(glob.glob('assets/resource/pipeline/**/*.json', recursive=True)):
        path = os.path.basename(p)
        d = json.load(open(p))
        changed = False
        for name, node in d.items():
            rec = node.get('recognition')
            if not isinstance(rec, dict) or rec.get('type') != 'TemplateMatch':
                continue
            tpl = rec.get('template')
            if not isinstance(tpl, str):
                continue
            # 同目录同名前缀的 bbox：foo.png -> foo_bbox.png
            stem = tpl[:-4]
            cand = None
            for suffix in ('', '_assets'):
                key = f'{stem}{suffix}_bbox.png'
                if key in bbox_rel:
                    cand = key
                    break
            if not cand:
                continue
            roi = roi_from_bbox(cand)
            if not roi:
                continue
            if node.get('roi') == roi:
                continue
            node['roi'] = roi
            changed = True
            applied.append((path, name, tpl, cand, roi))
        if changed and args.apply:
            json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print(f"可加 roi 的节点: {len(applied)}")
    for path, name, tpl, cand, roi in applied:
        print(f"  {path} | {name}\n      tpl={tpl}\n      bbox={cand} -> roi={roi}")
    if not args.apply:
        print("\n(未写回，加 --apply 生效)")


if __name__ == '__main__':
    main()
