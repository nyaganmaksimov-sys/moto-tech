BEGIN;
ALTER TABLE inventory_requests
  ADD COLUMN IF NOT EXISTS manager_comment text;
ALTER TABLE inventory_requests
  DROP CONSTRAINT IF EXISTS inventory_requests_status_check;
ALTER TABLE inventory_requests
  ADD CONSTRAINT inventory_requests_status_check
  CHECK(status IN ('requested','approved','ordered','in_transit','received','issued','rejected','cancelled'));
CREATE INDEX IF NOT EXISTS inventory_requests_created_by_idx ON inventory_requests(created_by,created_at DESC);
COMMIT;
