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

### Local Development: one command (Windows)

Double-click `dev.bat`, or from PowerShell:

```powershell
.\dev.ps1
```

It takes a fresh clone all the way to a running server: creates the virtualenv if
missing (picking a 3.10+ interpreter on purpose — the `python` on your PATH is
often an older one without Django), installs dependencies when they changed,
generates and applies migrations, then serves on http://127.0.0.1:8000.

```powershell
.\dev.ps1 -Superuser        # also create an admin account (random password, printed)
.\dev.ps1 -Port 9000 -Address 0.0.0.0   # different port, reachable from the LAN
.\dev.ps1 -Test             # run the test suite only
.\dev.ps1 -NoSetup          # don't touch the environment, just start
```

> Why this exists: the repo keeps `migrations/` in `.gitignore`, so a fresh clone
> has **no migration files at all** and nothing can be created until you generate
> them; and without `DEBUG=1` every asset under `/static/` (including the Markdown
> editor) 404s. Both are easy to trip over on a first run.

### Manual steps (other platforms, or if you want to see each step)

```bash
git clone https://github.com/aba2222/lean_forum.git
cd lean_forum

python -m venv venv
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

pip install -r requirements.txt

# note the explicit app names, see below
python manage.py makemigrations forum md_editor
python manage.py migrate

export DEBUG=1
python manage.py runserver
```

> `makemigrations` needs the explicit `forum md_editor` app labels. Without them,
> Django **skips apps that don't have a `migrations` package yet** — which is
> exactly the state of a fresh clone, so `forum` gets no tables and every page
> fails with `no such table: forum_post`.

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

> Local development: set `DEBUG=1`. With debug on, `runserver` serves app static files
> (including the Markdown editor) directly, so `collectstatic` is not needed.

## License

AGPL-3.0
