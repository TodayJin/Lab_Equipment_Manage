# LabManager 功能增强设计文档

> 2026-06-10

## 改动清单

### 1. 入库/出库器材选择器 → 自定义搜索下拉

- 替换原生 `<select>` 为自定义可搜索下拉组件
- 支持关键词搜索（名称/型号）+ 分类标签过滤
- 显示库存数量，低于阈值红色高亮
- 处理中文输入法 composition 事件，防止拼音阶段触发搜索
- 新增 `/api/equipment/list` JSON 接口
- 涉及文件：`src/stock.py`, `templates/stock/in.html`, `templates/stock/out.html`, `static/js/searchable-select.js`

### 2. 签到统计增强

- 三标签页：总览 / 时长排名 / 每日明细
- 时间段快捷选择 Chip（近一周/一月/两月/本学期 + 自定义日期）
- 点击成员弹出详情弹窗（每日明细柱状图 + 汇总卡片）
- 后端新增 `/lab/checkin/user/<id>/detail` API
- 涉及文件：`src/lab.py`, `templates/lab/checkin_stats.html`

### 3. 器材级联删除

- 移除"有记录不能删"限制
- 删除器材时级联删除关联 StockRecord + OperationLog
- 确认弹窗显示将被清除的数据量
- 涉及文件：`src/equipment.py`

### 4. 管理员删除记录

- 记录查询页面每条记录行末加删除图标（仅管理员可见）
- 二次确认（JS confirm → 后端确认弹窗）
- 删除后回写操作日志
- 涉及文件：`src/records.py`, `templates/records/index.html`

### 5. P2P 大文件传输修复

- 改为流式分块写入，避免大文件撑爆内存
- 在 `run.py` 中配置 Waitress `send_bytes` / `recv_bytes`
- 涉及文件：`src/chat.py`, `run.py`

### 6. 全系统中文字输入修复

- `templates/equipment/index.html` — 实时搜索 input 事件加 composition 处理
- `templates/chat/index.html` — 聊天 Enter 键加 composition 处理
- 新增的搜索下拉组件 — 自带 composition 处理
- 涉及文件：如上

### 7. 自动签退 + 防挂机

- 超过 12 小时未签退 → 后端自动签退
- 每 3/6/9 小时 → 浏览器通知 + Toast 提醒
- 60 分钟无操作 → 弹窗「你在实验室吗？」，5 分钟不响应自动签退
- 前端 `/checkin/status` 轮询 API
- 涉及文件：`src/lab.py`, `templates/lab/checkin.html`, `static/js/app.js`

### 8. UI 美化

- 整体设计系统统一（indigo 主色调、圆角卡片、微妙阴影）
- 按钮/卡片 micro-interaction 动画
- 签到统计图表渐变色
- 排名徽章动画
- 涉及文件：`static/css/style.css`, 各模板
