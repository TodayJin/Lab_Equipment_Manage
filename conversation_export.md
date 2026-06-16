# LabManager v3.2.2 — 续签系统调试对话记录

> 导出时间：2026-06-14
> 适用工具：OpenAI Codex / OpenCode / Claude / 其他 AI 编程助手
> 项目：电子技术创新实验室器材管理系统（Flask + SQLite）
> 远程仓库：https://github.com/TodayJin/Lab_Equipment_Manage

---

## 项目结构

```
D:\lab system item\Lab_Equipment_Manage\
├── src/
│   ├── app.py              # Flask 主应用
│   ├── admin.py            # 管理面板（含一键更新）
│   ├── lab.py              # 签到模块（含服务端续签检测）
│   ├── chat.py             # 聊天模块
│   ├── models.py           # SQLAlchemy 模型
│   └── stock.py            # 入库出库
├── templates/
│   ├── base.html           # 主布局（加载 CSS/JS）
│   ├── about/index.html    # 关于页
│   ├── auth/login.html     # 登录页
│   ├── lab/checkin.html    # 签到页
│   ├── lab/checkin_stats.html # 签到统计
│   └── stock/in.html, out.html # 入库出库
├── static/
│   ├── css/
│   │   ├── app.css         # 主样式（新版 UI）
│   │   ├── style.css       # 旧版样式（仍需加载）
│   │   └── dark.css        # 暗色模式
│   └── js/
│       ├── app.js          # 全局 JS（续签系统、Toast、聊天）
│       └── searchable-select.js
├── build.py                # PyInstaller 打包脚本
├── dist/
│   └── LabManager-V3.2.2.exe
├── 架构文档.md
├── 开发维护指南.md
└── README.md
```

---

## 本次会话完成的所有改动

### 1. 续签系统完全重构（核心改动）

**文件**：`static/js/app.js:84-279`（续签 IIFE 完整重写）

**设计原则**：`localStorage.lab_renew_ack` 为唯一状态源，`tick()` 每次重新读取，不依赖内存变量。

**数据模型**：
- `localStorage.lab_signin_ts` — 签到时间戳（ms）
- `localStorage.lab_renew_ack` — JSON 对象 `{"h3": true, "h6": true, "h9": true}`，记录用户确认过的检查点

**配置常量**（当前为生产值）：
```javascript
var RENEW_POINTS = [3, 6, 9];        // 3h / 6h / 9h 触发续签
var HARD_LIMIT_MIN = 12 * 60;        // 12h 硬性签退（720 分钟）
var GRACE_SEC = 5 * 60;              // 5 分钟响应倒计时（300 秒）
var STORAGE_TS = 'lab_signin_ts';
var STORAGE_ACK = 'lab_renew_ack';
```

**tick() 主循环逻辑**：
1. 从 localStorage 读取签到时间戳 + ack 标记
2. 计算已过分钟数 `elapsedMin`
3. 硬限制检查（12h 自动签退）
4. 倒计时中 → 每次 tick 重读 ack，发现已确认则关弹窗
5. 无弹窗 → 遍历检查点：`elapsedMin >= checkPoint*60 && !ack[ackKey(h)]` → 弹窗
6. 显示下一个检查点倒计时

**confirm() 逻辑**：
```javascript
confirm: function() {
    stopBeep();
    var idx = activeRenewIdx;   // 先保存索引
    removeModal();              // removeModal 会重置 activeRenewIdx = -1
    if (idx >= 0) {
        var key = ackKey(RENEW_POINTS[idx]);  // e.g., 'h3'
        var a = readAck();
        a[key] = true;
        writeAck(a);            // 写入 localStorage
    }
    LabToast.show('已确认在线，续签成功。', 'success', 3000);
},
```

**跨标签页同步**：无需额外逻辑，所有标签页的 `tick()` 每次都从 localStorage 重新读取 ack。

**countdownSec 倒计时中跨标签页确认**：
```javascript
if (countdownSec > 0) {
    var ack = readAck();
    if (activeRenewIdx >= 0) {
        var ch = RENEW_POINTS[activeRenewIdx];
        if (ack[ackKey(ch)]) { removeModal(); return; }  // 其他标签页已确认
    }
    // ... 倒计时递减逻辑
}
```

**蜂鸣管理**：
- `startBeep()` → 立即 beep + 每 2 秒 repeat + 15 秒后自动静音
- `stopBeep()` → 清除 interval timer
- 弹窗使用内联样式（不依赖外部 CSS）

### 2. 修复的 Bug 历程

#### Bug 1：续签弹窗不可见（CSS 问题）
- **原因**：`style.css` 中的 `.afk-warning-overlay` 等样式未被加载（`base.html` 只加载了 `app.css`）
- **修复**：弹窗使用内联 `setAttribute('style', ...)` 确保在任何页面都可见

#### Bug 2：登录页/入库出库页 CSS 缺失
- **原因**：`app.css` 替代 `style.css` 后，大量旧版类未迁移
- **修复**：在 `base.html` 重新加载 `style.css`（放在 `app.css` 之前），同时在 `app.css` 补充关键类（auth、stock、badges、toast、searchable-select）

#### Bug 3：确认后切换页面仍重复弹窗（旧版双 flag 系统）
- **原因**：`warnedInSession` 内存变量与 localStorage 之间的同步问题
- **修复**：完全重写为 localStorage 单状态源方案

#### Bug 4：重构后确认不写入 ack（`activeRenewIdx` 被覆盖）
- **原因**：`confirm()` 中 `removeModal()` 先于 ack 保存执行，`removeModal()` 将 `activeRenewIdx` 重置为 `-1`
- **修复**：`var idx = activeRenewIdx` 在 `removeModal()` 之前保存

#### Bug 5：`showModal()` 覆盖 `activeRenewIdx`
- **原因**：`tick()` 中 `activeRenewIdx = i` 在 `showModal(h)` 之前赋值，但 `showModal()` 内部调 `removeModal()` 把它重置为 `-1`
- **修复**：将 `activeRenewIdx = i` 移到 `showModal(h)` 调用之后

#### Bug 6：键名不匹配（旧版 grace 标记）
- **原因**：`confirm()` 存 `grace_h0.01666`（带 `h` 前缀），`tick()` 查 `grace_0.01666`（不带 `h` 前缀）
- **修复**：`k.substring(1)` 去掉前缀（此问题在重构后不再存在）

### 3. CSS 加载顺序修复

**文件**：`templates/base.html`
```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}?v=3.2.2">
<link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}?v=3.2.2">
```

`style.css`（基础层）→ `app.css`（覆盖层）。两套 CSS 变量不共享变量名（`--primary` vs `--pri`），互不冲突。

### 4. 版本号升级 v3.2.1 → v3.2.2

**修改的文件**：
- `src/admin.py:25` — `CURRENT_VERSION = "v3.2.2"`
- `build.py:6` — `--name=LabManager-V3.2.2`
- `templates/about/index.html:17` — 版本号显示
- `templates/base.html` — CSS/JS `?v=3.2.2` 缓存破除
- `README.md`、`架构文档.md`、`开发维护指南.md` — 版本引用

### 5. 其他改动

- **登录页恢复深色渐变背景**（`app.css` auth-wrapper 背景 `#0f1729→#1e3a5f→#0f1729`）
- **Toast 样式迁移**（从 `style.css` → `app.css`）
- **续签弹窗蜂鸣 15 秒后静音**（`setTimeout(stopBeep, 15000)`）
- **签到页 `checkin.html`** 适配新 localStorage key `lab_renew_ack`

---

## 关键代码片段

### app.js — 续签系统完整 IIFE

```javascript
// ═══════════════ 续签检测（全局，所有标签页生效） ═══════════════
//   用 localStorage 作唯一状态源，每次 tick() 重新读取，
//   不依赖内存变量，彻底解决跨标签页/页面切换重复弹窗问题
(function() {
    var RENEW_POINTS = [3, 6, 9];        // 3h / 6h / 9h 触发续签
    var HARD_LIMIT_MIN = 12 * 60;        // 12h 硬性签退
    var GRACE_SEC = 5 * 60;              // 5 分钟响应倒计时
    var STORAGE_TS = 'lab_signin_ts';
    var STORAGE_ACK = 'lab_renew_ack';

    var countdownSec = 0;
    var activeRenewIdx = -1;
    var beepTimer = null;

    function readAck() {
        try { return JSON.parse(localStorage.getItem(STORAGE_ACK)) || {}; } catch(e) { return {}; }
    }
    function writeAck(obj) { localStorage.setItem(STORAGE_ACK, JSON.stringify(obj)); }
    function ackKey(h) { return 'h' + h; }
    function getSigninTs() { var v = localStorage.getItem(STORAGE_TS); return v ? parseInt(v, 10) : null; }
    function fmtDur(m) { var h = Math.floor(m / 60), r = m % 60; return h > 0 ? h + 'h ' + r + 'm' : r + 'm'; }

    function beep() { /* AudioContext 800Hz square wave, 3 pulses */ }
    function startBeep() { stopBeep(); beep(); beepTimer = setInterval(beep, 2000); setTimeout(stopBeep, 15000); }
    function stopBeep() { if (beepTimer) { clearInterval(beepTimer); beepTimer = null; } }

    function removeModal() {
        stopBeep();
        var el = document.getElementById('renewModal');
        if (el) el.remove();
        countdownSec = 0;
        activeRenewIdx = -1;
    }

    function showModal(hour) {
        removeModal();
        countdownSec = GRACE_SEC;
        // ... 创建 overlay div with inline styles, append to body
    }

    function autoSignout() {
        stopBeep(); removeModal();
        fetch('/lab/checkin/auto-signout', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function() {
            localStorage.removeItem(STORAGE_TS);
            localStorage.removeItem(STORAGE_ACK);
            window.location.href = window.location.href.split('?')[0] + '?_=' + Date.now();
        })
        .catch(function() { /* fallback reload */ });
    }

    function tick() {
        var ts = getSigninTs();
        if (!ts) return;
        var elapsedMin = Math.floor((Date.now() - ts) / 60000);
        // ... 签到页面持续显示更新
        if (elapsedMin >= HARD_LIMIT_MIN) { autoSignout(); return; }

        // 倒计时中
        if (countdownSec > 0) {
            var ack = readAck();
            if (activeRenewIdx >= 0 && ack[ackKey(RENEW_POINTS[activeRenewIdx])]) {
                removeModal(); return;  // 其他标签页已确认
            }
            countdownSec--;
            // ... 更新倒计时显示
            if (countdownSec <= 0) { removeModal(); autoSignout(); }
            return;
        }

        // 检查所有续签点
        var ack = readAck();
        for (var i = 0; i < RENEW_POINTS.length; i++) {
            var h = RENEW_POINTS[i];
            if (elapsedMin >= h * 60 && !ack[ackKey(h)]) {
                showModal(h);
                activeRenewIdx = i;   // 放在 showModal() 之后！
                return;
            }
        }
        // ... 显示下一个检查点倒计时
    }

    window.addEventListener('storage', function(e) {
        if (e.key === STORAGE_TS && e.newValue === null) { removeModal(); }
    });

    window.LabRenew = {
        setSignInTs: function(t) { localStorage.setItem(STORAGE_TS, t); },
        confirm: function() {
            stopBeep();
            var idx = activeRenewIdx;   // 先保存！
            removeModal();
            if (idx >= 0) {
                var a = readAck();
                a[ackKey(RENEW_POINTS[idx])] = true;
                writeAck(a);
            }
            LabToast.show('已确认在线，续签成功。', 'success', 3000);
        },
        signout: function() { stopBeep(); autoSignout(); },
        tick: tick
    };

    setInterval(tick, 1000);
    tick();
})();
```

### lab.py — 服务端续签检测（供前端轮询参考）

```python
# /checkin/status 接口返回 need_renew 字段
renew_at = [3*60, 6*60, 9*60]  # 3h/6h/9h 检查点
need_renew = None
for n in renew_at:
    if duration_minutes >= n and duration_minutes < n + 5:  # 5分钟窗口
        need_renew = n // 60
        break
```

### checkin.html — localStorage 初始化

```javascript
(function() {
    var block = document.getElementById('checkedInBlock');
    if (block && block.dataset.checkedIn === 'true') {
        var tsStr = block.dataset.signinTs;
        if (tsStr) {
            var ts = new Date(tsStr).getTime();
            if (!isNaN(ts)) LabRenew.setSignInTs(ts);
        }
    } else {
        localStorage.removeItem('lab_signin_ts');
        localStorage.removeItem('lab_renew_ack');   // 注意：新版 key 名
    }
})();
```

---

## 调试过程时间线

| 阶段 | 用户反馈 | 修复 | 结果 |
|------|---------|------|------|
| 1 | 续签弹窗不可见 | 弹窗 inline style | ✅ 弹窗可见 |
| 2 | 登录页/入库出库页样式乱 | style.css 重新加载 | ✅ |
| 3 | 确认后切换页面仍弹窗 | grace 标记持久化 | ❌ 键名不匹配 |
| 4 | 同上 | `k.substring(1)` 修正键名 | ❌ 仍弹窗 |
| 5 | 第一次确认后突然蜂鸣但无弹窗 | 添加跨标签页 sync | ❌ 不稳定 |
| 6 | 用户要求完全重构 | 续签 IIFE 重写为 localStorage 单状态源 | ✅ 通过 |
| 7 | 确认后秒重复弹窗 | `confirm()` 中 `removeModal()` 重置 idx | ❌ 顺序错误 |
| 8 | 同上 | 先保存 idx 再 removeModal | ❌ showModal 内部覆盖 |
| 9 | 同上 | `activeRenewIdx = i` 移到 `showModal()` 之后 | ✅ 通过 |

---

## 设计决策

1. **localStorage 单状态源**：抛弃双 flag 内存缓存设计，所有状态通过 `localStorage.lab_renew_ack` 管理，`tick()` 每次重新读取。
2. **CSS 加载顺序**：`style.css`（基础）→ `app.css`（覆盖），两套变量不冲突。
3. **弹窗内联样式**：关键 overlay 样式 inline 写入，确保任何页面都可见。
4. **蜂鸣控制**：`setInterval` + 保存 timer ID，`stopBeep()` 完全控制停止，15 秒后自动静音。

---

## 当前文件状态

| 文件 | 状态 | 说明 |
|------|------|------|
| `static/js/app.js` | ✅ 已修改 | 续签系统完整重写 |
| `templates/base.html` | ✅ 已修改 | style.css 重新加载，版本号 v3.2.2 |
| `templates/lab/checkin.html` | ✅ 已修改 | localStorage key 名 `lab_renew_ack` |
| `src/admin.py` | ✅ 已修改 | `CURRENT_VERSION = "v3.2.2"` |
| `build.py` | ✅ 已修改 | `LabManager-V3.2.2` |
| `static/css/app.css` | ✅ 已修改 | auth/stock/toast/searchable-select 样式补充 |
| `dist/LabManager-V3.2.2.exe` | ✅ 已构建 | 生产配置 |
| `test_stats.py` | ⚠️ 未使用 | 之前的测试文件 |
