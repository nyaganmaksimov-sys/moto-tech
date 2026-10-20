BEGIN;
CREATE TABLE IF NOT EXISTS repair_work_items(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 repair_id uuid NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
 description text NOT NULL CHECK(length(trim(description))>0),
 quantity numeric(12,3) NOT NULL CHECK(quantity>0),
 unit_price_rub numeric(12,2) NOT NULL CHECK(unit_price_rub>=0),
 created_by uuid REFERENCES service_employees(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS repair_work_items_order_idx ON repair_work_items(repair_id);
COMMIT;
