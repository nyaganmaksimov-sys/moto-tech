BEGIN;
ALTER TABLE service_employees ADD COLUMN IF NOT EXISTS position text NOT NULL DEFAULT 'Сотрудник';
UPDATE service_employees SET position='Руководитель' WHERE role='owner_manager' AND position='Сотрудник';
COMMIT;
