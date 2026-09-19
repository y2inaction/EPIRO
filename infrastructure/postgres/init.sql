-- Runs once, on first initialisation of the data directory.
--
-- Keep this minimal: the schema itself is owned by Alembic. Only cluster-level
-- setup that a migration cannot perform belongs here.

-- PostGIS backs the Location.geom column.
CREATE EXTENSION IF NOT EXISTS postgis;

-- Quoting is required: uuid-ossp is not a valid bare identifier.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pg_trgm backs the gin_trgm_ops indexes behind name and directory lookups.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Permissions
GRANT ALL PRIVILEGES ON SCHEMA public TO epiro;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO epiro;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO epiro;

-- Log slow statements to aid development profiling.
ALTER DATABASE epiro SET log_min_duration_statement = 1000;

-- Note: encoding, lc_collate and lc_ctype are fixed when the database is
-- created and cannot be changed with ALTER DATABASE. They are set through the
-- POSTGRES_INITDB_ARGS / initdb options instead.
