BEGIN;
CREATE TABLE IF NOT EXISTS integration_1c_settings(
 id integer PRIMARY KEY CHECK(id=1),
 configuration text NOT NULL DEFAULT 'not_selected',
 mode text NOT NULL DEFAULT 'disabled' CHECK(mode IN ('disabled','http_json')),
 endpoint_url text,
 updated_by uuid REFERENCES service_employees(id),
 updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO integration_1c_settings(id) VALUES(1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS integration_1c_mappings(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 local_type text NOT NULL,
 local_id uuid NOT NULL,
 external_guid text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(local_type,local_id),
 UNIQUE(local_type,external_guid)
);
CREATE TABLE IF NOT EXISTS integration_1c_events(
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 direction text NOT NULL CHECK(direction IN ('export','import','test')),
 entity_type text NOT NULL,
 entity_id uuid,
 state text NOT NULL CHECK(state IN ('pending','success','failed')),
 details text,
 created_by uuid REFERENCES service_employees(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
