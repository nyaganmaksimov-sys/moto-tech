BEGIN;
CREATE SEQUENCE IF NOT EXISTS repair_order_number_seq START 1001;
CREATE TABLE IF NOT EXISTS repair_orders (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 order_number text NOT NULL UNIQUE,
 client_name text NOT NULL CHECK (length(btrim(client_name))>0),
 phone text,
 vehicle_type text NOT NULL DEFAULT 'Мотоцикл',
 brand text NOT NULL,
 model text NOT NULL,
 vin text,
 mileage_km numeric(12,1),
 mechanic_name text,
 complaint text NOT NULL DEFAULT '',
 intake_condition text NOT NULL DEFAULT '',
 status text NOT NULL DEFAULT 'accepted' CHECK(status IN ('accepted','diagnostics','repair','ready','issued','cancelled')),
 total_rub numeric(12,2) NOT NULL DEFAULT 0 CHECK (total_rub>=0),
 created_by uuid REFERENCES service_employees(id),
 updated_by uuid REFERENCES service_employees(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 version integer NOT NULL DEFAULT 1 CHECK(version>0)
);
CREATE INDEX IF NOT EXISTS repair_orders_updated_at ON repair_orders(updated_at DESC);
CREATE TABLE IF NOT EXISTS repair_order_events(
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 order_id uuid NOT NULL REFERENCES repair_orders(id) ON DELETE RESTRICT,
 actor_id uuid REFERENCES service_employees(id),
 event_type text NOT NULL,
 payload jsonb NOT NULL DEFAULT '{}'::jsonb,
 happened_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
