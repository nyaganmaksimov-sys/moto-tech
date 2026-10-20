BEGIN;
ALTER TABLE repair_orders ADD COLUMN IF NOT EXISTS mechanic_id uuid REFERENCES service_employees(id);
CREATE INDEX IF NOT EXISTS repair_orders_mechanic_idx ON repair_orders(mechanic_id);
COMMIT;
