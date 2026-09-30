# 发布流程（AALC-Meow）

## 当前状态：功能开发中，所有版本均为 beta

- workflow 的 `prerelease` 固定为 `true`，tag 一律带 `-beta` 后缀（如 `v0.3.0-beta.1`）。
- **应用内默认更新通道需要设为 BETA**：`GitHubUpdate.latestEligible()` 在 `STABLE` 通道会
  过滤掉 `prerelease = true` 的 Release，所以 beta 期间若不切到 BETA，应用内检查更新会一直
  显示"已是最新版"。开发完成后再把 workflow 改回 `prerelease: false` 并切回 `STABLE`。

## 一、签名（已落地，2026-09-27）

release keystore 已生成并接入 CI：

- 别名 `aalc`，RSA 4096，有效期至 2054-02-12
- 证书 SHA-256：`1B:4D:FF:F2:07:E4:55:E4:B9:DE:F5:B6:9A:58:0B:F0:18:96:76:24:26:AC:CC:45:5B:8D:01:48:BD:A5:2D:6F`
- keystore 文件与密码备份在 `~/.local/share/aalc-signing/`（权限 600），
  四个 Secrets（`KEYSTORE_BASE64`/`KEYSTORE_PASSWORD`/`KEY_ALIAS`/`KEY_PASSWORD`）
  已写入 `qi-1021/AALC-Meow` 仓库
- 已用 workflow_dispatch 手动构建验证：产物 APK 的 v2 签名证书指纹与上述一致
- **注意此前的 v0.1.0 – v0.3.0-beta.1 全部是 debug 签名**（keystore 接入前的构建）；
  换签名后旧包无法覆盖安装，如已装机需卸载重装一次

血泪教训（轮换 keystore 时必读）：

1. 现代 `keytool` 默认生成 **PKCS12**（即使后缀写 `.jks`），该格式**强制
   key 密码 = store 密码**。若给了两个不同密码，key 密码会被静默忽略，
   CI 会报 `Get Key failed: Given final block not properly padded`。
   **做法：store 与 key 用同一个密码。**
2. `gh secret set` 用 `echo xxx |` 管道会带入换行符导致密码错误，
   必须用 `printf '%s'` 或 Python `subprocess(input=...)` 写入。
3. `signingSetting()` 读到的 `KEYSTORE_PATH` 经 Gradle `file()` 解析，
   是**相对 `app/` 模块目录**的，所以 keystore 必须落在 `app/.signing/`，
   而 `KEYSTORE_PATH` 保持相对路径 `.signing/release.jks`。
4. 出包后按下式核对（本机无 build-tools 时可用 androguard 读 v2 块）：

   ```bash
   $ANDROID_HOME/build-tools/*/apksigner verify --print-certs AALC-Meow-vX.Y.Z-arm64-v8a.apk
   # 或：keytool -list -printcert -jarfile 仅支持 v1 签名，对 v2 包无效
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
python3 scripts/validate_pipelines.py
MAA_CLI=/path/to/MaaPiCli python3 scripts/verify_with_engine.py
```

## 六、从 MAAend-Meow 学到的经验（2026-09-27）

来源：`MAAend-Meow/docs/reports/debug-cli-and-remote-debug.md`。以下与本项目直接相关：

1. **本地构建必须完整复刻 CI 步骤** —— 已落地为 `scripts/build_local.sh`。
   漏 `prepare_aalc.py` 会拿到没准备的资源；漏 `setup_maa_framework.py` 会缺
   native `.so`，打出"能装能开 UI、但框架加载失败（`UnsatisfiedLinkError`）、
   任务立刻 `NOT_RUN`"的包。**调试结论只以本脚本打出的包为准。**

2. **D8 与 R8 接受面不同**（姊妹项目实测踩过）：release 能编不代表 debug 能编。
   D8 曾对某方法内部报 `ArrayIndexOutOfBoundsException` 而 R8 同代码无事。
   触发形状：Kotlin **局部函数**（捕获一圈局部变量）+ 方法上**一堆默认参数**；
   解法：局部函数抽成成员类型、实现体拆成不带默认参数的私有方法。
   **若出现"只有 debug 变体编不过"的诡异错误，先往这个方向查**，不要在业务代码里乱改。

3. **override 共用节点必须写全可变键**：MaaFramework 的 override 会继承该节点
   上一次的值，漏写一个 `only_rec` 这类键就会静默读空。
   本项目 DailyTasks 目前没有 `pipeline_override`，暂时不咬人；将来加配置覆盖时必须遵守。

4. **tasker 是单线程串行队列**：`MaaTaskerPostRecognition/PostAction` 与任务
   共用同一队列，运行中 post 只会排队。将来做应用内调试/探针时：
   只读观察必须用**不绑 controller 的独立 tasker**（否则框架在 task 结束时
   `auto_release_pressed` 会把正在跑的任务按着的手指放掉）；
   会驱动点击的操作必须排队、绝不阻塞调用方。

5. **调试 CLI 移植（待定，需用户确认）**：MAAend-Meow 已有一套成熟的调试 CLI
   （手机端裸 TCP 行协议 7777 端口 + `adb forward` + 运行中可用的 screenshot/ocr/run 探针），
   按那份文档 §8 可整体移植。本项目当前最需要它的场景是 **roi 提速采样**
   （`screenshot`/`ocr <node>` 可在任务运行时直接测各模板命中分布）。
   但它是给 App 加网络监听，即使有双闸门（BuildConfig.DEBUG + 应用内开关），
   是否引入由用户决定。

## 七、容器识别与后台模式（Kuyo / OurPlay，2026-09-30）

手机端边狱巴士常跑在沙箱容器里。系统层面只能看到容器本身，看不到里面的游戏。
先分清两种形态，对策完全不同：

| 容器 | 包名 | 形态 | 游戏在哪跑 | 后台模式 |
|---|---|---|---|---|
| Kuyo 游戏盒 | `org.kuyo.game` | **本地虚拟环境**为主（官方："自带虚拟环境""专属游戏空间"），兼有云游戏 | 盒内本地进程（虚拟化）或云端串流 | **可行**：把 `org.kuyo.game` 搬到虚拟屏，识别/点按照常 |
| OurPlay | `com.excean.gspace` | **GMS 环境**：游戏"导入"为本地 APK | 手机本地 | **可行**：与官方包同法，游戏包名不变（`com.ProjectMoon.LimbusCompany`） |

关键结论（2026-09-30 修正：Kuyo 以本地虚拟化运行为主，不是纯云）：

1. **为什么系统层面"识别不出里面的游戏"**：应用层虚拟化（VirtualApp 这类机制）
   让游戏跑在容器的进程里、UID 与容器相同，ActivityManager 看到的是容器的
   stub Activity，PackageManager 里根本没有游戏的包。这是机制决定的，
   不是我们的 bug——**不要试图从系统层面挖出里面的游戏，要反过来把容器本身当目标**。
2. **识别方法**：`AppWatchdog.getTopPackageOnDisplay(displayId)` 拿到的就是容器包名，
   直接把它当 target（容器是普通本地进程，`pidof` 判活、repin 都正常工作）。
   里面的游戏是什么，靠用户在选项里声明（`kuyo`/`ourplay`/`official`），
   或靠游戏 UI 自身的识别来确认，不靠包名。
3. **Kuyo 的唯一前置条件**：游戏必须已在盒内手动启动到可操作界面。
   我们的 `StartApp org.kuyo.game` 只能打开盒子。对云串流模式同样成立。
   对应 DailyTasks 的 `kuyo` 选项（描述里已写明）。
4. **`com.ourplay.limbuscompany` 不存在**：OurPlay 不改包（"导入游戏"模型），
   之前 option 里写的是编造包名，已改为官方包。
5. **Kuyo 串流/虚拟画面的识别**：若走云模式，画面是压缩流，模板阈值 0.75 可能偏严；
   先按现有阈值跑，日志里看实际得分再调，不要预先全局放宽。
6. **真机核实命令**（确认容器包名与虚拟化形态，游戏在盒内运行时执行）：
   ```bash
   # 容器本身是否安装：
   adb shell pm list packages | grep -i -E "kuyo|ourplay|projectmoon|limbus"
   # 系统看到的顶层 activity（虚拟化容器一般只暴露自己的 stub）：
   adb shell dumpsys activity activities | grep -E "mFocusedApp|topResumed" | head -3
   # 进程名（虚拟化游戏可能以原包名为进程名、但 UID 归容器）：
   adb shell ps -A | grep -i -E "kuyo|limbus|projectmoon"
   # 若 pm 里没有 com.ProjectMoon.LimbusCompany 但游戏正在盒内跑，
   # 即证实为虚拟化（游戏未向系统注册），识别只能靠容器包名 + 游戏 UI 自身。
   ```

来源：`MAAend-Meow/docs/reports/debug-cli-and-remote-debug.md`。以下与本项目直接相关：

1. **本地构建必须完整复刻 CI 步骤** —— 已落地为 `scripts/build_local.sh`。
   漏 `prepare_aalc.py` 会拿到没准备的资源；漏 `setup_maa_framework.py` 会缺
   native `.so`，打出"能装能开 UI、但框架加载失败（`UnsatisfiedLinkError`）、
   任务立刻 `NOT_RUN`"的包。**调试结论只以本脚本打出的包为准。**

2. **D8 与 R8 接受面不同**（姊妹项目实测踩过）：release 能编不代表 debug 能编。
   D8 曾对某方法内部报 `ArrayIndexOutOfBoundsException` 而 R8 同代码无事。
   触发形状：Kotlin **局部函数**（捕获一圈局部变量）+ 方法上**一堆默认参数**；
   解法：局部函数抽成成员类型、实现体拆成不带默认参数的私有方法。
   **若出现"只有 debug 变体编不过"的诡异错误，先往这个方向查**，不要在业务代码里乱改。

3. **override 共用节点必须写全可变键**：MaaFramework 的 override 会继承该节点
   上一次的值，漏写一个 `only_rec` 这类键就会静默读空。
   本项目 DailyTasks 目前没有 `pipeline_override`，暂时不咬人；将来加配置覆盖时必须遵守。

4. **tasker 是单线程串行队列**：`MaaTaskerPostRecognition/PostAction` 与任务
   共用同一队列，运行中 post 只会排队。将来做应用内调试/探针时：
   只读观察必须用**不绑 controller 的独立 tasker**（否则框架在 task 结束时
   `auto_release_pressed` 会把正在跑的任务按着的手指放掉）；
   会驱动点击的操作必须排队、绝不阻塞调用方。

5. **调试 CLI 移植（待定，需用户确认）**：MAAend-Meow 已有一套成熟的调试 CLI
   （手机端裸 TCP 行协议 7777 端口 + `adb forward` + 运行中可用的 screenshot/ocr/run 探针），
   按那份文档 §8 可整体移植。本项目当前最需要它的场景是 **roi 提速采样**
   （`screenshot`/`ocr <node>` 可在任务运行时直接测各模板命中分布）。
   但它是给 App 加网络监听，即使有双闸门（BuildConfig.DEBUG + 应用内开关），
   是否引入由用户决定。
