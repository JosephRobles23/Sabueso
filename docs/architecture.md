# Sabueso · Architecture Document (C4 Model)

**Version** 1.0  
**Fecha** 2026-05-13  
**Estado** Locked-in para hackathon hack@latam 2026  
**Audiencia** Equipo de desarrollo (solo dev + agentes via Emdash), jurado del hackathon, futuros contribuidores  
**Stack confirmado** Next.js 16 + Vercel · Python FastAPI + LangGraph en Cloud Run · Supabase Postgres · OpenRouter · LangSmith

---

## Tabla de contenidos

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Objetivos y atributos de calidad](#2-objetivos-y-atributos-de-calidad)
3. [C4 Level 1 — System Context](#3-c4-level-1--system-context)
4. [C4 Level 2 — Containers](#4-c4-level-2--containers)
5. [C4 Level 3 — Components](#5-c4-level-3--components)
6. [C4 Level 4 — Code (críticos)](#6-c4-level-4--code-críticos)
7. [Modelo de datos](#7-modelo-de-datos)
8. [Diagramas de secuencia](#8-diagramas-de-secuencia)
9. [Cross-cutting concerns](#9-cross-cutting-concerns)
10. [Arquitectura de despliegue](#10-arquitectura-de-despliegue)
11. [Estrategia multi-país](#11-estrategia-multi-país)
12. [Estrategia del demo](#12-estrategia-del-demo)
13. [Architecture Decision Records (ADRs)](#13-architecture-decision-records-adrs)
14. [Open questions y riesgos](#14-open-questions-y-riesgos)
15. [Apéndices](#15-apéndices)

---

## 1. Resumen ejecutivo

**Sabueso** es un sistema multi-agente de investigación periodística que automatiza la auditoría de funcionarios públicos, candidatos y empresas en LATAM, cruzando datos abiertos del Estado (legalización, contratos, patrimonio, registros, prensa) y entregando un *dossier* con evidencia citada y nivel de confianza por hallazgo.

### Tecnologías clave

| Capa | Tecnología |
|---|---|
| Frontend | Next.js 16 (App Router) + Vercel AI SDK 6 + AI Elements + cosmos.gl + shadcn/ui + Tailwind v4 |
| Backend | Python 3.12 + FastAPI + LangGraph (orchestrator) + Scrapling + CocoIndex |
| LLMs | OpenRouter como gateway único: Claude Sonnet 4.6 (orquestador + cache), Kimi K2.6 y DeepSeek V4-Flash (workers), GPT-4o (MoA verifier) |
| Datos | Supabase Postgres + pgvector + pgmq + pg_cron + pg_trgm |
| Cómputo | GCP Cloud Run service (API + SSE) + Cloud Run Jobs (workers + ingestion + PDF) |
| Storage | Google Cloud Storage para PDFs |
| Observabilidad | LangSmith (trazas agentes) + Cloud Logging + Vercel Analytics |
| CI/CD | GitHub Actions desde día 1 |
| Hosting | Vercel (frontend, subdominio) + GCP (backend, free trial 3 meses) |

### Decisiones arquitectónicas clave

1. **Orquestador-worker con LangGraph** sobre Postgres checkpointer para investigaciones reentrantes y trazables.
2. **SSE directo desde Cloud Run** (no Supabase Realtime) para entrega de eventos de investigación al frontend, vía Postgres LISTEN/NOTIFY.
3. **Tools inline en FastAPI** con schemas Pydantic exportables, preparados para migrar a MCP servers post-hackathon.
4. **Modelos vía OpenRouter** como gateway único, simplificando billing, fallback y observabilidad.
5. **Verificación MoA siempre activa** con 3 modelos diversos + agregador, garantizando consistencia del dossier.
6. **Multi-país desde día 1**: Perú como first-class, Chile + México + El Salvador como preview demoable con conectores limitados.
7. **Cloud Run multi-región como sustituto de proxies pagos** para rotación de IPs durante scraping.
8. **i18n + auth opcional + investigaciones públicas por defecto + share links con SSR + OG image**.

### Costo esperado

- Por investigación completa: **~$0.65** (5 subagentes × Kimi/V4 + Sabueso Sonnet con cache + MoA siempre activo).
- Demo + post-evento (~100 investigaciones): **~$65** en LLMs.
- Infraestructura: $0 (free tiers Vercel + GCP 3-month trial + Supabase + LangSmith).

---

## 2. Objetivos y atributos de calidad

### 2.1 Objetivos funcionales

| ID | Objetivo | Prioridad |
|---|---|---|
| O1 | Permitir investigar un funcionario/candidato/empresa con una sola query, sin auth | P0 |
| O2 | Mostrar la investigación en vivo con visualización Cinema (grafo + log + dossier) | P0 |
| O3 | Generar un dossier compartible con citas verificables y confianza por claim | P0 |
| O4 | Soportar Perú first-class (6 fuentes integradas) + 3 países preview (legalize-{cl,mx,sv}) | P1 |
| O5 | Exportar dossier como PDF firmado, descargable desde Cloud Storage | P1 |
| O6 | Modo en vivo real Y modo replay sintético para demo | P0 |
| O7 | Suscripciones a alertas (vía Zavu WhatsApp) para usuarios autenticados | P2 |
| O8 | Comparador de N candidatos lado a lado con heatmap de riesgo | P2 |
| O9 | i18n español + inglés desde día 1 (solo es-PE activo, en preparado) | P1 |

### 2.2 Atributos de calidad

| Atributo | Requisito |
|---|---|
| **Latency (UX)** | Primer evento visible al usuario en <2s después de submit. Investigación completa en <120s para entidad pre-cacheada, <180s para entidad nueva |
| **Cost ceiling** | $1.00 por investigación promedio. Cap duro $3.00 por investigación (kill switch) |
| **Throughput** | 10 investigaciones concurrentes mínimo durante demo. 50 burst peak |
| **Availability** | 99% durante el evento del fin de semana. No multi-region failover, monoregión es OK |
| **Auditability** | 100% de claims con source_url + extract + hash de snapshot. Confidence score por claim |
| **Observability** | Traza completa de cada subagente + tool call en LangSmith. Errores con stack en Cloud Logging |
| **Rate limit** | 10 investigaciones/IP anónima/día. 50 investigaciones/usuario autenticado/día |
| **Security** | API keys en GCP Secret Manager. RLS habilitado en Supabase. CORS estricto. CSP headers |
| **Accessibility** | WCAG 2.1 AA. Contraste 4.5:1. Keyboard nav. Reduced-motion respect. Aria-live para streaming |
| **i18n** | UI strings 100% en namespace `es` + `en` (estructura). Datos siempre en idioma original |

### 2.3 No-objetivos (explícitos)

- **No es un sistema judicial.** No afirma delitos, no imputa culpa. Reporta hallazgos verificables con confianza.
- **No reemplaza un periodista.** Es asistente; el periodista valida y publica.
- **No hace análisis predictivo ni de sentimiento de medios.** Versión 1.
- **No tiene auth obligatoria.** Hasta v2.
- **No soporta multi-tenancy ni teams.** Hasta v2.
- **No tiene API pública en v1.** El frontend es el único cliente.

---

## 3. C4 Level 1 — System Context

### 3.1 Diagrama de contexto

```
                       ╔══════════════════════════════════════════════╗
                       ║                                              ║
                       ║              SABUESO                         ║
   ┌────────────────►  ║   Sistema multi-agente de                    ║
   │  HTTPS           ║   investigación periodística                 ║
   │                   ║                                              ║
   │                   ║   - Acepta queries sobre entidades públicas  ║
┌──┴──────────────┐    ║   - Orquesta 7 investigadores especializados ║
│   USUARIOS       │   ║   - Cruza fuentes oficiales y prensa         ║
│                  │   ║   - Entrega dossier con evidencia citada     ║
│ • Periodistas    │   ║   - Visualización Cinema en tiempo real      ║
│ • Ciudadanos     │   ║                                              ║
│ • Auditores      │   ╚═══════╤═════╤═════╤═════╤═════╤═════╤═══════╝
│ • Jurado hack    │           │     │     │     │     │     │
│ • Visitantes     │           ▼     ▼     ▼     ▼     ▼     ▼
└──────────────────┘     ┌─────┴┐  ┌──┴───┐ ┌──┴──┐ ┌─┴──┐ ┌┴───┐ ┌┴────┐
                         │ LLMs │  │legali│ │SEACE│ │JNE │ │ El │ │Supa-│
                         │      │  │ze-pe │ │OCDS │ │Decl│ │Per.│ │base │
                         │OpenR │  │.cl   │ │     │ │    │ │    │ │Auth │
                         │outer │  │.mx   │ │     │ │SUNA│ │SUNA│ │     │
                         │      │  │.sv   │ │     │ │ RP │ │ T  │ │     │
                         └──────┘  └──────┘ └─────┘ └────┘ └────┘ └─────┘
                                                                    │
                                                                    ▼
                                                              ┌──────────┐
                                                              │  Zavu    │
                                                              │ WhatsApp │
                                                              │ (alertas)│
                                                              └──────────┘
```

### 3.2 Actores

| Actor | Descripción | Caso de uso primario |
|---|---|---|
| **Periodista de investigación** | Profesional buscando leads y cruces de datos | Lanzar investigación profunda + exportar dossier para artículo |
| **Ciudadano informado** | Votante o auditor cívico | Verificar perfil de candidato antes de votar |
| **Auditor / Funcionario de contraloría** | Profesional de control | Cruce sistemático de patrimonio vs contratos |
| **Jurado hack@latam** | Evaluadores del hackathon | Probar el demo, evaluar arquitectura y resultados |
| **Visitante orgánico** | Usuario que llega de link compartido | Consumir un dossier ya generado |

### 3.3 Sistemas externos

| Sistema | Tipo | Uso |
|---|---|---|
| **OpenRouter** | Gateway LLM | Punto único para Claude Sonnet 4.6, Claude Opus 4.7, Kimi K2.6, DeepSeek V4-Flash, GPT-4o |
| **LangSmith** | Observabilidad de agentes | Trazas de orquestador y subagentes, debugging |
| **legalize-pe / -cl / -mx / -sv** | API datos legales | Normas, leyes, gaceta oficial por país |
| **OECE OCDS** (Perú) | API contratos públicos | Adjudicaciones, montos, beneficiarios |
| **JNE Declara** (Perú) | Portal electoral | Hojas de vida de candidatos como PDF |
| **SUNARP** (Perú) | Registro de propiedades | Inmuebles, vehículos, empresas |
| **SUNAT** (Perú) | Tributario | RUC, representantes legales |
| **El Peruano** | Diario oficial | Decretos, resoluciones, nombramientos |
| **Manolo.rocks** | Portal Transparencia Estado | Cargos públicos por DNI |
| **datos.gob.pe** | CKAN nacional | 4,500+ datasets oficiales |
| **Supabase** | BaaS (Auth, DB, Realtime opcional, Storage) | Persistencia primaria |
| **Google Cloud Platform** | IaaS (Cloud Run, Storage, Secret Manager) | Cómputo y storage de PDFs |
| **Vercel** | Hosting frontend + Blob + KV | UI, rate limit, perks del hackathon |
| **Zavu** | API mensajería (sponsor) | Alertas WhatsApp/SMS |

### 3.4 Flujos de alto nivel

- **Lectura/Investigación:** Usuario → Frontend Vercel → Cloud Run API → OpenRouter (LLMs) + Supabase (datos cacheados) + Scrapers (datos frescos) → Supabase (persistencia) → SSE stream → Frontend
- **Compartir:** Usuario → Frontend → Server-rendered dossier público con OG image → URL `/i/[id]` compartible
- **Exportar PDF:** Usuario click "Exportar" → API → Cloud Run Job genera HTML → Playwright PDF → GCS bucket → Signed URL → Frontend descarga
- **Alertas:** Usuario suscribe vía Zavu → API guarda subscription → Trigger en Postgres cuando hay updates → Job envía WhatsApp

---

## 4. C4 Level 2 — Containers

### 4.1 Diagrama de containers

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  USUARIO (browser)                                                              │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │ HTTPS
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────────┐  ┌─────────────────────┐  ┌──────────────────────────┐
│  C1 FRONTEND      │  │  C2 VERCEL KV        │  │  C3 VERCEL BLOB          │
│  Next.js 16 App   │  │  Rate limit + cache  │  │  PDFs exportados (link)  │
│  Vercel · Edge    │  │  Free tier           │  │  Free tier 0.5 GB        │
└─────────┬─────────┘  └─────────────────────┘  └──────────────────────────┘
          │ fetch + SSE
          │ (api.sabueso.vercel.app)
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  C4 API SERVICE        ·    GCP Cloud Run service                         │
│  Python 3.12 + FastAPI + Uvicorn workers                                  │
│  Región principal: southamerica-east1 (São Paulo, latencia óptima Perú)   │
│  min-instances=1 · max-instances=10 · timeout=3600s · concurrency=80      │
│                                                                            │
│  Responsabilidades:                                                       │
│  • POST /api/investigate          → encolar y devolver investigation_id   │
│  • GET  /api/stream/{id}          → SSE stream de eventos                 │
│  • GET  /api/investigations/{id}  → fetch del dossier final               │
│  • GET  /api/search?q=            → autocompletado pg_trgm                │
│  • POST /api/export-pdf/{id}      → encolar generación PDF                │
│  • POST /api/subscribe            → suscripción Zavu                      │
│  • GET  /api/healthz              → liveness                              │
│                                                                            │
│  Patrón SSE: cada conexión abre LISTEN investigation_{id} en Postgres     │
└──────────┬─────────────────────────────────────────────────────────────┬─┘
           │                                                              │
           │ pgmq.send / SELECT                                          │ NOTIFY listener
           ▼                                                              ▲
┌─────────────────────────────────────┐                          ┌─────────┴────────┐
│  C5 SUPABASE POSTGRES                │                          │  C6 INVESTIG.    │
│  • Postgres 16 + pgvector + pgmq    │ ◄── INSERT events ──────►│  WORKERS         │
│  • pg_cron + pg_trgm + tsvector     │                          │  GCP Cloud Run   │
│  • Realtime (no usado en v1)        │                          │  Jobs            │
│  • Auth (Google OAuth + magic)      │                          │                  │
│  • LangGraph checkpointer state     │                          │  • 1 job por     │
│                                     │                          │    investigación │
│  Tablas core:                       │                          │  • LangGraph     │
│  - entities, claims, edges          │                          │  • 7 subagentes  │
│  - investigations                   │                          │  • 60-min timeout│
│  - investigation_events             │                          │  • Multi-region  │
│  - tool_cache, sources              │                          │    para scraping │
│  - users, subscriptions             │                          └─────────┬────────┘
│  - i18n_messages                    │                                    │
└─────────────────────────────────────┘                                    │
                                                                           │
                                                                           ▼
                                                                  ┌────────────────┐
                                                                  │ C9 OpenRouter   │
                                                                  │ Gateway LLM    │
                                                                  └────────────────┘

┌─────────────────────────┐    ┌─────────────────────────┐    ┌─────────────────────────┐
│  C7 PIPELINE JOB         │    │  C8 PDF GENERATOR JOB    │    │  C10 CLOUD STORAGE      │
│  GCP Cloud Run Job       │    │  GCP Cloud Run Job       │    │  GCS bucket             │
│  CocoIndex incremental   │    │  Playwright + weasyprint │    │  PDFs originales JNE    │
│  Manual trigger (v1)     │    │  Sube a GCS, devuelve URL│    │  Dossiers exportados    │
│  Multi-region scrape     │    │  Signed URL 7 días        │    │  Lifecycle 90 días       │
│  Usa Scrapling           │    │                          │    │                          │
└─────────────────────────┘    └─────────────────────────┘    └─────────────────────────┘

┌─────────────────────────┐    ┌─────────────────────────┐
│  C11 GitHub Actions     │    │  C12 LangSmith           │
│  CI: lint + test        │    │  Trazas LangGraph        │
│  CD: deploy a Cloud Run │    │  Free tier 5K traces/mes │
│      deploy a Vercel    │    │                          │
└─────────────────────────┘    └─────────────────────────┘
```

### 4.2 Containers detallados

#### C1 · Frontend (Next.js 16 + Vercel)

- **Purpose:** UI/UX del usuario. Renderiza el Cinema mode, dossiers, búsqueda, comparador.
- **Technology:** Next.js 16, App Router, React 19, TypeScript 5.6+, Tailwind v4, shadcn/ui, Vercel AI SDK 6, AI Elements, cosmos.gl, @nivo/sankey, @visx/timeline, next-intl, TanStack Query, Supabase JS (solo Auth + read directo opcional).
- **Hosting:** Vercel, subdominio gratuito `sabueso.vercel.app` (decidido por usuario).
- **Renderings:**
  - SSG para `/`, `/about`, páginas marketing.
  - SSR para `/i/[id]` (importante para SEO y OG cards).
  - Client-side para `/app/*` autenticadas y para Cinema mode (Realtime).
- **Auth:** Supabase Auth, Google OAuth + magic link. Opcional para investigar; requerido para suscribir alertas y guardar.
- **Routing i18n:** `next-intl` con prefijos `/es/...` y `/en/...`. Redirect inicial detecta `Accept-Language`. Default `es-PE`.
- **Servicios Vercel asociados:**
  - **Vercel KV** (Redis serverless): rate limit por IP + session storage de demos cacheados.
  - **Vercel Blob:** copia espejo de los PDFs (para CDN edge) — el primario está en GCS.
  - **Vercel Analytics + Speed Insights:** métricas del frontend.
  - **OG Image API:** generación dinámica de imagen social por dossier (`/api/og?investigation_id=...`).

#### C2 · Vercel KV

- **Purpose:** Rate limit + sesiones de demo + cache rápido.
- **Technology:** Vercel KV (Redis-compatible).
- **Datos guardados:**
  - `ratelimit:ip:{ip}:investigations` → counter con TTL 24h.
  - `ratelimit:user:{uid}:investigations` → counter con TTL 24h.
  - `demo-state:{user_session}:{investigation_id}` → estado del replay del demo.

#### C3 · Vercel Blob

- **Purpose:** Espejo de PDFs para descarga rápida desde edge.
- **Technology:** Vercel Blob storage.
- **Política:** subida desde el job de PDF (GCS primario), espejo en Blob para edge delivery con auto-purge a 30 días.

#### C4 · API Service (FastAPI en Cloud Run)

- **Purpose:** API HTTP/SSE punto único entre el frontend y el backend agéntico.
- **Technology:** Python 3.12, FastAPI, Uvicorn, asyncpg (Postgres async), pgmq-client.
- **Deployment:** GCP Cloud Run service, `southamerica-east1`, contenedor Docker.
- **Config:**
  - `min-instances=1` (evitar cold start)
  - `max-instances=10`
  - `timeout=3600s` (necesario para SSE de larga duración)
  - `concurrency=80`
  - `memory=1Gi · cpu=1`
  - `min-cpu-throttling=false` (mantener CPU mientras la conexión SSE esté abierta)
- **Endpoints:**
  ```
  POST   /api/v1/investigate           → encola investigación, retorna investigation_id en <500ms
  GET    /api/v1/stream/{id}           → SSE stream de eventos de la investigación (timeout 3500s)
  GET    /api/v1/investigations/{id}   → fetch dossier final (markdown + metadata)
  GET    /api/v1/investigations        → listado paginado (con filtros)
  GET    /api/v1/entities/{id}         → detalle de entidad
  GET    /api/v1/search?q=&country=    → autocompletado pg_trgm
  POST   /api/v1/export-pdf/{id}       → encola PDF job, devuelve job_id
  GET    /api/v1/export-pdf/{job_id}   → estado del PDF + signed URL si listo
  POST   /api/v1/subscribe             → suscripción a alertas
  GET    /api/v1/healthz               → liveness probe
  GET    /api/v1/readyz                → readiness (incluye check de Supabase)
  ```
- **Auth middleware:** opcional. Si el header `Authorization: Bearer <jwt>` está presente, valida contra Supabase. Si no, permite acceso anónimo con rate limit por IP.

#### C5 · Supabase Postgres

- **Purpose:** Persistencia única. Datos relacionales, vectores, eventos, cola, sesiones, checkpoints LangGraph.
- **Technology:** Postgres 16 con extensiones: `pgvector`, `pgmq`, `pg_cron`, `pg_trgm`, `tsvector`, `uuid-ossp`.
- **Plan:** Supabase Free tier (500 MB DB, 2 GB bandwidth/mes, suficiente para hackathon y unas semanas post).
- **Conexión:** desde Cloud Run (API y Workers) vía pooler de Supabase (modo transaction).
- **Realtime:** habilitado pero **no usado en v1** (la entrega de eventos al frontend es vía SSE directo desde Cloud Run).

#### C6 · Investigation Workers (Cloud Run Jobs)

- **Purpose:** Ejecutar el LangGraph orchestrator + 7 subagentes para una investigación específica.
- **Technology:** Python 3.12, LangGraph, langchain-core, asyncpg, scrapling, openai-python (apuntado a OpenRouter), anthropic-python.
- **Deployment:** Cloud Run Job. Un job = una investigación.
- **Trigger:** API service llama `gcloud run jobs execute investigation-worker --args="--investigation-id=..."` (vía API REST de Cloud Run).
- **Multi-region:** los jobs corren en pool de regiones (`southamerica-east1`, `us-central1`, `us-east1`, `us-west1`, `europe-west1`) seleccionadas por round-robin desde el API service. Esto da rotación de IPs egress para scraping sin proxies pagos.
- **Config:**
  - `task-timeout=3600s`
  - `memory=2Gi · cpu=2`
  - `max-retries=1`
  - `parallelism=1` (no necesitamos paralelismo de tasks por job)

#### C7 · Pipeline Job (CocoIndex)

- **Purpose:** Ingesta incremental de fuentes pre-cacheadas (legalize-pe, OCDS, JNE PDFs, etc.) a Supabase con embeddings.
- **Technology:** Python 3.12, CocoIndex, Scrapling.
- **Trigger:** Manual en v1 (gcloud CLI o GitHub Actions workflow_dispatch). Cron diario se agrega post-hackathon.
- **Frecuencia:** ad-hoc durante hackathon, luego diario 3 AM Lima.

#### C8 · PDF Generator Job

- **Purpose:** Renderizar dossier markdown → HTML stylizado → PDF firmado en GCS.
- **Technology:** Python 3.12, Playwright (Chromium headless) o WeasyPrint, google-cloud-storage.
- **Trigger:** API service encola un job al endpoint `POST /api/v1/export-pdf/{id}`.
- **Output:** sube a GCS bucket `sabueso-dossiers`, devuelve signed URL válida 7 días.

#### C9 · OpenRouter

- **Purpose:** Gateway único para todos los LLMs. Unifica billing, fallback automático, observabilidad básica.
- **Modelos invocados:**
  - `anthropic/claude-sonnet-4.6` — orquestador con cache breakpoints
  - `anthropic/claude-opus-4.7` — sintetizador final del dossier (1 llamada por investigación)
  - `moonshot/kimi-k2.6` — subagentes ReWOO (El Buscador, El Contador, La Tasadora, El Letrado)
  - `deepseek/deepseek-v4-flash` — subagentes ReAct (El Detective, El Periodista)
  - `openai/gpt-4o` — uno de los 3 modelos del MoA verifier
- **Credit:** $20 perk del hackathon. Cap de uso configurado en dashboard de OpenRouter.

#### C10 · Google Cloud Storage

- **Purpose:** Storage primario de PDFs (originales JNE + dossiers exportados).
- **Technology:** GCS bucket regional `southamerica-east1`.
- **Buckets:**
  - `sabueso-jne-pdfs` — PDFs originales de hojas de vida (privado, signed URLs por sesión)
  - `sabueso-dossiers` — PDFs exportados (público con signed URL por share)
- **Lifecycle:** archive a Nearline a 90 días, delete a 365 días.

#### C11 · GitHub Actions

- **Purpose:** CI/CD. Lint, test, build, deploy.
- **Workflows:**
  - `ci.yml` — corre en cada PR: ruff + mypy + pytest backend; eslint + tsc + vitest frontend.
  - `deploy-api.yml` — corre en merge a `main`: build container, push a Artifact Registry, deploy a Cloud Run.
  - `deploy-jobs.yml` — corre en merge: build y registrar Cloud Run Jobs.
  - `deploy-web.yml` — Vercel autodetecta vía Git integration, no requiere workflow.
  - `ingest.yml` — manual `workflow_dispatch` para correr pipeline ingest.

#### C12 · LangSmith

- **Purpose:** Observabilidad de agentes. Trazas completas con tools, prompts, tokens, latencia.
- **Plan:** Free tier (5K traces/mes), suficiente para hackathon.
- **Integración:** variables `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` en Cloud Run env.

---

## 5. C4 Level 3 — Components

### 5.1 Componentes del Frontend (C1)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  C1 FRONTEND                                                             │
│                                                                          │
│  app/                                                                    │
│  ├── (marketing)/                  ── Páginas SSG públicas               │
│  ├── (app)/                                                              │
│  │   ├── layout.tsx                ── Shell autenticada                  │
│  │   ├── page.tsx                  ── Home con buscador                  │
│  │   ├── search/                                                         │
│  │   ├── i/[id]/                                                         │
│  │   │   ├── page.tsx              ── Cinema view default                │
│  │   │   ├── graph/page.tsx        ── Grafo full screen                  │
│  │   │   ├── sankey/page.tsx       ── Sankey                             │
│  │   │   ├── timeline/page.tsx     ── Timeline                           │
│  │   │   └── dossier/page.tsx      ── Lectura plana SSR                  │
│  │   ├── redaccion/                ── La Redacción (team)                │
│  │   ├── hemeroteca/               ── Archivo histórico                  │
│  │   └── comparar/                 ── Comparador                          │
│  └── api/                                                                │
│      ├── og/route.tsx              ── Vercel OG image dinámica           │
│      ├── proxy/[...path]/route.ts  ── Proxy SSE → Cloud Run (opcional)   │
│      └── ratelimit/route.ts        ── Vercel KV rate limit               │
│                                                                          │
│  components/                                                             │
│  ├── ai-elements/                  ── Conversation, Message, Reasoning,  │
│  │                                    Tool, Source (de Vercel)           │
│  ├── investigation/                                                      │
│  │   ├── InvestigatorAvatar.tsx                                          │
│  │   ├── InvestigatorWorkstation.tsx                                     │
│  │   ├── DelegationArrow.tsx                                             │
│  │   ├── InvestigatorBadge.tsx                                           │
│  │   ├── StatusPill.tsx                                                  │
│  │   ├── TaskCard.tsx                                                    │
│  │   ├── DrilldownPanel.tsx                                              │
│  │   ├── InvestigationGraph.tsx    ── cosmos.gl wrapper                  │
│  │   ├── DossierPanel.tsx                                                │
│  │   ├── TimelineScrubber.tsx                                            │
│  │   ├── EvidenceChip.tsx                                                │
│  │   └── ConfidenceBadge.tsx                                             │
│  ├── ui/                           ── shadcn/ui base                     │
│  └── i18n/                         ── language switcher                  │
│                                                                          │
│  lib/                                                                    │
│  ├── api.ts                        ── fetch wrapper a Cloud Run          │
│  ├── sse.ts                        ── EventSource client + reconnect     │
│  ├── supabase/                     ── client (Auth + optional reads)     │
│  ├── i18n/                         ── next-intl configuration            │
│  ├── kv.ts                         ── Vercel KV helpers                  │
│  └── localStorage.ts               ── Persistencia demo                  │
│                                                                          │
│  hooks/                                                                  │
│  ├── useInvestigation.ts           ── SSE + state machine                │
│  ├── useGraph.ts                   ── Mutaciones del grafo en vivo       │
│  └── useLocale.ts                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

**Patrones clave del frontend:**

- **Streaming SSE custom** (no `useChat` plain): hook `useInvestigation(id)` abre `EventSource` directamente al Cloud Run API. Procesa eventos `agent_started`, `tool_call`, `claim_created`, `edge_discovered`, `investigation_complete`. Actualiza estado React con TanStack Query mutations.
- **localStorage en demo:** `useLocalStorageInvestigation(id)` sincroniza el estado actual a `localStorage` para que un refresh del browser retome donde estaba (también backup ante caída de internet).
- **OG image generator:** `/api/og` recibe `?id=...`, fetchea metadata mínima del dossier, renderiza React → image vía Vercel OG. Incluye nombre de la entidad, foto avatar, score de alertas, "Sabueso · Investigación pública".
- **i18n carga catalogs en build:** mensajes en `messages/es.json` y `messages/en.json`. Server Components leen del catalog en build (zero JS cost). Client Components que necesiten i18n usan `useTranslations()` de next-intl.

### 5.2 Componentes del API Service (C4)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  C4 API SERVICE  (FastAPI)                                               │
│                                                                          │
│  src/                                                                    │
│  ├── main.py                       ── FastAPI app factory                │
│  ├── deps.py                       ── DI (db pool, auth, settings)       │
│  ├── settings.py                   ── Pydantic Settings                  │
│  │                                                                       │
│  ├── routes/                                                             │
│  │   ├── investigate.py            ── POST /investigate                  │
│  │   ├── stream.py                 ── GET /stream/{id} SSE               │
│  │   ├── investigations.py         ── GET, list, etc.                    │
│  │   ├── entities.py               ── GET /entities/{id}                 │
│  │   ├── search.py                 ── GET /search                        │
│  │   ├── export.py                 ── POST /export-pdf                   │
│  │   ├── subscribe.py              ── POST /subscribe                    │
│  │   └── health.py                                                       │
│  │                                                                       │
│  ├── services/                                                           │
│  │   ├── investigation.py          ── create, enqueue (pgmq), trigger    │
│  │   │                                Cloud Run Job                      │
│  │   ├── search.py                 ── pg_trgm + tsvector queries         │
│  │   ├── pdf.py                    ── enqueue PDF job                    │
│  │   ├── subscription.py           ── Zavu integration                   │
│  │   └── rate_limit.py             ── Vercel KV calls (via HTTP)         │
│  │                                                                       │
│  ├── sse/                                                                │
│  │   ├── stream.py                 ── SSE response generator             │
│  │   ├── listener.py               ── Postgres LISTEN/NOTIFY async       │
│  │   └── events.py                 ── Event schema (pydantic)            │
│  │                                                                       │
│  ├── auth/                                                               │
│  │   ├── middleware.py             ── valida JWT de Supabase             │
│  │   └── current_user.py           ── dependency                         │
│  │                                                                       │
│  ├── db/                                                                 │
│  │   ├── pool.py                   ── asyncpg pool a Supabase            │
│  │   ├── repository/               ── repos por agregado                 │
│  │   │   ├── investigations.py                                           │
│  │   │   ├── entities.py                                                 │
│  │   │   ├── claims.py                                                   │
│  │   │   └── events.py                                                   │
│  │   └── migrations/               ── schema versionado                  │
│  │                                                                       │
│  ├── observability/                                                      │
│  │   ├── logging.py                ── structlog + Cloud Logging          │
│  │   ├── tracing.py                ── OpenTelemetry → LangSmith bridge   │
│  │   └── metrics.py                                                      │
│  │                                                                       │
│  └── models/                       ── Pydantic schemas                   │
│      ├── investigation.py                                                │
│      ├── entity.py                                                       │
│      └── event.py                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

**Componentes críticos:**

- **`InvestigationService.create_and_dispatch()`** — flujo:
  1. Validar input (entity name + country).
  2. Check rate limit (Vercel KV via HTTP API).
  3. Buscar entidad existente o crear stub.
  4. INSERT en `investigations` con status=`pending`.
  5. `pgmq.send('investigation_queue', {investigation_id})`.
  6. Trigger Cloud Run Job vía REST API (`run.googleapis.com/.../jobs:run` con OIDC token).
  7. Retornar `{investigation_id}` al frontend.

- **`SSEListener`** — pattern:
  ```python
  async def stream_events(investigation_id: UUID):
      async with db_pool.acquire() as conn:
          await conn.add_listener(f'inv_{investigation_id}', _handler)
          while True:
              event = await event_queue.get()
              yield f"data: {event.json()}\n\n"
              if event.type == "investigation_complete":
                  break
  ```
  - Cada cliente abre su propia conexión Postgres con LISTEN.
  - Cloud Run conn pool dimensionado para soportar 80 conexiones concurrentes (límite Supabase free: 60 directas, 200 pooler).
  - Trade-off conocido: si Cloud Run instancia muere, SSE se corta. Frontend reconecta con `EventSource` y resume desde `last_event_id` (filtrar `> last_id` en query inicial).

### 5.3 Componentes del Investigation Worker (C6)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  C6 INVESTIGATION WORKER                                                 │
│                                                                          │
│  src/                                                                    │
│  ├── main.py                       ── Cloud Run Job entrypoint           │
│  │                                                                       │
│  ├── orchestrator/                                                       │
│  │   ├── graph.py                  ── LangGraph state machine            │
│  │   ├── state.py                  ── TypedDict de estado                │
│  │   ├── nodes/                                                          │
│  │   │   ├── plan.py               ── Sabueso planner                    │
│  │   │   ├── delegate.py           ── Fan-out a subagentes               │
│  │   │   ├── verify_moa.py         ── MoA verifier                       │
│  │   │   ├── synthesize.py         ── Final dossier writer (Opus 4.7)   │
│  │   │   └── persist.py            ── Save to claims, edges, events     │
│  │   └── checkpointer.py           ── Postgres checkpointer config       │
│  │                                                                       │
│  ├── investigators/                ── 7 subagentes                       │
│  │   ├── base.py                   ── BaseInvestigator                   │
│  │   ├── buscador.py               ── El Buscador (Recon, ReWOO, Kimi)  │
│  │   ├── tasadora.py               ── La Tasadora (Patrimony, ReAct)    │
│  │   ├── contador.py               ── El Contador (Contracts, ReWOO)    │
│  │   ├── letrado.py                ── El Letrado (Legal, ReWOO)         │
│  │   ├── detective.py              ── El Detective (Relationships)      │
│  │   ├── periodista.py             ── El Periodista (News)               │
│  │   └── jueza.py                  ── La Jueza (Verifier, MoA)          │
│  │                                                                       │
│  ├── tools/                        ── Catálogo de tools por país         │
│  │   ├── registry.py               ── ToolRegistry con namespacing       │
│  │   ├── pe/                                                             │
│  │   │   ├── seace.py              ── search_seace_contracts(...)        │
│  │   │   ├── legalize.py           ── query_legalize_pe(...)             │
│  │   │   ├── jne.py                ── fetch_jne_hoja_vida(...)           │
│  │   │   ├── sunarp.py                                                   │
│  │   │   ├── manolo.py                                                   │
│  │   │   └── el_peruano.py                                               │
│  │   ├── cl/                       ── Preview: legalize-cl               │
│  │   ├── mx/                       ── Preview: legalize-mx               │
│  │   └── sv/                       ── Preview: legalize-sv               │
│  │                                                                       │
│  ├── llm/                                                                │
│  │   ├── client.py                 ── OpenAI-compatible → OpenRouter     │
│  │   ├── caching.py                ── Anthropic prompt caching helpers   │
│  │   └── routing.py                ── Lógica de elegir modelo por rol    │
│  │                                                                       │
│  ├── scrapers/                                                           │
│  │   ├── base.py                   ── Scrapling wrapper con retry        │
│  │   ├── region_router.py          ── Round-robin entre Cloud Run        │
│  │   │                                regions para egress IP diverso     │
│  │   └── adapters/                 ── Por sitio                          │
│  │                                                                       │
│  ├── events/                       ── Productor de events                │
│  │   ├── emitter.py                ── INSERT + NOTIFY                    │
│  │   └── schemas.py                                                      │
│  │                                                                       │
│  └── prompts/                      ── Markdown files con cache breakpts  │
│      ├── sabueso_system.md                                               │
│      ├── buscador_system.md                                              │
│      ├── tasadora_system.md                                              │
│      ├── ... (uno por investigador)                                      │
│      └── jueza_moa_system.md                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

**El grafo LangGraph (esquemático):**

```
                         START
                           │
                           ▼
                  ┌────────────────┐
                  │  load_context  │  fetch entity + history
                  └────────┬───────┘
                           ▼
                  ┌────────────────┐
                  │  sabueso_plan  │  Claude Sonnet 4.6 (cached)
                  │  → genera plan │  outputs: list of (agent, task)
                  └────────┬───────┘
                           ▼
                  ┌────────────────┐
                  │   fan_out      │  conditional Send() en LangGraph
                  └─┬───┬───┬───┬──┘
                    │   │   │   │   ... (1 send por subagente)
                    ▼   ▼   ▼   ▼
              ┌──────┐┌──────┐...  N subagentes en paralelo
              │buscar││tasar │     cada uno corre ReWOO o ReAct
              └──┬───┘└──┬───┘     emite events durante el run
                 │      │
                 └───┬──┘
                     ▼
              ┌──────────────┐
              │   collect    │   recolecta todos los claims
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │  jueza_moa   │   3 modelos verifican
              │  (siempre)   │   GPT-4o + Kimi + Claude (agg)
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │  synthesize  │   Claude Opus 4.7
              │  (Sabueso)   │   produce dossier markdown final
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │   persist    │   commit final state
              └──────┬───────┘
                     ▼
                    END
```

### 5.4 Componentes del Pipeline Job (C7)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  C7 PIPELINE JOB · CocoIndex                                             │
│                                                                          │
│  flows/                                                                  │
│  ├── pe_legalize_flow.py           ── ingiere legalize-pe API           │
│  ├── pe_seace_flow.py              ── pull OCDS JSON                    │
│  ├── pe_jne_pdfs_flow.py           ── descarga PDFs + extracción texto  │
│  ├── pe_manolo_flow.py             ── scrape Portal Transparencia       │
│  ├── pe_el_peruano_flow.py                                              │
│  ├── cl_legalize_flow.py           ── preview Chile                     │
│  ├── mx_legalize_flow.py           ── preview México                    │
│  ├── sv_legalize_flow.py           ── preview Salvador                  │
│  └── common/                                                             │
│      ├── embedding.py              ── OpenRouter → text-embedding-3-sm  │
│      ├── extract.py                ── PyMuPDF + Tika fallback           │
│      └── upsert.py                 ── batch upsert a Supabase           │
│                                                                          │
│  Cada flow es un grafo CocoIndex:                                       │
│    source → transform → embed → sink (Postgres)                         │
│    Incremental: solo procesa lo nuevo/modificado                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.5 Componentes del PDF Job (C8)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  C8 PDF GENERATOR                                                        │
│                                                                          │
│  src/                                                                    │
│  ├── main.py                       ── Cloud Run Job entry                │
│  ├── renderer.py                   ── Playwright headless                │
│  │                                    fetch /i/[id]/dossier print mode   │
│  │                                    page.pdf({ format, margin })       │
│  ├── template.py                   ── HTML template alternativo          │
│  │                                    (fallback WeasyPrint si PW falla)  │
│  ├── storage.py                    ── upload GCS + signed URL            │
│  └── watermark.py                  ── stamp footer con timestamp + QR    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. C4 Level 4 — Code (críticos)

### 6.1 Orquestador · LangGraph state machine

```python
# src/orchestrator/state.py
from typing import TypedDict, Annotated, Literal
from operator import add

class InvestigationState(TypedDict):
    investigation_id: str
    target_entity_id: str
    country: Literal["pe", "cl", "mx", "sv"]
    locale: str  # "es", "en"
    
    # Plan generated by Sabueso
    plan: list[dict]                # [{agent, task, priority}]
    
    # Claims accumulated from subagents (annotated with add reducer)
    claims: Annotated[list[dict], add]
    
    # Edges (entity-entity relations) discovered
    edges: Annotated[list[dict], add]
    
    # Events emitted (for SSE)
    events: Annotated[list[dict], add]
    
    # MoA verification results
    verified_claims: list[dict]
    
    # Final dossier markdown
    dossier_md: str
    
    # Metadata
    started_at: str
    cost_usd: float
    token_usage: dict
```

```python
# src/orchestrator/graph.py
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Send

def build_graph():
    g = StateGraph(InvestigationState)
    
    g.add_node("load_context", load_context)
    g.add_node("plan", sabueso_plan)
    g.add_node("collect", collect_claims)
    g.add_node("verify", jueza_moa)
    g.add_node("synthesize", sabueso_synthesize)
    g.add_node("persist", persist_final)
    
    # Subagent nodes
    for agent in ["buscador", "tasadora", "contador", "letrado", 
                  "detective", "periodista"]:
        g.add_node(agent, investigator_runners[agent])
    
    g.add_edge(START, "load_context")
    g.add_edge("load_context", "plan")
    
    # Fan-out: plan returns list of (agent, task) → Send to each
    g.add_conditional_edges("plan", fan_out)
    
    # Each subagent → collect
    for agent in ["buscador", "tasadora", "contador", "letrado", 
                  "detective", "periodista"]:
        g.add_edge(agent, "collect")
    
    g.add_edge("collect", "verify")
    g.add_edge("verify", "synthesize")
    g.add_edge("synthesize", "persist")
    g.add_edge("persist", END)
    
    checkpointer = PostgresSaver.from_conn_string(DB_URL)
    return g.compile(checkpointer=checkpointer)

def fan_out(state: InvestigationState) -> list[Send]:
    """Conditional edge: spawn N parallel subagent tasks."""
    return [
        Send(task["agent"], {**state, "current_task": task})
        for task in state["plan"]
    ]
```

### 6.2 Subagente base · ReWOO/ReAct

```python
# src/investigators/base.py
from abc import ABC, abstractmethod
from enum import Enum

class Strategy(Enum):
    REWOO = "rewoo"   # Plan once, parallel tools, synthesize
    REACT = "react"   # Iterative Thought-Action-Observation

class BaseInvestigator(ABC):
    callsign: str
    role: str
    color: str
    model: str           # e.g. "moonshot/kimi-k2.6"
    strategy: Strategy
    system_prompt_path: str
    
    def __init__(self, country: str, locale: str, db, emitter):
        self.country = country
        self.locale = locale
        self.tools = ToolRegistry.get_tools_for(country, self.allowed_tools)
        self.db = db
        self.emitter = emitter  # produces events
    
    async def run(self, task: dict, state: InvestigationState) -> dict:
        """Execute task, return list of claims."""
        await self.emitter.emit({
            "type": "agent_started",
            "agent": self.callsign,
            "task": task["task"],
        })
        
        if self.strategy == Strategy.REWOO:
            return await self._run_rewoo(task, state)
        else:
            return await self._run_react(task, state)
    
    async def _run_rewoo(self, task, state):
        # 1. Plan with placeholders
        plan = await self._plan(task, state)
        # 2. Execute all tools in parallel
        results = await asyncio.gather(
            *[self._execute_step(s) for s in plan.steps]
        )
        # 3. Synthesize claims
        return await self._synthesize(task, plan, results)
    
    async def _run_react(self, task, state):
        # Loop: thought → action → observation → ...
        history = []
        for step in range(MAX_REACT_STEPS):
            decision = await self._decide(task, history)
            if decision.action == "finish":
                return await self._extract_claims(history)
            obs = await self._execute_tool(decision.tool, decision.args)
            history.append({"thought": decision.thought, 
                           "action": decision.action,
                           "args": decision.args,
                           "observation": obs})
            await self.emitter.emit({
                "type": "tool_call",
                "agent": self.callsign,
                "tool": decision.tool,
                "args": decision.args,
                "observation_summary": str(obs)[:200],
            })
```

### 6.3 MoA Verifier · La Jueza

```python
# src/investigators/jueza.py
class LaJueza:
    """Mixture of Agents verifier. 3 models verify each claim, 
    1 aggregates."""
    
    PROPOSERS = [
        ("anthropic/claude-sonnet-4.6", "anthropic"),
        ("moonshot/kimi-k2.6", "openrouter"),
        ("openai/gpt-4o", "openai"),
    ]
    AGGREGATOR = "anthropic/claude-sonnet-4.6"
    
    async def verify_all(self, claims: list[Claim]) -> list[VerifiedClaim]:
        """Run MoA on every claim. (G4: siempre activo)"""
        return await asyncio.gather(
            *[self._verify_one(c) for c in claims]
        )
    
    async def _verify_one(self, claim: Claim) -> VerifiedClaim:
        # 1. Each proposer independently verifies
        verdicts = await asyncio.gather(*[
            self._propose(claim, model, provider)
            for model, provider in self.PROPOSERS
        ])
        # 2. Aggregator synthesizes consensus + final confidence
        consensus = await self._aggregate(claim, verdicts)
        
        return VerifiedClaim(
            claim_id=claim.id,
            verified=consensus.verified,
            confidence=consensus.confidence,
            disagreements=[v for v in verdicts if v.disagrees],
            verifier_notes=consensus.notes,
        )
```

### 6.4 SSE stream pattern · Cloud Run + LISTEN/NOTIFY

```python
# src/sse/stream.py
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
import asyncpg

router = APIRouter()

@router.get("/api/v1/stream/{investigation_id}")
async def stream(
    investigation_id: str,
    request: Request,
    last_event_id: str = None,
):
    async def event_generator():
        # 1. Send any missed events first (resume on reconnect)
        if last_event_id:
            missed = await get_events_since(investigation_id, last_event_id)
            for event in missed:
                yield {
                    "id": str(event.id),
                    "event": event.type,
                    "data": event.payload_json,
                }
        
        # 2. Listen for new events via Postgres NOTIFY
        async with db_pool.acquire() as conn:
            channel = f"inv_{investigation_id.replace('-','_')}"
            queue = asyncio.Queue()
            
            def handler(conn, pid, channel, payload):
                queue.put_nowait(payload)
            
            await conn.add_listener(channel, handler)
            
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    
                    try:
                        payload = await asyncio.wait_for(
                            queue.get(), timeout=30.0
                        )
                        event = await fetch_event(payload)
                        yield {
                            "id": str(event.id),
                            "event": event.type,
                            "data": event.payload_json,
                        }
                        if event.type == "investigation_complete":
                            break
                    except asyncio.TimeoutError:
                        yield {"event": "heartbeat", "data": "{}"}
            finally:
                await conn.remove_listener(channel, handler)
    
    return EventSourceResponse(event_generator())
```

```sql
-- Postgres trigger: on INSERT to investigation_events, NOTIFY listener
CREATE OR REPLACE FUNCTION notify_investigation_event()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify(
        'inv_' || replace(NEW.investigation_id::text, '-', '_'),
        NEW.id::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_notify_event
AFTER INSERT ON investigation_events
FOR EACH ROW EXECUTE FUNCTION notify_investigation_event();
```

### 6.5 Tool registry · namespaced por país, MCP-ready

```python
# src/tools/registry.py
from typing import Callable
from pydantic import BaseModel

class ToolDef(BaseModel):
    name: str
    country: str
    description: str
    input_schema: dict      # JSON Schema, MCP-compatible
    output_schema: dict
    handler: Callable
    cache_ttl: int = 3600   # seconds
    
class ToolRegistry:
    _tools: dict[str, ToolDef] = {}
    
    @classmethod
    def register(cls, country: str):
        def decorator(func):
            tool_def = ToolDef(
                name=func.__name__,
                country=country,
                description=func.__doc__,
                input_schema=cls._extract_schema(func, "input"),
                output_schema=cls._extract_schema(func, "output"),
                handler=func,
            )
            cls._tools[f"{country}:{func.__name__}"] = tool_def
            return func
        return decorator
    
    @classmethod
    def get_tools_for(cls, country: str, allowed: list[str]) -> list[ToolDef]:
        return [
            cls._tools[f"{country}:{name}"]
            for name in allowed
            if f"{country}:{name}" in cls._tools
        ]
    
    @classmethod
    def export_as_mcp(cls) -> dict:
        """Export all tools as MCP server manifest. Used by post-hackathon
        migration to standalone MCP servers."""
        return {
            "tools": [t.dict() for t in cls._tools.values()]
        }
```

```python
# src/tools/pe/seace.py
from src.tools.registry import ToolRegistry

class SearchSeaceInput(BaseModel):
    ruc: str = Field(..., regex=r"^\d{11}$")
    year_from: int = Field(2014, ge=2000)
    year_to: int = Field(2026, le=2030)

class SearchSeaceOutput(BaseModel):
    contracts: list[Contract]
    total_amount: float
    currency: str = "PEN"

@ToolRegistry.register(country="pe")
async def search_seace_contracts(
    ruc: str, year_from: int = 2014, year_to: int = 2026
) -> SearchSeaceOutput:
    """Search OECE OCDS for contracts where the given RUC is a 
    contracting party. Returns aggregated total and individual 
    contracts."""
    # 1. Check cache
    cached = await tool_cache.get(("seace", ruc, year_from, year_to))
    if cached: return cached
    
    # 2. Call OCDS API
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://contratacionesabiertas.osce.gob.pe/api/...",
            params={"ruc": ruc, "year_from": year_from},
        )
    
    # 3. Parse + cache + return
    result = SearchSeaceOutput.parse(r.json())
    await tool_cache.set(("seace", ruc, year_from, year_to), result, ttl=86400)
    return result
```

---

## 7. Modelo de datos

### 7.1 Diagrama ER (resumido)

```
┌──────────────┐         ┌────────────────────┐        ┌──────────────┐
│  countries   │◄────────│      entities      │───────►│   sources    │
│  pe,cl,mx,sv │         │ id, type, country  │        │ url, hash    │
└──────────────┘         │ name, identifier   │        └──────┬───────┘
                         │ search_vector      │               │
                         │ embedding (1536)   │               │
                         └────────┬───────────┘               │
                                  │                           │
                                  │ N:1                      N:1
                                  │                           │
                         ┌────────▼───────────┐               │
        ┌──N:1───────────│      claims        │───────────────┘
        │                │ id, entity_id      │
        │                │ predicate, value   │
        │                │ source_id          │
┌───────▼──────┐         │ confidence, agent  │
│ investigations│         │ supersedes_id     │
│  id, target  │         │ verified_by_jueza  │
│  status      │         └────────────────────┘
│  plan jsonb  │
│  dossier_md  │         ┌────────────────────┐
│  cost_usd    │         │      edges         │
│  user_id?    │         │ from_entity        │
└──────┬───────┘         │ to_entity, type    │
       │                 │ weight, evidence   │
       │ 1:N             │ confidence         │
       ▼                 └────────────────────┘
┌────────────────────┐
│ investigation_events│   (SSE source)
│ id BIGSERIAL       │
│ investigation_id   │
│ type, payload jsonb│
│ agent_callsign     │
│ created_at         │
└────────────────────┘

┌──────────┐    ┌────────────────┐    ┌────────────────────┐
│  users   │───►│ subscriptions  │    │   tool_cache       │
│ (supabase│    │ entity_id      │    │ key text pkey      │
│  auth)   │    │ channels jsonb │    │ value jsonb        │
│          │    │ user_id        │    │ expires_at         │
└──────────┘    └────────────────┘    └────────────────────┘
```

### 7.2 Tablas core

#### `entities`

```sql
CREATE TABLE entities (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country         CHAR(2) NOT NULL CHECK (country IN ('pe','cl','mx','sv')),
    type            TEXT NOT NULL CHECK (type IN (
                       'person','company','government_entity','contract'
                    )),
    identifier      TEXT,              -- DNI/RUC/CURP/RUT/DUI según país
    name            TEXT NOT NULL,
    aliases         TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    embedding       VECTOR(1536),
    search_vector   TSVECTOR GENERATED ALWAYS AS (
                       setweight(to_tsvector('spanish', coalesce(name,'')), 'A') ||
                       setweight(to_tsvector('spanish', coalesce(identifier,'')), 'B') ||
                       setweight(to_tsvector('spanish', array_to_string(aliases,' ')), 'C')
                    ) STORED,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (country, type, identifier)
);

CREATE INDEX idx_entities_search ON entities USING GIN (search_vector);
CREATE INDEX idx_entities_name_trgm ON entities USING GIN (name gin_trgm_ops);
CREATE INDEX idx_entities_embedding ON entities USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_entities_country_type ON entities(country, type);
```

#### `claims`

```sql
CREATE TABLE claims (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id),
    entity_id       UUID NOT NULL REFERENCES entities(id),
    predicate       TEXT NOT NULL,         -- "owns","employed_by","received_contract",...
    object_value    JSONB NOT NULL,        -- structured value
    object_entity_id UUID REFERENCES entities(id),  -- if value is an entity
    source_id       UUID NOT NULL REFERENCES sources(id),
    source_extract  TEXT,                  -- max 500 chars de la fuente
    source_hash     TEXT,                  -- SHA-256 del contenido en snapshot
    confidence      FLOAT CHECK (confidence BETWEEN 0 AND 1),
    agent_callsign  TEXT NOT NULL,
    superseded_by   UUID REFERENCES claims(id),
    verified_by_jueza BOOLEAN DEFAULT FALSE,
    verified_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_claims_entity ON claims(entity_id);
CREATE INDEX idx_claims_investigation ON claims(investigation_id);
CREATE INDEX idx_claims_predicate ON claims(predicate);
CREATE INDEX idx_claims_not_superseded ON claims(entity_id) WHERE superseded_by IS NULL;
```

#### `edges`

```sql
CREATE TABLE edges (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id),
    from_entity     UUID NOT NULL REFERENCES entities(id),
    to_entity       UUID NOT NULL REFERENCES entities(id),
    type            TEXT NOT NULL,    -- "spouse","employed_by","awarded_contract","owns_share"
    weight          FLOAT DEFAULT 1.0,
    confidence      FLOAT CHECK (confidence BETWEEN 0 AND 1),
    evidence_claims UUID[] DEFAULT '{}',  -- array de claim_ids que sustentan
    discovered_at   TIMESTAMPTZ DEFAULT now(),
    agent_callsign  TEXT,
    UNIQUE (from_entity, to_entity, type)
);

CREATE INDEX idx_edges_from ON edges(from_entity);
CREATE INDEX idx_edges_to ON edges(to_entity);
CREATE INDEX idx_edges_type ON edges(type);
```

#### `investigations`

```sql
CREATE TABLE investigations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_entity_id UUID NOT NULL REFERENCES entities(id),
    country         CHAR(2) NOT NULL,
    locale          TEXT NOT NULL DEFAULT 'es',
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
                       'pending','planning','running','verifying',
                       'synthesizing','complete','failed','cancelled'
                    )),
    plan            JSONB DEFAULT '[]',
    dossier_md      TEXT,
    cost_usd        NUMERIC(8,4) DEFAULT 0,
    token_usage     JSONB DEFAULT '{}',
    progress_pct    SMALLINT DEFAULT 0,
    user_id         UUID,   -- null = anonymous
    is_public       BOOLEAN DEFAULT TRUE,
    started_at      TIMESTAMPTZ DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    error_message   TEXT
);

CREATE INDEX idx_investigations_target ON investigations(target_entity_id);
CREATE INDEX idx_investigations_user ON investigations(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_investigations_status ON investigations(status);
CREATE INDEX idx_investigations_public ON investigations(is_public, finished_at DESC) 
   WHERE is_public = TRUE AND status = 'complete';
```

#### `investigation_events`

```sql
CREATE TABLE investigation_events (
    id              BIGSERIAL PRIMARY KEY,
    investigation_id UUID NOT NULL REFERENCES investigations(id),
    type            TEXT NOT NULL,    -- "agent_started","tool_call","claim_created",
                                       -- "edge_discovered","verification_done",
                                       -- "investigation_complete"
    agent_callsign  TEXT,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_events_investigation_id ON investigation_events(investigation_id, id);
```

#### `sources`

```sql
CREATE TABLE sources (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url             TEXT NOT NULL,
    source_type     TEXT NOT NULL CHECK (source_type IN (
                       'legalize','seace','jne','sunarp','sunat','el_peruano',
                       'manolo','press','wayback','user_upload'
                    )),
    title           TEXT,
    snapshot_at     TIMESTAMPTZ DEFAULT now(),
    content_hash    TEXT,             -- SHA-256
    content_storage TEXT,             -- gs://bucket/path or null si solo URL
    country         CHAR(2)
);

CREATE UNIQUE INDEX uq_sources_url_snapshot ON sources(url, snapshot_at);
```

#### `tool_cache`

```sql
CREATE TABLE tool_cache (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_tool_cache_expiry ON tool_cache(expires_at);

-- cleanup vía pg_cron cada hora
SELECT cron.schedule('cleanup-tool-cache', '0 * * * *', 
    $$DELETE FROM tool_cache WHERE expires_at < now()$$);
```

#### `subscriptions`

```sql
CREATE TABLE subscriptions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL,  -- Supabase auth.users.id
    entity_id       UUID NOT NULL REFERENCES entities(id),
    channels        JSONB NOT NULL, -- {"whatsapp": "+51...", "email": "..."}
    triggers        JSONB DEFAULT '["new_claim","conflict_detected"]',
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, entity_id)
);
```

### 7.3 LangGraph checkpointer

LangGraph crea sus propias tablas en el mismo Postgres:

- `checkpoint_migrations`
- `checkpoints`
- `checkpoint_writes`

Configuradas con `PostgresSaver.from_conn_string(DB_URL)` al inicializar el grafo.

### 7.4 RLS (Row-Level Security)

```sql
-- investigations: público lee si is_public=true; owner siempre
ALTER TABLE investigations ENABLE ROW LEVEL SECURITY;

CREATE POLICY investigations_public_read ON investigations
    FOR SELECT USING (is_public = TRUE);

CREATE POLICY investigations_owner_all ON investigations
    FOR ALL USING (user_id = auth.uid());

-- subscriptions: solo owner
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY subscriptions_owner ON subscriptions
    FOR ALL USING (user_id = auth.uid());

-- Service role bypass para backend (API y workers usan service_role key)
```

### 7.5 Migraciones

Versionadas en `apps/api/migrations/`:
- `001_init.sql`
- `002_extensions.sql`
- `003_core_tables.sql`
- `004_indexes.sql`
- `005_triggers_notify.sql`
- `006_rls.sql`
- `007_seed_entities_demo.sql` (los 5 funcionarios pre-cacheados)

Aplicadas con `supabase migration up` durante CI/CD.

---

## 8. Diagramas de secuencia

### 8.1 Nueva investigación (happy path)

```
Usuario   Frontend(Vercel)   API(CR)   Postgres   Worker(CR Job)   OpenRouter   Sources
  │           │                │          │              │              │           │
  │ click     │                │          │              │              │           │
  │ "Invest." │                │          │              │              │           │
  ├──────────►│                │          │              │              │           │
  │           │ POST /invest.  │          │              │              │           │
  │           ├───────────────►│          │              │              │           │
  │           │                │ check    │              │              │           │
  │           │                │ rate-lim │              │              │           │
  │           │                ├──Vercel KV API─────────►              │           │
  │           │                │ INSERT investigations    │              │           │
  │           │                ├─────────►│              │              │           │
  │           │                │ pgmq.send│              │              │           │
  │           │                ├─────────►│              │              │           │
  │           │                │ trigger Cloud Run Job   │              │           │
  │           │                ├──────────────────────────►              │           │
  │           │                │ 202 {investigation_id}                  │           │
  │           │◄───────────────┤                                         │           │
  │           │ navigate       │                                         │           │
  │           │ /i/[id]        │                                         │           │
  │           │ open SSE       │                                         │           │
  │           │ /stream/[id]   │                                         │           │
  │           ├───────────────►│                                         │           │
  │           │                │ LISTEN inv_*                            │           │
  │           │                ├─────────►│                              │           │
  │           │                │          │              │ start LangGraph           │
  │           │                │          │              ├──────────────►│           │
  │           │                │          │              │ Sabueso plan  │           │
  │           │                │          │              │◄──────────────┤           │
  │           │                │          │              │ INSERT events │           │
  │           │                │          │◄─────────────┤               │           │
  │           │                │          │ NOTIFY        │               │           │
  │           │                │◄─────────┤              │               │           │
  │           │ SSE: plan      │          │              │               │           │
  │           │◄───────────────┤          │              │               │           │
  │ ve plan   │                │          │              │               │           │
  │◄──────────┤                │          │              │               │           │
  │           │                │          │              │ fan_out to 6 investigators│
  │           │                │          │              ├──────────────►│           │
  │           │                │          │              │ El Contador → tool calls  │
  │           │                │          │              │ search_seace  │           │
  │           │                │          │              │               ├──────────►│
  │           │                │          │              │               │   API     │
  │           │                │          │              │               │◄──────────┤
  │           │                │          │              │ claim created │           │
  │           │                │          │              │ INSERT claim  │           │
  │           │                │          │              │ INSERT event  │           │
  │           │                │          │◄─────────────┤               │           │
  │           │                │          │ NOTIFY        │               │           │
  │           │                │◄─────────┤              │               │           │
  │           │ SSE: claim     │          │              │               │           │
  │           │◄───────────────┤          │              │               │           │
  │ ve nodo   │                │          │              │               │           │
  │ aparecer  │                │          │              │               │           │
  │◄──────────┤                │          │              │               │           │
  │           │     ... (repite por cada investigador en paralelo)       │           │
  │           │                │          │              │ collect       │           │
  │           │                │          │              │ → La Jueza MoA│           │
  │           │                │          │              ├──────────────►│           │
  │           │                │          │              │ 3 verifies + agg          │
  │           │                │          │              │◄──────────────┤           │
  │           │                │          │              │ synthesize    │           │
  │           │                │          │              │ Opus 4.7      │           │
  │           │                │          │              ├──────────────►│           │
  │           │                │          │              │◄──────────────┤           │
  │           │                │          │              │ dossier_md    │           │
  │           │                │          │              │ UPDATE inv    │           │
  │           │                │          │◄─────────────┤               │           │
  │           │                │          │ NOTIFY complete               │           │
  │           │                │◄─────────┤              │               │           │
  │           │ SSE: complete  │          │              │               │           │
  │           │◄───────────────┤          │              │               │           │
  │ ve final  │                │          │              │               │           │
  │◄──────────┤                │          │              │               │           │
```

### 8.2 Reconexión SSE (después de network glitch)

```
Frontend       API
   │           │
   │ EventSource auto-reconnect
   │ con Last-Event-ID: 12345
   ├──────────►│
   │           │ GET /stream/{id}?last_event_id=12345
   │           │ SELECT events WHERE id > 12345
   │           │  AND investigation_id = ...
   │           │ stream backlog
   │◄──────────┤
   │           │ LISTEN inv_*
   │           │ (resume from NOTIFY)
   │           │
```

### 8.3 Exportar PDF

```
Usuario      Frontend     API         pgmq        PDF Job        GCS         
  │ click       │           │           │             │             │
  │ "Export"    │           │           │             │             │
  ├────────────►│           │           │             │             │
  │             │ POST /export-pdf/{id} │             │             │
  │             ├──────────►│           │             │             │
  │             │           │ pgmq.send │             │             │
  │             │           ├──────────►│             │             │
  │             │           │ trigger Job             │             │
  │             │           ├─────────────────────────►             │
  │             │           │ 202 {job_id}            │             │
  │             │◄──────────┤           │             │             │
  │ "Generando..."          │           │             │             │
  │◄────────────┤           │           │             │             │
  │             │           │           │             │ launch Chrome│
  │             │           │           │             │ fetch /dossier print mode  │
  │             │           │           │             │ page.pdf()  │
  │             │           │           │             │ upload      │
  │             │           │           │             ├────────────►│
  │             │           │           │             │ signed URL  │
  │             │           │           │             │◄────────────┤
  │             │           │           │             │ UPDATE jobs │
  │             │           │           │◄────────────┤ status=done │
  │             │ polling /export-pdf/{job_id}        │             │
  │             ├──────────►│           │             │             │
  │             │ SELECT job│           │             │             │
  │             │ status=done + signed_url            │             │
  │             │◄──────────┤           │             │             │
  │ download    │           │           │             │             │
  │◄────────────┤           │           │             │             │
```

### 8.4 Demo replay mode

```
Usuario       Frontend            localStorage      API          Postgres
  │              │                     │             │              │
  │ click demo   │                     │             │              │
  │ "Cerrón"     │                     │             │              │
  ├─────────────►│                     │             │              │
  │              │ check localStorage  │             │              │
  │              │ for demo:cerron     │             │              │
  │              ├────────────────────►│             │              │
  │              │ has events array    │             │              │
  │              │◄────────────────────┤             │              │
  │              │ open fake EventSource              │              │
  │              │ replay events with                │              │
  │              │ artificial timing                 │              │
  │              │ (~10s total)                      │              │
  │              │                     │             │              │
  │              │ if no localStorage:               │              │
  │              │ POST /investigate?mode=replay     │              │
  │              ├──────────────────────────────────►│              │
  │              │                                   │ SELECT pre-recorded events
  │              │                                   ├─────────────►│
  │              │ SSE stream con timing escalado   │              │
  │              │◄──────────────────────────────────┤              │
  │              │ cache to localStorage            │              │
  │              ├────────────────────►│             │              │
  │ ve replay    │                     │             │              │
  │◄─────────────┤                     │             │              │
```

---

## 9. Cross-cutting concerns

### 9.1 Authentication & Authorization

- **Provider:** Supabase Auth.
- **Métodos:** Google OAuth (primario), magic link (fallback).
- **Anónimos:** sin auth pueden investigar y ver dossiers públicos. Rate limit 10/IP/día vía Vercel KV.
- **Autenticados:** rate limit 50/usuario/día. Pueden suscribir alertas, marcar private, ver hemeroteca personal.
- **JWT:** Supabase emite JWT. Frontend lo guarda en httpOnly cookie. API valida vía `python-jose` con JWKS de Supabase.
- **RLS:** policies en Postgres restringen lectura/escritura por `auth.uid()`.

### 9.2 Observabilidad

| Capa | Herramienta | Qué se mide |
|---|---|---|
| Frontend | Vercel Analytics + Speed Insights | Core Web Vitals, page views |
| API service | structlog → Cloud Logging | HTTP requests, latency, errors |
| API service | OpenTelemetry → Cloud Trace | Distributed tracing entre containers |
| Workers (agentes) | LangSmith | Trazas de LangGraph + tool calls + tokens + costos |
| Workers (logs) | structlog → Cloud Logging | Errores de scrapers, retries |
| Postgres | Supabase dashboard | Queries lentas, conexiones |
| Costos LLM | OpenRouter dashboard + table propia | Budget tracking por investigación |

**Tracing helpers:**

```python
# src/observability/tracing.py
from langsmith import traceable

@traceable(name="investigation_run", run_type="chain")
async def run_investigation(state):
    ...

@traceable(name="tool_search_seace", run_type="tool")
async def search_seace(...):
    ...
```

### 9.3 i18n (decisión G3)

- **Librería:** `next-intl` para el frontend.
- **Catalogs:** `messages/es.json`, `messages/en.json`. Solo `es` traducido en v1; estructura de `en` lista.
- **Defaults:** `es-PE` para Perú, `es-CL` para Chile, `es-MX` para México, `es-SV` para Salvador, `en-US` fallback.
- **Server Components:** import directo del catalog, zero JS payload.
- **Client Components:** `useTranslations()` hook.
- **Country selector:** dropdown en navbar, persiste en cookie. Cambia ruta a `/{country}/...` opcionalmente.
- **Datos del dominio:** **siempre en idioma original** (no traducimos nombres de funcionarios ni de leyes).
- **Fecha/moneda:** `Intl.DateTimeFormat` + `Intl.NumberFormat` por locale.
- **Backend:** acepta `Accept-Language`, persiste `locale` en `investigations.locale`. Algunos prompts del orquestador tienen variante por locale.

### 9.4 Rate limiting (decisión G8)

```
Anónimos:     10 investigations / IP / 24h
Autenticados: 50 investigations / user / 24h
Búsquedas:    300 / IP / hour (más laxo)
PDF export:   20 / IP / 24h
```

**Implementación:** Vercel KV con clave `ratelimit:{type}:{key}` y TTL, lectura/escritura desde API routes de Next.js (middleware) y desde Cloud Run API (vía HTTP a Vercel REST).

### 9.5 Cost management

- **Per-investigation budget:** $1.00 default, $3.00 hard cap. Si una investigación pasa de $1.00, los siguientes subagentes se ejecutan en modelo más barato (DeepSeek V4-Flash). Si pasa de $3.00, se aborta con error.
- **Token tracking:** cada llamada a OpenRouter retorna `usage`; el worker suma a `investigations.token_usage` y `cost_usd`.
- **Prompt caching:** todos los system prompts de Claude tienen 4 cache breakpoints (Anthropic permite hasta 4). Reducción esperada de costo input en runs subsecuentes: 90%.
- **Dashboard interno:** `/admin/costs` (auth-protected) muestra costo por investigación, por modelo, por usuario.

### 9.6 Seguridad

- **API keys:** todas en GCP Secret Manager. Inyectadas como env vars al deployar Cloud Run.
- **Supabase service_role key:** solo Cloud Run la conoce, nunca expuesta al frontend.
- **CORS:** API permite `sabueso.vercel.app` y `localhost:3000`.
- **CSP headers** estrictos en Next.js.
- **Input sanitization:** Pydantic models en todos los endpoints. SQL injection prevenido por asyncpg parameter binding.
- **Output filtering:** dossiers no incluyen DNI completo de personas privadas (mask con `*****`). Sí incluyen RUC público.
- **Rate limit + Captcha (Cloudflare Turnstile)** después de 3 investigaciones consecutivas anónimas.
- **Disclaimer legal** en footer y al inicio de cada dossier: *"Información derivada de fuentes públicas. Sin imputación de delito. Sabueso no garantiza completitud."*

### 9.7 Resiliencia

| Falla | Mitigación |
|---|---|
| Tool externa falla (ej SUNARP 503) | Retry con backoff exponencial (3 intentos). Si falla persistente, claim marcado con `partial=true`. Investigación continúa. |
| Cloud Run instance muere mid-SSE | Frontend EventSource reconecta automáticamente con `Last-Event-ID`. API entrega backlog desde ese ID. |
| Cloud Run Job muere mid-investigation | LangGraph checkpointer en Postgres → API detecta `started_at` viejo y status=`running` con heartbeat stale → re-encola con `resume=true` flag |
| OpenRouter cae | Fallback configurado en OpenRouter mismo (cascada de providers). Si todo cae, claim agent falla → claim con confidence=0 → siguiente agente continúa. |
| Postgres connection pool exhausted | asyncpg pool con max_size=20, queue para cola los excedentes. Cloud Run autoscales si saturación persistente. |
| Vercel KV cae (rate limit) | Fallback: in-memory rate limit en Cloud Run con TTL. Menos preciso pero servicio sigue. |
| Scraping bloqueado (IP banned) | Round-robin a otra región Cloud Run. Si todas fallan, marca claim como `source_unavailable`. |

---

## 10. Arquitectura de despliegue

### 10.1 Estructura del repo (monorepo)

```
sabueso/
├── apps/
│   ├── web/                ── Next.js 16
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── messages/       ── i18n catalogs
│   │   └── package.json
│   ├── api/                ── FastAPI service
│   │   ├── src/
│   │   ├── migrations/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   ├── worker/             ── Investigation worker Cloud Run Job
│   │   ├── src/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   ├── pipeline/           ── CocoIndex ingestion Job
│   │   ├── flows/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── pdf/                ── PDF generator Job
│       ├── src/
│       ├── pyproject.toml
│       └── Dockerfile
├── packages/
│   ├── shared-types/       ── TypeScript + Pydantic schemas exportados
│   ├── ui/                 ── React components (importable por web)
│   └── agents-prompts/     ── Prompts compartibles
├── docs/
│   ├── architecture.md     ── ESTE DOCUMENTO
│   ├── uiux-spec.md
│   └── adrs/
├── infra/
│   ├── terraform/          ── GCP IaC (opcional, post-hackathon)
│   └── supabase/
│       └── migrations/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── deploy-api.yml
│       ├── deploy-jobs.yml
│       └── ingest.yml
├── pnpm-workspace.yaml
├── turbo.json
└── README.md
```

### 10.2 GCP project structure

```
Project: sabueso-hack-2026
Region principal: southamerica-east1 (São Paulo)
Regiones secundarias (para scraping rotation): 
  us-central1, us-east1, us-west1, europe-west1

Recursos:
  Cloud Run services:
    - sabueso-api          (FastAPI service)
  Cloud Run Jobs:
    - investigation-worker  (LangGraph runner)
    - pdf-generator         (Playwright PDF)
    - pipeline-ingest       (CocoIndex)
  Cloud Storage buckets:
    - sabueso-jne-pdfs      (privado, signed URLs)
    - sabueso-dossiers      (privado, signed URLs)
  Secret Manager:
    - openrouter-api-key
    - anthropic-api-key (opcional, directo)
    - supabase-service-role-key
    - langsmith-api-key
    - vercel-kv-rest-token
    - zavu-api-key
  Artifact Registry:
    - sabueso-images (Docker images)
  IAM:
    - Service account: sabueso-cloudrun-sa
      Permissions: Secret accessor, Storage admin (sus buckets),
                   Cloud Run admin (lanzar Jobs)
```

### 10.3 Vercel project

```
Project: sabueso
Framework: Next.js 16
Domain: sabueso.vercel.app (default)
Environment variables:
  NEXT_PUBLIC_API_BASE = https://sabueso-api-xyz.run.app
  NEXT_PUBLIC_SUPABASE_URL = https://xxx.supabase.co
  NEXT_PUBLIC_SUPABASE_ANON_KEY = ...
  SUPABASE_SERVICE_ROLE_KEY = ... (server-only)
  VERCEL_KV_REST_API_URL = ...
  VERCEL_KV_REST_API_TOKEN = ...
  
Add-ons:
  - Vercel KV (free tier)
  - Vercel Blob (free tier)
  - Vercel AI Gateway (free tier, opcional para AI Elements)
  - Vercel Analytics + Speed Insights
```

### 10.4 CI/CD (GitHub Actions)

#### `.github/workflows/ci.yml`

```yaml
name: CI
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lint-test-web:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
      - run: pnpm install
      - run: pnpm lint
      - run: pnpm typecheck
      - run: pnpm test

  lint-test-python:
    strategy:
      matrix:
        app: [api, worker, pipeline, pdf]
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/${{ matrix.app }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run ruff check
      - run: uv run mypy src
      - run: uv run pytest
```

#### `.github/workflows/deploy-api.yml`

```yaml
name: Deploy API
on:
  push:
    branches: [main]
    paths:
      - 'apps/api/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WIF }}
          service_account: sabueso-deploy@sabueso-hack-2026.iam
      - uses: google-github-actions/setup-gcloud@v2
      - name: Build and push
        run: |
          cd apps/api
          gcloud builds submit --tag southamerica-east1-docker.pkg.dev/sabueso-hack-2026/sabueso-images/api:${{ github.sha }}
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy sabueso-api \
            --region=southamerica-east1 \
            --image=southamerica-east1-docker.pkg.dev/sabueso-hack-2026/sabueso-images/api:${{ github.sha }} \
            --min-instances=1 \
            --max-instances=10 \
            --memory=1Gi \
            --cpu=1 \
            --timeout=3600 \
            --concurrency=80 \
            --no-cpu-throttling \
            --service-account=sabueso-cloudrun-sa@sabueso-hack-2026.iam
```

#### `.github/workflows/deploy-jobs.yml`

Similar pero `gcloud run jobs deploy` para los 3 jobs (`investigation-worker`, `pdf-generator`, `pipeline-ingest`).

#### `.github/workflows/ingest.yml`

```yaml
name: Manual Ingest
on:
  workflow_dispatch:
    inputs:
      flow:
        type: choice
        options: [pe_legalize, pe_seace, pe_jne_pdfs, all]
      country:
        type: choice
        options: [pe, cl, mx, sv]

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - run: |
          gcloud run jobs execute pipeline-ingest \
            --region=southamerica-east1 \
            --args="--flow=${{ inputs.flow }},--country=${{ inputs.country }}"
```

### 10.5 Multi-region scraping strategy

```python
# src/scrapers/region_router.py
REGIONS = [
    "southamerica-east1",
    "us-central1", 
    "us-east1",
    "us-west1",
    "europe-west1",
]

class RegionRouter:
    """When the investigation worker scrapes, it can request a 
    helper Cloud Run service in a different region to do the 
    actual fetch. This gives us 5 different egress IPs."""
    
    async def fetch(self, url: str, strategy: str = "round_robin"):
        if strategy == "round_robin":
            region = REGIONS[self._counter % len(REGIONS)]
            self._counter += 1
        else:
            region = self._select_best_region(url)
        
        helper_url = f"https://sabueso-scraper-{region}.run.app/fetch"
        async with httpx.AsyncClient() as c:
            r = await c.post(helper_url, json={"url": url})
        return r.json()
```

*Implementación post-hackathon si los gov peruanos comienzan a bloquear. Día 1-3 usamos egress directo del Cloud Run de São Paulo.*

---

## 11. Estrategia multi-país (decisión A3)

### 11.1 Modelo dimensional

Cada entidad, claim, edge e investigación tiene `country` como dimensión. Las tools están namespaceadas por país. La UI muestra un país por sesión, switchable.

### 11.2 Por país

| País | Status | Fuentes integradas | Identificador | Locale |
|---|---|---|---|---|
| **Perú** 🇵🇪 | **First-class** | legalize-pe, OECE OCDS, JNE Declara, SUNARP, SUNAT, El Peruano, Manolo, datos.gob.pe | DNI / RUC | es-PE |
| **Chile** 🇨🇱 | Preview demoable | legalize-cl (BCN), Mercado Público (preview) | RUT | es-CL |
| **México** 🇲🇽 | Preview demoable | legalize-mx (LeyesNet preview), CompraNet API | CURP / RFC | es-MX |
| **El Salvador** 🇸🇻 | Preview demoable | legalize-sv (Asamblea Legislativa preview) | DUI | es-SV |

**Preview = tiene legalize integrado (búsqueda en leyes), pero los conectores de contratos/patrimonio están en placeholder con datos sintéticos o muy limitados. Se muestra banner: "Modo preview · datos limitados".**

### 11.3 Implementación

- `entities.country` define dimensión.
- `ToolRegistry` retorna tools filtradas por país.
- LangGraph branch condicional: si `country != "pe"`, usa subset reducido de investigadores (solo Buscador + Letrado + Periodista).
- Frontend muestra banner amarillo en preview mode.

### 11.4 Escalabilidad

Agregar un nuevo país post-hackathon:
1. Definir locale en `messages/`.
2. Crear `tools/{country}/legalize.py` (puede ser scraper o API).
3. Mapear identifier nacional (e.g. Brasil → CPF/CNPJ).
4. Agregar a enum de `country` en migrations.
5. Insertar entidades semilla y datos test.

Esfuerzo estimado: 1-2 días por país nuevo.

---

## 12. Estrategia del demo

### 12.1 Cinco entidades target (sugerencia con criterio neutral)

Mi recomendación para máximo impacto + balance político + diversidad demostrativa. **Validar con criterio editorial antes de cachear:**

| # | Tipo | Criterio | Sugerencias |
|---|---|---|---|
| 1 | Candidato presidencial 2026 | Viralidad electoral, debate público activo | Elegir 1 de los registrados ante JNE 2026 con mayor cobertura mediática. Idealmente uno con declaración patrimonial reciente publicada. |
| 2 | Congresista actual con escándalo documentado | Caso "vivo" con publicaciones de prensa investigativa cruzables | Cualquier congresista con investigación periodística publicada en IDL Reporteros, OjoPúblico o Convoca en los últimos 12 meses. |
| 3 | Ex-presidente con caso cerrado o sentenciado | Profundidad histórica, fuentes consolidadas | Cualquier ex-presidente con sentencia firme reciente o caso archivado documentado. Toledo (sentencia 2024) o Castillo (caso en curso) ofrecen amplitud. |
| 4 | Gobernador regional polémico | Nivel sub-nacional, "out of spotlight" pero documentable | Un gobernador regional con denuncias de contraloría publicadas y RUCs vinculados a empresas familiares. |
| 5 | Funcionario técnico del MEF, MINSA o MINEDU | El cruce SEACE+patrimonio "invisible" — el que sorprende al jurado | Un alto cargo (Viceministro / Director ejecutivo) con declaración jurada publicada y cargos en MEF/MINSA durante un periodo con SEACE accesible. |

**Criterios duros para selección:**

- Toda información debe ser pública y verificable.
- Mezcla deliberada de espectro político (mínimo 2 partidos distintos).
- Al menos 1 caso "abierto" + 1 caso "cerrado/sentenciado".
- Al menos 1 candidato 2026 (carga electoral).
- Evitar nombres con orden judicial activa de protección.
- Disclaimer en cada dossier.

**Recomendación operativa:** elegir los 5 nombres el día 0 con asesoría de algún periodista de OjoPúblico o IDL si es posible. Esto da legitimidad.

### 12.2 Modo replay sintético

- Día 0 noche: lanzar las 5 investigaciones reales contra APIs en vivo. Persistir TODOS los eventos en `investigation_events` con timestamps relativos.
- En el demo: usuario clickea uno de los 5 cacheados → frontend detecta `mode=replay&seed_id=...` → `useInvestigation` hook lee eventos pre-grabados de Supabase + los re-emite con timing artificial proporcional (~10s total).
- Cero llamadas externas durante el demo. 100% confiable.
- localStorage también guarda la sesión por si Supabase falla.

### 12.3 Modo en vivo (E2)

Si el jurado pide investigar un nombre no cacheado:
- Botón visible "Modo en vivo · esto tomará 60-180s".
- Lanza investigación real contra APIs.
- Mismo Cinema mode pero con timing real (más lento).
- Si tarda mucho, se puede pausar y mostrar dossier parcial.

### 12.4 localStorage backup (E3)

```typescript
// hooks/useInvestigationLocalCache.ts
useEffect(() => {
  if (!investigation) return;
  localStorage.setItem(
    `sabueso:investigation:${investigation.id}`,
    JSON.stringify({
      events: investigation.events,
      dossier: investigation.dossier_md,
      cached_at: new Date().toISOString(),
    })
  );
}, [investigation]);

// On mount, hydrate from cache while waiting for SSE
const cached = useMemo(() => {
  const raw = localStorage.getItem(`sabueso:investigation:${id}`);
  return raw ? JSON.parse(raw) : null;
}, [id]);
```

Beneficio: si conexión se cae mid-demo, el último estado conocido sigue visible. Reconexión SSE rellena el resto.

---

## 13. Architecture Decision Records (ADRs)

### ADR-001 · Usar LangGraph para el orquestador

**Status:** Aceptado  
**Contexto:** Necesitamos coordinación multi-agente con estado persistente, fan-out paralelo y trazabilidad para debug del demo.  
**Decisión:** LangGraph con Postgres checkpointer.  
**Alternativas consideradas:** Hand-roll con asyncio (más simple, sin persistencia gratis), CrewAI (más rígido), Anthropic Agent SDK (multi-provider menos limpio).  
**Consecuencias:** Curva de aprendizaje ~4h. Persistencia gratis. LangSmith integrado. API pre-1.0 (riesgo de cambios). 200-300 líneas de wiring extra vs hand-roll.

### ADR-002 · SSE directo desde Cloud Run (no Supabase Realtime)

**Status:** Aceptado  
**Contexto:** Necesitamos entrega de eventos en tiempo real al frontend durante la investigación.  
**Decisión:** SSE servido por FastAPI en Cloud Run usando Postgres LISTEN/NOTIFY.  
**Alternativas consideradas:** Supabase Realtime (más simple pero acopla frontend al cliente Supabase + límite 200 conexiones free tier).  
**Consecuencias:** Más control. Reconexión con Last-Event-ID funciona. Cloud Run timeout=3600s soporta SSE largo. Mayor complejidad de implementación.

### ADR-003 · OpenRouter como gateway LLM único

**Status:** Aceptado  
**Contexto:** Usamos 5 modelos de 4 proveedores (Anthropic, Moonshot, DeepSeek, OpenAI).  
**Decisión:** Todo el tráfico LLM pasa por OpenRouter.  
**Alternativas consideradas:** Vercel AI Gateway (más caro post-trial), API directas (complejidad multi-SDK).  
**Consecuencias:** Un billing. Failover automático. $20 crédito perk. Pequeño overhead de latencia (~50-100ms). Algunas features Anthropic-specific (cache_control headers) hay que confirmar funcionan vía OpenRouter — fallback a Anthropic API directa si falla.

### ADR-004 · Supabase como BaaS único

**Status:** Aceptado  
**Contexto:** Necesitamos Auth + Postgres + Storage + cola.  
**Decisión:** Supabase para todo excepto storage de PDFs (que va a GCS).  
**Alternativas consideradas:** Postgres self-managed en Cloud SQL, Firebase Auth.  
**Consecuencias:** Stack unificado. RLS gratis. Realtime disponible si lo necesitamos. Free tier 500MB suficiente para hackathon.

### ADR-005 · GCS para PDFs (no Supabase Storage)

**Status:** Aceptado (decisión usuario)  
**Contexto:** PDFs son archivos grandes (1-5 MB cada uno).  
**Decisión:** Google Cloud Storage en bucket regional.  
**Alternativas consideradas:** Supabase Storage (1GB free), Vercel Blob (500MB free).  
**Consecuencias:** Free tier GCS 5GB. Lifecycle rules. Signed URLs nativos. Acoplamiento al stack GCP.

### ADR-006 · Tools inline en FastAPI, MCP-ready

**Status:** Aceptado  
**Contexto:** Necesitamos definir tools para los agentes. MCP es estándar abierto.  
**Decisión:** Tools como funciones Python decoradas con `@ToolRegistry.register()`. Schema exportable como JSON-Schema/MCP manifest.  
**Alternativas consideradas:** MCP servers desde día 1 (más boilerplate).  
**Consecuencias:** Setup más rápido. Migración post-hackathon a MCP es 1-2 días de trabajo (los schemas ya están). Tools se pueden testear unitariamente.

### ADR-007 · MoA verifier siempre activo

**Status:** Aceptado (decisión usuario)  
**Contexto:** Calidad del dossier es crítica.  
**Decisión:** La Jueza corre 3 modelos + agregador en cada claim, siempre.  
**Alternativas consideradas:** Triggered por threshold de confianza (más barato).  
**Consecuencias:** ~$0.15 extra por investigación. Consistencia + confianza mayor. Más resistente a alucinaciones de un solo modelo.

### ADR-008 · Subdominio Vercel (no domain custom)

**Status:** Aceptado (decisión usuario)  
**Contexto:** Dominio custom cuesta ~$15 y propaga DNS.  
**Decisión:** `sabueso.vercel.app`.  
**Consecuencias:** Sin gastos. Menos branding. Trivial cambiar post-hackathon.

### ADR-009 · Ingesta manual día 1 (no cron automático)

**Status:** Aceptado (decisión usuario)  
**Contexto:** Hackathon es de duración corta.  
**Decisión:** Pipeline ingest se dispara con `workflow_dispatch` desde GitHub Actions.  
**Alternativas consideradas:** Cloud Scheduler diario.  
**Consecuencias:** Más simple. Datos frescos según trigger manual. Cron se agrega trivial post-hackathon.

### ADR-010 · Knowledge graph en Postgres puro (no AGE)

**Status:** Aceptado (decisión usuario)  
**Contexto:** Necesitamos representar relaciones entidad-entidad.  
**Decisión:** Tablas relacionales `entities`, `edges`, `claims` con índices BTREE.  
**Alternativas consideradas:** Apache AGE (extensión grafo Postgres), Neo4j.  
**Consecuencias:** SQL convencional. Queries de grafo limitadas (BFS hasta 3 saltos OK, paths complejos lentos). Frontend cosmos.gl recibe edges+nodes de SQL simple.

---

## 14. Open questions y riesgos

### 14.1 Open questions (a resolver en construcción)

1. **¿Anthropic prompt caching funciona vía OpenRouter?** Necesita verificación día 0. Plan B: usar Anthropic SDK directo solo para Sabueso/Opus.
2. **¿Supabase free tier conexión limit alcanza?** 60 directas + 200 pooler. Con 10 investigaciones concurrentes cada una abriendo 1 LISTEN + LangGraph operations, podría apretarse. Plan B: upgrade a Pro ($25) si necesario.
3. **¿Cloud Run multi-region helper services necesarios?** Día 1-2 probar scraping con región única; si bloqueos, levantar helpers.
4. **¿Quién provee los nombres de los 5 funcionarios target?** Necesita decisión editorial del usuario.
5. **¿Zavu API tiene sandbox para testing?** Verificar para el demo.

### 14.2 Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| OpenRouter API key se queda sin crédito mid-demo | Baja | Alto | Pre-cargar tarjeta con $50 extra. Monitor en dashboard. |
| Cloud Run cold start mata el primer demo | Baja | Medio | `min-instances=1`. Warmup ping cada 5 min. |
| Sitios gov peruanos bloquean IP de Cloud Run | Media | Medio | Cloud Run multi-region. Webshare como fallback. |
| LangGraph API cambia breaking en versión nueva | Baja | Alto | Pin version exacta. No actualizar durante hackathon. |
| Postgres LISTEN/NOTIFY no escala bien | Baja | Alto | Solo 10-50 conexiones concurrentes esperadas. Plan B: polling cada 500ms si falla. |
| Jurado pide investigar a alguien con orden judicial de protección | Baja | Alto | Whitelist de candidatos validados. Sandbox mode con disclaimer si insiste. |
| Solo dev se enferma día 2 | Media | Crítico | Demo replay funciona sin internet. Documentación lista para retomar. |
| Frontend cosmos.gl lagea en monitor del jurado | Media | Medio | Fallback "lite mode" con SVG estático D3. |
| Algún subagente entra en loop infinito | Media | Alto | Hard timeout 60s por subagente. Max 15 tool calls. |

---

## 15. Apéndices

### Apéndice A · Catálogo de tools por país

#### Perú (first-class)

| Tool | Subagente principal | Cache TTL | Latencia esperada |
|---|---|---|---|
| `search_seace_contracts(ruc, year_from, year_to)` | El Contador | 24h | 500ms |
| `get_contract_detail(contract_id)` | El Contador | 7d | 300ms |
| `query_legalize_pe(query, semantic=true)` | El Letrado | 7d | 200ms |
| `get_legalize_law(law_id)` | El Letrado | 30d | 100ms |
| `find_dni_record(name, last_name)` | El Buscador | 7d | 500ms |
| `find_ruc_record(name_or_ruc)` | El Buscador | 7d | 500ms |
| `fetch_jne_hoja_vida(candidate_id)` | La Tasadora | 30d | 5s (PDF) |
| `query_sunarp_properties(dni)` | La Tasadora | 7d | 2s |
| `query_sunarp_board(ruc)` | El Detective | 7d | 2s |
| `find_relatives(dni, degree=2)` | El Detective | 30d | 1s |
| `search_manolo(dni_or_name)` | El Buscador | 24h | 1s |
| `search_el_peruano(query, date_from, date_to)` | El Periodista | 7d | 1s |
| `search_news_archive(entity_name)` | El Periodista | 1d | 2s |
| `query_inforegistro(...)` | El Detective | 7d | 1s |

#### Chile, México, El Salvador (preview)

Solo `query_legalize_{cl,mx,sv}(query)` y `search_news_archive(entity_name, country)` activas.

### Apéndice B · Estructura de prompt con cache breakpoints

```python
# src/orchestrator/nodes/plan.py
SABUESO_SYSTEM = """
[BREAKPOINT 1: identity + reglas globales, cacheable, ~2K tokens]
Eres Sabueso, jefe de redacción investigativa de un equipo de 6
especialistas. Tu misión es coordinar investigaciones de funcionarios
públicos, candidatos y empresas en LATAM cruzando datos abiertos.

Reglas duras:
- Nunca afirmas delito, solo "patrones consistentes con..."
- Toda afirmación requiere cita verificable
- Si no hay evidencia, dilo explícitamente
- Idioma: {locale}
- País: {country}

[BREAKPOINT 2: team roster + capabilities, cacheable, ~1.5K tokens]
Tu equipo (delegás siempre vía Send al subagente apropiado):

- El Buscador: encuentra DNI, RUC, identifica entidades
- La Tasadora: cruza patrimonio declarado vs realidad
- El Contador: rastrea contratos SEACE/OECE
- El Letrado: busca leyes votadas, sentencias
- El Detective: mapea familia/socios/directorios
- El Periodista: archivos de prensa, escándalos

[BREAKPOINT 3: tool catalog disponible, cacheable, ~3K tokens]
Tools disponibles según país {country}:
{tool_catalog_filtered}

[BREAKPOINT 4: few-shot ejemplos, cacheable, ~2K tokens]
Ejemplos de planes bien formados:

Ejemplo 1 — Investigar congresista:
{ "plan": [
  { "agent": "buscador", "task": "Confirmar DNI y trayectoria de X" },
  { "agent": "tasadora", "task": "Obtener declaración JNE y cruzar SUNARP" },
  ... ] }

Ejemplo 2 — Investigar empresa:
{ ... }

[VARIABLE: contexto del target específico, NO cacheable]
Investigando: {entity_name}
Tipo: {entity_type}
Identificador: {identifier}
Contexto adicional: {user_query}

Genera plan JSON. Sin texto extra antes ni después.
"""
```

Cache hit esperado: 90% en runs subsecuentes. Costo input → 10% del nominal.

### Apéndice C · Ambientes y configuración

| Variable | Dev | Hack | Prod |
|---|---|---|---|
| `SUPABASE_URL` | https://dev.supabase.co | https://hack.supabase.co | https://prod.supabase.co |
| `OPENROUTER_API_KEY` | sk-or-... (limited) | sk-or-... ($20 perk) | sk-or-... (paid) |
| `CLOUD_RUN_REGION` | us-central1 | southamerica-east1 | southamerica-east1 + replicas |
| `LANGSMITH_PROJECT` | sabueso-dev | sabueso-hack | sabueso-prod |
| `MIN_INSTANCES` | 0 | 1 | 2 |
| `LOG_LEVEL` | DEBUG | INFO | INFO |

### Apéndice D · Glosario

- **Claim:** una unidad atómica de información sobre una entidad. Ej: "Empresa Y recibió contrato $10M del MINSA en 2024".
- **Edge:** una relación tipada entre dos entidades. Ej: "X spouse_of Y".
- **Confidence:** float [0,1] que mide cuán cierta es una afirmación, asignado por el subagente y verificado por La Jueza.
- **Cinema mode:** la vista de investigación en vivo con grafo + log + dossier.
- **OODA loop:** Observe-Orient-Decide-Act, el ciclo interno de un subagente ReAct.
- **MoA (Mixture of Agents):** patrón donde N proposers verifican y un aggregator decide.
- **Cache breakpoint:** marca explícita en un prompt Anthropic para que el sistema cachee desde esa posición hacia atrás.
- **Dossier:** el reporte final markdown que entrega Sabueso al cierre de una investigación.

### Apéndice E · Métricas para evaluar éxito del demo

| Métrica | Target |
|---|---|
| Latencia primer evento visible | <2s |
| Latencia investigación completa (cached) | <15s |
| Latencia investigación completa (live) | <120s |
| % uptime durante hackathon | 99% |
| % claims con cita válida | 100% |
| Costo promedio por investigación | <$1 |
| Conexiones SSE simultáneas soportadas | 50 |
| Eventos por segundo visibles | hasta 5 |
| Render del grafo 60 fps en monitor estándar | sí |
| Páginas con score Lighthouse > 90 | landing, dossier |

---

## Cierre

Este documento es el contrato arquitectónico de Sabueso v1. Cualquier cambio durante la construcción debe quedar registrado como un nuevo ADR. La fuente única de verdad sobre estado de tareas está en Linear (proyecto Sabueso, cycle Hackathon hack@latam).

Construir en este orden, paralelizando con Emdash worktrees:

1. Migraciones Supabase (schema + RLS + triggers + extensions)
2. ToolRegistry + 3 tools básicas (legalize-pe, search_seace, search_manolo)
3. Subagente base + 1 subagente concreto (El Contador)
4. LangGraph orchestrator esqueleto (1 nodo solo)
5. API service: /investigate + /stream básicos
6. Frontend skeleton + 1 página /i/[id]
7. End-to-end happy path: query → 1 investigador → 1 claim → SSE → display
8. Expandir a 6 subagentes + MoA verifier
9. Cinema mode UI (cosmos.gl)
10. Polish del demo + replay mode + localStorage
11. PDF export + share
12. Multi-país preview
13. CI/CD final + deploy
14. Ensayo de pitch x10

> *"Sabueso no es un buscador. Es un equipo que investiga por vos."*

---

**Final del documento.**  
**Versión 1.0 · 2026-05-13**  
**Lock-in para construcción.**
