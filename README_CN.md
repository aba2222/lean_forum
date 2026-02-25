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
| `DEBUG` | 调试模式 | `0` |

## 测试

```bash
python manage.py test
```

## 许可证

AGPL-3.0
