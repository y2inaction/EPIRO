-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgvector;
CREATE EXTENSION IF NOT EXISTS uuid-ossp;

-- Set up encoding and locale
ALTER DATABASE epiro SET encoding = 'UTF8';
ALTER DATABASE epiro SET lc_collate = 'C';
ALTER DATABASE epiro SET lc_ctype = 'C';

-- Create schema
CREATE SCHEMA IF NOT EXISTS public;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA public TO epiro;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO epiro;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO epiro;

-- Log queries over 1 second in development
ALTER DATABASE epiro SET log_min_duration_statement = 1000;
