BEGIN;
CREATE TABLE IF NOT EXISTS service_price_items(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 category text NOT NULL DEFAULT 'Работы',
 name text NOT NULL CHECK(length(trim(name))>0),
 price_rub numeric(12,2) NOT NULL CHECK(price_rub>=0),
 active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS service_finance_entries(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 entry_type text NOT NULL CHECK(entry_type IN ('income','expense')),
 amount_rub numeric(12,2) NOT NULL CHECK(amount_rub>0),
 category text NOT NULL,
 description text NOT NULL DEFAULT '',
 repair_id uuid REFERENCES repair_orders(id),
 recorded_by uuid REFERENCES service_employees(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS service_finance_entries_date_idx ON service_finance_entries(created_at DESC);
COMMIT;
