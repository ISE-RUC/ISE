# 学院学生综合服务与党团管理平台

## 快速启动（前端展示）

### 1. 安装 Django

```bash
pip install django
```

### 2. 启动开发服务器

```bash
python manage.py runserver
```

访问 http://127.0.0.1:8000/ 即可看到主页。

## 项目结构

```
ISE/
├── apps/                    # 应用模块
│   ├── users/              # 用户管理
│   ├── qa/                 # 智能问答
│   ├── party/              # 党团事务
│   ├── certificate/        # 证明开具
│   ├── notification/       # 通知公告
│   └── profile/            # 个人画像
├── config/                 # Django 配置
├── templates/              # HTML 模板
├── static/                 # 静态文件（CSS/JS/图片）
└── docs/                   # 文档
```

## 功能模块

主页展示了 5 个功能模块的入口：

- **智能问答**：待组员实现
- **党团事务**：待组员实现
- **证明开具**：待组员实现
- **通知公告**：待组员实现
- **个人画像**：待组员实现

## 开发说明

各模块的 views.py 和 templates 已创建占位页面，组员可以在此基础上开发具体功能。

主页位于 `templates/home.html`，点击各模块卡片会跳转到对应的功能页面（如 `templates/qa/index.html`）。

样式文件在 `static/css/main.css`。
