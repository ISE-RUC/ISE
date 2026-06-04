# users 登录模块迁移说明

## 新环境

直接执行：

```bash
python manage.py migrate
```

## 已存在旧库的环境

如果数据库里已经有 `users_user`、`users_auditlog` 等旧表，但 `users` 模块还没有迁移记录，请先执行：

```bash
python manage.py migrate users --fake-initial
python manage.py migrate
```

再根据需要初始化演示账号：

```bash
python manage.py seed_demo_users
```

## 原因

本次为 `users` 模块补充了正式迁移文件，并新增了 `employee_id` 字段。
旧环境如果此前是通过无迁移方式创建表，需要使用 `--fake-initial` 对齐迁移状态。
