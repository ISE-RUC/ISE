# 学院学生综合服务与党团管理平台

基于 Django 的学院学生综合服务平台，目标覆盖党团事务、智能问答、证明申请、通知公告和学生画像等模块。

当前仓库已经不再是纯静态骨架，`party` 模块已具备可演示、可验收的管理与学生双端能力：

- 学生查看党团进度
- 学生查看时间轴
- 学生上传当前节点材料
- 学生提交当前节点审批
- 管理老师查看待审批任务
- 管理老师通过或驳回审批
- 管理老师批量审批待办任务
- 管理老师按规则撤回审批结果
- 管理老师配置流程规则
- 管理老师批量导入导出流程数据
- 学生查看提醒与历史链路

## 当前推荐启动方式

推荐优先使用测试库配置启动，不要直接依赖仓库中的默认 `db.sqlite3`。

原因：

- 当前仓库新增了 `users` 和 `party` 的迁移文件
- 默认库 `db.sqlite3` 保留了更早阶段的迁移历史
- 直接使用默认库时，可能会出现迁移不一致提示

推荐命令如下：

```bash
pip install -r requirements.txt
python manage.py migrate --settings=config.settings_testdb
python manage.py seed_party_data --with-demo-users --settings=config.settings_testdb
python manage.py runserver --settings=config.settings_testdb
```

启动后访问：

`http://127.0.0.1:8000/`

## 演示账号

执行 `seed_party_data --with-demo-users` 后会生成以下账号：

- 管理老师：`party_admin / party1234`
- 入党流程学生：`party_student / party1234`
- 入团流程学生：`league_student / party1234`

可直接体验的页面：

- 学生端首页：`/party/student/`
- 学生端时间轴：`/party/student/timeline/`
- 学生端材料页：`/party/student/materials/`
- 学生端历史页：`/party/student/history/`
- 管理端成员列表：`/party/admin/members/`
- 管理端审批页：`/party/admin/approvals/`
- 管理端规则页：`/party/admin/rules/`
- 管理端导入导出页：`/party/admin/import/`

## 默认库说明

如果你直接运行：

```bash
python manage.py runserver
```

Django 可能会提示 `users` 迁移未应用。这不是 `runserver` 本身有问题，而是默认 `db.sqlite3` 与当前代码中的迁移状态不一致。

当前阶段：

- 想直接看页面和操作闭环：使用 `config.settings_testdb`
- 想继续整理默认开发库：需要额外处理旧库迁移历史

## 项目结构

```text
ISE/
├── apps/
│   ├── users/              # 自定义用户、角色、审计日志
│   ├── qa/                 # 智能问答
│   ├── party/              # 党团事务
│   ├── certificate/        # 证明开具
│   ├── notification/       # 通知公告
│   └── profile/            # 学生画像
├── config/                 # Django 配置
├── docs/                   # 项目文档
├── static/                 # 静态资源
├── templates/              # Django 模板
├── manage.py
└── requirements.txt
```

## 党团事务模块现状

`apps/party` 当前已经补齐以下能力：

- 数据模型与迁移
- 最小种子数据初始化命令
- 服务层：
  - `workflow.py`
  - `approval.py`
  - `reminder.py`
  - `import_export.py`
- 查询层：
  - `selectors.py`
- 表单层：
  - `forms.py`
- 学生端页面
- 管理端页面
- 提醒同步命令
- Excel 导入导出
- 审计日志接入
- 基础测试覆盖

初始化命令：

```bash
python manage.py seed_party_data --settings=config.settings_testdb
python manage.py seed_party_data --with-demo-users --settings=config.settings_testdb
```

## 主要文档

- 开发指南：[docs/开发指南.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/开发指南.md)
- 前端样式指南：[docs/前端样式指南.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/前端样式指南.md)
- Django 模板使用指南：[docs/Django模板使用指南.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/Django模板使用指南.md)
- 管理员操作手册：[docs/党团模块管理员操作手册.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团模块管理员操作手册.md)
- 学生端使用手册：[docs/党团模块学生端使用手册.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团模块学生端使用手册.md)
- 测试库启动与验收清单：[docs/党团模块测试库启动与验收清单.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团模块测试库启动与验收清单.md)
- SRS 提取稿：[docs/_srs_extracted.txt](/C:/Users/LENOVO/Desktop/vs/ISE/docs/_srs_extracted.txt)
- 党团模块设计说明：[architecture.md](/C:/Users/LENOVO/Desktop/vs/ISE/apps/party/docs/architecture.md)

## 当前验收建议

如果你现在要按操作手册走一遍检测，建议顺序是：

1. 使用 `config.settings_testdb` 进入可运行环境
2. 先打开 [docs/党团模块测试库启动与验收清单.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团模块测试库启动与验收清单.md)
3. 再按 [docs/党团模块管理员操作手册.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团模块管理员操作手册.md) 和 [docs/党团模块学生端使用手册.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团模块学生端使用手册.md) 逐项检查

## 当前下一步任务

当前仓库里，`party` 模块已经完成“入党流程最小闭环 + 入团流程基础闭环”，后续建议按以下顺序推进：

1. 先完成一轮完整人工验收并收口问题
2. 再增强管理端高密度视图与页面联动
3. 再推进提醒调度的计划任务化
4. 再完善 `league` 流程的演示数据、文档和细节体验
5. 最后整理交付与部署文档

详细任务拆分见：

- [docs/党团模块开发清单.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团模块开发清单.md)
- [docs/党团事务模块实施方案.md](/C:/Users/LENOVO/Desktop/vs/ISE/docs/党团事务模块实施方案.md)
