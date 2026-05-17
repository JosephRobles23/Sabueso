-- 006_rls.sql
-- Row-Level Security.
--
-- Política:
--   investigations  → cualquiera lee las públicas; el dueño accede a todas las suyas
--   subscriptions   → solo el dueño (lectura/escritura)
--
-- Las APIs y workers que corren con service_role bypassan RLS por diseño
-- (Supabase aplica `BYPASSRLS` al rol `service_role`).
-- El resto del schema (entities, claims, edges, sources, investigation_events,
-- tool_cache) no habilita RLS: queda como espacio de lectura compartida vía API.

-- ---------------------------------------------------------------------------
-- investigations
-- ---------------------------------------------------------------------------
ALTER TABLE investigations ENABLE ROW LEVEL SECURITY;

-- Lectura pública: cualquier rol autenticado o anon ve investigaciones públicas
CREATE POLICY investigations_public_read ON investigations
    FOR SELECT
    USING (is_public = TRUE);

-- Acceso total para el dueño (incluye lectura de las privadas)
CREATE POLICY investigations_owner_all ON investigations
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- ---------------------------------------------------------------------------
-- subscriptions
-- ---------------------------------------------------------------------------
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY subscriptions_owner ON subscriptions
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());
