-- MOTO TECH / 001_storage_foundation.sql
-- Execute in a private PostgreSQL database. No public write routes are enabled by this migration.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS storage_contracts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_number text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','stored','return_requested','returned','cancelled')),
    customer_id uuid,
    vehicle_id uuid,
    owner_name text NOT NULL,
    owner_phone text,
    vin text NOT NULL,
    brand_model text NOT NULL,
    plate text,
    vehicle_year integer CHECK (vehicle_year BETWEEN 1885 AND 2200),
    vehicle_color text,
    mileage_km numeric(12,1) CHECK (mileage_km >= 0),
    engine_number text,
    location_label text,
    monthly_rate_rub numeric(12,2) NOT NULL DEFAULT 0 CHECK (monthly_rate_rub >= 0),
    received_at timestamptz,
    planned_return_at timestamptz,
    returned_at timestamptz,
    body_condition text,
    other_condition text,
    damage_description text,
    accessories jsonb NOT NULL DEFAULT '{}'::jsonb,
    document_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    billing_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by uuid,
    updated_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    CONSTRAINT storage_vin_present CHECK (length(btrim(vin)) > 0),
    CONSTRAINT storage_owner_present CHECK (length(btrim(owner_name)) > 0),
    CONSTRAINT storage_return_order CHECK (returned_at IS NULL OR received_at IS NULL OR returned_at >= received_at),
    CONSTRAINT storage_return_consistency CHECK (status <> 'returned' OR returned_at IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS storage_one_active_vin
    ON storage_contracts (upper(regexp_replace(vin, '[[:space:]-]', '', 'g')))
    WHERE status IN ('draft', 'stored', 'return_requested');

CREATE TABLE IF NOT EXISTS storage_photos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id uuid NOT NULL REFERENCES storage_contracts(id) ON DELETE RESTRICT,
    kind text NOT NULL CHECK (kind IN ('front','rear','left','right','vin','dashboard','damage','other','pts')),
    object_key text NOT NULL UNIQUE,
    sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    mime_type text NOT NULL CHECK (mime_type IN ('image/jpeg','image/png','image/webp')),
    size_bytes bigint NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 12582912),
    note text,
    captured_at timestamptz,
    uploaded_at timestamptz NOT NULL DEFAULT now(),
    uploaded_by uuid,
    deleted_at timestamptz,
    deleted_by uuid,
    CHECK (kind <> 'damage' OR nullif(btrim(note),'') IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS storage_photos_by_contract
    ON storage_photos(contract_id, kind) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS storage_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contract_id uuid NOT NULL REFERENCES storage_contracts(id) ON DELETE RESTRICT,
    event_type text NOT NULL CHECK (event_type IN
      ('created','updated','photo_added','photo_removed','accepted','return_requested','returned','cancelled','payment_recorded')),
    actor_id uuid,
    happened_at timestamptz NOT NULL DEFAULT now(),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS storage_events_contract_time ON storage_events(contract_id, happened_at);

-- Applications must enforce roles, photo completeness and transitions transactionally.
-- Photo object bytes live ONLY in a private object store; PostgreSQL holds metadata.
-- Do not issue public SELECT or write grants to anonymous/application-guest roles.
COMMIT;
