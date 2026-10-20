BEGIN;
CREATE TABLE IF NOT EXISTS service_appointments(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 client_id uuid NOT NULL REFERENCES service_clients(id),
 vehicle_id uuid REFERENCES service_vehicles(id),
 scheduled_at timestamptz NOT NULL,
 service_description text NOT NULL,
 status text NOT NULL DEFAULT 'scheduled' CHECK(status IN ('scheduled','arrived','completed','cancelled')),
 notes text,
 created_by uuid REFERENCES service_employees(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS service_appointments_schedule_idx ON service_appointments(scheduled_at);
CREATE TABLE IF NOT EXISTS service_warranties(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 repair_id uuid NOT NULL REFERENCES repair_orders(id),
 complaint text NOT NULL,
 resolution text,
 status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','review','resolved','rejected')),
 created_by uuid REFERENCES service_employees(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
