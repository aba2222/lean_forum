#!/usr/bin/env bash

set -e

echo "部署 Lean Forum"
echo
echo "将执行："
echo "  - 同步源代码"
echo "  - 执行 Django migrations"
echo "  - 重启 Gunicorn"
echo

read -r -p "输入源代码地址: " SOURCE
read -r -p "输入 SSH 地址 (root@example.com): " HOST
read -r -p "输入远程目录 (~/lean_forum): " REMOTE_DIR
read -r -p "输入部署版本: " VERSION

DEPLOY_TIME="$(date '+%Y-%m-%d %H:%M:%S %Z')"
REMOTE="$HOST:$REMOTE_DIR"

echo
echo "本地目录: $SOURCE"
echo "远程目录: $REMOTE"
echo "部署版本: $VERSION"
echo "部署时间: $DEPLOY_TIME"
echo

cat > "$SOURCE/lean_forum/context_processors.py" <<PY
def deploy_info(request):
    return {
        "SITE_VERSION": "$VERSION",
        "DEPLOY_TIME": "$DEPLOY_TIME",
    }

PY

echo "==> 检查文件变化..."
echo

rsync -avzn --itemize-changes \
    --exclude='lean_forum/settings.py' \
    "$SOURCE/" \
    "$REMOTE"

echo
read -r -p "确认继续部署？[y/N] " answer

if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
    echo "已取消部署。"
    exit 0
fi

echo
echo "==> 开始同步文件..."

rsync -avz \
    --exclude='lean_forum/settings.py' \
    "$SOURCE/" \
    "$REMOTE"

echo
echo "==> 文件同步完成。"

echo "==> 执行 Django 部署操作..."

ssh "$HOST" <<EOF
set -e

cd "$REMOTE_DIR"

echo "==> Django check..."
source ./venv/bin/activate
python manage.py check

echo "==> Django migrate..."
python manage.py migrate --noinput

echo "==> Collect static..."
python manage.py collectstatic --noinput

echo "==> Restart Gunicorn..."
sudo systemctl restart lean-forum

echo "==> 检查服务状态..."
sudo systemctl is-active --quiet lean-forum

echo
echo "==> 部署成功！"
EOF
