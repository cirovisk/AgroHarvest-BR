-- WARNING: Replace 'SUA_SENHA_SEGURA_AQUI' with a real strong password before running this script.
CREATE ROLE api_reader WITH LOGIN PASSWORD 'SUA_SENHA_SEGURA_AQUI';
GRANT CONNECT ON DATABASE cultivares_db TO api_reader;
GRANT USAGE ON SCHEMA public TO api_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO api_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO api_reader;
