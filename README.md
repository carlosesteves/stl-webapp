# stl-webapp

FastAPI app with a server-rendered public site (Jinja2 + HTMX) and an admin area for editing the database. Deployed on Render, database on Supabase Postgres.

## Local development

```
mise install
cp .env.example .env
docker compose up -d db
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Tests: `uv run pytest` (SQLite in memory, no Supabase needed).

## Layout

- `app/routers/public.py` – public pages
- `app/routers/admin.py` – `/admin` login and Item CRUD
- `app/auth.py` – Supabase JWT verification and `require_admin`
- `app/supabase.py` – password sign-in against Supabase Auth
- `alembic/` – migrations

## Admin access

Admins sign in at `/admin/login` with their Supabase email and password. A user is an admin when their `app_metadata.role` is `admin`. Set it in the Supabase dashboard (Authentication > Users) or with the service-role API. `user_metadata` is user-editable and is not trusted.

Tokens are verified by algorithm: HS256 with `SUPABASE_JWT_SECRET`, or ES256/RS256 via the project's JWKS endpoint.

## Deploying to Render

1. Create a Blueprint from this repo (`render.yaml`).
2. Set `DATABASE_URL` (Supabase connection string; the session pooler is the safe choice on Render), `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_JWT_SECRET` if needed.
3. Migrations run on each start.
