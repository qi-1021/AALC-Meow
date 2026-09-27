# 发布流程（AALC-Meow）

## 当前状态：功能开发中，所有版本均为 beta

- workflow 的 `prerelease` 固定为 `true`，tag 一律带 `-beta` 后缀（如 `v0.3.0-beta.1`）。
- **应用内默认更新通道需要设为 BETA**：`GitHubUpdate.latestEligible()` 在 `STABLE` 通道会
  过滤掉 `prerelease = true` 的 Release，所以 beta 期间若不切到 BETA，应用内检查更新会一直
  显示"已是最新版"。开发完成后再把 workflow 改回 `prerelease: false` 并切回 `STABLE`。

## 一、签名（重要，务必在铺开装机前完成）

已发布的 v0.1.0 – v0.2.3 全部是 **debug 签名**（CI 未配置 keystore，`KEYSTORE_PATH` 为空，
`AndroidApplicationConventionPlugin.kt:163` 回退到 debug signingConfig）。

**为什么必须换**：Android 要求覆盖安装时签名一致。一旦换了正式签名，此前 debug 签名的包
无法覆盖升级，用户只能卸载重装（会丢本地配置）。

配置步骤：

1. 本地生成 keystore（**密码请自行保管，不要提交到仓库**）：

   ```bash
   keytool -genkeypair -v \
     -keystore aalc-release.jks \
     -alias aalc \
     -keyalg RSA -keysize 4096 -validity 10000
   ```

2. 在 GitHub 仓库添加 Secrets（Settings → Secrets and variables → Actions）：
   - `KEYSTORE_BASE64`：`base64 -i aalc-release.jks | pbcopy`
   - `KEYSTORE_PASSWORD`
   - `KEY_ALIAS`（上例为 `aalc`）
   - `KEY_PASSWORD`

3. 下次出包时 workflow 会自动注入这四个环境变量
   （`signingSetting()` 优先读环境变量，见 `build-logic/.../BuildSettings.kt:29`）。
   未配置时打 warning 并回退 debug 签名，**CI 不会因此失败**。

4. 出包后核对签名是否已切换：

   ```bash
   # 从 Release 下载 APK 后本地核对
   $ANDROID_HOME/build-tools/*/apksigner verify --print-certs AALC-Meow-vX.Y.Z-arm64-v8a.apk
   ```

## 二、模板资产的黄金法则（血泪教训）

模板必须与**控制器输出的截图尺寸**严格同比例，否则 `matchTemplate` 得分会崩塌。

- 本项目控制器把截图归一化到**短边 720p**（`SCREENSHOT_TARGET_SHORT_SIDE = 720`，
  见 `MaaRunner.kt:414`），实际画面为 1280×720。
- 官方 AALC 的资源是 **2560×1440 全屏透明图**，运行时按
  `ImageUtils.load_image()` → 整图 `win_size/1440` 缩放 → `get_bbox()` 裁剪
  （`upstream/aalc/utils/image_utils.py:15,101,147`）。
- 因此本项目模板的**唯一正确比例是 0.5**。

重新生成 / 审计：

```bash
python3 scripts/regen_templates.py --check   # 审计尺寸偏差
python3 scripts/regen_templates.py --apply   # 按官方链路重导
python3 scripts/audit_templates.py           # 逐张列出可疑模板
```

**改动截图归一化尺寸后，必须重跑 `regen_templates.py --apply`。**

## 三、流程逻辑必须对齐官方

业务流以 `upstream/aalc/tasks/` 为唯一权威（submodule 指向
`KIYI671/AhabAssistantLimbusCompany`，当前 V1.6.1-beta.2）。

已按官方重建的部分：

- `road_to_mir()` 入口候选链（`tasks/mirror/mirror.py:129`）——含
  `resume` / `enter_mirror`(阈值 0.78) / `infinity_mirror` / `enter_assets` /
  `mirror_dungeons` / `drive`。原版第 184 行明确注释掉 `quick_start`
  （"从这里进可能会进轨道线"），本项目也已移除。
- `team_formation()` 编队（`tasks/teams/team_formation.py:33-77`）——官方
  **不使用罪人头像模板**，而是以 `teams/identify_assets.png` 为锚点，
  按 `first_sinner = anchor + (-1800, +130) * scale` 加两排 `(270*i, 0)` /
  `(270*(i-6), +500) * scale` 偏移点击。本项目用 `target_offset` 表达同一语义。

注意：`/Volumes/mac第三磁盘/codes/Projects/AALC_Python` 是作者早年的未完成尝试，
**不是权威参考，不要依据它**。

## 四、性能：模板匹配为何慢

未加 `roi` 时，每个模板都在 1280×720 全屏做 `matchTemplate`，单次约 1.5 s
（实测 234 次匹配共 362 s）。路由节点一次迭代有 5–11 个候选，因此会非常慢。

- 官方没有 roi 概念，用同位置的 `*_bbox.png` 模板限定搜索窗口
  （`ImageUtils.get_bbox`）。本项目对应到 MaaFramework 的 `roi` 字段。
- 官方仅 10 张 `*_bbox.png`，不足以覆盖 158 个节点，**需要真机多次采样
  各模板命中位置分布后逐个补 roi**，不可凭猜测批量设置。
- 参考：`scripts/apply_roi.py` 已实现从官方 `*_bbox.png` 自动派生 roi 的逻辑。

## 五、发版

```bash
git tag -a v0.3.0-beta.1 -m "..." 
git push origin master --tags
gh run list -R qi-1021/AALC-Meow -L 2      # 等 Build AALC-Meow APK 变绿
gh release view v0.3.0-beta.1 -R qi-1021/AALC-Meow
```

推 tag 前务必跑一次全量校验：

```bash
python3 -c "
import json, glob
for p in glob.glob('assets/**/*.json', recursive=True): json.load(open(p))
print('JSON ok')"
```
