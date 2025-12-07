# Lean Forum

It's a simple forum, made by Django.

Use it to run:

``` bash
"gunicorn lean_forum.wsgi:application --bind 0.0.0.0:8000"
```

If you want to run it in debug mode.

Use it:

``` bash
export DEBUG=1
python manage.py runserver
```

`python manage.py test` to run test.
