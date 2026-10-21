# MOTO TECH Service — Proxmox deployment (preproduction)

This stack is intended for a dedicated **Debian 12 VM on Proxmox** with Docker Engine and Docker Compose plugin.
Recommended starting VM: **4 vCPU, 8 GB RAM, 100 GB SSD**, increase storage according to photos.
Do not expose the Proxmox host or database ports directly to the internet.

## Install
1. Create isolated Debian VM, allocate fixed LAN IP, configure firewall and SSH keys.
2. Install Docker Engine + Compose plugin from official Docker repository.
3. Clone `https://github.com/nyaganmaksimov-sys/moto-tech`, checkout `deploy/proxmox-stack`.
4. `cd deploy/proxmox && cp .env.example .env && chmod 600 .env`; generate a long random password.
5. Run `docker compose up -d --build`.
6. Initialize schema **once** with:
   `docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < ../../backend/migrations/001_initial.sql`
7. Check `curl -fsS http://127.0.0.1:18080/health`.
8. Put a hardened HTTPS reverse proxy **on the VM/LAN gateway**, forwarding to `127.0.0.1:18080`. Terminate TLS using a valid certificate; publish **only TCP 443**. Set rate limiting and upstream timeouts. Do not deploy API publicly until authentication and uploads have been implemented.

## Data separation
- `pgdata`: private PostgreSQL volume.
- `photos`: reserved private application photos volume, **uploads not implemented yet**.
- `backups`: database dumps only, 14-day local retention. **Not a complete backup**.
- No shared folders or credentials with A4PRINT HUB.
- Do not store client photos or data in GitHub Pages localStorage for production.

## Backups
The example backup container runs a daily logical database dump. For actual operation,
set up encrypted offsite backups **including the photos volume**, restore tests,
Proxmox VM snapshots and monitoring/alerts. A VM snapshot alone is not a replacement
for PostgreSQL-aware backups.

## Security / current limitations
This is an infrastructure foundation, not production-ready CRM. No user authentication,
photo-upload endpoints, access control, transactional intake-photo validation, or audit-safe delete policy
are implemented yet. The UI remains a local GitHub Pages demo.

IMPORTANT: DO NOT PUT REAL CLIENT DATA IN THIS STACK UNTIL THOSE ARE READY.

## Previous Render resources
The earlier Render database and service were created separately. This branch does not
modify or delete them; decide later whether to suspend them to avoid unintended charges.
