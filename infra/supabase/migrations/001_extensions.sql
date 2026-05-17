-- 001_extensions.sql
-- Habilita las extensiones requeridas por el modelo de datos.
--   uuid-ossp : uuid_generate_v4() para PKs UUID
--   pg_trgm   : búsqueda por similitud (trigram) y operadores gin_trgm_ops
--   vector    : columnas pgvector + índices ivfflat (embeddings 1536-d)
--   pgmq      : cola de mensajes interna (futuro: dispatch async)
--   pg_cron   : scheduler para cleanup periódico de tool_cache
--
-- Supabase mantiene el esquema `extensions` en el search_path por defecto,
-- pero todas se invocan sin schema-qualifier desde el resto de las migraciones.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgmq;
CREATE EXTENSION IF NOT EXISTS pg_cron;
