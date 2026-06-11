# LabManager - 实验室器材管理系统

电子技术创新实验室专用器材管理系统，支持器材管理、入库出库、签到统计、群聊文件共享。

## 技术栈

Python Flask + SQLite + Bootstrap 5 + Chart.js

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python run.py

# 浏览器访问
http://localhost:5000
```

## 打包

```bash
python build.py
# 输出: dist/LabManager-V3.1.exe
```

## 目录结构

```
lab-inventory/
├── run.py                 # 启动入口
├── build.py               # 打包脚本
├── requirements.txt
├── src/                   # 后端源码
│   ├── app.py             # Flask 工厂
│   ├── models.py          # 数据模型 (13张表)
│   └── ...                # 13个蓝图模块
├── templates/             # Jinja2 模板
├── static/                # 前端资源 (全部本地化)
└── instance/              # 运行时数据
```

## 主要功能

- **器材管理** — CRUD + 可搜索下拉 + 分类过滤 + 库存预警
- **入库/出库** — 库存快照 + 操作日志 + 事务保护
- **记录查询** — 6维度高级筛选 + CSV导出 + 管理员删除
- **签到系统** — 签到/签退 + 续签确认(3/6/9h) + 12h自动签退 + 防挂机
- **签到统计** — 时长排名 + 成员详情 + 每日明细图表 + 时间段筛选
- **公告 & 值日** — 公告发布(管理) + 值日排班(全员可见)
- **群聊 & 文件** — 群聊 + 共享文件 + P2P点对点传输
- **分片上传** — 10MB/片分片上传，支持5GB大文件，可取消
- **管理后台** — 用户管理 + 权限控制 + 操作日志 + 数据备份

## 许可证

MIT
