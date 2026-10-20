BEGIN;
CREATE TABLE IF NOT EXISTS service_clients (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 full_name text NOT NULL CHECK(length(trim(full_name))>0),
 phone text,
 email text,
 notes text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS service_vehicles (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 client_id uuid NOT NULL REFERENCES service_clients(id) ON DELETE RESTRICT,
 vehicle_type text NOT NULL DEFAULT 'Мотоцикл',
 brand text NOT NULL,
 model text NOT NULL,
 year integer CHECK(year BETWEEN 1900 AND 2200),
 vin text,
 plate text,
 notes text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS service_vehicles_client_idx ON service_vehicles(client_id);
CREATE UNIQUE INDEX IF NOT EXISTS service_vehicles_vin_unique ON service_vehicles(upper(trim(vin))) WHERE vin IS NOT NULL AND trim(vin)<>'';
COMMIT;
