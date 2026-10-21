ALTER TABLE crm_tasks ADD COLUMN IF NOT EXISTS repair_id uuid REFERENCES repair_orders(id);
ALTER TABLE crm_tasks ADD COLUMN IF NOT EXISTS storage_id uuid REFERENCES storage_contracts(id);
CREATE TABLE IF NOT EXISTS crm_task_comments (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), task_id uuid NOT NULL REFERENCES crm_tasks(id) ON DELETE CASCADE, author_id uuid NOT NULL REFERENCES service_employees(id), body text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS crm_task_comments_task_idx ON crm_task_comments(task_id,created_at);
