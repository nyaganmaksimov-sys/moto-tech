ALTER TABLE repair_orders ADD COLUMN IF NOT EXISTS damage_description text NOT NULL DEFAULT '';
ALTER TABLE repair_orders ADD COLUMN IF NOT EXISTS accessories_received text NOT NULL DEFAULT '';
ALTER TABLE repair_orders ADD COLUMN IF NOT EXISTS fuel_level text NOT NULL DEFAULT '';
ALTER TABLE repair_orders ADD COLUMN IF NOT EXISTS inspection_updated_at timestamptz;
