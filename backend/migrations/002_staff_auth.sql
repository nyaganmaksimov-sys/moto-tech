BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS service_employees (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 username text NOT NULL UNIQUE CHECK (username = lower(username)),
 password_hash text NOT NULL,
 full_name text NOT NULL,
 role text NOT NULL CHECK (role IN ('owner_manager','manager','administrator','mechanic')),
 active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS storage_contracts_status_idx ON storage_contracts(status,updated_at DESC);
COMMIT;
