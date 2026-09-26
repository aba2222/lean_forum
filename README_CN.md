# Lean Forum

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2+-092E20?logo=django&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)
![License](https://img.shields.io/badge/License-AGPL--3.0-blue)

一个基于 Django 的轻量级论坛系统。

**在线体验:** [lforum.dpdns.org](https://lforum.dpdns.org)

## 功能特性

- Markdown 编辑器（支持 LaTeX 数学公式）
- 帖子发布、评论、删除
- 个人主页与头像（支持上传头像，未设置时回退为字母头像）
- 文章合集
- AI 机器人（发帖时 `@bot` 召唤）
- Web Push 浏览器推送通知
- 明暗主题切换（跟随系统 / 手动切换）
- RESTful API（基于 Django REST Framework）
- Docker 部署支持

## 技术栈

- **后端:** Django 5.2+, Django REST Framework
- **前端:** Bootstrap 5.3, Bootstrap Icons, github-markdown-css, MathJax
- **编辑器:** django5-mdeditor
- **数据库:** SQLite（默认）
- **其他:** django-webpush, bleach, OpenAI API

## 快速开始

### 环境要求

- Python 3.10+

### 本地开发（推荐使用虚拟环境）

```bash
# 克隆仓库
git clone https://github.com/aba2222/lean_forum.git
cd lean_forum

# 创建并激活虚拟环境
python -m venv venv
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 数据库迁移
python manage.py makemigrations
python manage.py migrate

# 启动开发服务器
export DEBUG=1
python manage.py runserver
```

访问 http://127.0.0.1:8000

### Docker 部署

```bash
docker build -t lean-forum .
docker run -p 8000:8000 lean-forum
```

### 生产环境

```bash
python manage.py migrate
gunicorn lean_forum.wsgi:application --bind 0.0.0.0:8000
```

#### 反向代理：`client_max_body_size` 一定要调大

**这是部署后最容易踩的一个坑。** nginx 的 `client_max_body_size` 默认只有
**1 MB**，而本站的头像上限是 2 MB（GIF/WebP 动图 6 MB）、编辑器音频上限
是 25 MB。请求体超限时，nginx 会在请求**到达 Django 之前**就返回
`413 Request Entity Too Large` —— 应用侧完全不知情，用户只看到一张 nginx
的错误页，表单里其它内容也一起丢了。

先查出该配多少（它从代码里的真实常量读，不是文档里手抄的）：

```bash
python manage.py upload_limits
```

```
应用接受的上传上限：
  个人资料 · 头像（静态图）          2 MB
  个人资料 · 头像（GIF/WebP 动图）  6 MB
  编辑器 · 帖子/评论图片           10 MB
  编辑器 · 帖子/评论音频           25 MB

  # nginx
  client_max_body_size 30m;
```

完整的最小可用配置：

```nginx
server {
    listen 80;
    server_name your-domain.example;

    # 必须 ≥ 应用接受的最大上传体积（见上）；默认的 1 MB 会让头像/图片上传直接 413
    client_max_body_size 30m;

    # 交给 nginx 托管静态与上传文件时，记得把 SERVE_STATIC / SERVE_MEDIA 设为 0
    location /static/ {
        alias /path/to/lean_forum/staticfiles/;   # 先跑 collectstatic
    }

    location /media/ {
        alias /path/to/lean_forum/uploads/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;

        # 应用要能从 X-Forwarded-For 里取到真实客户端 IP（见环境变量一节）
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

改完 `nginx -s reload` 即可。

> 只调 `client_max_body_size` 还不够：`FORUM_TRUSTED_PROXY_COUNT` 也要按
> 前面有几层反代设对，否则日志里的客户端 IP 会全是 nginx 那一台。

#### 其它部署步骤

```bash
python manage.py collectstatic --noinput
python manage.py build_search_index    # 建全文索引；不跑也行，第一次搜索会自动建
```

## API 文档

基于 Django REST Framework，提供只读 RESTful API（匿名可读，写操作需认证）。

### 帖子列表

```
GET /api/posts/
```

支持分页参数：`?limit=20&offset=0`

响应示例：

```json
{
  "count": 50,
  "next": "/api/posts/?limit=20&offset=20",
  "results": [
    {
      "id": 1,
      "author": "username",
      "title": "帖子标题",
      "content": "帖子内容...",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

### 帖子详情

```
GET /api/posts/{id}/
```

响应包含评论列表：

```json
{
  "id": 1,
  "author": "username",
  "title": "帖子标题",
  "content": "帖子内容...",
  "created_at": "2026-01-01T00:00:00Z",
  "comments": [
    {
      "id": 1,
      "author": "username",
      "content": "评论内容",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SECRET_KEY` | Django 密钥 | 内置开发密钥 |
| `DEBUG` | 调试模式；只有 `1`/`true`/`yes`/`on` 才算开启 | `0` |
| `SERVE_MEDIA` | 由 Django 直接提供 `/media/` 上传文件（头像、帖子图片）；已用 nginx/CDN 托管 `/media/` 时设为 `0` | `1` |
| `SERVE_STATIC` | 由 Django 直接提供 `/static/`（需先 `collectstatic`）；已用前置服务器托管时设为 `0` | `1` |

> 本地开发请设置 `DEBUG=1`。开启调试后 `runserver` 会直接从各 app 的 `static/` 目录
> 提供静态文件（含 Markdown 编辑器），无需先跑 `collectstatic`。

## 测试

```bash
python manage.py test
```

## 许可证

AGPL-3.0
