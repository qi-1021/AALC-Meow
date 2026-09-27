#!/usr/bin/env python3
"""按 MaaFramework 3.1 Pipeline 协议校验 assets 下的 pipeline JSON。

背景：非法字段（如 `recognition_and`、`timeout_next`）不会静默忽略，而是让
整个资源加载失败，应用启动即崩。本脚本在提交前把这类问题挡住。

检查项：
  1. 顶层字段白名单
  2. recognition 内部字段白名单
  3. And/Or 必须用 all_of/any_of，子项必须用 recognition（不是 type）
  4. next 引用的节点存在
  5. template 指向的图片存在
  6. OCR 必须用 expected（不是 text）

用法: python3 scripts/validate_pipelines.py
"""
import os, sys, glob, json, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

IMG = 'assets/resource/image'

TOP_KEYS = {
    # 元信息
    'doc', 'name',
    # 识别
    'recognition', 'roi', 'roi_offset', 'fast_roi', 'box_index', 'expected',
    'all_of', 'any_of', 'sub_name', 'order_by', 'index', 'threshold', 'method',
    'mask_as_blue', 'green_mask', 'count', 'replace', 'only_rec', 'model',
    'color_filter', 'custom_recognition', 'custom_recognition_param',
    'hit_pattern', 'hit_color', 'max_track_index', 'auto_recognition',
    'reduce_recognition', 'focus', 'focus_recognition', 'focus_target',
    'interrupt',
    # 动作
    'action', 'action_params', 'target', 'target_offset', 'contact', 'pressure',
    'custom_action', 'custom_action_param', 'input', 'input_type', 'input_extra',
    'preset', 'enabled', 'direction', 'distance', 'begin', 'end', 'while', 'body',
    # 流转
    'next', 'next_touch', 'on_error', 'reset', 'reset_recognition', 'reset_action',
    'reset_next', 'rerun', 'refresh_interval', 'run', 'timeout', 'trans_offset',
    'trans_touch', 'pre_wait_freezes', 'post_wait_freezes', 'pre_delay', 'post_delay',
    'action_delay',
}
# Pipeline v1 简写：recognition 为字符串时，识别参数直接平铺在顶层
V1_RECOGNITION_PARAMS = {
    'template', 'expected', 'threshold', 'method', 'mask_as_blue', 'green_mask',
    'count', 'order_by', 'index', 'replace', 'only_rec', 'model', 'color_filter',
    'labels', 'max_track_index', 'all_of', 'any_of', 'custom_recognition',
    'custom_recognition_param', 'hit_pattern', 'hit_color',
}
RECOGNITION_KEYS = {
    'type', 'recognition', 'template', 'expected', 'roi', 'roi_offset', 'threshold',
    'method', 'mask_as_blue', 'green_mask', 'count', 'order_by', 'index', 'replace',
    'only_rec', 'model', 'color_filter', 'labels', 'custom_recognition',
    'custom_recognition_param', 'hit_pattern', 'hit_color', 'max_track_index',
    'all_of', 'any_of', 'sub_name', 'box_index', 'and', 'or', 'input',
}
# 已知非法字段（踩过的坑，留档避免回归）
BANNED = {
    'recognition_and': 'And/Or 必须用 all_of / any_of',
    'recognition_or': 'And/Or 必须用 all_of / any_of',
    'timeout_next': '超时分支请用 on_error',
    'fast_recognition': '字段名是 fast_roi',
}


def collect():
    nodes = {}
    for f in glob.glob('assets/resource/pipeline/**/*.json', recursive=True):
        name = os.path.basename(f)
        d = json.load(open(f, encoding='utf-8'))
        for node_name, node in d.items():
            nodes[node_name] = (name, node, f)
    return nodes


def check():
    errs, warns = [], []
    nodes = collect()
    have = {os.path.relpath(p, IMG) for p in glob.glob(f'{IMG}/**/*.png', recursive=True)}

    for name, (fname, node, path) in nodes.items():
        where = f"{fname}:{name}"
        rec = node.get('recognition')
        is_v1 = isinstance(rec, str)
        is_v2 = isinstance(rec, dict)

        for k in node:
            if k in BANNED:
                errs.append(f"{where}: 非法字段 '{k}' —— {BANNED[k]}")
            elif k not in TOP_KEYS and not (is_v1 and k in V1_RECOGNITION_PARAMS):
                errs.append(f"{where}: 未知顶层字段 '{k}'")

        if is_v2:
            for k in rec:
                if k == 'text':
                    errs.append(f"{where}: recognition.text 非法 —— OCR 请用 expected")
                elif k not in RECOGNITION_KEYS:
                    errs.append(f"{where}: recognition.{k} 未知识别字段")
            if rec.get('type') == 'OCR' and 'expected' not in rec:
                warns.append(f"{where}: OCR 无 expected，将匹配全部结果")
        elif is_v1:
            if rec == 'OCR' and 'expected' not in node:
                warns.append(f"{where}: OCR 无 expected，将匹配全部结果")
        elif 'action' in node:
            # 终点节点 / 纯动作节点：只有 action 没有 recognition 是合法用法
            pass
        else:
            errs.append(f"{where}: recognition 必须是字符串(v1)或对象(v2)，"
                        f"实际 {type(rec).__name__}")

        for comb in ('all_of', 'any_of'):
            for i, sub in enumerate(node.get(comb, []) or []):
                if isinstance(sub, str):
                    continue
                if 'recognition' not in sub:
                    errs.append(f"{where}: {comb}[{i}] 缺 'recognition'（不能写 'type'）")

        nxt = node.get('next')
        if isinstance(nxt, str):
            nxt = [nxt]
        for t in (nxt or []) + (node.get('on_error') or []) + (node.get('reset_next') or []):
            if t not in nodes:
                errs.append(f"{where}: next 指向不存在的节点 '{t}'")

        for m in re.finditer(r'"template"\s*:\s*"([^"]+)"', json.dumps(node, ensure_ascii=False)):
            if m.group(1) not in have:
                errs.append(f"{where}: 模板不存在 '{m.group(1)}'")

    return nodes, errs, warns


def main():
    nodes, errs, warns = check()
    print(f"节点总数: {len(nodes)}")
    print(f"错误: {len(errs)}   警告: {len(warns)}")
    for e in errs:
        print("  [错误]", e)
    for w in warns:
        print("  [警告]", w)
    if errs:
        return 1
    print("通过")
    return 0


if __name__ == '__main__':
    sys.exit(main())
