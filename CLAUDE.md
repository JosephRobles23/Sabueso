# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Sabueso is a multi-agent investigative journalism platform for auditing public officials in Latin America. It orchestrates 7 specialized AI investigators that cross-reference open government data and produce cited dossiers with confidence scores.

Built for hack@latam 2026. License: MIT.

## Commands

```bash
# Development (all apps via Turborepo)
pnpm dev

# Build / lint / typecheck / test
pnpm build
pnpm lint
pnpm typecheck
pnpm test

# Format
pnpm format

# Frontend only
cd apps/web && pnpm dev
cd apps/web && pnpm test        # vitest run
cd apps/web && pnpm typecheck   # tsc --noEmit

# Python services (use uv)
cd apps/api && uv sync && uvicorn src.main:app --reload
cd apps/worker && uv sync
cd apps/pipeline && uv sync
cd apps/pdf && uv sync

# Python lint/type
cd apps/api && ruff check . && mypy .
cd apps/worker && ruff check . && mypy .

# Single test (frontend)
cd apps/web && pnpm vitest run path/to/test.ts

# Single test (python)
cd apps/api && pytest tests/test_specific.py -v
```

## Architecture

**Monorepo** managed by pnpm workspaces + Turborepo.

```
apps/
  web/        → Next.js 16, React 19, Vercel AI SDK 6, shadcn/ui, TailwindCSS v4
  api/        → FastAPI, asyncpg, SSE (sse-starlette), JWT auth
  worker/     → LangGraph orchestrator + 7 investigators, OpenRouter LLM gateway
  pipeline/   → CocoIndex data ingestion
  pdf/        → Playwright-based dossier→PDF

packages/
  shared-types/ → TypeScript enums/interfaces shared across frontend
  ui/           → React component library (cn utility, CVA, tailwind-merge)
  agents-prompts/ → System prompts for investigators
```

**Data flow:** User → web → api (SSE stream) → worker (LangGraph + checkpointing) → scrapers/tools → Supabase Postgres → api SSE → web real-time UI.

**LLM routing:** All models go through OpenRouter. Primary: Claude Sonnet 4.6 (orchestrator), Kimi K2.6 (recon), DeepSeek V4-Flash (contracts). Cost target: ~$0.65/investigation, hard cap $3.00.

**Database:** Supabase Postgres with pgvector, pgmq, pg_cron, pg_trgm. Migrations in `infra/supabase/`.

## Key Conventions

- **Language:** UI strings in Spanish, code identifiers in English, docs in Spanish.
- **TypeScript paths:** `@/*` maps to app root, `@sabueso/shared-types` and `@sabueso/ui` to packages.
- **Python:** 3.12+, ruff (line-length 100, rules E,F,I,N,W,UP), mypy strict, hatchling build backend.
- **Formatting:** Prettier (no semi, double quotes, trailing commas, tabWidth 2, printWidth 100, tailwind plugin).
- **Multi-country:** Tools organized by country code (`worker/src/tools/pe/`, `/cl/`, `/mx/`, `/sv/`). Peru is first-class.
- **Agent callsigns:** sabueso, el-buscador, la-tasadora, el-contador, el-letrado, el-detective, el-periodista, la-jueza.

## Design System

Visual identity follows Anthropic/Claude branding:
- **Accent:** Terra Cotta `#DA7756`
- **Light mode:** canvas `#FAF9F5`, text `#141413`
- **Dark mode:** canvas `#141413`, text `#FAF9F5`
- **Typography:** Copernicus (display), Styrene B (body), JetBrains Mono (data). Free fallbacks: Lora, Poppins.
- **Semantic colors:** green `#788C5D` (declared), blue `#6A9BCC` (discovered), amber `#D4A843` (ambiguous), red `#C4583A` (suspicious).

Full spec in `docs/uiux-spec.md`.

## Environment

Required env vars are in `.env.example`. Critical ones:
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (frontend)
- `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL` (backend)
- `OPENROUTER_API_KEY` (LLM gateway)
- `LANGCHAIN_API_KEY` (observability)
- `GCP_PROJECT_ID`, `GCP_REGION` (infra)
