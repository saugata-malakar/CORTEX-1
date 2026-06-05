-- Cortex — scripts/init_db.sql
-- Runs once on first Postgres container start.
-- Creates extensions and sets performance parameters.
-- Tables are created by SQLAlchemy / Alembic — not here.

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"; -- query performance stats
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- trigram similarity for full-text search

-- ── Performance settings (session-level defaults) ────────────────────────────
ALTER SYSTEM SET shared_buffers            = '256MB';
ALTER SYSTEM SET effective_cache_size      = '768MB';
ALTER SYSTEM SET maintenance_work_mem      = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = '0.9';
ALTER SYSTEM SET wal_buffers              = '16MB';
ALTER SYSTEM SET default_statistics_target = '100';
ALTER SYSTEM SET random_page_cost         = '1.1';  -- SSD
ALTER SYSTEM SET effective_io_concurrency = '200';  -- SSD

-- ── Application role (least-privilege for app connection) ────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cortex_app') THEN
    CREATE ROLE cortex_app LOGIN PASSWORD 'cortexpass';
  END IF;
END $$;

GRANT CONNECT ON DATABASE cortex_db TO cortex_app;
GRANT USAGE ON SCHEMA public TO cortex_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cortex_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO cortex_app;

-- ── Read-only analytics role ──────────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cortex_readonly') THEN
    CREATE ROLE cortex_readonly LOGIN PASSWORD 'readonlypass';
  END IF;
END $$;

GRANT CONNECT ON DATABASE cortex_db TO cortex_readonly;
GRANT USAGE ON SCHEMA public TO cortex_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO cortex_readonly;

-- ── Partition hint (future-proofing) ─────────────────────────────────────────
-- When audit_logs exceeds 50M rows, partition by created_at RANGE monthly.
-- Placeholder comment for the DBA — not implemented until needed.
-- Example:
--   ALTER TABLE audit_logs RENAME TO audit_logs_old;
--   CREATE TABLE audit_logs (LIKE audit_logs_old INCLUDING ALL)
--     PARTITION BY RANGE (created_at);
--   CREATE TABLE audit_logs_2025_01 PARTITION OF audit_logs
--     FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

COMMENT ON DATABASE cortex_db IS 'Cortex Structural Intelligence Platform v1.4';
