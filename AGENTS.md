# Peak Group of Schools — Base44 Dev Environment

## Stack
- Django 6.x, Python 3.12, SQLite (default), WhiteNoise, Gunicorn (production only).
- Dev server: `python manage.py runserver 0.0.0.0:3000` (auto-reload via inotify; works with the bind mount).

## Running in the sandbox
- `docker compose -f docker-compose.base44.yml up -d --build` boots the app on port 3000.
- The compose startup installs `requirements-dev.txt`, runs migrations, seeds demo data, then starts the dev server.
- No external credentials are required to boot. All integrations (Google Meet, M-Pesa, PayPal, Stripe, WhatsApp) are optional.

## Key env vars
- `DJANGO_DEBUG=true` — required for dev; enables auto-reload and static file serving.
- `DJANGO_ALLOWED_HOSTS=*` — the sandbox host rotates, so a wildcard is used in dev.
- `DJANGO_CSRF_TRUSTED_ORIGINS` — set to the preview origin so POST forms work through the proxy.
- `DJANGO_SECRET_KEY` — has a dev fallback in settings.py; set a real value via secrets for any shared environment.

## Demo accounts (seeded by `seed_school_data`)
- Admin: `admin@school.com` / `admin123`
- Teacher: `teacher@school.com` / `teacher123`
- Student: `student@school.com` / `student123`
- Parent: `parent@school.com` / `parent123`

## Health check
- `GET /healthz` returns `ok` if the database is reachable.

## Optional integrations
- Google Meet, M-Pesa, PayPal, Stripe, WhatsApp — all optional. Without credentials, payment flows record demo payments and no meeting links are generated.
