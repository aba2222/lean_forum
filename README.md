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
| `DEBUG` | Debug mode | `0` |

## License

AGPL-3.0
