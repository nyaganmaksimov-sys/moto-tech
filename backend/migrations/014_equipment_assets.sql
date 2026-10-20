BEGIN;
CREATE TABLE IF NOT EXISTS equipment_assets (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 inventory_number text NOT NULL UNIQUE,
 name text NOT NULL,
 category text NOT NULL DEFAULT 'Оборудование',
 serial_number text,
 manufacturer text,
 model text,
 location text,
 custodian_id uuid REFERENCES service_employees(id),
 condition text NOT NULL DEFAULT 'working' CHECK(condition IN ('working','maintenance','broken','retired')),
 purchase_date date,
 purchase_cost_rub numeric(12,2) CHECK(purchase_cost_rub>=0),
 notes text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS equipment_audits (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 asset_id uuid NOT NULL REFERENCES equipment_assets(id),
 checked_by uuid REFERENCES service_employees(id),
 result text NOT NULL CHECK(result IN ('present','missing','damaged')),
 comment text,
 checked_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS equipment_audits_asset_idx ON equipment_audits(asset_id,checked_at DESC);
COMMIT;
