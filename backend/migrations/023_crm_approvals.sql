ALTER TABLE crm_tasks DROP CONSTRAINT IF EXISTS crm_tasks_status_check;
ALTER TABLE crm_tasks ADD CONSTRAINT crm_tasks_status_check CHECK (status IN ('open','in_progress','review','done','cancelled'));
CREATE TABLE IF NOT EXISTS crm_task_reviews (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), task_id uuid NOT NULL REFERENCES crm_tasks(id) ON DELETE CASCADE, actor_id uuid NOT NULL REFERENCES service_employees(id), decision text NOT NULL, comment text, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS crm_task_reviews_task_idx ON crm_task_reviews(task_id,created_at);
