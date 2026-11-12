-- Engine 03 - Medical Knowledge Store (SQLite)
-- Stage 2: schema design. Keys, foreign keys and indexes are chosen for
-- indexed lookups by disease_id and by symptom_name.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS DISEASE (
    disease_id   INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    description  TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS SYMPTOM (
    symptom_id    INTEGER PRIMARY KEY,
    symptom_name  TEXT    NOT NULL UNIQUE,              -- canonical, normalised (e.g. high_fever)
    display_name  TEXT    NOT NULL,                     -- for the UI (e.g. High fever)
    weight        INTEGER CHECK (weight IS NULL OR weight BETWEEN 1 AND 7)
);

-- Many-to-many link: a disease has many symptoms, a symptom appears in many diseases.
CREATE TABLE IF NOT EXISTS DISEASE_SYMPTOM (
    disease_id  INTEGER NOT NULL REFERENCES DISEASE(disease_id)  ON DELETE CASCADE,
    symptom_id  INTEGER NOT NULL REFERENCES SYMPTOM(symptom_id)  ON DELETE CASCADE,
    PRIMARY KEY (disease_id, symptom_id)
);
-- The primary key already indexes (disease_id, symptom_id); this covers lookups by symptom.
CREATE INDEX IF NOT EXISTS idx_disease_symptom_symptom ON DISEASE_SYMPTOM(symptom_id);

-- One guidance row per disease: up to four precautions plus general diet guidance.
CREATE TABLE IF NOT EXISTS GUIDANCE (
    disease_id     INTEGER PRIMARY KEY REFERENCES DISEASE(disease_id) ON DELETE CASCADE,
    precaution_1   TEXT,
    precaution_2   TEXT,
    precaution_3   TEXT,
    precaution_4   TEXT,
    diet_guidance  TEXT
);
