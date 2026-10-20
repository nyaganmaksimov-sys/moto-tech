BEGIN;
CREATE TABLE IF NOT EXISTS inventory_suppliers(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 name text NOT NULL CHECK(length(trim(name))>0),
 contact_person text,
 phone text,
 email text,
 notes text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS inventory_requests(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 part_name text NOT NULL CHECK(length(trim(part_name))>0),
 sku text,
 quantity numeric(12,3) NOT NULL CHECK(quantity>0),
 supplier_id uuid REFERENCES inventory_suppliers(id),
 repair_id uuid REFERENCES repair_orders(id),
 status text NOT NULL DEFAULT 'requested'
   CHECK(status IN ('requested','ordered','received','cancelled')),
 notes text,
 created_by uuid REFERENCES service_employees(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS inventory_requests_status_idx ON inventory_requests(status,created_at DESC);
COMMIT;
