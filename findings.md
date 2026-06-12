# LabManager 功能增强 — 发现记录

## 2026-06-10 会话发现

### 中文输入法打断问题位置
- `templates/equipment/index.html:114` — 器材列表实时搜索 input 事件
- `templates/chat/index.html:47` — 聊天框 Enter 键提交
- 新增的器材搜索下拉组件 — 自带 composition 处理

### 文件传输问题
- P2P 发送使用 `file.save()` 同步写入，大文件可能阻塞超时
- Waitress 默认缓冲区小，需增大 `send_bytes`/`recv_bytes`
- 改为 64KB 分块流式写入

### 器材删除限制
- `equipment.py:125` 原逻辑：`stock_records.count() > 0` 拒绝删除
- 改为级联删除 StockRecord + OperationLog

### 签到状态
- 需要后端自动签退（12h）+ 前端 AFK 检测（60min）+ 3h 通知轮询

### 已修改文件
- `src/equipment.py` — 级联删除
- `src/records.py` — 管理员删除记录 + API
- `src/stock.py` — 器材列表 JSON API
- `src/lab.py` — 签到统计 API + 自动签退 + 状态轮询
- `src/chat.py` — 流式文件写入
- `run.py` — Waitress 大文件配置
- `static/js/app.js` — Toast 通知 + AFK 检测
- `static/js/searchable-select.js` — 新建，可搜索下拉组件
- `static/css/style.css` — 新增组件样式 + 动画
- `templates/stock/in.html` — 使用可搜索下拉
- `templates/stock/out.html` — 使用可搜索下拉
- `templates/equipment/index.html` — composition 事件修复
- `templates/chat/index.html` — composition 事件修复
- `templates/records/index.html` — 管理员删除按钮
- `templates/lab/checkin_stats.html` — 完全重写，三标签页交互
    - `templates/lab/checkin.html` — 签到状态轮询 + AFK 检测

## 2026-06-12 会话发现

### 未读消息红点实现
- 新增 `UserSettings.last_read_chat_id` 字段记录用户已读位置
- 新增 `GET /chat/unread` API 返回未读消息数
- 打开群聊页 (`/chat/`) 自动标记已读
- `app.py` 新增 `inject_unread()` 上下文处理器
- `base.html` 侧边栏群聊项添加红色徽标 `<span class="chat-unread-badge">`
- `app.js` 新增全局轮询每 3s 更新未读数
- `style.css` 新增 `.chat-unread-badge` 样式

### 已修改文件
- `src/models.py` — UserSettings 新增 last_read_chat_id
- `src/chat.py` — 群聊页标记已读 + `/chat/unread` API
- `src/app.py` — unread_count 上下文处理器
- `templates/base.html` — 侧边栏未读徽标
- `templates/about/index.html` — 版本信息下方添加标识
- `static/js/app.js` — 全局未读轮询
- `static/css/style.css` — 徽标样式
- `README.md` — 群聊说明更新
- `架构文档.md` — 路由/模型/特性描述更新
- `开发维护指南.md` — V3.2 新增记录
- `说明文档.md` — 功能列表/源码清单更新
