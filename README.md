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
| `FORUM_TRUSTED_PROXY_COUNT` | Number of reverse proxies in front of Django. `0` = exposed directly, `1` = one nginx. See below | `0` |
| `FORUM_GEOIP_API` | Endpoint used to turn a client IP into a region for the profile page; `{ip}` is substituted. Empty disables online lookups | ip-api.com |
| `FORUM_GEOIP_TIMEOUT` | Region lookup timeout in seconds | `2` |

> Local development: set `DEBUG=1`. With debug on, `runserver` serves app static files
> (including the Markdown editor) directly, so `collectstatic` is not needed.

### About the profile region

The region shown on a profile page (e.g. "浙江 杭州") is derived from the user's IP.
Only the province/city level is stored or displayed — **the full IP is never shown**.
It replaces the old "location" text field that users had to fill in themselves.

- Lookups happen **on login and on profile save only**, at most once every 12 hours per
  IP. A failed lookup never breaks login; the region is left empty or keeps its
  previous value.
- **`FORUM_TRUSTED_PROXY_COUNT` must match your setup.** Behind nginx without setting it
  to `1`, every user shows the same region (nginx's machine). Without a proxy but set to
  `1`, a client can fabricate its own region via a forged `X-Forwarded-For`.
- **By default one request goes to ip-api.com** (free, no key, Chinese output). To keep
  user IPs off third-party services, point `FORUM_GEOIP_API` at your own service or set
  it empty — with it empty, only private addresses get a region and everything else is
  blank.

## License

AGPL-3.0
