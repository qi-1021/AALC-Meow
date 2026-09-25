# AALC-Meow (边狱公司 / 边狱巴士小助手 Android 原生端)

<div align="center">

<img src="logo.png" alt="AALC-Meow Logo" width="128" height="128">

# AALC-Meow

**基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 架构的高性能《边狱公司》（Limbus Company）Android 移动端自动化工具**

[![License](https://img.shields.io/badge/license-AGPL%203.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Android-green.svg)](https://developer.android.com)
[![MaaFramework](https://img.shields.io/badge/MaaFramework-v5.14.0-orange.svg)](https://github.com/MaaXYZ/MaaFramework)
[![AALC Upstream](https://img.shields.io/badge/AALC-Upstream-brightgreen.svg)](https://github.com/KIYI671/AhabAssistantLimbusCompany)

</div>

---

## 🌟 项目设计与特性

- **📱 彻底摆脱 PC 与重量级 Python 依赖**：将原版 AALC 的 Python/PySide6 体系转译为声明式 MaaFramework Pipeline，在手机端以纯 C++ 引擎毫秒级原生运行。
- **🎮 全平台与全容器兼容**：针对边狱公司在手机端普遍通过 **OurPlay、Kuyo 游戏盒** 等沙箱容器运行的特点，原生提供**前台画面捕获驱动**，无需关心外层包裹容器，画面即控。
- **🔋 超轻量与内存极省**：摒弃 2GB+ 的 OnnxRuntime-Python 内存占用，全套运行时仅占约 100MB 运行内存。
- **🎯 16 KB 分页对齐**：全量底层动态库严格执行 16 KB 页面对齐，完美适配 Android 15+ 现代操作系统。
- **🛡️ 纯免 Root（Shizuku 优先）**：推荐使用 [Shizuku](https://shizuku.rikka.app/) 免 Root 授权，通过系统底层虚拟显示器与注入通道稳定控制。
- **🔄 首期核心闭环**：
  1. **体力全换脑啡肽模块（自动换饼）**：主界面一键全换模块。
  2. **战斗自动胜率连线**：自动 P 键胜率连线与齿轮回合推进，直至战斗胜利结算。

---

## 📱 运行要求

| 项目 | 要求 | 说明 |
| :--- | :--- | :--- |
| **操作系统** | Android 9.0（API 28）及以上 | 推荐 Android 11+，后台虚拟空间兼容性更佳 |
| **提权方案** | [Shizuku](https://shizuku.rikka.app/) 或 Root 权限 | 推荐使用 Shizuku，免 Root 即可直接调用系统底层 Native 控制器 |
| **设备架构** | `arm64-v8a`（主流真机） / `x86_64`（PC 模拟器） | 默认提供单架构轻量化包，安装包体积紧凑 |
| **目标游戏** | 《边狱公司》（Limbus Company）客户端 | 支持原生客户端、OurPlay、Kuyo 及各类游戏空间 |

---

## 📄 开源许可证与致谢

- 本项目基于 [AGPL-3.0 License](LICENSE) 开源。
- 感谢 [KIYI671/AhabAssistantLimbusCompany](https://github.com/KIYI671/AhabAssistantLimbusCompany) 提供的优质边狱巴士自动化思路与图像资源。
- 感谢 [MaaXYZ/MaaFramework](https://github.com/MaaXYZ/MaaFramework) 与 [Aliothmoon/MaaFwApp](https://github.com/Aliothmoon/MaaFwApp) 提供的跨平台自动化框架与 Android 运行架构支持。

---

## 📬 联系方式

- 问题与建议：欢迎提交 [Issues](https://github.com/qi-1021/AALC-Meow/issues)
- 开发者邮箱：[qiisme1021@icloud.com](mailto:qiisme1021@icloud.com)
