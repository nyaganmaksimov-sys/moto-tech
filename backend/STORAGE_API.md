# MOTO TECH storage API — development

This branch is not a production deployment.

Requirements: Python 3.11+, private PostgreSQL, HTTPS, a 32+ character random MOTOTECH_JWT_SECRET, DATABASE_URL, MOTOTECH_ALLOWED_ORIGINS and dependencies from backend/requirements.txt.

Apply migrations 001_storage_foundation.sql then 002_staff_auth.sql to a private database. Create employee accounts only by a trusted administrator; store Argon2 hashes rather than plaintext passwords. There are no default employee credentials or public registration route.

Implemented: POST /auth/login, GET /auth/me, GET /storage, POST /storage (draft only), GET /storage/{id}. All storage routes require a valid session and an active employee account. Mechanics and managers can start draft intake.

Not yet implemented: object upload, completed intake, return and delivery workflow, photo authorization, deployment, rate limiting, backup verification and frontend integration. Do not store real client data in the GitHub Pages prototype.

Tests: python -m unittest discover -s backend/tests -v

Before production use: configure authentication throttling, private object storage, signed photo access, atomic intake completion, migration tests, backups and role-based frontend integration.

## Photo intake (development only)
Set MOTOTECH_PRIVATE_PHOTO_ROOT to an existing, private directory owned by the API service user (not within any public/static web root). Limit filesystem and backup access to authorized operators. The API converts validated JPEG/PNG/WEBP images to private JPEGs, removes embedded EXIF metadata and stores their SHA-256 hashes in PostgreSQL.
- POST /storage/{id}/photos (multipart kind, note, photo; bearer token)
- POST /storage/{id}/accept (JSON version and condition_confirmed=true; bearer token)

Acceptance requires front, rear, left, right and VIN images, a written condition, and existing private files. Images remain unavailable through public URLs. Set up HTTPS, private backups, upload quotas, auth throttling, and media scan/isolation before using customer data.
