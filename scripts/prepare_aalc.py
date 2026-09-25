#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prepare AALC assets, OCR models, and configuration for Android packaging.
Ensures zero pollution of system /tmp (all caches/temps in project root).
"""

import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = PROJECT_ROOT / ".tmp"
ASSETS_ROOT = PROJECT_ROOT / "assets"
OCR_TARGET_DIR = ASSETS_ROOT / "resource" / "model" / "ocr"

TMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(TMP_DIR)
os.environ["TEMP"] = str(TMP_DIR)
os.environ["TMP"] = str(TMP_DIR)

OCR_BASE_URL = "https://raw.githubusercontent.com/MaaXYZ/MaaCommonAssets/main/OCR/ppocr_v6/small"
OCR_FILES = ["det.onnx", "rec.onnx", "keys.txt"]


def log(msg: str):
    print(f"[AALC-Prep] {msg}", flush=True)


def ensure_ocr_models():
    OCR_TARGET_DIR.mkdir(parents=True, exist_ok=True)
    all_exist = all((OCR_TARGET_DIR / f).is_file() for f in OCR_FILES)
    if all_exist:
        log("OCR models already present.")
        return

    log("Downloading OCR models from MaaCommonAssets...")
    for f in OCR_FILES:
        dest = OCR_TARGET_DIR / f
        if dest.is_file() and dest.stat().st_size > 0:
            log(f"  {f} already downloaded.")
            continue
        url = f"{OCR_BASE_URL}/{f}"
        log(f"  Downloading {f} from {url}...")
        req = urllib.request.Request(url, headers={"User-Agent": "AALC-Android-Prep"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as out:
            shutil.copyfileobj(resp, out)
        log(f"  Saved {f} ({dest.stat().st_size / (1024 * 1024):.2f} MB)")
    log("All OCR models prepared.")


def ensure_local_properties():
    props_file = PROJECT_ROOT / "local.properties"
    content = [
        "# Auto-generated configuration for AALC Android packaging",
        "pi.profile=pi-profile.yaml",
        "build.debugAbi=arm64-v8a",
        "build.releaseAbi=arm64-v8a",
        "",
    ]
    if not props_file.is_file():
        props_file.write_text("\n".join(content), encoding="utf-8")
        log("Created local.properties pointing to pi-profile.yaml")
    else:
        existing = props_file.read_text(encoding="utf-8")
        if "pi.profile=" not in existing:
            props_file.write_text(existing.rstrip() + "\npi.profile=pi-profile.yaml\n", encoding="utf-8")
            log("Added pi.profile to local.properties")


def main():
    log("Starting AALC Android preparation...")
    ensure_ocr_models()
    ensure_local_properties()
    log("Preparation complete!")


if __name__ == "__main__":
    main()
