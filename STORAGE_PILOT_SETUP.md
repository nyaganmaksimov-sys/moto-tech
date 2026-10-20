# MOTO TECH — объединённый пилот хранения

This branch combines the existing demo UI, a separate server intake UI at docs/storage-server.html, PostgreSQL models and API. It is **not deployed** and is **not production-ready**.

## Local-only preparation
1. Install Docker Compose on a secured test host.
2. Copy `.env.storage-pilot.example` to `.env`. Replace every placeholder with randomly generated secrets. Use URL-safe characters for POSTGRES_PASSWORD because DATABASE_URL is assembled as a URL.
3. Run `docker compose -f compose.storage-pilot.yml up -d --build`.
4. Apply migrations once, in order (back up any existing database first):
   `docker compose -f compose.storage-pilot.yml exec -T db psql -U mototech -d mototech < backend/migrations/001_storage_foundation.sql`
   `docker compose -f compose.storage-pilot.yml exec -T db psql -U mototech -d mototech < backend/migrations/002_staff_auth.sql`
5. Add employee test accounts with randomly generated passwords and Argon2 hashes via trusted DBA tooling. No default credentials are supplied.
6. Verify `http://127.0.0.1:10000/health` on the test host. Browser interface requires HTTPS reverse proxy and MOTOTECH_ALLOWED_ORIGINS set to its exact origin; `docs/storage-server.html` intentionally refuses non-HTTPS API URLs.
7. Run `python -m unittest discover -s backend/tests -v` in an environment with backend/requirements.txt installed. Also test upload, return, concurrency and backups against a disposable database.

Important: never forward the database port; API binds to local loopback. Protect the private photo volume and database backups. The server does not yet provide photo download, API edit endpoints, permissions fine-tuning, rate limiting, malware scanning or a tested recovery procedure. Do not add real personal data until these are ready. For now, use only generated demo information.

Existing `docs/index.html` remains a localStorage demo with Supabase-linked features; `docs/storage-server.html` is an isolated API-connected pilot, **not a fully merged production app**.
