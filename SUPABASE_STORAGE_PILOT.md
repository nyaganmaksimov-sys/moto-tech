# MOTO TECH — бесплатное тестовое хранение фотографий

Supabase project: MOTO TECH (`kjgalcvxxjnapcaocvry`)
Private bucket: `moto-tech-test-photos` (public=false, file limit 12 MB, JPEG).
Verified in Supabase on 2026-10-20.

The server uses `backend/api/supabase_storage.py` for photo upload, existence checks,
and cleanup. Only PostgreSQL object keys are returned to browser clients.
No public bucket policies or signed anonymous URLs are created.

## Render configuration
Set in the *dedicated MOTO TECH service* environment (never GitHub or browser):
- `MOTOTECH_SUPABASE_URL=https://kjgalcvxxjnapcaocvry.supabase.co`
- `MOTOTECH_SUPABASE_SECRET_KEY`: a secret/server-side API key from the MOTO TECH Supabase project

Do not send API keys in chat. The ChatGPT Supabase connection does not transfer its credentials to Render.
Render continues to require its own configured DATABASE_URL and MOTOTECH_JWT_SECRET.
Migrations and staff accounts must exist before testing end-to-end.

The existing Render API service follows branch `backend/postgres-foundation`,
while this code is in `integration/storage-pilot`. No deployment is performed by
these changes. Before redirecting Render to the integration branch, run the CI tests,
verify database schema and authentication, and confirm environment variables.

**Use fictional customers and motorcycles only.** The free storage tier has limited
capacity and does not replace backups, retention policy, secure document handling,
or a production-ready access-control review.
