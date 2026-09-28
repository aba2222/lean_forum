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

### 本地开发：一条命令

Windows 上直接双击 `dev.bat`，或者在 PowerShell 里：

```powershell
.\dev.ps1
```

它会从「刚 clone 下来什么都没有」一路做到「浏览器里能打开」：
没虚拟环境就建（自动挑一个 3.10+ 的解释器，不会误用 PATH 上的旧版本）、
依赖变了就装、生成并执行迁移，最后在 http://127.0.0.1:8000 起服务。

```powershell
.\dev.ps1 -Superuser        # 顺便建好后台账号（密码随机生成并打印）
.\dev.ps1 -Port 9000 -Address 0.0.0.0   # 换端口，并允许局域网访问
.\dev.ps1 -Test             # 只跑测试
.\dev.ps1 -NoSetup          # 不碰环境，只用现有的启动
```

> 为什么要单独做这个脚本：这个仓库把 `migrations/` 放进了 `.gitignore`，
> 刚 clone 下来一个迁移文件都没有，**必须先生成迁移**才能建表；
> 而且 `DEBUG=1` 不设的话 `/static/` 下的编辑器资源全是 404。
> 这两点都会让第一次跑起来的人卡住。

### 手动步骤（其它平台，或者想知道每一步在做什么）

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

# 数据库迁移（注意要带上 app 名，原因见下）
python manage.py makemigrations forum md_editor
python manage.py migrate

# 启动开发服务器
export DEBUG=1
python manage.py runserver
```

> `makemigrations` 必须显式写上 `forum md_editor`。不带参数的
> `makemigrations` 会**跳过连 `migrations` 目录都还不存在的 app**——
> 而刚 clone 下来正是这种情况，结果就是 `forum` 一张表都不建，
> 页面一访问就报 `no such table: forum_post`。

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
