# Sabueso · Linear Tasks (condensado a 20)

**Basado en:** `sabueso-architecture-c4.md` v1.0 + `sabueso-uiux-spec.md` v1  
**Origen:** consolidación de 134 tasks granulares en 20 unidades ejecutables  
**Filosofía:** cada task es un sprint de 1 worktree (~6–12h con coding agent). Pensados para que un solo developer con Emdash + 5 worktrees pueda paralelizarlos.

---

## 0. Setup en Linear

### 0.1 Workspace

```yaml
team:        { name: "Sabueso", identifier: "SAB" }
project:     { name: "Sabueso v1 · hack@latam 2026" }
cycle:       { name: "Hackathon Sprint", start: "2026-05-15", end: "2026-05-17" }
```

### 0.2 Labels (mínimas)

| Label | Color | Uso |
|---|---|---|
| `p0` | `#DC2626` | Sin esto no hay demo |
| `p1` | `#F59E0B` | Importante pero diferible |
| `p2` | `#71717A` | Post-hackathon OK |
| `wt-infra` | `#64748B` | Worktree GCP, CI/CD, Cloud Run |
| `wt-data` | `#22C55E` | Worktree pipeline, scrapers, tools |
| `wt-agents` | `#FB923C` | Worktree orchestrator, subagents |
| `wt-api` | `#3B82F6` | Worktree FastAPI service |
| `wt-frontend` | `#F472B6` | Worktree Next.js, UI |
| `wt-demo` | `#EAB308` | Worktree demo prep, pitch |

### 0.3 Estimaciones

Escala 1pt ≈ 30–45 min de un coding agent eficiente. 8pts ≈ medio día de trabajo de un worktree.

### 0.4 Cómo crear esto vía Linear MCP

```
Para cada task del archivo:
  linear-create-issue({
    team: "SAB",
    project: "Sabueso v1",
    title: <task.title>,
    description: <task.description + acceptance>,
    priority: <task.priority>,
    estimate: <task.estimate>,
    labels: <task.labels>
  })
  
Después: linear-create-issue-relation para dependencies (type=blocks)
```

---

## 1. Resumen de los 20 tasks

| # | Task | Worktree | Estimate | Priority | Bloquea a |
|---|---|---|---|---|---|
| S-01 | Foundation setup (GCP + Supabase + Vercel + Emdash + monorepo) | infra | 6pts | p0 | S-02, S-03, S-09 |
| S-02 | Database schema completo (migrations + RLS + triggers) | data | 8pts | p0 | S-03, S-05, S-06 |
| S-03 | API service: FastAPI deployable con auth + search | api | 10pts | p0 | S-07, S-08, S-10 |
| S-04 | Tool registry + 8 herramientas Perú con cache | data | 12pts | p0 | S-05, S-06 |
| S-05 | Investigator framework + LLM client + prompts | agents | 9pts | p0 | S-06, S-10 |
| S-06 | LangGraph orchestrator completo (estado + nodos + checkpointer) | agents | 12pts | p0 | S-07, S-10 |
| S-07 | Worker Cloud Run Job + dispatch desde API | infra+api | 7pts | p0 | S-10 |
| S-08 | Events + SSE end-to-end con LISTEN/NOTIFY + reconnect | api | 8pts | p0 | S-10 |
| S-09 | Frontend skeleton (Next 16 + i18n + Supabase + AI Elements) | frontend | 8pts | p0 | S-10, S-12 |
| S-10 | Primer end-to-end (El Contador + happy path en vivo) | cross | 5pts | p0 | S-11, S-12 |
| S-11 | 6 investigadores restantes + La Jueza (MoA) | agents | 10pts | p0 | S-17 |
| S-12 | Cinema Mode UI completo (3 paneles + floor + drilldown + grafo) | frontend | 12pts | p0 | S-13, S-17 |
| S-13 | Modos de visualización (Sankey + Timeline + scrubber) | frontend | 6pts | p1 | — |
| S-14 | La Redacción + Hemeroteca + Comparador | frontend | 6pts | p1 | — |
| S-15 | Pipeline CocoIndex (legalize-pe + SEACE + JNE PDFs) | data | 8pts | p1 | S-17 |
| S-16 | PDF Export (Playwright + GCS + signed URLs + UI) | infra+frontend | 6pts | p1 | — |
| S-17 | Demo replay mode + localStorage + Director + live toggle | frontend+demo | 6pts | p0 | S-20 |
| S-18 | Multi-país preview (Chile + México + Salvador) | cross | 5pts | p1 | — |
| S-19 | Share + SEO + Subscriptions Zavu | frontend+api | 8pts | p1 | — |
| S-20 | Observabilidad + security + CI/CD + pitch + demo prep | cross | 10pts | p0 | — |

**Total:** ~160pts. Con paralelización de 5 worktrees y un coding agent eficiente por worktree, esto es ejecutable en 4 días.

---

## 2. Las 20 tasks completas

### S-01 · Foundation setup

**Title:** `[Setup] GCP + Supabase + Vercel + OpenRouter + monorepo + Emdash`  
**Priority:** P0 · **Estimate:** 6pts · **Labels:** `p0`, `wt-infra`  
**Dependencies:** none  
**Bloquea:** S-02, S-03, S-09

**Description:**

Crear y configurar todas las cuentas, proyectos y accesos externos antes del kickoff. Sin esto, el día 1 se quema en setup en vez de en código. También incluye levantar el monorepo y conectar Emdash con sus 5 worktrees.

**Scope incluido:**
- GCP project `sabueso-hack-2026` con free trial, APIs habilitadas, service account, Artifact Registry, GCS buckets (`sabueso-jne-pdfs`, `sabueso-dossiers`).
- Supabase project con extensiones habilitadas (`pgvector`, `pgmq`, `pg_cron`, `pg_trgm`, `uuid-ossp`).
- Vercel project linkeado a GitHub, KV + Blob activados, env vars placeholder.
- OpenRouter cuenta con $20 crédito perk, cap de gasto $40.
- LangSmith cuenta free tier, project `sabueso-hack`.
- Monorepo `sabueso/` con pnpm workspaces + Turborepo. Estructura: `apps/{web,api,worker,pipeline,pdf}/`, `packages/{shared-types,ui,agents-prompts}/`, `docs/`, `infra/`, `.github/workflows/`.
- Copiar `sabueso-architecture-c4.md` y `sabueso-uiux-spec.md` a `docs/`.
- Emdash desktop instalado, 5 worktrees creados (`wt-infra`, `wt-data`, `wt-agents`, `wt-api`, `wt-frontend`), `.emdash.json` con lifecycle scripts, conexión a Linear.

**Acceptance Criteria:**
- [ ] `gcloud projects describe sabueso-hack-2026` retorna OK
- [ ] Supabase Studio accesible, extensiones visibles en `pg_extension`
- [ ] `sabueso.vercel.app` retorna 200 (página default Next)
- [ ] OpenRouter API key probada con `curl` retorna respuesta válida
- [ ] LangSmith dashboard accesible
- [ ] `pnpm install && pnpm build` en monorepo pasa sin error
- [ ] 5 worktrees visibles en Emdash con sus agentes asignados
- [ ] Linear project + cycle + labels creados según sección 0
- [ ] Repo en GitHub con `main` protegido, README placeholder

**Files:**
- `pnpm-workspace.yaml`, `turbo.json`, `package.json`
- `apps/{web,api,worker,pipeline,pdf}/` con `package.json` o `pyproject.toml`
- `packages/shared-types/`, `packages/ui/`, `packages/agents-prompts/`
- `docs/architecture.md`, `docs/uiux-spec.md`
- `.emdash.json`, `.gitignore`, `.editorconfig`, `.prettierrc`
- `LICENSE` (MIT)

**Technical notes:**
- Service account `sabueso-cloudrun-sa` con permisos: Secret Accessor, Storage Admin, Cloud Run Admin.
- Vercel KV REST API URL y token guardar en password manager.
- Anotar `PROJECT_ID`, `SUPABASE_DB_URL`, todos los API keys en `.env.example`.

---

### S-02 · Database schema completo

**Title:** `[Data] Migrations Supabase: tables + indexes + RLS + triggers + seed`  
**Priority:** P0 · **Estimate:** 8pts · **Labels:** `p0`, `wt-data`  
**Dependencies:** S-01  
**Bloquea:** S-03, S-05, S-06

**Description:**

Crear todas las migraciones Supabase del modelo de datos del C4. Incluye tablas core, índices, RLS policies, triggers de LISTEN/NOTIFY (base del SSE), y seed de 1 entity demo para testing.

**Scope incluido:**
- Migration 001: extensions (`vector`, `pgmq`, `pg_cron`, `pg_trgm`, `uuid-ossp`)
- Migration 002: tablas core (`entities`, `claims`, `edges`, `sources`)
- Migration 003: tablas operacionales (`investigations`, `investigation_events`, `tool_cache`, `subscriptions`)
- Migration 004: índices (GIN search, ivfflat embedding, BTREE FKs, parciales)
- Migration 005: triggers + función `notify_investigation_event` + pg_cron cleanup
- Migration 006: RLS policies (`investigations` público + owner, `subscriptions` owner-only)
- Migration 007: seed con 1 entity demo + 1 source + 1 claim para testing

**Acceptance Criteria:**
- [ ] `supabase migration up` aplica las 7 migraciones sin errores
- [ ] `SELECT extname FROM pg_extension` muestra las 5 extensions
- [ ] Tablas creadas: `entities`, `claims`, `edges`, `sources`, `investigations`, `investigation_events`, `tool_cache`, `subscriptions`
- [ ] Constraints CHECK aplicados (country enum, confidence range, status enum)
- [ ] Test manual: en una sesión `LISTEN inv_test;`, en otra `INSERT INTO investigation_events(investigation_id='test',...)`, la primera recibe el payload
- [ ] RLS test: usuario A no SELECT subscriptions de usuario B
- [ ] Service role bypassa RLS confirmado
- [ ] pg_cron schedule activo: `SELECT * FROM cron.job` muestra cleanup-tool-cache
- [ ] Índices funcionales: `EXPLAIN ANALYZE` en query de búsqueda muestra uso de GIN
- [ ] Seed entity es queryable por `pg_trgm` similarity

**Files:**
- `infra/supabase/migrations/001_extensions.sql`
- `infra/supabase/migrations/002_core_tables.sql`
- `infra/supabase/migrations/003_operational_tables.sql`
- `infra/supabase/migrations/004_indexes.sql`
- `infra/supabase/migrations/005_triggers.sql`
- `infra/supabase/migrations/006_rls.sql`
- `infra/supabase/migrations/007_seed.sql`

**Technical notes:**
- Referencia: C4 model sección 7 (Modelo de datos) tiene el DDL completo.
- `investigation_events.id` debe ser `BIGSERIAL` para Last-Event-ID en SSE.
- `entities.search_vector` es columna generada (`GENERATED ALWAYS AS`).
- Sanitizar UUIDs en channel name de NOTIFY: `replace(uuid::text, '-', '_')` porque NOTIFY no acepta guiones.

---

### S-03 · API service deployable

**Title:** `[API] FastAPI con auth + search + endpoints base + deploy Cloud Run`  
**Priority:** P0 · **Estimate:** 10pts · **Labels:** `p0`, `wt-api`  
**Dependencies:** S-01, S-02  
**Bloquea:** S-07, S-08, S-10

**Description:**

Construir y desplegar el API service en Cloud Run. Incluye estructura modular, DI, repos asyncpg, auth middleware Supabase opcional, endpoints base (`/investigate`, `/search`, `/healthz`, `/readyz`), CORS, CSP, Dockerfile multi-stage, deploy con todos los flags correctos.

**Scope incluido:**
- FastAPI app factory con CORS configurado
- Settings con Pydantic Settings
- DI: db pool asyncpg (Supabase), settings injection
- Repos: `InvestigationRepo`, `EntityRepo`, `ClaimRepo`, `EventRepo` con métodos async
- Auth middleware: valida JWT Supabase via JWKS si presente, sino anónimo
- Endpoints: `POST /investigate` (con rate-limit hook), `GET /search`, `GET /entities/{id}`, `GET /healthz`, `GET /readyz`
- Search con `pg_trgm` + `tsvector` combinado, ranking por similarity + ts_rank
- Dockerfile multi-stage (builder uv + runtime slim)
- Deploy a Cloud Run `southamerica-east1` con `min-instances=1`, `timeout=3600`, `concurrency=80`, `no-cpu-throttling`
- Secrets desde GCP Secret Manager inyectados como env

**Acceptance Criteria:**
- [ ] `uvicorn src.main:app` corre local en puerto inyectado por Emdash
- [ ] `/api/v1/healthz` retorna `{status: "ok"}`
- [ ] `/api/v1/readyz` retorna `{db: "ok", supabase: "ok"}` y chequea conexión real
- [ ] `POST /api/v1/investigate` con `{entity_query, country, locale}` retorna 202 + `{investigation_id}` en <500ms (sin worker aún, solo INSERT + pgmq.send)
- [ ] `GET /api/v1/search?q=cerron&country=pe` retorna resultados en <100ms
- [ ] JWT válido de Supabase pasa middleware; JWT inválido → 401; sin header → anónimo (current_user=None)
- [ ] `docker build` produce imagen <300MB
- [ ] `gcloud run deploy sabueso-api` exitoso
- [ ] `curl https://sabueso-api-xxx.run.app/api/v1/healthz` retorna 200 desde internet
- [ ] CORS permite `sabueso.vercel.app` y `localhost:3000`
- [ ] Tests pytest: ≥70% cobertura en routes/ y services/

**Files:**
- `apps/api/pyproject.toml`
- `apps/api/src/main.py`, `deps.py`, `settings.py`
- `apps/api/src/routes/{investigate,search,health,entities}.py`
- `apps/api/src/services/{investigation,search}.py`
- `apps/api/src/db/{pool,repository/*}.py`
- `apps/api/src/auth/{middleware,current_user}.py`
- `apps/api/src/models/{investigation,entity,event}.py`
- `apps/api/Dockerfile`
- `apps/api/tests/...`

**Technical notes:**
- Pool asyncpg: `min_size=5, max_size=20` (cuidado con límite Supabase free 60).
- Cache JWKS de Supabase 5min para evitar latencia.
- En `POST /investigate`: rate-limit hook ahora retorna OK siempre (la implementación real viene en S-20). Sí hacer INSERT + pgmq.send.

---

### S-04 · Tool registry + 8 herramientas Perú

**Title:** `[Data] ToolRegistry MCP-ready + 8 tools PE con cache TTL`  
**Priority:** P0 · **Estimate:** 12pts · **Labels:** `p0`, `wt-data`  
**Dependencies:** S-02  
**Bloquea:** S-05, S-06

**Description:**

Implementar el sistema de tools que los subagentes invocan. Registry con namespacing por país, schemas exportables como MCP manifest, cache layer con TTL diferenciado. Implementar las 8 tools de Perú necesarias para los 7 subagentes.

**Scope incluido:**

**Registry (foundation):**
- `ToolRegistry` con decorator `@register(country=...)`
- Auto-extracción de schema desde Pydantic models
- `get_tools_for(country, allowed)` filtra por país
- `export_as_mcp()` retorna manifest JSON-Schema válido
- Cache wrapper `cached_tool_call` con key SHA256 de args, TTL configurable, cleanup vía pg_cron

**Las 8 tools Perú:**
1. `query_legalize_pe(query, semantic=true, limit=10)` — TTL 7d
2. `search_seace_contracts(ruc, year_from, year_to)` — TTL 24h, paginación OCDS
3. `search_manolo(dni_or_name)` — TTL 24h, Scrapling stealth
4. `fetch_jne_hoja_vida(candidate_id)` — TTL 30d, PyMuPDF + upload GCS
5. `query_sunarp_properties(dni)` — TTL 7d, Scrapling
6. `find_relatives(dni, degree=2)` — TTL 30d
7. `search_el_peruano(query, date_from, date_to)` — TTL 7d
8. `search_news_archive(entity_name)` — TTL 1d, prioriza IDL/OjoPúblico/Convoca/Wayback

**Acceptance Criteria:**
- [ ] `ToolRegistry.register(country="pe")` decorator funcional
- [ ] `get_tools_for("pe", ["search_seace_contracts"])` retorna 1 tool con schema
- [ ] `export_as_mcp()` retorna JSON válido contra MCP spec
- [ ] Cache hit: 2da llamada misma args retorna sin invocar handler
- [ ] Cache miss + INSERT en tool_cache con `expires_at = now() + ttl`
- [ ] Cada una de las 8 tools tiene test E2E con caso real (1 RUC público, 1 DNI público, 1 candidato JNE, etc.)
- [ ] PDF extraction de JNE retorna text + upload a GCS confirmado
- [ ] Scraping respeta rate limit (max 2 req/s por sitio)
- [ ] Retry con backoff exponencial en errores 5xx (max 3 intentos)
- [ ] Schemas Pydantic estrictos para input + output de cada tool
- [ ] Errores tipados: `ToolError`, `RateLimitedError`, `SourceUnavailableError`

**Files:**
- `apps/worker/src/tools/registry.py`
- `apps/worker/src/tools/cache.py`
- `apps/worker/src/tools/pe/{legalize,seace,manolo,jne,sunarp,relatives,el_peruano,news}.py`
- `apps/worker/tests/tools/...`

**Technical notes:**
- Si OECE OCDS API rate-limita, usar dump CSV histórico como fallback.
- JNE PDFs scaneados: usar Tika como fallback de PyMuPDF.
- Búsqueda semántica de legalize-pe: pgvector contra embeddings ya en Supabase (asume que se pre-pobló o se hará en S-15).
- Manolo: identificar selectors estables, fallar gracefully si cambian.

---

### S-05 · Investigator framework + LLM client

**Title:** `[Agents] BaseInvestigator + ReWOO/ReAct + LLM client + prompts loader`  
**Priority:** P0 · **Estimate:** 9pts · **Labels:** `p0`, `wt-agents`  
**Dependencies:** S-02, S-04  
**Bloquea:** S-06, S-10

**Description:**

Construir la framework de subagentes que los 7 investigadores heredan. Incluye clase base abstracta, estrategias ReWOO y ReAct, cliente LLM unificado (OpenRouter), helpers de prompt caching Anthropic, y loader de prompts desde markdown.

**Scope incluido:**

**Base + estrategias:**
- `BaseInvestigator(ABC)` con atributos: callsign, role, color, model, strategy, allowed_tools, system_prompt_path
- Método `run(task, state)` despacha según strategy
- `_run_rewoo()`: plan → parallel tools → synthesize
- `_run_react()`: thought-action-observation loop, max_steps=15, hard timeout 60s
- `_emit_event()`: insert en investigation_events
- Permission gate: subagente solo accede tools en `allowed_tools`

**LLM client:**
- `LLMClient` class con método `complete(model, messages, tools=None)`
- Apuntado a `https://openrouter.ai/api/v1`
- Tracking automático de tokens + costo en `state.token_usage` y `state.cost_usd`
- Retry exponencial en 429/503
- Pricing table por modelo en `llm/pricing.py`

**Prompt caching:**
- `apply_cache_breakpoints(messages, breakpoints)` inyecta `cache_control: ephemeral` en posiciones marcadas
- Verificación si OpenRouter pasa header correcto; fallback a Anthropic SDK directo para modelos `anthropic/*` si no

**Prompt loader:**
- `load_prompt(name, vars, locale)` lee markdown + frontmatter YAML
- Variables Jinja2
- Crea placeholders: `sabueso_system.md`, `buscador_system.md`, `tasadora_system.md`, `contador_system.md`, `letrado_system.md`, `detective_system.md`, `periodista_system.md`, `jueza_moa_system.md`

**Acceptance Criteria:**
- [ ] Clase abstracta `BaseInvestigator` correcta (no instanciable, métodos abstractos definidos)
- [ ] `Strategy.REWOO` y `Strategy.REACT` enums
- [ ] Test con mock LLM: ReWOO ejecuta 3 tools en paralelo, ReAct hace 3 iteraciones
- [ ] LLMClient retry funciona ante mock de 429
- [ ] Token tracking: después de 5 llamadas, `state.token_usage.input` y `cost_usd` correctos
- [ ] `apply_cache_breakpoints` inyecta `cache_control` en los 4 puntos correctos
- [ ] Detecta automáticamente si OpenRouter respeta cache (fallback a Anthropic directo)
- [ ] Prompt loader carga frontmatter, parsea variables, devuelve string final
- [ ] Tests unitarios pasan al ≥75% cobertura

**Files:**
- `apps/worker/src/investigators/base.py`
- `apps/worker/src/llm/{client,caching,routing,pricing}.py`
- `apps/worker/src/prompts/loader.py`
- `apps/worker/src/prompts/{sabueso,buscador,tasadora,contador,letrado,detective,periodista,jueza_moa}_system.md` (placeholders con estructura de 4 breakpoints)
- `apps/worker/tests/investigators/test_base.py`
- `apps/worker/tests/llm/test_caching.py`

**Technical notes:**
- ReAct decision parsing: usar `json.loads` con `extra_ignored_fields` tolerante; si falla, retry con error feedback al LLM.
- Hard timeout 60s en ReAct: si llega al límite, fuerza `finish` action y extrae claims con observaciones disponibles.
- Pricing inicial: Sonnet 4.6 $3/$15 per M tokens, Kimi K2.6 $0.74/$3.50, V4-Flash $0.14/$0.28 (promo $0.435/$0.87 V4-Pro hasta 31-May), GPT-4o $2.50/$10.

---

### S-06 · LangGraph orchestrator

**Title:** `[Agents] LangGraph completo: state + 6 nodos + fan-out + checkpointer`  
**Priority:** P0 · **Estimate:** 12pts · **Labels:** `p0`, `wt-agents`  
**Dependencies:** S-02, S-05  
**Bloquea:** S-07, S-10

**Description:**

Construir el grafo de orquestación: state tipo TypedDict con reducers, los 6 nodos del flujo (load_context, plan, collect, verify, synthesize, persist), conditional edge fan_out con Send(), Postgres checkpointer apuntado a Supabase.

**Scope incluido:**

**State:**
- `InvestigationState(TypedDict)` exacto según C4 sección 6.1
- Campos acumulativos `Annotated[list, add]` para claims, edges, events
- Test de merge concurrente

**Builder:**
- `build_graph()` registra todos los nodos y aristas
- `PostgresSaver.from_conn_string(DB_URL)` configura checkpointer
- LangGraph crea sus tablas (`checkpoints`, etc.) en Supabase en primera corrida

**Nodos:**
1. `load_context` — fetch entity + historial reciente
2. `sabueso_plan` — Claude Sonnet 4.6 con 4 cache breakpoints, parsea plan JSON
3. `fan_out` — conditional edge que emite N `Send()` (uno por subagente del plan)
4. (placeholder nodes) `buscador`, `tasadora`, `contador`, `letrado`, `detective`, `periodista` — referencia las clases que se crean en S-10/S-11
5. `collect` — barrier después del fan-out
6. `jueza_moa` — placeholder, implementación en S-11
7. `synthesize` — Claude Opus 4.7 produce dossier final markdown
8. `persist` — UPDATE investigations + INSERT claims/edges

**Acceptance Criteria:**
- [ ] State definido y typecheck passes (mypy strict)
- [ ] `build_graph().compile()` no falla
- [ ] Postgres checkpointer crea sus tablas en primera invocación
- [ ] Test integración: graph con 1 subagente mockeado completa todo el flujo
- [ ] State final tiene: 2 claims (del mock), status update, eventos emitidos, dossier_md no vacío
- [ ] Checkpoint queries: `SELECT * FROM checkpoints WHERE thread_id = ?` retorna ≥3 rows (uno por step)
- [ ] Sabueso plan retorna list[{agent, task, priority}] válido
- [ ] Sabueso plan reintentar 1 vez si JSON malformado
- [ ] fan_out emite tantos `Send()` como tasks en el plan
- [ ] `synthesize` produce markdown estructurado con secciones
- [ ] `persist` ejecuta transacción atómica (rollback si algo falla)

**Files:**
- `apps/worker/src/orchestrator/state.py`
- `apps/worker/src/orchestrator/graph.py`
- `apps/worker/src/orchestrator/edges.py` (fan_out)
- `apps/worker/src/orchestrator/nodes/{load_context,plan,collect,synthesize,persist}.py`
- `apps/worker/src/orchestrator/checkpointer.py`
- `apps/worker/tests/test_graph_integration.py`

**Technical notes:**
- LangGraph version: pin exacta en pyproject. No actualizar durante hackathon.
- El nodo `synthesize` usa Opus solo para el dossier final (1 call), no para reasoning del orquestador.
- Plan JSON schema validation con Pydantic; si retry falla 2 veces, fallback a plan default (los 6 investigadores con tareas genéricas).

---

### S-07 · Worker Cloud Run Job + dispatch

**Title:** `[Infra] Worker Job entry + Dockerfile + deploy + API trigger`  
**Priority:** P0 · **Estimate:** 7pts · **Labels:** `p0`, `wt-infra`, `wt-api`  
**Dependencies:** S-03, S-06  
**Bloquea:** S-10

**Description:**

Empaquetar el orquestador como Cloud Run Job. Implementar dispatch desde el API service vía REST API de GCP con OIDC token. Garantizar idempotencia con pgmq.

**Scope incluido:**
- Worker entrypoint `main.py` recibe `--investigation-id`, fetches state, corre graph, escribe outputs
- Dockerfile multi-stage del worker (incluye Scrapling, opcionalmente Playwright lazy)
- `gcloud run jobs deploy investigation-worker` con `task-timeout=3600`, `memory=2Gi`, `cpu=2`
- API service: `InvestigationService.dispatch_worker()` real: usa `google-auth` para OIDC, POST a Cloud Run Jobs REST
- pgmq idempotency: API hace `pgmq.send` después de INSERT, worker consume con `pgmq.read` + delete on success, retry visible si falla

**Acceptance Criteria:**
- [ ] `docker build apps/worker` exitoso, imagen <500MB
- [ ] `gcloud run jobs deploy investigation-worker` exitoso
- [ ] Manual test: `gcloud run jobs execute investigation-worker --args="--investigation-id=test-uuid"` corre y deja logs
- [ ] Desde API: POST `/api/v1/investigate` → INSERT investigations → pgmq.send → trigger Cloud Run Job vía REST → Job execution visible en GCP Console
- [ ] Si worker crashea, mensaje vuelve a la cola (pgmq visibility_timeout)
- [ ] Worker consume mensajes idempotente: si misma investigation_id se procesa 2 veces, no duplica claims
- [ ] Logs estructurados en Cloud Logging

**Files:**
- `apps/worker/src/main.py`
- `apps/worker/Dockerfile`
- `apps/api/src/services/investigation.py` (método `dispatch_worker`)
- `infra/cloudrun/jobs/investigation-worker.yaml` (config declarativa)

**Technical notes:**
- OIDC token: `google.auth.compute_engine.IDTokenCredentials` con audience `https://run.googleapis.com`
- pgmq config: `visibility_timeout=300s`, max retries handled by Cloud Run `--max-retries=1`
- Worker debe escribir heartbeats a `investigations.last_heartbeat` cada 30s para que el API detecte zombies.

---

### S-08 · Events + SSE end-to-end

**Title:** `[API] Event schemas + SSE endpoint + LISTEN/NOTIFY + reconnect`  
**Priority:** P0 · **Estimate:** 8pts · **Labels:** `p0`, `wt-api`  
**Dependencies:** S-02, S-03  
**Bloquea:** S-10

**Description:**

Construir el canal de comunicación en vivo entre el worker y el frontend. EventEmitter en el worker, schemas Pydantic, SSE endpoint en FastAPI con LISTEN/NOTIFY, reconexión con Last-Event-ID, heartbeat.

**Scope incluido:**

**Schemas:**
- 12 event types definidos con Pydantic:
  - `investigation_started`, `plan_generated`, `agent_started`, `tool_call`, `claim_created`, `edge_discovered`, `agent_finished`, `verification_done`, `synthesis_started`, `investigation_complete`, `investigation_failed`, `heartbeat`
- Export TypeScript via `pydantic2ts` a `packages/shared-types`

**Emitter (worker side):**
- `EventEmitter` class con método async `emit(type, payload, agent_callsign=None)`
- Insert en `investigation_events`
- El trigger SQL (T-011 ya creado) dispara NOTIFY

**SSE endpoint:**
- `GET /api/v1/stream/{investigation_id}` retorna `text/event-stream`
- Acepta `Last-Event-ID` header o `last_event_id` query
- Conexión asyncpg dedicada con `LISTEN inv_<sanitized_uuid>`
- Async queue captura notificaciones, generator yields como SSE
- Heartbeat cada 30s
- Cierra cuando recibe `investigation_complete/failed` o `request.is_disconnected()`
- Backlog: si `last_event_id` presente, primero envía eventos > ese ID

**Acceptance Criteria:**
- [ ] 12 event schemas validables con Pydantic
- [ ] TypeScript types generados en `packages/shared-types/events.ts`
- [ ] Worker emite eventos: SELECT desde `investigation_events` muestra inserts
- [ ] cURL test: `curl -N https://api.../stream/{id}` recibe stream
- [ ] Headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`
- [ ] Cada SSE event tiene formato `id: N\nevent: type\ndata: {json}\n\n`
- [ ] Heartbeat se envía si no hay eventos en 30s
- [ ] Reconnect: cliente con `Last-Event-ID: 5` recibe 6, 7, 8+ correctamente
- [ ] Múltiples clientes pueden suscribirse al mismo investigation_id (test con 2 cURL paralelos)
- [ ] Stream termina graceful con `investigation_complete` o cuando cliente se desconecta

**Files:**
- `apps/worker/src/events/{emitter,schemas}.py`
- `apps/api/src/routes/stream.py`
- `apps/api/src/sse/{stream,listener,events}.py`
- `packages/shared-types/events.ts` (generado)
- `apps/api/tests/test_sse.py`

**Technical notes:**
- Channel name sanitization: `f"inv_{uuid.replace('-','_')}"` porque NOTIFY rechaza guiones.
- Connection pool: cada SSE consume 1 connection del pool asyncpg. Con max_size=20 y free tier Supabase 60 directas, sostiene hasta 20 SSE simultáneos por instancia Cloud Run.
- Si pool agotado: log warning + 503 con `Retry-After: 5`.
- `sse-starlette` package facilita el `EventSourceResponse`.

---

### S-09 · Frontend skeleton

**Title:** `[Frontend] Next 16 App Router + i18n + Supabase Auth + AI Elements + TanStack Query`  
**Priority:** P0 · **Estimate:** 8pts · **Labels:** `p0`, `wt-frontend`  
**Dependencies:** S-01  
**Bloquea:** S-10, S-12

**Description:**

Levantar la app Next 16 con todas las capas base: routing, i18n, autenticación opcional, cliente API, hooks de investigación con SSE, design tokens del UI/UX spec, primera versión funcional de home y `/i/[id]`.

**Scope incluido:**

**Setup:**
- Next 16 App Router + TypeScript 5.6+
- Tailwind v4 con tokens del UI/UX spec sección 3 (paleta + tipografía + radius + motion)
- Fuentes: Antonio, Instrument Serif, Geist Sans, IBM Plex Mono via `next/font/google`
- shadcn/ui: button, card, dialog, dropdown, input, label, popover, sheet, tabs, tooltip, toast, command, sonner
- Dark/light mode con `next-themes`

**i18n:**
- next-intl con `es` (traducido) y `en` (placeholder)
- Routing `/es/...` y `/en/...` opcional, default `es-PE`
- Country selector navbar

**Auth:**
- Supabase Auth: Google OAuth + magic link
- Páginas `/auth/login`, `/auth/callback`
- Hook `useUser()`, helper `getCurrentUser()`
- Anónimo navega sin trabas

**API + State:**
- API client `lib/api.ts` con funciones tipadas (importa types desde `packages/shared-types`)
- TanStack Query 5 con QueryClientProvider
- Hook `useInvestigation(id)` con `EventSource` SSE + reconnect con Last-Event-ID
- Hook `useLocalStorageInvestigation(id)` persistencia local
- Procesa los 12 event types y mantiene state machine local

**Páginas:**
- `/` (marketing)
- `/app` home con buscador prominente + autocompletado debouncing → `/api/v1/search`
- `/i/[id]` skeleton de 3 paneles con placeholders

**Acceptance Criteria:**
- [ ] `pnpm dev` arranca app en puerto inyectado por Emdash
- [ ] `sabueso.vercel.app` deployea automáticamente desde git push
- [ ] Login con Google funciona y persiste sesión
- [ ] Anónimo accede a `/app` y `/i/[id]` sin login
- [ ] Toggle dark/light mode funciona y persiste
- [ ] Toggle idioma cambia strings sin reload
- [ ] Autocompletado: debounce 200ms, llama `/api/v1/search`, muestra max 10 resultados con highlight
- [ ] `useInvestigation` abre EventSource y procesa eventos mockeados correctamente (test con servidor SSE local)
- [ ] Reconexión SSE: kill conexión, frontend reconecta con `Last-Event-ID` correcto
- [ ] localStorage persiste último estado y rehidrata al reload
- [ ] Lighthouse score >85 en home y /i/[id] (sin datos reales)
- [ ] Mobile-responsive (mobile-first design)

**Files:**
- `apps/web/app/(marketing)/page.tsx`
- `apps/web/app/(app)/{page,layout}.tsx`
- `apps/web/app/(app)/i/[id]/page.tsx`
- `apps/web/app/auth/{login,callback}/page.tsx` y `route.ts`
- `apps/web/app/providers.tsx`
- `apps/web/components/ai-elements/...` (Conversation, Message, Reasoning, Tool, Source, etc. - via shadcn add)
- `apps/web/components/ui/...` (shadcn base)
- `apps/web/lib/{api,supabase/client,supabase/server,sse,kv,localStorage}.ts`
- `apps/web/hooks/{useUser,useInvestigation,useLocalStorageInvestigation,useLocale}.ts`
- `apps/web/i18n.ts`, `apps/web/messages/{es,en}.json`
- `apps/web/proxy.ts` (Next 16 proxy: Supabase session refresh + i18n routing; reemplaza al deprecado `middleware.ts`)
- `apps/web/tailwind.config.ts`, `apps/web/app/globals.css`

**Technical notes:**
- AI Elements: `npx ai-elements@latest add` para los componentes ownership.
- TanStack Query setup en `providers.tsx` con QueryClient en cliente.
- EventSource no soporta headers custom — pasar `last_event_id` como query param.
- localStorage save throttled cada 500ms para evitar thrashing.

---

### S-10 · Primer end-to-end (El Contador)

**Title:** `[E2E] Happy path: query → El Contador → claim → SSE → display`  
**Priority:** P0 · **Estimate:** 5pts · **Labels:** `p0`, `wt-agents`, `wt-frontend`  
**Dependencies:** S-03, S-05, S-06, S-07, S-08, S-09  
**Bloquea:** S-11, S-12

**Description:**

Construir el primer investigador real (El Contador) y conectar todo el pipeline end-to-end. Es el milestone más importante: prueba que la arquitectura funciona. A partir de acá los próximos 6 subagentes son cookie-cutter.

**Scope incluido:**

**El Contador:**
- `ElContador(BaseInvestigator)` con callsign="el-contador", color violet-500
- Strategy=REWOO, model="moonshot/kimi-k2.6"
- allowed_tools=["search_seace_contracts"]
- Prompt `contador_system.md` con identidad + reglas + cache breakpoints + 1 few-shot

**Demo entity seed:**
- Migration 008 con 1 entity real (un funcionario público con RUC asociado público y verificable)
- 1 source y 1 claim semilla para testing

**Wiring final:**
- Backend: orchestrator delega a "contador" → El Contador corre → emite tool_call → emite claim → barrier collect → synthesize (Opus 4.7) → persist
- Frontend: useInvestigation procesa todos los eventos, muestra en chat de Mission Control + dossier creciendo

**Smoke test:**
- Script `scripts/smoke-test.sh` POST a `/api/v1/investigate` con entity demo
- Verifica recibe ≥3 eventos SSE en <30s
- Verifica `investigations.status = 'complete'` al final
- Integrado en CI post-deploy

**Acceptance Criteria:**
- [ ] El Contador implementado y unit-tested (mock LLM + mock tool)
- [ ] Migration 008 aplicada con seed entity verificable
- [ ] Demo manual: usuario abre `sabueso.vercel.app`, tipea nombre seed, submit
- [ ] `/i/[id]` muestra plan, agent_started, tool_call de search_seace, 1 claim creado
- [ ] Dossier final no vacío con menos sección "Contratos"
- [ ] Tiempo total <60s end-to-end
- [ ] Costo de la corrida <$0.50 (verificable en `investigations.cost_usd`)
- [ ] Smoke test pasa en CI
- [ ] Video screen recording de la corrida exitosa (subido a Vercel Blob)

**Files:**
- `apps/worker/src/investigators/contador.py`
- `apps/worker/src/prompts/contador_system.md` (versión completa)
- `infra/supabase/migrations/008_seed_demo_entity.sql`
- `scripts/smoke-test.sh`
- `.github/workflows/smoke-test.yml`

**Technical notes:**
- Si la corrida real es muy lenta por SEACE: hacer un dry-run con datos cacheados primero.
- Si el seed entity tiene RUC con muchos contratos, el output puede ser largo. Limitar tools a year_from=2020 para acelerar.
- Documentar tiempos parciales: API response <500ms, plan <5s, El Contador <30s, synthesize <15s.

---

### S-11 · 6 investigadores restantes + La Jueza (MoA)

**Title:** `[Agents] Buscador + Tasadora + Letrado + Detective + Periodista + Jueza`  
**Priority:** P0 · **Estimate:** 10pts · **Labels:** `p0`, `wt-agents`  
**Dependencies:** S-10  
**Bloquea:** S-17

**Description:**

Implementar los 6 subagentes restantes siguiendo el patrón establecido con El Contador. Incluye La Jueza (verifier MoA single-layer) que siempre corre.

**Scope incluido:**

**Investigadores (5):**

1. **El Buscador** (Recon)
   - Strategy ReWOO, Kimi K2.6
   - Tools: `search_manolo`, `find_dni_record`, `find_ruc_record`
   - Output: claims tipo `is_dni`, `is_ruc`, `holds_position`, `affiliated_with_party`

2. **La Tasadora** (Patrimony)
   - Strategy ReAct (PDFs impredecibles), DeepSeek V4-Flash
   - Tools: `fetch_jne_hoja_vida`, `query_sunarp_properties`
   - Detección de discrepancia declarado-vs-real

3. **El Letrado** (Legal)
   - Strategy ReWOO, DeepSeek V4-Flash
   - Tools: `query_legalize_pe`, `search_sentences` (placeholder), `cross_vote_interest` (placeholder)
   - Output: claims sobre votos vs intereses económicos

4. **El Detective** (Relationships)
   - Strategy ReAct, DeepSeek V4-Flash
   - Tools: `find_relatives`, `query_sunarp_board`, `expand_network` (placeholder)
   - Genera `edges` tipo `spouse_of`, `parent_of`, `board_member_of`, `shareholder_of`

5. **El Periodista** (News)
   - Strategy ReAct, Kimi K2.6
   - Tools: `search_news_archive`, `wayback_machine` (placeholder), `search_twitter_archive` (placeholder)
   - Claims con cita literal + URL archivada

**La Jueza (MoA):**

6. **La Jueza** (Verifier)
   - PROPOSERS: `claude-sonnet-4.6`, `kimi-k2.6`, `gpt-4o`
   - AGGREGATOR: `claude-sonnet-4.6`
   - `verify_all(claims)` paralelo con asyncio.gather
   - Cada claim recibe: `verified`, `confidence_final`, `disagreements`, `verifier_notes`
   - **G4 decisión: SIEMPRE corre, no por threshold**
   - Persist en `claims.verified_by_jueza = TRUE`

**Acceptance Criteria:**
- [ ] 5 investigadores implementados, cada uno con su prompt completo
- [ ] Cada investigador unit-tested con mock LLM + mock tools
- [ ] La Jueza implementada, paralela con asyncio.gather
- [ ] La Jueza tracking de disagreements: si 3 proposers difieren mucho, confidence_final baja
- [ ] LangGraph orchestrator: nodo `verify` invoca La Jueza sobre todos los claims
- [ ] Test integración: investigación con 3 subagentes activos + La Jueza completa correctamente
- [ ] Costo de investigación completa con 6 subagentes + La Jueza <$1.00 (verificar en logs)
- [ ] Cada claim final tiene confidence ajustada por La Jueza

**Files:**
- `apps/worker/src/investigators/{buscador,tasadora,letrado,detective,periodista,jueza}.py`
- `apps/worker/src/prompts/{buscador,tasadora,letrado,detective,periodista,jueza_moa}_system.md` (completos)
- `apps/worker/tests/investigators/test_all.py`

**Technical notes:**
- La Jueza chunk: si hay >20 claims, batch en grupos de 10 para reducir latencia.
- Reuse del LLMClient — ya tracking de tokens y costo.
- Cada prompt sigue mismo formato (identidad → reglas → tools → few-shot → variable).
- El Detective genera principalmente **edges**, no claims. Diferente del resto.

---

### S-12 · Cinema Mode UI completo

**Title:** `[Frontend] Cinema Mode: 3 paneles + Operatives Floor + Drilldown + Grafo cosmos.gl`  
**Priority:** P0 · **Estimate:** 12pts · **Labels:** `p0`, `wt-frontend`  
**Dependencies:** S-09, S-10  
**Bloquea:** S-13, S-17

**Description:**

Implementar el corazón visual del producto: el Cinema Mode según `sabueso-uiux-spec.md`. Incluye componentes atómicos, layout de 3 paneles, Operatives Floor con cubículos pulsantes, drill-down lateral, y grafo en vivo con cosmos.gl.

**Scope incluido:**

**Componentes atómicos:**
- `InvestigatorAvatar.tsx` (Notionists/Lorelei seed fija, tamaños 48/64/96, estados, speech bubble)
- `InvestigatorWorkstation.tsx` (disco tinted + LED pulsante + placard + status pill)
- `DelegationArrow.tsx` (SVG Bezier + marching ants CSS keyframe)
- `StatusPill.tsx` (5 estados con color + texto)
- `ConfidenceBadge.tsx` (chip con score)
- `EvidenceChip.tsx` (link a fuente)

**Layout principal de `/i/[id]`:**
- Header sticky con breadcrumb, ID, progreso, acciones
- 3-panel layout con `react-resizable-panels`: Mission Control (28%) + Investigation Floor (44%) + Dossier (28%)
- Operatives Floor banda inferior (140px alto)
- Timeline Scrubber banda muy inferior (48px alto)

**Mission Control panel:**
- Tabs: "Chat" + "Pistas"
- Chat: AI Elements `Conversation` con messages tipados por investigador (avatar + color), `Reasoning` collapsible, `Tool` plegable, `Source` chips
- Pistas: 4-column kanban (Por asignar / Listas / En curso / Cerradas/Bloqueadas)
- PromptInput al fondo para refinement

**Investigation Floor:**
- Tabs: Grafo (default) + Sankey + Timeline (los 2 últimos placeholder, se hacen en S-13)
- `InvestigationGraph.tsx` wrapper de cosmos.gl
- Recibe nodes + edges del state, renderiza force-directed
- Color de nodos según semantic (declared/discovered/ambiguous/suspicious/conflict/verified)
- Grosor de aristas = confidence
- Materialización spring-soft de nuevos nodos
- Pulse rojo en nodos con conflict
- Click node → emite onNodeClick(entity_id)
- Click edge → emite onEdgeClick(edge_id) abre DrilldownPanel del source
- Filtros laterales colapsables (monto, aristas rojas, rango fecha, grado familia)

**Dossier panel:**
- react-markdown con plugins (remark-gfm, rehype-sanitize)
- ConfidenceBadge inline cada claim
- EvidenceChip components para fuentes
- Live streaming durante synthesize

**Operatives Floor (banda inferior):**
- Grid de 7 cubículos
- Cada cubículo refleja estado actual del subagente
- DelegationArrow dibuja paths entre cubículos para tareas en curso
- Click cubículo → abre DrilldownPanel
- Responsive: scroll horizontal en mobile

**Drilldown Panel:**
- Sheet shadcn slide-in desde derecha
- Identidad investigator + modelo + estado
- Pista en curso (titulo, quien delegó, prioridad)
- Subtareas delegadas (árbol expandible)
- Activity timeline live (cada evento con borde izquierdo coloreado por tipo)
- Hilo de misión read-only
- Acciones: pausar / reasignar / cancelar (mockeadas v1)

**Acceptance Criteria:**
- [ ] Todos los 6 componentes atómicos renderizables en isolation (Storybook opcional)
- [ ] Layout 3-paneles funcional con resize entre paneles
- [ ] Mission Control: chat muestra mensajes con avatares correctos por investigador
- [ ] AI Elements `Tool` muestra tool calls correctamente con input/output
- [ ] Kanban: cards aparecen en columna correcta según estado
- [ ] Investigation Graph: nodes y edges renderizan en cosmos.gl con colores correctos
- [ ] Nuevo nodo aparece con spring animation cuando llega `claim_created` event
- [ ] Click en cubículo abre DrilldownPanel del investigador correcto
- [ ] Drilldown Activity Timeline live-updates con cada nuevo event SSE filtrado por callsign
- [ ] DelegationArrow marching ants se anima cuando hay pista en running
- [ ] Color coding de eventos en activity timeline correcto
- [ ] Esc cierra DrilldownPanel
- [ ] Mobile: 3 paneles colapsan a vertical stack
- [ ] Accessible: keyboard nav, aria-live, contraste 4.5:1
- [ ] Reduced-motion: desactiva animaciones según preferencia del sistema

**Files:**
- `apps/web/components/investigation/{InvestigatorAvatar,InvestigatorWorkstation,DelegationArrow,StatusPill,ConfidenceBadge,EvidenceChip}.tsx`
- `apps/web/components/investigation/{OperativesFloor,MissionControl,InvestigationGraph,DossierPanel,DrilldownPanel,TimelineScrubber}.tsx`
- `apps/web/app/(app)/i/[id]/page.tsx` (rewrite con 3-panel layout)
- `apps/web/lib/graph/cosmos-helpers.ts`

**Technical notes:**
- Cosmograph React (CC BY-NC 4.0): OK para Sabueso open-source non-commercial. Alternativa: `react-force-graph-2d` MIT.
- AI Elements ownership: `npx ai-elements@latest add conversation message reasoning tool source response`
- Calcular posiciones de DelegationArrows post-render del Operatives Floor con `useRef` + `useLayoutEffect`.
- LED pulse: `@keyframes pulse-led` 1.4s ease-in-out infinite.
- Marching ants: `stroke-dasharray: 5,3; animation: ants 800ms linear infinite;`

---

### S-13 · Modos de visualización

**Title:** `[Frontend] Sankey mode + Timeline mode + Timeline Scrubber + Dossier read-only`  
**Priority:** P1 · **Estimate:** 6pts · **Labels:** `p1`, `wt-frontend`  
**Dependencies:** S-12  
**Bloquea:** —

**Description:**

Agregar las vistas alternativas al Investigation Floor: Sankey para flujo de dinero, Timeline para vista cronológica, scrubber temporal, y modo dossier-only SSR para SEO.

**Scope incluido:**

**Sankey mode:**
- Toggle "💰 Flujo de dinero" en Investigation Floor
- `@nivo/sankey` con dataset derivado de edges tipo `received_amount`
- Coloring: verde si declarado, rojo si va a beneficiario cercano
- Hover tooltip con monto agregado
- Cross-fade 200ms entre modos

**Timeline mode:**
- `@visx/timeline` o `lightweight-charts` para eventos cronológicos
- Eventos atómicos: nacimientos, postulaciones, contratos, votos, sentencias
- Agrupados por año
- Click evento → zoom al nodo en grafo (al volver a modo grafo)

**Timeline Scrubber (banda inferior, 48px):**
- Línea horizontal con marcas de año
- Eventos como puntos del color del investigador
- Drag scrubber → grafo (en modo grafo) anima estado a esa fecha
- Doble-click en punto → zoom al evento
- Min-Max según rango real de events

**Dossier-only mode (SSR):**
- Ruta `/i/[id]/dossier` Server Component
- Fetch del dossier desde Supabase directo (sin SSE)
- HTML completo en respuesta inicial
- CSS print-friendly
- OG meta tags poblados desde server

**Acceptance Criteria:**
- [ ] Toggle entre Grafo/Sankey/Timeline con cross-fade smooth
- [ ] Sankey muestra flujos de dinero correctamente si hay datos
- [ ] Sankey con dataset vacío muestra "Sin datos de flujos de dinero aún"
- [ ] Timeline ordena eventos por fecha, agrupa por año
- [ ] Timeline scrubber drag funcional, grafo responde
- [ ] `/i/[id]/dossier` SSR: HTML inicial completo (verificable con `curl`)
- [ ] Lighthouse SEO score >90 en `/i/[id]/dossier`
- [ ] Print stylesheet aplica: márgenes A4, sin sidebars
- [ ] OG meta tags: `og:title`, `og:description`, `og:image` (placeholder por ahora)

**Files:**
- `apps/web/components/investigation/{SankeyView,TimelineView,TimelineScrubber}.tsx`
- `apps/web/app/(app)/i/[id]/dossier/page.tsx`
- `apps/web/app/(app)/i/[id]/dossier/print.css`

**Technical notes:**
- Si SEACE no provee monto en algunos contratos, Sankey los muestra como nodos sin flow (visual placeholder).
- Timeline events derivados de `claims` + `edges` con campo `temporal_anchor`.

---

### S-14 · La Redacción + Hemeroteca + Comparador

**Title:** `[Frontend] Páginas /redaccion + /hemeroteca + /comparar`  
**Priority:** P1 · **Estimate:** 6pts · **Labels:** `p1`, `wt-frontend`  
**Dependencies:** S-09  
**Bloquea:** —

**Description:**

Construir las páginas accesorias: el equipo (La Redacción con ID badges estilo press pass), el archivo (Hemeroteca con todas las investigaciones), y el comparador.

**Scope incluido:**

**InvestigatorBadge (ID press pass):**
- Card con lanyard hole superior
- Banda upper con color del investigador
- Retrato cuadrado con crop marks (4 cruces de 8px en esquinas)
- Callsign en Instrument Serif italic
- Datos en IBM Plex Mono: rol, modelo, ID, status
- Barcode CSS-rendered (variación pseudoaleatoria por hash del callsign)
- Hover: sube 4px + shadow profundo

**La Redacción `/redaccion`:**
- Grid responsive de 7 badges (defaults) + N custom
- Click badge → navega a `/redaccion/[callsign]`
- Acción "Contratar" (top-right): clona base como template
- Toggle activo/inactivo persistido en tabla `investigator_configs(user_id, callsign, config_jsonb)`

**Expediente `/redaccion/[callsign]`:**
- Form shadcn con Zod validation
- Editable: identidad, modelo, skills permitidos, reglas (system prompt textarea), pre-aprobaciones (tools sin confirmación)
- Tab "Estadísticas": pistas trabajadas, confianza promedio, fuentes top, tasa blocked/done
- Botón "Restaurar default"

**Hemeroteca `/hemeroteca`:**
- Server Component SSR de lista inicial
- Filtros: Abiertas / Cerradas / Públicas / Tuyas (requiere auth)
- Búsqueda full-text con `pg_trgm`
- Pagination con Server Actions
- Cada item: menú ⋯ con Reabrir / Compartir / Archivar / Eliminar
- Card: stripe izquierda color estado, contadores (pistas, alertas, fuentes), timestamp

**Comparador `/comparar`:**
- Selector de 2-4 entidades (autocomplete)
- Cards lado a lado
- Heatmap de riesgo por dimensión (Patrimonio, Contratos, Conflictos, Antecedentes)
- Score agregado por entidad (calculado por Supabase RPC)
- Indicadores visuales 🟢🟡🔴

**Acceptance Criteria:**
- [ ] InvestigatorBadge renderiza con barcode CSS distintivo por callsign
- [ ] `/redaccion`: grid de 7 badges visibles, click navega correctamente
- [ ] Expediente edit + save persiste cambios en DB
- [ ] Toggle activo/inactivo afecta investigations subsiguientes (si "El Periodista" off, plan no lo incluye)
- [ ] `/hemeroteca` SSR: HTML inicial con lista
- [ ] Filtros funcionan + paginación
- [ ] `/comparar` con 3 entidades muestra heatmap
- [ ] RPC `compare_entities(entity_ids[])` calcula scores correctos
- [ ] Mobile responsive

**Files:**
- `apps/web/components/investigation/InvestigatorBadge.tsx`
- `apps/web/app/(app)/redaccion/{page.tsx,[callsign]/page.tsx}`
- `apps/web/app/(app)/hemeroteca/page.tsx`
- `apps/web/app/(app)/comparar/page.tsx`
- `infra/supabase/migrations/009_investigator_configs.sql` (nueva tabla)
- `infra/supabase/migrations/010_rpc_compare.sql`

**Technical notes:**
- Crop marks: usar `::before` y `::after` con 4 spans absolutos de 8px posicionados en cada esquina del retrato.
- Barcode: array de 20-30 `<i>` elements con widths variables. Seed por callsign hash.

---

### S-15 · Pipeline CocoIndex

**Title:** `[Data] Pipeline ingest: legalize-pe + SEACE + JNE PDFs`  
**Priority:** P1 · **Estimate:** 8pts · **Labels:** `p1`, `wt-data`  
**Dependencies:** S-02  
**Bloquea:** S-17

**Description:**

Construir el pipeline de ingesta incremental con CocoIndex que pre-popula Supabase con los datasets que los subagentes consultan. Tres flows: legalize-pe (1,617 normas), SEACE (24 meses recientes filtrado), JNE PDFs (candidatos 2026).

**Scope incluido:**

**CocoIndex base:**
- `apps/pipeline/pyproject.toml` con cocoindex, gcsfs
- Helpers comunes: `embedding.py` (OpenRouter text-embedding-3-small), `extract.py` (PyMuPDF + Tika), `upsert.py` (batch upsert a Supabase)

**Flow 1: pe_legalize**
- Source: clone legalize-pe repo o API REST
- Cada ley → entity tipo `law` (1,617 entidades)
- Embedding del título + summary
- Idempotent por `law_id` UNIQUE
- Target: <1h corrida full

**Flow 2: pe_seace**
- Source: OCDS API `contratacionesabiertas.osce.gob.pe`
- Filtros: últimos 24 meses, entidades grandes (MINSA, MEF, MTC, ESSALUD, gobiernos regionales top 10)
- Cada contrato → entity tipo `contract` + edges a empresa adjudicataria + entidad pública compradora
- Incremental por OCID
- Target: <2h corrida full

**Flow 3: pe_jne_pdfs**
- Source: itera candidatos JNE 2026 (35 presidenciales + 190 congresistas = 225 docs)
- Para cada uno: descarga PDF, sube a GCS `sabueso-jne-pdfs`, extrae texto, parsea estructura
- Crea entity persona + claims (estudios, patrimonio, cargos previos)
- Embeddings de declaraciones para búsqueda semántica

**Deploy:**
- Dockerfile pipeline con cocoindex + PyMuPDF + Tika
- `gcloud run jobs deploy pipeline-ingest`
- `.github/workflows/ingest.yml` con `workflow_dispatch` inputs (`flow`, `country`)

**Acceptance Criteria:**
- [ ] `pnpm dev` en `apps/pipeline` corre flow dummy local
- [ ] Flow pe_legalize completa con 1,617 entidades insertadas
- [ ] Flow pe_seace completa con ≥10K contracts
- [ ] Flow pe_jne_pdfs completa con ≥150 PDFs procesados (algunos fallan, OK)
- [ ] Incremental: 2da corrida no duplica ni reprocesa lo ya hecho
- [ ] Embeddings searchables con `query_legalize_pe(semantic=true)`
- [ ] GitHub Actions `ingest.yml` con manual dispatch funcional
- [ ] Cloud Run Job logs en Cloud Logging

**Files:**
- `apps/pipeline/pyproject.toml`
- `apps/pipeline/flows/{pe_legalize,pe_seace,pe_jne_pdfs}_flow.py`
- `apps/pipeline/flows/common/{embedding,extract,upsert}.py`
- `apps/pipeline/Dockerfile`
- `.github/workflows/ingest.yml`

**Technical notes:**
- Reservar tiempo: la corrida full de los 3 flows puede tomar 4-6h. Hacerlo Mié 13 noche o Jue 14.
- Embedding cost: ~$0.02 por 1M tokens en `text-embedding-3-small`. 1,617 leyes ~10K tokens cada uno = 16M tokens = $0.32. Asumible.
- Si JNE bloquea descarga masiva, throttle a 1 PDF/3s.

---

### S-16 · PDF Export

**Title:** `[Infra+Frontend] PDF generator Job (Playwright) + GCS + signed URLs + UI`  
**Priority:** P1 · **Estimate:** 6pts · **Labels:** `p1`, `wt-infra`, `wt-frontend`  
**Dependencies:** S-13  
**Bloquea:** —

**Description:**

Generación server-side de PDFs del dossier. Cloud Run Job con Playwright que renderiza la página dossier-only en print mode, sube a GCS, retorna signed URL. Botón "Exportar PDF" en frontend.

**Scope incluido:**

**PDF Job:**
- Dockerfile `apps/pdf` con Playwright + chromium pre-installed
- `main.py` entrypoint: recibe `--investigation-id`, fetch dossier URL, page.pdf(), upload GCS
- Watermark/footer: timestamp, QR code, disclaimer
- Sube a `sabueso-dossiers` bucket
- Genera signed URL 7 días
- UPDATE en tabla `pdf_exports(investigation_id, gcs_path, signed_url, expires_at, status)`

**API:**
- `POST /api/v1/export-pdf/{investigation_id}` → encola job + INSERT pdf_exports status=pending → retorna `{job_id}`
- `GET /api/v1/export-pdf/{job_id}` → retorna status + signed_url si done

**Frontend:**
- Botón "Exportar PDF" en `DossierPanel`
- Click → POST + modal con loading state
- Polling cada 2s al status endpoint
- Cuando done: download attr en `<a>` que abre signed URL
- Toast de éxito/error

**Acceptance Criteria:**
- [ ] Dockerfile pdf builds <1GB
- [ ] `gcloud run jobs deploy pdf-generator` exitoso
- [ ] Manual test: trigger job con investigation_id válido → PDF en `sabueso-dossiers`
- [ ] PDF tiene: portada con nombre entity, secciones del dossier, footer con timestamp + QR + disclaimer
- [ ] Signed URL accesible desde browser sin auth
- [ ] Frontend: click Exportar → modal aparece → polling → download disponible <60s
- [ ] PDF print stylesheet aplicado: márgenes A4, tipografía legible
- [ ] Migration 011 con tabla `pdf_exports`

**Files:**
- `apps/pdf/src/{main,renderer,storage,watermark}.py`
- `apps/pdf/Dockerfile`
- `apps/pdf/pyproject.toml`
- `apps/api/src/routes/export.py`
- `apps/api/src/services/pdf.py`
- `apps/web/components/investigation/ExportPdfButton.tsx`
- `infra/supabase/migrations/011_pdf_exports.sql`

**Technical notes:**
- Playwright en Cloud Run: usar `--no-sandbox` flag + `mcr.microsoft.com/playwright/python` base image.
- QR code: librería `qrcode` Python, embed como data URI en HTML del print mode.
- Si Playwright es muy pesado, fallback a WeasyPrint (HTML→PDF pure Python, sin browser).

---

### S-17 · Demo replay mode

**Title:** `[Demo+Frontend] Pre-cache 5 demos + replay engine + localStorage + Director + live toggle`  
**Priority:** P0 · **Estimate:** 6pts · **Labels:** `p0`, `wt-frontend`, `wt-demo`  
**Dependencies:** S-11, S-15  
**Bloquea:** S-20

**Description:**

Hacer el demo del lunes a prueba de balas. Pre-grabar 5 investigaciones reales, implementar replay engine que las reproduce con timing artificial, localStorage backup, hidden Director mode, toggle live/replay.

**Scope incluido:**

**Selección de 5 funcionarios:**
- Aplicar criterios neutrales del C4 sección 12.1
- Diversidad: 1 candidato presidencial 2026, 1 congresista actual con caso documentado, 1 ex-presidente, 1 gobernador regional, 1 funcionario técnico MEF/MINSA
- Validar accesibilidad de fuentes para cada uno
- Idealmente: consulta breve con periodista de OjoPúblico, IDL Reporteros o Convoca

**Pre-cache:**
- Lanzar 5 investigaciones reales en modo live día 0 noche
- Validar editorialmente cada dossier
- Si algún output es problemático (información errónea, sesgo), re-correr o reemplazar
- Snapshot SQL: `pg_dump --table=investigations --table=investigation_events --table=claims --table=edges` con `WHERE investigation_id IN (5 ids)` para restore si algo se borra

**Replay engine:**
- `useInvestigation` detecta query `?mode=replay`
- Fetch events ordered by id desde Supabase
- Re-emite con delays calculados (total ~10s)
- Estado React idéntico al modo real

**localStorage backup:**
- `useLocalStorageInvestigation`: save en cada update con throttle 500ms
- Restore al mount mientras carga SSE
- Funciona offline si Supabase cae

**Director mode (Cmd+Opt+D hidden):**
- Overlay aparece sobre el Cinema mode
- Controles: Play/Pause, Forward, End, Slider de timeline
- Solo activo en `mode=replay`

**Live toggle:**
- Botón visible "Modo en vivo · esto tomará 60-180s"
- En home, dropdown next to entity selector
- Toggle entre replay (5 cacheadas) y live (real, costos reales)
- Banner explicativo: "demo cacheado" vs "investigación real con APIs activas"

**Acceptance Criteria:**
- [ ] 5 funcionarios seleccionados con justificación documentada en `docs/demo-targets.md`
- [ ] 5 investigations status='complete' en Supabase, dossiers editorialmente validados
- [ ] Snapshot SQL guardado en `infra/supabase/seed/demo_investigations.sql`
- [ ] Replay engine: URL `/i/{id}?mode=replay` reproduce con timing ~10s
- [ ] Indistinguible visualmente de investigación en vivo
- [ ] localStorage: kill SSE conexión, refresh, último estado visible inmediatamente
- [ ] Director mode: Cmd+Opt+D abre overlay, play/pause funcional, scrub funcional
- [ ] Botón Modo en vivo: toggle correcto, banner correcto
- [ ] Cada uno de los 5 demos: video screen-recording 60s subido a Vercel Blob
- [ ] Time-to-wow: <8s desde click hasta primer hallazgo rojo visible

**Files:**
- `docs/demo-targets.md`
- `infra/supabase/seed/demo_investigations.sql`
- `apps/web/hooks/{useInvestigation,useLocalStorageInvestigation}.ts` (extender con replay logic)
- `apps/web/components/director/DirectorMode.tsx`
- `apps/web/components/home/LiveOrReplayToggle.tsx`
- `scripts/record-demos.ts` (helper para correr 5 investigations y persistir)

**Technical notes:**
- Replay timing: si la investigación real tomó 90s, comprimir a 10s = factor 9x. Distribuir delays proporcionalmente.
- Director mode keyboard listener solo activo si `mode=replay`.
- Para evitar memory leaks: cleanup intervals en cleanup del useEffect.

---

### S-18 · Multi-país preview

**Title:** `[Cross] Country selector + 3 tools legalize {cl, mx, sv} + LangGraph branch`  
**Priority:** P1 · **Estimate:** 5pts · **Labels:** `p1`, `wt-data`, `wt-frontend`, `wt-agents`  
**Dependencies:** S-04, S-06, S-09  
**Bloquea:** —

**Description:**

Hacer el sistema multi-país demoable. Selector en UI, 3 tools de legalize-* adicionales, branching condicional en LangGraph que usa subset reducido de investigadores para países no-Perú.

**Scope incluido:**

**Country selector UI:**
- Dropdown en navbar con 4 flags 🇵🇪 🇨🇱 🇲🇽 🇸🇻
- Persist en cookie + URL param `?c=cl`
- Banner amarillo "Modo preview · datos limitados" si != pe

**Tools adicionales:**
1. `query_legalize_cl(query, semantic)` — conector BCN Chile (legalize-cl repo si existe, sino scraping HTML)
2. `query_legalize_mx(query, semantic)` — LeyesNet o similar, puede ser mock con dataset estático para preview
3. `query_legalize_sv(query, semantic)` — Asamblea Legislativa El Salvador, mock OK para preview

**LangGraph branching:**
- Si `state.country != "pe"`: Sabueso plan usa subset reducido (Buscador + Letrado + Periodista solamente)
- Emite event `preview_mode_warning` que el frontend renderiza como banner
- Tasadora/Contador/Detective no se ejecutan en preview

**Acceptance Criteria:**
- [ ] Country dropdown visible en navbar, persiste selección
- [ ] Banner "Modo preview" aparece en /app y /i/[id] si país != pe
- [ ] Las 3 tools legalize implementadas (mocks aceptables para mx y sv)
- [ ] Test: investigation con country=cl completa usando 3 investigadores
- [ ] Test: investigation con country=mx completa con datos placeholder
- [ ] LangGraph branch correcto: state.country drives plan
- [ ] Sabueso prompt menciona país en el contexto: "Investigando en {country}, fuentes disponibles: {limited_list}"

**Files:**
- `apps/web/components/CountrySelector.tsx`
- `apps/web/components/PreviewModeBanner.tsx`
- `apps/worker/src/tools/cl/legalize.py`
- `apps/worker/src/tools/mx/legalize.py`
- `apps/worker/src/tools/sv/legalize.py`
- `apps/worker/src/orchestrator/nodes/plan.py` (modificar para branching)

**Technical notes:**
- legalize-cl realmente existe (Crafter Station equivalente). Usar.
- México y Salvador: mocks con 5-10 leyes hardcoded para que el demo funcione. Mejor que esfuerzo real para preview.

---

### S-19 · Share + SEO + Subscriptions

**Title:** `[Frontend+API] SSR dossier + OG image + share + Zavu WhatsApp`  
**Priority:** P1 · **Estimate:** 8pts · **Labels:** `p1`, `wt-frontend`, `wt-api`  
**Dependencies:** S-13  
**Bloquea:** —

**Description:**

Hacer las investigaciones virales (compartibles con OG cards bonitas) y suscribibles (alertas WhatsApp vía sponsor Zavu).

**Scope incluido:**

**SSR dossier público:**
- Confirmar que `/i/[id]/dossier` es completamente SSR (Server Component)
- Fetch desde Supabase Postgres directo (no via SSE)
- HTML inicial completo, listo para crawlers
- Loading skeleton si está aún en progress

**Vercel OG Image API:**
- `app/api/og/route.tsx` con `ImageResponse` from next/og
- Recibe `?id=...`, fetch metadata mínima
- Renderiza imagen 1200x630 con: avatar/foto entity, score de alertas, nombre, "Sabueso · Investigación pública"
- Fuentes pre-loaded
- Cacheable con `revalidate=3600`

**Share button + flow:**
- Botón "Compartir" en dossier header
- Dialog con 3 opciones: Copy URL, Tweet preformatted, WhatsApp share deeplink
- Tweet incluye nombre entity + URL + emoji 🐕‍🦺

**Public/Private toggle:**
- Switch UI en header de investigación (solo si auth + es owner)
- UPDATE `investigations.is_public`
- RLS respeta el cambio

**Suscripciones Zavu:**
- Cliente Python `apps/api/src/services/zavu.py` con `send_whatsapp(number, message, template_id?)`
- Endpoint `POST /api/v1/subscribe` requiere auth, INSERT en `subscriptions`
- Trigger SQL after INSERT claim: detecta nuevas claims sobre entidades suscritas → pgmq.send `notification_queue`
- Job dedicado consume queue y envía WhatsApp (mock funcional para demo: log + opcional envío real al jurado)
- Frontend: modal "Suscribir a alertas" con input phone + país code + confirmación

**Acceptance Criteria:**
- [ ] `curl https://sabueso.vercel.app/i/{id}/dossier` retorna HTML completo del dossier
- [ ] Lighthouse SEO score >90 en /dossier
- [ ] `/api/og?id={uuid}` retorna PNG válida 1200x630 con datos correctos
- [ ] Compartir URL en Twitter: preview muestra OG image
- [ ] Share dialog 3 opciones funcionales
- [ ] Toggle público/privado actualiza DB y RLS lo respeta (anon no ve si privada)
- [ ] Zavu integration: test send a número propio funciona
- [ ] Trigger SQL detecta nuevo claim y encola
- [ ] Modal suscripción valida formato phone E.164

**Files:**
- `apps/web/app/(app)/i/[id]/dossier/page.tsx` (SSR strict)
- `apps/web/app/api/og/route.tsx`
- `apps/web/components/investigation/ShareDialog.tsx`
- `apps/web/components/investigation/PublicToggle.tsx`
- `apps/web/components/investigation/SubscribeDialog.tsx`
- `apps/api/src/routes/subscribe.py`
- `apps/api/src/services/zavu.py`
- `infra/supabase/migrations/012_subscription_trigger.sql`

**Technical notes:**
- OG image: usar `@vercel/og` library. Fuentes via `fetch()` cached.
- Zavu sandbox key (si tiene): probar antes del demo.
- En demo en vivo: configurar sub para el número del jurado, dispararse en momento exacto del pitch.

---

### S-20 · Observabilidad + Security + CI/CD + Demo prep + Pitch

**Title:** `[Cross] LangSmith + rate limit + Workload Identity + workflows + pitch + README`  
**Priority:** P0 · **Estimate:** 10pts · **Labels:** `p0`, `wt-infra`, `wt-demo`  
**Dependencies:** S-03, S-10, S-17  
**Bloquea:** —

**Description:**

Cerrar el sistema con todos los aspectos cross-cutting + preparación del pitch del lunes. Esto se ejecuta en paralelo a otras tasks pero algunas piezas (rate limit, smoke test) bloquean producción.

**Scope incluido:**

**Observabilidad:**
- LangSmith env vars en Cloud Run (api + worker): `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`
- Decorators `@traceable` en funciones clave del orchestrator
- structlog config con processors JSON en api + worker
- Cost tracking per investigation visible en `investigations.cost_usd`

**Security & rate limit:**
- Proxy Next 16 (`apps/web/proxy.ts`, ex-`middleware.ts`) con Vercel KV INCR + TTL
- Limits: 10/IP anónima/24h, 50/user autenticado/24h, 300 search/IP/hour, 20 export-pdf/IP/24h
- 429 con Retry-After header
- Double-check rate limit en FastAPI service (Vercel KV REST API)
- CORS estricto: solo `sabueso.vercel.app` + localhost
- CSP headers en next.config.js
- Disclaimer legal en footer + cada dossier inicio

**CI/CD:**
- Workload Identity Federation entre GitHub Actions y GCP (pool + provider + binding)
- `.github/workflows/ci.yml`: matrix lint+test (web + 4 python apps)
- `.github/workflows/deploy-api.yml`: paths filter, build + deploy a Cloud Run + smoke test post-deploy
- `.github/workflows/deploy-jobs.yml`: matrix sobre los 3 Cloud Run Jobs
- Vercel git integration: preview en PRs, production en merge
- Smoke test integrado: POST /investigate + verify ≥3 SSE events + status complete

**Demo prep & pitch:**
- `docs/pitch.md` con script de 3 min: dolor (30s) → demo en vivo (90s) → arquitectura (30s) → roadmap (30s)
- Slides opcionales (3-5 slides en slides.com o pitch.com)
- Demo video 60s screen recording con voiceover
- README.md brutal: hero, video embedded, problema, solución, arquitectura diagram (export del C4), stack badges, demo URL, getting started, sponsors
- Ensayo: 10 pases del pitch cronometrado a 3:00 min exacto

**Acceptance Criteria:**
- [ ] LangSmith dashboard muestra traces de investigations reales con tools + tokens + costo
- [ ] Cloud Logging muestra logs estructurados JSON
- [ ] Rate limit: 11ª request anónima en 24h → 429
- [ ] CORS test: request desde origin no autorizado → bloqueado
- [ ] CSP headers presentes en responses
- [ ] Disclaimer visible en footer + cada dossier
- [ ] GitHub Actions: PR runs CI, merge a main runs deploys
- [ ] Workload Identity: deploys funcionan sin service account key local
- [ ] Smoke test pasa en CI después de cada deploy a Cloud Run
- [ ] Pitch script escrito y cronometrado <3:00 min
- [ ] Demo video <60s, subido a Vercel Blob, link en README
- [ ] README.md con todos los elementos (hero, video, badges, sponsors, demo link)
- [ ] Lo que ensayes el pitch al menos 10 veces antes del lunes
- [ ] Easter egg footer "🐕‍🦺 Construido en 4 días con Emdash + Claude + Kimi"

**Files:**
- `apps/web/proxy.ts` (Next 16 proxy)
- `apps/api/src/auth/rate_limit.py`
- `apps/api/src/observability/{logging,tracing,metrics}.py`
- `apps/web/next.config.js` (CSP headers)
- `.github/workflows/{ci,deploy-api,deploy-jobs,smoke-test}.yml`
- `infra/gcp/workload-identity.tf` o instructions in `docs/setup-wif.md`
- `docs/pitch.md`
- `docs/demo-video.mp4` (placeholder, real subido a Blob)
- `README.md` (rewrite final)

**Technical notes:**
- Workload Identity Federation setup: una sola vez, ~30 min con la doc oficial.
- README hero: usar `placeholder.com` o screenshot real del Cinema Mode.
- Pitch: practicar en voz alta. Grabarse en video, criticar. Iterar.

---

## 3. Diagrama de dependencias

```
S-01 (setup) ─┬─► S-02 (db) ──┬─► S-03 (api) ──┬─► S-07 (worker job)─┐
              │               │                │                     │
              │               │                ├─► S-08 (SSE) ───────┤
              │               │                │                     │
              │               ├─► S-04 (tools)─┴─► S-05 (investigtr) ┤
              │               │                                       │
              │               │                ┌─► S-06 (LangGraph) ─┤
              │               │                │                     ▼
              │               │                │                S-10 (E2E)──┬─► S-11 (resto invest.)─┐
              ├─► S-09 (frontend skel) ────────┘                              │                      │
              │                                                               │                      ▼
              │                                                               ▼                S-17 (replay)
              │                                                          S-12 (Cinema Mode)         │
              │                                                                │                    ▼
              │                                                                ├─► S-13 (viz)  S-20 (prep)
              │                                                                ├─► S-14 (pages)
              │                                                                ├─► S-15 (pipeline)
              │                                                                ├─► S-16 (PDF)
              │                                                                ├─► S-18 (multi-país)
              │                                                                ├─► S-19 (share)
              └─► S-20 (cross: CI/CD + observability + pitch)
```

---

## 4. Plan de ejecución por día

**Mié 13 - Vie 15 (pre-event, opcional según rules):**
- S-01 (foundation)
- Empezar S-02 si reglas permiten infra setup pre-event

**Sáb 15 (kickoff, 18:00 hasta madrugada, ~10h):**
- Paralelo en 3 worktrees:
  - wt-data: S-02 (db) → S-04 (tools, parcial)
  - wt-api: S-03 (api skeleton)
  - wt-frontend: S-09 (frontend skeleton)
- Vos personalmente: S-05 + S-06 (investigators framework + LangGraph), las piezas más sensibles

**Dom 16 (todo el día, ~14h):**
- Mañana paralelo en 4 worktrees:
  - wt-data: S-04 (terminar 8 tools)
  - wt-agents: S-06 (terminar LangGraph) → S-10 (E2E)
  - wt-infra: S-07 (worker job)
  - wt-api: S-08 (SSE)
- Mediodía: hito crítico S-10 (primer E2E). Si no funciona, parar y arreglar.
- Tarde: S-11 (resto investigadores) + S-12 (Cinema Mode)
- Noche: S-15 (pipeline ingest, correr durante la noche)

**Lun 17 (8h hasta entrega):**
- Mañana: terminar S-12 + S-13 (Sankey/Timeline) + S-17 (replay mode)
- **FREEZE features al mediodía.**
- Tarde: S-20 (observability + CI/CD + pitch + README + demo video)
- Última hora: ensayo pitch ×10

**Diferibles si no llegás:** S-14 (Redacción/Hemeroteca), S-16 (PDF), S-18 (multi-país), S-19 (share/Zavu)

---

## 5. Conteo final

- **20 tasks** consolidando 134 tasks granulares
- **P0:** 13 tasks (~110 pts)
- **P1:** 6 tasks (~37 pts)
- **P2:** 1 task (parcial dentro de S-19)
- **Estimación total:** ~160 pts

Con 5 worktrees paralelos y agentic coding eficiente (Claude Code / Codex / Kimi Code), estos 20 tasks son ejecutables en 4 días por un solo developer.

---

## 6. Cómo crear esto en Linear vía MCP

### Opción rápida (recomendada)

Desde Claude con Linear MCP conectado:

> "Lee el archivo `sabueso-linear-tasks-condensed.md`. Crea en Linear el project 'Sabueso v1 · hack@latam 2026' en el team Sabueso. Después crea las 20 issues de la sección 2 con title, description (incluye Description + Acceptance Criteria + Files + Technical notes), priority, estimate y labels. No crees parent epics, todas son issues normales. Reportame los IDs creados."

Después: 

> "Crea los issue relations de tipo 'blocks' según el diagrama de dependencias en la sección 3."

### Opción manual

20 issues son creables a mano en 30-45 min en la UI de Linear. Cada uno copy-paste desde este archivo.

---

**Final del documento.**  
**Listo para Linear MCP en bulk.**
