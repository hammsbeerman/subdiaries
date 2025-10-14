
# Tabbed Journal – Packaged Project

This is a packaged Django project scaffold based on our spec:
- Multi‑org, roles (Owner/Admin/Moderator/Author/Subuser)
- Tiered moderation (L1 → Final)
- Tabs with visibility levels + team/organizational scoping
- Self‑registration with admin approval
- Profiles with default + custom fields (org‑level schema trickle‑down)
- Celery + Redis for async email
- MySQL
- Dev/Prod settings split
- Git + deploy scripts (Gunicorn, Celery worker/beat, Nginx)
- Billing (feature‑flagged) with plan quotas (mods/authors/subusers/custom tabs)
- Teams and linked moderators (controlled visibility)
- Reporting (profiles completion), tab usage

> This bundle includes a **working baseline** plus placeholders for some advanced flows to keep things manageable. Fill in TODOs as you enable features.

## Quickstart (Dev)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_SETTINGS_MODULE=journal_project.settings.dev
cp .env.example .env  # edit values
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_org
python manage.py runserver
```

## Production (Ubuntu 24.04)
See `deploy/` for systemd units and Nginx examples. Set `DJANGO_SETTINGS_MODULE=journal_project.settings.prod` in systemd.
