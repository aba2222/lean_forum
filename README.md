# Lean Forum

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2+-092E20?logo=django&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)
![License](https://img.shields.io/badge/License-AGPL--3.0-blue)

A lightweight forum system built with Django.

[中文文档](README_CN.md) | **Live Demo:** [lforum.dpdns.org](https://lforum.dpdns.org)

## Features

- Markdown editor with LaTeX math support
- Post creation, comments, and deletion
- Personal profile page with avatar upload (falls back to a letter avatar)
- Post collections
- AI bot (mention `@bot` in a post)
- Web Push browser notifications
- Light/Dark theme toggle
- RESTful API (Django REST Framework)
- Docker deployment support

## Tech Stack

- **Backend:** Django 5.2+, Django REST Framework
- **Frontend:** Bootstrap 5.3, Bootstrap Icons, github-markdown-css, MathJax
- **Editor:** django5-mdeditor
- **Database:** SQLite (default)
- **Other:** django-webpush, bleach, OpenAI API

## Quick Start

### Requirements

- Python 3.10+

### Local Development (venv recommended)

```bash
git clone https://github.com/aba2222/lean_forum.git
cd lean_forum

python -m venv venv
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate

export DEBUG=1
python manage.py runserver
```

Visit http://127.0.0.1:8000

### Docker

```bash
docker build -t lean-forum .
docker run -p 8000:8000 lean-forum
```

### Production

```bash
python manage.py migrate
gunicorn lean_forum.wsgi:application --bind 0.0.0.0:8000
```

#### Reverse proxy: raise `client_max_body_size`

**This is the easiest thing to trip over after deploying.** nginx defaults
`client_max_body_size` to **1 MB**, while avatars go up to 2 MB (6 MB for
animated GIF/WebP) and editor audio up to 25 MB. When the body exceeds the
limit, nginx answers `413 Request Entity Too Large` **before the request ever
reaches Django** — the app never sees it, the user just gets an nginx error
page, and the rest of the form is lost too.

Ask the project what the number should be (it reads the real constants, rather
than a value copied into the docs):

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

Minimal working config:

```nginx
server {
    listen 80;
    server_name your-domain.example;

    # must be >= the largest upload the app accepts (see above);
    # the 1 MB default makes avatar/image uploads fail with 413
    client_max_body_size 30m;

    # when nginx serves these, set SERVE_STATIC / SERVE_MEDIA to 0
    location /static/ {
        alias /path/to/lean_forum/staticfiles/;   # run collectstatic first
    }

    location /media/ {
        alias /path/to/lean_forum/uploads/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;

        # so the app can see the real client IP (see the env var section)
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then `nginx -s reload`.

> `client_max_body_size` alone is not enough: set `FORUM_TRUSTED_PROXY_COUNT` to
> match how many proxies you have in front, or every client IP in the logs will
> be nginx's own machine.

#### Other deployment steps

```bash
python manage.py collectstatic --noinput
python manage.py build_search_index    # optional; the first search builds it anyway
```

## API

Read-only RESTful API. Anonymous read access; write operations require authentication.

### List Posts

```
GET /api/posts/?limit=20&offset=0
```

### Post Detail (includes comments)

```
GET /api/posts/{id}/
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | Built-in dev key |
| `DEBUG` | Debug mode; only `1`/`true`/`yes`/`on` enables it | `0` |
| `SERVE_MEDIA` | Serve `/media/` uploads (avatars, post images) from Django. Set to `0` when a front-end server (nginx/CDN) already handles `/media/` | `1` |
| `SERVE_STATIC` | Serve `/static/` from Django (requires `collectstatic`). Set to `0` when a front-end server handles `/static/` | `1` |

> Local development: set `DEBUG=1`. With debug on, `runserver` serves app static files
> (including the Markdown editor) directly, so `collectstatic` is not needed.

## License

AGPL-3.0
