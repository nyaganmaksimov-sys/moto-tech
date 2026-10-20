BEGIN;
CREATE TABLE IF NOT EXISTS staff_pin_devices (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 employee_id uuid NOT NULL REFERENCES service_employees(id) ON DELETE CASCADE,
 device_hash text NOT NULL UNIQUE,
 pin_hash text NOT NULL,
 label text NOT NULL DEFAULT 'Браузер',
 failures int NOT NULL DEFAULT 0,
 locked_until timestamptz,
 expires_at timestamptz NOT NULL DEFAULT (now()+interval '90 days'),
 revoked_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 last_used_at timestamptz
);
CREATE INDEX IF NOT EXISTS staff_pin_devices_employee_idx ON staff_pin_devices(employee_id);
COMMIT;
