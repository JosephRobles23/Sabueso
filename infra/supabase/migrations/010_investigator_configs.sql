-- 010_investigator_configs.sql
-- Personalización por usuario de los 7 investigadores configurables (S-14).
--
-- Modelo:
--   (user_id, callsign) → JSONB libre con `active`, `model`, `skills`,
--   `rules`, `pre_approved_tools`, `display_name`, etc. El shape se valida
--   en el cliente con Zod; en DB solo garantizamos la PK y el dominio del
--   callsign.
--
-- Semillas automáticas:
--   Al INSERT en auth.users disparamos `seed_investigator_configs_for_user`
--   y poblamos las 7 configs activas por default (la-jueza queda excluida
--   porque es verificadora MoA, no investigadora editable). El frontend
--   permite togglear `active=false` para excluir al investigador del plan.
--
-- RLS:
--   Solo el dueño puede leer/escribir sus configs. El rol `service_role`
--   bypassa RLS por diseño (Supabase) para que el worker pueda consultar
--   configs al armar el plan.

-- ---------------------------------------------------------------------------
-- investigator_configs
-- ---------------------------------------------------------------------------
CREATE TABLE investigator_configs (
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    callsign    TEXT NOT NULL CHECK (callsign IN (
                   'sabueso','el-buscador','la-tasadora','el-contador',
                   'el-letrado','el-detective','el-periodista','la-jueza'
                )),
    config      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, callsign)
);

CREATE INDEX idx_investigator_configs_user ON investigator_configs (user_id);

-- ---------------------------------------------------------------------------
-- updated_at trigger (set_updated_at vive en 005_triggers.sql)
-- ---------------------------------------------------------------------------
CREATE TRIGGER trg_investigator_configs_set_updated_at
    BEFORE UPDATE ON investigator_configs
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
ALTER TABLE investigator_configs ENABLE ROW LEVEL SECURITY;

CREATE POLICY investigator_configs_owner ON investigator_configs
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- ---------------------------------------------------------------------------
-- Seed automático al crear el usuario.
-- SECURITY DEFINER porque el trigger corre con privilegios de la cuenta que
-- inserta en auth.users (signup vía GoTrue) y necesitamos INSERT a nuestra
-- tabla; el search_path se fija explícitamente a public para mitigar la
-- clase de ataques que explota un search_path arbitrario al elevar.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION seed_investigator_configs_for_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    INSERT INTO public.investigator_configs (user_id, callsign, config)
    VALUES
        (NEW.id, 'sabueso',       jsonb_build_object('active', true)),
        (NEW.id, 'el-buscador',   jsonb_build_object('active', true)),
        (NEW.id, 'la-tasadora',   jsonb_build_object('active', true)),
        (NEW.id, 'el-contador',   jsonb_build_object('active', true)),
        (NEW.id, 'el-letrado',    jsonb_build_object('active', true)),
        (NEW.id, 'el-detective',  jsonb_build_object('active', true)),
        (NEW.id, 'el-periodista', jsonb_build_object('active', true))
    ON CONFLICT (user_id, callsign) DO NOTHING;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_seed_investigator_configs
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION seed_investigator_configs_for_user();
