#!/bin/bash
# PostgreSQL 数据库初始化脚本

set -e

# 从 .env 文件读取配置
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "错误: 未找到 .env 文件"
    echo "请先创建 .env 文件: cp .env.example .env"
    exit 1
fi

# 验证必需的环境变量
if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    echo "错误: .env 文件中缺少必需的配置项"
    echo "需要: DB_NAME, DB_USER, DB_PASSWORD"
    exit 1
fi

echo "正在创建 PostgreSQL 数据库和用户..."
echo "数据库名: $DB_NAME"
echo "用户名: $DB_USER"

# 创建用户（如果不存在）
sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename = '$DB_USER'" | grep -q 1 || \
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"

# 创建数据库（如果不存在）
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

# 授予权限
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -d $DB_NAME -c "GRANT ALL ON SCHEMA public TO $DB_USER;"

echo "✓ 数据库 $DB_NAME 和用户 $DB_USER 创建成功"
echo ""
echo "下一步："
echo "1. 确保已安装依赖: pip install -r requirements.txt"
echo "2. 运行迁移: python manage.py migrate"
echo "3. 创建超级用户: python manage.py createsuperuser"
