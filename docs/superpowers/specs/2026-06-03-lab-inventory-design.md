# 实验室器材管理系统 — 设计文档

> 日期：2026-06-03  
> 技术栈：Python Flask 3 + SQLAlchemy + SQLite + Jinja2 + Bootstrap 5

## 1. 产品概述

部署在实验室公共电脑上的局域网 Web 应用。成员可注册账号，查看库存、入库、出库，支持自定义多条件筛选查询记录。

### 功能清单
- 用户注册/登录
- 器材分类管理
- 器材 CRUD + 库存预警
- 入库（填写数量/封装/型号/备注）→ 库存增加 + 操作日志
- 出库（校验库存）→ 库存扣减 + 操作日志
- 高级筛选查询（按人/类型/器材/分类/时间范围） + 分页
- 仪表盘首页（库存概览 + 预警 + 最近记录）

## 2. 数据模型

### User
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| username | String(80) unique | 用户名 |
| password_hash | String(200) | werkzeug 哈希 |
| role | String(20) default='member' | admin/member |
| created_at | DateTime | 注册时间 |

### Category
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| name | String(80) unique | 分类名 |
| description | Text | 描述 |
| created_at | DateTime | 创建时间 |

### Equipment
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| name | String(200) | 器材名称 |
| model | String(200) | 型号 |
| packaging | String(200) | 封装 |
| category_id | Integer FK → Category | 分类 |
| stock_quantity | Integer default=0 | 当前库存 |
| alert_threshold | Integer default=0 | 预警阈值 |
| unit | String(50) default='个' | 单位 |
| remark | Text | 备注 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### StockRecord
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| equipment_id | Integer FK → Equipment | 器材 |
| user_id | Integer FK → User | 操作人 |
| type | String(10) | 'in' / 'out' |
| quantity | Integer | 操作数量 |
| before_stock | Integer | 操作前库存 |
| after_stock | Integer | 操作后库存 |
| remark | Text | 备注 |
| created_at | DateTime | 操作时间 |

## 3. 路由设计

| 路由 | 方法 | 说明 | 权限 |
|------|------|------|------|
| /login | GET/POST | 登录 | 公开 |
| /register | GET/POST | 注册 | 公开 |
| /logout | GET | 登出 | 登录 |
| / | GET | 仪表盘首页 | 登录 |
| /equipment | GET | 器材列表（搜索/过滤/预警） | 登录 |
| /equipment/new | GET/POST | 新增器材 | 登录 |
| /equipment/<id>/edit | GET/POST | 编辑器材 | 登录 |
| /equipment/<id>/delete | POST | 删除器材 | 登录 |
| /categories | GET/POST | 分类列表 + 新增 | 登录 |
| /categories/<id>/edit | GET/POST | 编辑分类 | 登录 |
| /categories/<id>/delete | POST | 删除分类 | 登录 |
| /stock/in | GET/POST | 入库 | 登录 |
| /stock/out | GET/POST | 出库 | 登录 |
| /records | GET | 高级筛选查询 + 分页 | 登录 |

## 4. 页面设计

- **登录/注册**：居中卡片式表单
- **仪表盘**：顶部统计卡片（总器材数/总库存量/本月入库/本月出库），中间库存预警表格，底部最近操作记录
- **器材列表**：搜索框 + 分类下拉过滤 + 表格（库存低于阈值高亮红色行）
- **入库/出库**：选择器材（下拉搜索）+ 填写数量 + 备注，提交确认
- **记录查询**：多条件筛选面板（可折叠）+ 结果表格 + 分页

## 5. UI 设计方向

- 风格：现代专业实验室风格，简洁实用
- 配色：蓝色主色调 + 白色背景（专业、可信赖）
- 字体：系统原生字体栈
- 框架：Bootstrap 5 + 自定义 CSS
- 响应式：适配 1280px+ 实验室显示器

## 6. 架构决策

- Flask 单体应用，Blueprint 模块化
- SQLite 数据库（单文件，零配置）
- Werkzeug 密码哈希
- Flask-Login Session 管理
- 数据库事务保护入库/出库操作
- 绑定 0.0.0.0:5000 允许局域网访问
