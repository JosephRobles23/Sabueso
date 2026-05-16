# 🐕‍🦺 Sabueso

> **Sistema multi-agente de investigación periodística para combatir la corrupción en LATAM.**

Sabueso automatiza la auditoría de funcionarios públicos, candidatos y empresas cruzando datos abiertos del Estado (legalización, contratos, patrimonio, registros, prensa) y entregando un *dossier* con evidencia citada y nivel de confianza por hallazgo.

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | Next.js 16 · Vercel AI SDK 6 · AI Elements · cosmos.gl · shadcn/ui |
| Backend | Python 3.12 · FastAPI · LangGraph · Scrapling · CocoIndex |
| LLMs | OpenRouter → Claude Sonnet 4.6 · Kimi K2.6 · DeepSeek V4-Flash · GPT-4o |
| Datos | Supabase Postgres · pgvector · pgmq |
| Infra | GCP Cloud Run · Cloud Storage · Vercel |

## Demo

> 🚧 En construcción — disponible el 17 de mayo 2026

## Arquitectura

Ver `docs/architecture.md` para el modelo C4 completo.

## Desarrollo

```bash
# Prerrequisitos: Node >= 20, pnpm >= 9, Python >= 3.12, uv, Docker
git clone https://github.com/YOUR_USERNAME/sabueso.git
cd sabueso
cp .env.example .env  # Llena las variables
pnpm install          # Frontend + packages
cd apps/api && uv sync   # Backend
cd apps/worker && uv sync
```

## Documentación

- [`docs/architecture.md`](docs/architecture.md) — C4 model
- [`docs/uiux-spec.md`](docs/uiux-spec.md) — Cinema Mode UI spec
- [`docs/linear-tasks.md`](docs/linear-tasks.md) — 20 tasks condensadas

## Licencia

MIT — ver [LICENSE](LICENSE)

---

*Construido en 4 días para [hack@latam 2026](https://hack.indies.la/) con Emdash + Claude + Kimi 🐕‍🦺*
