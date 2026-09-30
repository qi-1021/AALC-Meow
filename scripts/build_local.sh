#!/usr/bin/env bash
#
# 本地构建（工具链全在移动硬盘上，不依赖 CI / 网络）。
#
# 用法：
#   scripts/build_local.sh            # debug 变体（默认，装机测试用这个）
#   scripts/build_local.sh release    # release 变体（用本地备份的正式 keystore 打包）
#
# 产物：app/build/outputs/apk/<variant>/app-<variant>.apk
#
# ## 为什么需要这个脚本（而不是直接 ./gradlew）
#
# 1. **必须先跑 `prepare_aalc.py`**：上游 OCR 模型与资源准备都在这个脚本里。
#    CI 在 gradle 之前显式跑它（`.github/workflows/build-apk.yml`）；
#    **本地直接 gradle 会拿到没准备的资源包**——那种包能装、能跑，
#    但行为与发布包不一致，调试结论会假。
# 2. **必须跑 `setup_maa_framework.py`**：MaaFramework 的 native `.so`
#    （`libMaaFramework.so` 等）不在 git 里，由这个脚本从 GitHub Release
#    下载并铺进 `app/src/main/jniLibs/<abi>/`。**漏了它打出的包会缺
#    `libMaaFramework.so`**：能装、能开 UI，但框架加载失败
#    （`MAA_LOAD_FAIL UnsatisfiedLinkError`）、任何任务都以 `NOT_RUN` 收场。
# 3. **固定 JDK 17**：与 CI 对齐（actions/setup-java 用 17）。工具链位置见下。
# 4. **固定 SDK / Gradle 家目录**：都放移动硬盘（系统盘空间紧张）。
# 5. **release 变体用正式签名**：读 `~/.local/share/aalc-signing/` 的本地备份
#    keystore（与 CI Secrets 同源）。debug 签名的包每次 key 都不同，
#    覆盖安装前必须卸载重装；正式签名则可直接 `adb install -r`。
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── 工具链位置（移动硬盘）───────────────────────────────────────────────
JDK_HOME="${AALC_JDK_HOME:-/Volumes/mac第三磁盘/AndroidStudio/JDK/temurin17/Contents/Home}"
ANDROID_SDK="${AALC_ANDROID_SDK:-/Volumes/mac第三磁盘/AndroidStudio/SDK}"

if [ ! -x "$JDK_HOME/bin/java" ]; then
  echo "找不到 JDK：$JDK_HOME（用 AALC_JDK_HOME 覆盖）" >&2
  exit 1
fi
if [ ! -d "$ANDROID_SDK/platforms" ]; then
  echo "找不到 Android SDK：$ANDROID_SDK（用 AALC_ANDROID_SDK 覆盖）" >&2
  exit 1
fi

export JAVA_HOME="$JDK_HOME"
export ANDROID_HOME="$ANDROID_SDK"
export ANDROID_SDK_ROOT="$ANDROID_SDK"
# Gradle 依赖缓存：~/.gradle 已软链到 /Volumes/mac第三磁盘/codes/.gradle-home

VARIANT="${1:-debug}"
cd "$REPO_ROOT"

echo "== [1/3] 准备上游资源（prepare_aalc.py，与 CI 同一步）=="
python3 scripts/prepare_aalc.py

echo "== [2/3] 铺 MaaFramework native 库（setup_maa_framework.py，与 CI 同一步）=="
MAAFW_TOKEN="$(env -u http_proxy -u https_proxy gh auth token 2>/dev/null || true)"
if [ -n "$MAAFW_TOKEN" ]; then
  GITHUB_TOKEN="$MAAFW_TOKEN" python3 scripts/setup_maa_framework.py --abi arm64-v8a
else
  python3 scripts/setup_maa_framework.py --abi arm64-v8a
fi

# release 变体：注入本地备份的正式 keystore。
# signingSetting() 优先读环境变量（见 build-logic/.../BuildSettings.kt），
# local.properties 里的残留不会覆盖这里。
if [ "$VARIANT" = "release" ]; then
  LOCAL_KS="$HOME/.local/share/aalc-signing/aalc-release.jks"
  LOCAL_CRED="$HOME/.local/share/aalc-signing/credentials.txt"
  if [ ! -f "$LOCAL_KS" ]; then
    echo "找不到本地正式 keystore：$LOCAL_KS" >&2
    exit 1
  fi
  mkdir -p app/.signing
  cp "$LOCAL_KS" app/.signing/release.jks
  export KEYSTORE_PATH=".signing/release.jks"
  export KEYSTORE_PASSWORD="$(python3 -c "import re;print(re.search(r'^storepass:\s*(\S+)',open('$LOCAL_CRED').read(),re.M).group(1))")"
  export KEY_ALIAS="aalc"
  export KEY_PASSWORD="$KEYSTORE_PASSWORD"   # PKCS12 要求 key 密码 = store 密码
  echo "== 已注入正式签名（sha256 见 credentials.txt 与 docs/RELEASING.md）=="
fi

echo "== [3/3] gradle assemble${VARIANT} =="
case "$VARIANT" in
  debug)   ./gradlew assembleDebug ;;
  release) ./gradlew assembleRelease ;;
  *) echo "未知变体：$VARIANT（只支持 debug / release）" >&2; exit 2 ;;
esac

echo
echo "== 产物 =="
find app/build/outputs/apk -name "*.apk" -newermt "-10 minutes" -print
