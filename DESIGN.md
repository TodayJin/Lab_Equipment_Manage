---
name: LabManager
description: 电子技术创新实验室器材管理系统 — 轨道工作站风格终端
colors:
  quantum-glow: "#8C57FF"
  quantum-deep: "#7E4EE6"
  quantum-soft: "#A379FF"
  success-green: "#34C759"
  warning-orange: "#FF9500"
  danger-red: "#FF3B30"
  surface-light: "#F2F2F7"
  surface-mid: "#E5E5EA"
  surface-dark: "#1C1C1E"
typography:
  body:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "15.5px"
    fontWeight: 400
    lineHeight: 1.65
rounded:
  sm: "8px"
  md: "14px"
  lg: "20px"
  pill: "999px"
spacing:
  sm: "12px"
  md: "20px"
  lg: "28px"
components:
  button-primary:
    backgroundColor: "{colors.quantum-glow}"
    textColor: "#fff"
    rounded: "{rounded.pill}"
    padding: "10px 24px"
  button-glass:
    backgroundColor: "rgba(255,255,255,.55)"
    rounded: "{rounded.pill}"
    padding: "10px 24px"
  panel:
    backgroundColor: "rgba(255,255,255,.72)"
    rounded: "{rounded.lg}"
  input:
    backgroundColor: "rgba(255,255,255,.5)"
    rounded: "{rounded.md}"
    padding: "10px 16px"
---

# Design System: LabManager

## 1. Overview

**Creative North Star: "轨道工作站"**

实验室公共电脑上的器材管理系统，设计语言像一个模块化的空间站控制面板。界面由半透明面板层叠而成，背景有持续运行的粒子模拟（星场/星云），暗示系统始终在线。每一个操作即时响应，不留整页刷新。

深色模式是默认姿态，浅色模式提供"实验室日光"替代。五套主题色覆盖紫蓝绿橙粉，像工作站可切换的 HUD 配色方案。

**Key Characteristics:**
- 毛玻璃面板层叠（backdrop-filter blur 24px, saturate 160%）
- 全圆角胶囊按钮，按压有弹性反馈
- 粒子背景动效持续运行，切换有淡入淡出
- AJAX 局部更新，操作零等待
- 五种 HUD 配色一键切换

This system explicitly rejects: 企业 OA 表格风格, 纯白卡片堆叠, 整页刷新, 静态背景, 直角表格。

## 2. Colors

五套主题色共用同一中性色底板，切换主题只改变主色/辅色/强调色。

### Primary
- **量子辉光 Quantum Glow** (#8C57FF): 主按钮、侧边栏高亮、统计卡片顶部渐变线、时间芯片激活态。默认紫色，可通过主题选择器切换为蓝/绿/橙/粉。
- **量子深色 Quantum Deep** (#7E4EE6): 按钮 hover 态、侧边栏导航渐变深端。
- **量子柔光 Quantum Soft** (#A379FF): 图标光晕、深色模式 tag 激活文字色。

### Secondary
- **成功绿** (#34C759): 入库标签、成功 Toast 左边框。
- **警告橙** (#FF9500): 签退按钮、出库标签、续签提醒。
- **危险红** (#FF3B30): 删除按钮、库存预警闪烁。

### Neutral
- **表面亮** (#F2F2F7): 浅色模式页面底色。
- **表面中** (#E5E5EA): 边框、分割线、禁用态。
- **表面深** (#1C1C1E): 深色模式页面底色、浅色模式正文色。
- **文字次** (rgba(60,60,67,.6)): 辅助文字、placeholder。
- **文字弱** (rgba(60,60,67,.3)): 禁用文字、非活跃图标。

### Named Rules
**The One Accent Rule.** 主色占比不超过任何屏幕的 15%。侧边栏一项高亮、一个主按钮、一条顶部渐变线，就够。

## 3. Typography

**Font:** Inter + 系统字体栈（PingFang SC / Microsoft YaHei 覆盖中文）

**Character:** 几何无衬线，清晰直接，不装饰。中文用系统原生字体保证渲染质量。

### Hierarchy
- **Page Title** (700, 20px, 1.2): 顶栏页面标题。
- **Panel Heading** (650, 16px, 1.3): 面板标题。
- **Body** (400, 15.5px, 1.65): 正文、表格内容、按钮标签。行宽不超过 75ch。
- **Small/Badge** (600, 11-13px, letter-spacing 0.3-0.5px): 表头、徽章、辅助信息。

## 4. Elevation

采用**毛玻璃分层策略**：面板/卡片通过 `backdrop-filter: blur()` 叠加半透明背景产生深度，配合多层柔和投影增强层次。

### Shadow Vocabulary
- **ambient-sm** (`0 1px 3px rgba(0,0,0,.04), 0 1px 2px rgba(0,0,0,.02)`): 顶栏、过滤栏。
- **ambient-md** (`0 4px 12px rgba(0,0,0,.06), 0 2px 4px rgba(0,0,0,.03)`): 面板、卡片、统计卡片、表格容器。
- **ambient-lg** (`0 8px 24px rgba(0,0,0,.08), 0 4px 8px rgba(0,0,0,.04)`): 弹窗模态框。

### Named Rules
**The Glass-Over-Flat Rule.** 所有容器面板必须有 backdrop-filter 毛玻璃效果。纯色面板仅在极简场景（如登录页背景）使用。

## 5. Components

### Buttons
- **Shape:** 全圆角胶囊（999px），`padding: 10px 24px`，`font-weight: 600`。
- **Primary:** 量子辉光渐变背景，白色文字，hover 加深 + 上浮 1px。
- **Glass:** 半透明白底 + 10 层 box-shadow 模拟玻璃折射高光。hover 增强阴影 + scale(1.03)，active scale(0.96) + 弹性回弹动画。
- **Focus:** 无额外 outline，依赖主题色背景变化传达状态。

### Panels / Cards
- **Corner:** 20px 圆角，overflow hidden。
- **Background:** rgba(255,255,255,.72) + blur(24px) saturate(160%)。
- **Shadow:** ambient-md。
- **Border:** 1px solid rgba(255,255,255,.5)。

### Inputs / Fields
- **Style:** 14px 圆角，1.5px solid rgba(0,0,0,.1) 边框，半透明白底。
- **Focus:** 边框变主题色 + 0 0 0 4px 主题色光晕（opacity .1），上浮 2px。
- **Dark:** 背景变深灰半透明，边框变白半透明。

### Table
- **Container:** 20px 圆角 + 毛玻璃背景 + overflow hidden 统一裁切。
- **Header:** 半透明主题色底色，12px 大写 tracking。
- **Row hover:** td 背景微变主题色（opacity .04）。
- **Last row:** 底角 20px 圆角。

### Navigation
- **Sidebar:** 固定左侧 260px，毛玻璃背景，导航项右侧半圆角胶囊。
- **Active:** 量子辉光渐变 + 白色文字 + 投影。
- **Topbar:** 毛玻璃卡片式，64px 高，20px 圆角。

### Background Effects
- **粒子网络:** 120 个发光粒子 + 连线 + 鼠标光晕，默认启用。
- **光影流动:** 6 个渐变光斑漂移 + anime.js 色相循环，可切换。
- **切换器:** 右下角两个胶囊按钮，opacity 淡入淡出切换，localStorage 持久化。

## 6. Do's and Don'ts

### Do:
- **Do** 所有删除/撤销/签退操作用 AJAX + Toast 反馈，不整页刷新。
- **Do** 表格容器用 20px 圆角 + overflow hidden 裁切直角内容。
- **Do** 深色模式优先，浅色作为备选。
- **Do** 按钮使用全圆角胶囊（999px）+ 按压弹性动画。
- **Do** 面板保持 backdrop-filter 毛玻璃效果贯穿全局。

### Don't:
- **Don't** 使用直角表格或直角卡片（参考：企业 OA 系统风格）。
- **Don't** 整页刷新任何操作（参考：传统 form POST 提交）。
- **Don't** 使用纯白不透明面板（毛玻璃半透明是默认）。
- **Don't** 在卡片上同时使用 1px 边框 + 大阴影（ghost-card 反模式，选其一）。
- **Don't** 圆角超过 24px（卡片上限，按钮/标签可用 pill）。
- **Don't** 使用渐变文字（background-clip: text）。
