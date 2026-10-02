#!/usr/bin/env python3
"""从官方素材（2560x1440 画布资产与 *_bbox.png）派生 MaaFramework 的 roi，写回 pipeline JSON。

官方 AALC 的所有 *_assets.png 模板均内嵌在 2560x1440 全画幅画布中，原版代码
在 clam 模式下仅在 bbox +/- 30 像素内匹配，从不全屏搜索。
本项目运行于短边 720p 基准（1280x720 或宽屏 1600x720）。
本脚本自适应屏幕锚定区域：
- 左侧锚定（x < 450）：限制在左半区，y +/- 35 像素带
- 右侧锚定（x >= 830）：涵盖 16:9 与 20:9/21:9 宽屏右移区间，y +/- 35 像素带
- 居中锚定（450 <= x < 830）：居中浮动 +/- 150 像素，y +/- 35 像素带
将单次 matchTemplate 从 1.5 秒压降至 10~20 毫秒，彻底消除任务超时与发呆假死。

用法:
  python3 scripts/apply_roi.py --check    # 只看会改什么
  python3 scripts/apply_roi.py --apply    # 写回 pipeline JSON
"""
import os, sys, glob, json, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np
from PIL import Image
from scripts.regen_templates import find_official, official_get_bbox, SCALE

UP = 'upstream/aalc/assets/images/default'
OUR_IMG = 'assets/resource/image'

# 手工校准的特定非 2560x1440 模板的物理区域
SPECIAL_ROIS = {
    'battle/gear_right.png': [950, 180, 650, 350],  # 战斗右侧齿轮区
}

# 官方在部分 bbox 上做了手动外扩（mirror.py:157-162），这里复刻同样的外扩量
OFFICIAL_EXPAND = {
    'mirror/road_to_mir/infinity_mirror_bbox.png': (-70, 0, 100, 0),
}


def calculate_roi_from_bbox(bb):
    """根据 2560x1440 下的 bbox，计算 720p 基准下自适应带鱼屏的 roi"""
    x1 = int(round(bb[0] * SCALE))
    y1 = int(round(bb[1] * SCALE))
    x2 = int(round(bb[2] * SCALE))
    y2 = int(round(bb[3] * SCALE))
    w = max(1, x2 - x1)
    h = max(1, y2 - y1)

    # 纵向带：y 坐标在不同比例手机上完全一致，仅需预留 +/- 35px 动画与微位移容错
    y_roi = max(0, y1 - 35)
    h_roi = min(720 - y_roi, h + 70)

    # 横向自适应：按屏幕锚点区域划分
    if x1 < 450:
        # 左侧锚定（如返回键、暂停键）：锁定在左侧区域
        x_roi = max(0, x1 - 50)
        w_roi = min(650, w + 100)
    elif x1 >= 830:
        # 右侧锚定（如出击、胜率、DRIVE）：带鱼屏会向右平移，搜索从基准左缘到最右边缘
        x_roi = max(0, x1 - 60)
        w_roi = 750
    else:
        # 居中锚定（如确认弹窗、中心关卡卡片）：宽屏会微调居中，左右留出扩展余量
        x_roi = max(0, x1 - 100)
        w_roi = min(1000, w + 300)

    return [x_roi, y_roi, w_roi, h_roi]


def roi_from_bbox_file(bbox_rel):
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
    bb = official_get_bbox(arr)
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

    bboxes = sorted(glob.glob(f'{OUR_IMG}/**/*_bbox.png', recursive=True))
    bbox_rel = {os.path.relpath(p, OUR_IMG): p for p in bboxes}

    applied = []
    file_count = 0

    for p in sorted(glob.glob('assets/resource/pipeline/**/*.json', recursive=True)):
        path = os.path.basename(p)
        d = json.load(open(p, encoding='utf-8'))
        changed = False

        for name, node in d.items():
            rec = node.get('recognition')
            tpl = None
            if isinstance(rec, dict) and rec.get('type') == 'TemplateMatch':
                tpl = rec.get('template')
            elif isinstance(rec, str) and rec == 'TemplateMatch':
                tpl = node.get('template')
            elif node.get('template'):
                tpl = node.get('template')

            if not isinstance(tpl, str):
                continue

            # 1. 优先查特定 ROI
            roi = SPECIAL_ROIS.get(tpl)

            # 2. 查同名 bbox
            if not roi:
                stem = tpl[:-4]
                cand = None
                for suffix in ('', '_assets'):
                    key = f'{stem}{suffix}_bbox.png'
                    if key in bbox_rel:
                        cand = key
                        break
                if cand:
                    roi = roi_from_bbox_file(cand)

            # 3. 查 2560x1440 官方源画布
            if not roi:
                src = find_official(tpl)
                if src:
                    im = Image.open(src)
                    if im.size == (2560, 1440):
                        arr = np.array(im.convert('RGBA'))
                        bb = official_get_bbox(arr)
                        if bb:
                            roi = calculate_roi_from_bbox(bb)

            if not roi:
                continue

            if node.get('roi') == roi:
                continue

            node['roi'] = roi
            changed = True
            applied.append((path, name, tpl, roi))

        if changed and args.apply:
            file_count += 1
            json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print(f"可加/已更新 roi 的节点数: {len(applied)}")
    for path, name, tpl, roi in applied[:30]:
        print(f"  [{path}] {name:<25} tpl={tpl:<35} -> roi={roi}")
    if len(applied) > 30:
        print(f"  ... 另有 {len(applied) - 30} 个节点已配置 ROI")

    if not args.apply:
        print("\n(未写回，加 --apply 生效)")
    else:
        print(f"\n已成功写回 {file_count} 个 pipeline 配置文件！")


if __name__ == '__main__':
    main()
