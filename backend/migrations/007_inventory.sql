BEGIN;
CREATE TABLE IF NOT EXISTS inventory_parts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 sku text NOT NULL UNIQUE,
 name text NOT NULL CHECK(length(trim(name))>0),
 unit text NOT NULL DEFAULT 'шт',
 quantity numeric(12,3) NOT NULL DEFAULT 0 CHECK(quantity>=0),
 purchase_price numeric(12,2) NOT NULL DEFAULT 0 CHECK(purchase_price>=0),
 sale_price numeric(12,2) NOT NULL DEFAULT 0 CHECK(sale_price>=0),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS inventory_movements (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 part_id uuid NOT NULL REFERENCES inventory_parts(id),
 employee_id uuid REFERENCES service_employees(id),
 repair_id uuid REFERENCES repair_orders(id),
 delta numeric(12,3) NOT NULL CHECK(delta<>0),
 reason text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS inventory_movements_part_idx ON inventory_movements(part_id,created_at DESC);
COMMIT;
