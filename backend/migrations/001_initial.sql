-- MOTO TECH Service: PostgreSQL foundation, version 0.3
-- All timestamps UTC. No personal data should be committed to Git.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS employees (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 name text NOT NULL,
 role text NOT NULL CHECK(role IN ('owner','admin','reception','mechanic','warehouse')),
 login text UNIQUE NOT NULL,
 password_hash text NOT NULL,
 active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS customers (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 full_name text NOT NULL,
 phone text,
 notes text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS makes (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name text NOT NULL UNIQUE,
 vehicle_type text NOT NULL
);
CREATE TABLE IF NOT EXISTS models (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 make_id bigint NOT NULL REFERENCES makes(id),
 name text NOT NULL,
 UNIQUE(make_id,name)
);
CREATE TABLE IF NOT EXISTS vehicles (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 customer_id uuid NOT NULL REFERENCES customers(id),
 vehicle_type text NOT NULL CHECK(vehicle_type IN ('motorcycle','atv','scooter','ebike','other')),
 make text NOT NULL,
 model text NOT NULL,
 model_year integer CHECK(model_year BETWEEN 1900 AND 2200),
 vin text,
 frame_number text,
 mileage numeric(12,1) CHECK(mileage>=0),
 mileage_unit text DEFAULT 'km',
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vehicles_customer ON vehicles(customer_id);
CREATE INDEX IF NOT EXISTS idx_vehicles_vin ON vehicles(vin) WHERE vin IS NOT NULL;
CREATE TABLE IF NOT EXISTS price_items (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 code text UNIQUE,
 vehicle_type text NOT NULL,
 category text NOT NULL,
 name text NOT NULL,
 description text,
 base_price_kopecks bigint NOT NULL CHECK(base_price_kopecks>=0),
 price_from boolean NOT NULL DEFAULT false,
 manual_quote boolean NOT NULL DEFAULT false,
 active boolean NOT NULL DEFAULT true,
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS orders (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 order_number bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 customer_id uuid NOT NULL REFERENCES customers(id),
 vehicle_id uuid NOT NULL REFERENCES vehicles(id),
 created_by uuid REFERENCES employees(id),
 assigned_to uuid REFERENCES employees(id),
 complaint text,
 intake_notes text,
 status text NOT NULL DEFAULT 'accepted' CHECK(status IN ('draft','accepted','diagnosis','awaiting_approval','in_progress','waiting_parts','ready','delivered','closed','cancelled')),
 complexity numeric(6,2) NOT NULL DEFAULT 1 CHECK(complexity>0),
 discount_pct numeric(5,2) NOT NULL DEFAULT 0 CHECK(discount_pct BETWEEN 0 AND 100),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS order_photos (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 order_id uuid NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
 storage_key text NOT NULL UNIQUE,
 sha256 text NOT NULL,
 stage text NOT NULL CHECK(stage IN ('intake','damage','repair','after')),
 mime_type text NOT NULL CHECK(mime_type IN ('image/jpeg','image/png','image/webp')),
 uploaded_by uuid REFERENCES employees(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_order_photos_order ON order_photos(order_id);
CREATE TABLE IF NOT EXISTS order_lines (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 order_id uuid NOT NULL REFERENCES orders(id),
 price_item_id uuid REFERENCES price_items(id),
 kind text NOT NULL CHECK(kind IN ('work','part','material')),
 name text NOT NULL,
 quantity numeric(12,3) NOT NULL CHECK(quantity>0),
 price_kopecks bigint NOT NULL CHECK(price_kopecks>=0),
 cost_kopecks bigint NOT NULL DEFAULT 0 CHECK(cost_kopecks>=0),
 approval_status text NOT NULL DEFAULT 'pending' CHECK(approval_status IN ('pending','approved','rejected')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS payments (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 order_id uuid NOT NULL REFERENCES orders(id),
 amount_kopecks bigint NOT NULL CHECK(amount_kopecks>0),
 method text NOT NULL CHECK(method IN ('cash','card','transfer','invoice')),
 recorded_by uuid REFERENCES employees(id),
 external_receipt_id text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS stock_items (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 sku text UNIQUE,
 name text NOT NULL,
 unit text NOT NULL DEFAULT 'шт',
 purchase_kopecks bigint NOT NULL DEFAULT 0,
 sale_kopecks bigint NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS stock_movements (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 stock_item_id uuid NOT NULL REFERENCES stock_items(id),
 order_id uuid REFERENCES orders(id),
 quantity_delta numeric(12,3) NOT NULL CHECK(quantity_delta<>0),
 reason text NOT NULL,
 created_by uuid REFERENCES employees(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit_log (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 actor_id uuid REFERENCES employees(id),
 order_id uuid REFERENCES orders(id),
 event text NOT NULL,
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_order ON audit_log(order_id,created_at DESC);
-- API must create order + at least one intake photo in a single transaction,
-- then commit. A DB trigger will be added after server upload workflow is in place.
