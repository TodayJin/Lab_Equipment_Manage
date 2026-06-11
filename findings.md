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
