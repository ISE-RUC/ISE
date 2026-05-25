#!/bin/bash
# PostgreSQL 数据库初始化脚本

set -e

DB_NAME="ise_db"
DB_USER="ise_user"
DB_PASSWORD="1@mAp0wErfulP@ssw0rd"

echo "正在创建 PostgreSQL 数据库和用户..."

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
