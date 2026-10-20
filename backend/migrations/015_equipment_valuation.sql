ALTER TABLE equipment_assets ADD COLUMN IF NOT EXISTS estimated_value_rub numeric(12,2) CHECK(estimated_value_rub >= 0);
ALTER TABLE equipment_assets ADD COLUMN IF NOT EXISTS valuation_date date;
