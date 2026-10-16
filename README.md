# Peak Group of Schools

A Django-powered school portal demo for school administrators, teachers, students, and parents. Django handles application logic and templates; WhiteNoise serves static files, and Gunicorn runs the Django WSGI application in production.

## Features

- Role-based sign-in and dashboards for admins, teachers, students, and parents.
- Public student account creation with server-side password hashing; staff accounts remain staff-managed.
- Scheduled live lessons with meeting spaces created directly through the Google Meet REST API.
- A school library for learning materials and an exams area for PDF uploads.
- An interactive KCSE-style Physics practical lab for investigating a resistor's current-voltage relationship. It is a revision simulation, not an official KNEC examination paper.
- A practical-lab directory with interactive 3D Geography, Languages, Computer Science, Music, Biology, and Chemistry studios, alongside the Physics and Electrical labs. Subject activities include terrain and rainfall modeling, browser-based listening practice, binary conversion, synthesized musical notes, microscopy, and simulated indicator tests.
- A date-based practical attendance register where teachers and admins record and review which students were present or absent.
- Student invoices and payment records, with optional M-Pesa STK Push, PayPal Checkout, and Stripe Checkout integrations.
- Support tickets and contact forms.

Without payment-provider credentials, payment flows record demo payments. Google Meet lesson scheduling requires configured Google Workspace credentials; no fake meeting links are generated. Do not treat locally recorded demo payments or sample accounts as production data.

## Run locally

Requirements: Python 3.12 or newer. SQLite is used by default, so a local database server is not required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
set -a
source .env
set +a
python manage.py migrate --noinput
python manage.py seed_school_data
python manage.py runserver 127.0.0.1:8000
```

The portal is available at <http://127.0.0.1:8000>. The `.env` file is sourced into the current shell because Django does not load it automatically. Keep local secrets in `.env`; do not commit credentials.

`seed_school_data` creates sample accounts, library materials, classes, and invoices. It is safe to rerun for the existing sample records; it does not reset passwords on accounts that already exist.

## Demo accounts

These credentials are for local development only. Never use them on a public deployment.

Demo accounts:

- Admin: `admin@school.com` / `admin123`
- Teacher: `teacher@school.com` / `teacher123`
- Student: `student@school.com` / `student123`
- Parent: `parent@school.com` / `parent123`

## Configuration

The application reads settings from environment variables. Add optional integration settings to `.env` as needed.

| Variable | Purpose | Default or behavior |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Django signing and security key | The built-in fallback is for local development only; set a private value elsewhere. |
| `DJANGO_DEBUG` | Enable Django debug mode | `false` in settings; `.env.example` sets it to `true` for local development. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hostnames | `localhost,127.0.0.1,testserver` |
| `DATABASE_URL` | Database connection URL | If omitted, SQLite is used. |
| `SCHOOL_DB_PATH` | SQLite database file path | `db.sqlite3` in the project directory; ignored when `DATABASE_URL` is set. |
| `SCHOOL_MEDIA_ROOT` | Directory for uploaded files | `media/` in the project directory. |
| `PORT` | Web server port | `8000` locally; Render provides the production port. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins | Empty; use full origins such as `https://portal.example.com`. |
| `SECURE_SSL_REDIRECT` | Redirect HTTP requests to HTTPS | `false` |
| `SECURE_HSTS_SECONDS` | HSTS duration in seconds | `0` |

Render supplies `DATABASE_URL`, `PORT`, and `RENDER_EXTERNAL_HOSTNAME`. Its Blueprint configures the public bind address, persistent media directory, HTTPS redirect, and HSTS. Review host and security settings before using another hosting platform.

### Optional integrations

- **Google Meet:** Enable the Google Meet API in a Google Cloud project and configure Workspace domain-wide delegation for `https://www.googleapis.com/auth/meetings.space.created`. Set `GOOGLE_SERVICE_ACCOUNT_JSON` to the service-account key JSON and `GOOGLE_MEET_DELEGATE_EMAIL` to the Workspace user account that should own created meeting spaces. The service account delegates user authentication to this Workspace account. Keep the service-account key secret; use compact single-line JSON or configure it as a deployment secret. The Meet API creates the meeting space directly; lesson title and schedule are stored in the school portal.
- **M-Pesa:** Set `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_SHORTCODE`, and `MPESA_PASSKEY`. `MPESA_ENV` defaults to `sandbox`; use `production` only with live Daraja credentials. `MPESA_CALLBACK_URL` can override the callback URL.
- **PayPal:** Set `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`. `PAYPAL_ENV` defaults to `sandbox`; use `live` for the live API.
- **Stripe:** Set `STRIPE_SECRET_KEY` to enable Stripe Checkout. Use a Stripe test key while testing.
- **WhatsApp Groups API:** Set `WHATSAPP_API_VERSION`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, and `WHATSAPP_GROUP_ID` to send practical invitations directly into an API-managed group. Keep the access token in deployment secrets or `.env`; never commit it. Meta Groups API requires an Official Business Account and Cloud API-managed group. It cannot send into ordinary groups created in the WhatsApp app.

## Development commands

Run Django's configuration checks and test suite with:

```bash
python manage.py check
python manage.py test
```

To create the first administrator on a deployed instance, run `python manage.py create_portal_admin`. It prompts for administrator details and a password of at least 12 characters. Do not seed demo accounts on a public deployment.

## Project structure

- `config/` – Django settings, URL configuration, and WSGI application.
- `school/` – models, views, Google Meet and payment integrations, tests, and management commands.
- `/labs` – the practical-lab directory; `/labs/geography`, `/labs/languages`, `/labs/computer`, `/labs/music`, `/labs/biology`, and `/labs/chemistry` open guided subject studios. Interactions and observations stay in the browser; all activities are educational simulations and do not replace supervised practical work.
- `templates/` – Django templates for portal pages.
- `static/` – CSS and browser-side JavaScript collected and served by WhiteNoise.
- `library/` – bundled library resources.
- `render.yaml` – Render Blueprint for the web service, PostgreSQL database, and upload disk.

## Deploy on Render

The Blueprint in `render.yaml` creates a paid web service, PostgreSQL database, and persistent disk for uploads. Review current Render pricing before applying it. Deploy through <https://render.com/deploy?repo=https://github.com/kbw033u-netizen/school-lms-platform> and apply the Blueprint. The build installs dependencies and collects static files, the pre-deploy step runs migrations, and Gunicorn serves Django on Render's assigned port. Render checks `/healthz`, which verifies that the app can reach its database. Uploaded media is stored on the persistent disk. Demo accounts are not seeded in production.

After the first deploy, open the service Shell and run `python manage.py create_portal_admin`, then sign in and create staff accounts. Add Google Workspace or payment-provider credentials as Render environment variables if live integrations are required. Exam PDFs are stored under `media/exams/`.
