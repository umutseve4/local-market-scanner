-- PostgreSQL schema for local-market-scanner.
--
-- SQLite is the default runtime store (see src/lms/storage.py). This file is
-- the reference schema for when the dataset outgrows SQLite or needs to be
-- shared. Apply with:  psql "$DATABASE_URL" -f sql/schema.sql

CREATE TABLE IF NOT EXISTS businesses (
    source                 TEXT        NOT NULL,
    source_id              TEXT        NOT NULL,
    name                   TEXT        NOT NULL,
    category               TEXT        NOT NULL,
    district               TEXT,
    address                TEXT,
    phone                  TEXT,
    email                  TEXT,
    website                TEXT,
    social_url             TEXT,
    opening_hours          TEXT,
    lat                    DOUBLE PRECISION,
    lon                    DOUBLE PRECISION,
    has_website            BOOLEAN     NOT NULL DEFAULT FALSE,
    has_social             BOOLEAN     NOT NULL DEFAULT FALSE,
    digital_maturity_score SMALLINT    NOT NULL,
    lead_priority          TEXT        NOT NULL,
    scanned_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT businesses_pkey PRIMARY KEY (source, source_id),
    CONSTRAINT businesses_score_range CHECK (digital_maturity_score BETWEEN 0 AND 100),
    CONSTRAINT businesses_priority_values CHECK (lead_priority IN ('high', 'medium', 'low')),
    CONSTRAINT businesses_lat_range CHECK (lat IS NULL OR lat BETWEEN -90 AND 90),
    CONSTRAINT businesses_lon_range CHECK (lon IS NULL OR lon BETWEEN -180 AND 180)
);

CREATE INDEX IF NOT EXISTS idx_businesses_priority
    ON businesses (lead_priority, digital_maturity_score);

CREATE INDEX IF NOT EXISTS idx_businesses_category
    ON businesses (category);

CREATE INDEX IF NOT EXISTS idx_businesses_no_website
    ON businesses (digital_maturity_score)
    WHERE has_website = FALSE;

COMMENT ON TABLE businesses IS
    'Public health-sector facilities scanned from OpenStreetMap (ODbL).';
COMMENT ON COLUMN businesses.digital_maturity_score IS
    '0-100; lower means weaker digital presence, i.e. a stronger lead.';

-- Run-level scan history (PostgreSQL mirror of src/lms/history.py's SQLite
-- tables, used by `lms scan --track` and `lms runs`).

CREATE TABLE IF NOT EXISTS scan_runs (
    run_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    source          TEXT        NOT NULL,
    bbox            TEXT,
    total_count     INTEGER     NOT NULL DEFAULT 0,
    new_count       INTEGER     NOT NULL DEFAULT 0,
    changed_count   INTEGER     NOT NULL DEFAULT 0,
    unchanged_count INTEGER     NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS business_history (
    run_id      BIGINT NOT NULL REFERENCES scan_runs (run_id),
    source      TEXT   NOT NULL,
    source_id   TEXT   NOT NULL,
    change_type TEXT   NOT NULL
        CHECK (change_type IN ('new', 'changed', 'unchanged')),
    snapshot    JSONB  NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT business_history_pkey PRIMARY KEY (run_id, source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_history_business
    ON business_history (source, source_id, run_id);

COMMENT ON TABLE scan_runs IS
    'One row per tracked scan; counters summarise the diff against the previous run.';
COMMENT ON TABLE business_history IS
    'Per-business snapshot for each tracked run; snapshot holds the full record as JSONB.';

-- Example: top outreach candidates.
--   SELECT name, category, phone, district, digital_maturity_score
--   FROM businesses
--   WHERE lead_priority = 'high' AND (phone IS NOT NULL OR email IS NOT NULL)
--   ORDER BY digital_maturity_score, name
--   LIMIT 50;
