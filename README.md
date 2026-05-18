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

### Orquestación de agentes — LangGraph Hierarchical Fan-Out + Barrier

El orquestador **Sabueso** planifica la investigación y delega en paralelo a 7 investigadores especializados. Cada sub-agente usa el patrón **ReWOO** (Reasoning WithOut Observation) para planificar sus tool-calls antes de ejecutarlas. **La Jueza** aplica verificación **Mixture-of-Agents (MoA)** sobre los hallazgos antes de la síntesis final.

```mermaid
flowchart TB
    START((Inicio)) --> load[/"🗄️ load_context<br/>Fetch entity + historial desde DB"/]
    load --> plan["🐕‍🦺 <b>Sabueso</b> — Plan<br/><i>Claude Sonnet 4.6</i><br/>Genera PlanStep[] según query"]

    plan -- "Fan-Out via Send()" --> buscador & tasadora & contador & letrado & detective & periodista

    subgraph parallel ["Ejecución en paralelo — Patrón ReWOO"]
        direction LR
        buscador["🔍 <b>El Buscador</b><br/><i>Reconocimiento</i><br/>Resolución de identidad"]
        tasadora["🏠 <b>La Tasadora</b><br/><i>Patrimonio</i><br/>Bienes e inmuebles"]
        contador["📋 <b>El Contador</b><br/><i>Contratos</i><br/>Compras públicas"]
        letrado["⚖️ <b>El Letrado</b><br/><i>Legal</i><br/>Hojas de vida + normas"]
        detective["🕵️ <b>El Detective</b><br/><i>Redes</i><br/>Familiares y socios"]
        periodista["📰 <b>El Periodista</b><br/><i>Prensa</i><br/>Archivo periodístico"]
    end

    buscador & tasadora & contador & letrado & detective & periodista --> collect["⏳ collect<br/>Barrier — espera a todos"]
    collect --> jueza["👩‍⚖️ <b>La Jueza</b><br/><i>Verificación MoA</i><br/>Valida claims cruzando fuentes"]
    jueza --> synth["🐕‍🦺 <b>Sabueso</b> — Síntesis<br/><i>Claude Opus 4.7</i><br/>Genera dossier markdown"]
    synth --> persist[/"🗄️ persist<br/>Escritura transaccional a DB"/]
    persist --> END((Fin))

    style parallel fill:#f9f5ed,stroke:#DA7756,stroke-width:2px
    style plan fill:#fef3ed,stroke:#DA7756
    style synth fill:#fef3ed,stroke:#DA7756
    style jueza fill:#fef3ed,stroke:#6A9BCC
    style collect fill:#f5f5f5,stroke:#999
```

### Persistencia de contexto — LangGraph Checkpointing + Supabase

El estado de investigación (`InvestigationState`) fluye entre nodos usando **canales reductores** de LangGraph. Los campos acumulativos (`claims`, `edges`, `events`) se concatenan automáticamente tras el fan-out paralelo. El checkpointer persiste cada snapshot en PostgreSQL para tolerancia a fallos y reanudación.

```mermaid
flowchart LR
    subgraph state ["InvestigationState (TypedDict)"]
        direction TB
        accum["<b>Canales acumulativos</b><br/><code>Annotated[list, operator.add]</code><br/>─────────────────────<br/>• claims: hallazgos<br/>• edges: relaciones<br/>• events: telemetría"]
        lww["<b>Last-write-wins</b><br/>─────────────────────<br/>• investigation_id<br/>• plan: PlanStep[]<br/>• dossier_md<br/>• cost_usd / token_usage<br/>• status"]
    end

    subgraph checkpoint ["LangGraph Checkpointer"]
        direction TB
        pg["🐘 <b>PostgresSaver</b><br/><i>Producción</i>"]
        mem["💾 <b>InMemorySaver</b><br/><i>Testing</i>"]
    end

    subgraph supabase ["Supabase PostgreSQL"]
        direction TB
        t1["checkpoints<br/><i>Snapshots por thread_id</i>"]
        t2["checkpoint_writes<br/><i>Escrituras incrementales</i>"]
        t3["checkpoint_blobs<br/><i>Estado serializado</i>"]
        sep["─────────────────────"]
        t4["investigations<br/><i>status, plan, dossier,<br/>cost, progress</i>"]
        t5["claims<br/><i>ON CONFLICT DO NOTHING</i>"]
        t6["edges<br/><i>ON CONFLICT upsert</i>"]
    end

    state -- "Cada nodo<br/>snapshot" --> checkpoint
    checkpoint --> supabase
    pg -. "SUPABASE_DB_URL" .-> t1 & t2 & t3

    persist_node["persist node<br/><i>Transacción atómica</i>"] --> t4 & t5 & t6

    style state fill:#f9f5ed,stroke:#DA7756,stroke-width:2px
    style checkpoint fill:#eef4fa,stroke:#6A9BCC,stroke-width:2px
    style supabase fill:#f0f7f0,stroke:#788C5D,stroke-width:2px
```

### Fuentes de datos — Tool Registry por país

Los agentes acceden a datos gubernamentales abiertos mediante un **registro de herramientas** (`ToolRegistry`) con namespace por país, caché por TTL y rate-limiting por host. Perú es first-class; Chile, México y El Salvador están en preview.

```mermaid
flowchart TB
    subgraph registry ["ToolRegistry — apps/worker/src/tools/"]
        direction TB
        cache["🗃️ Cache por TTL<br/><code>cached_tool_call()</code>"]
        rate["⏱️ Rate Limiter<br/>por hostname"]
    end

    subgraph peru ["🇵🇪 Perú — First-Class"]
        direction TB
        seace["📋 <b>search_seace_contracts</b><br/>OSCE/SEACE — Contratos públicos<br/><i>contratacionesabiertas.osce.gob.pe</i><br/>TTL: 24h · 1 req/s"]
        manolo["🏛️ <b>search_manolo</b><br/>Manolo.pe — Visitas a entidades<br/><i>www.manolo.pe</i><br/>TTL: 24h · 2 req/s"]
        sunarp["🏠 <b>query_sunarp_properties</b><br/>SUNARP — Registro de propiedades<br/><i>www.sunarp.gob.pe</i><br/>TTL: 7d · 1 req/s"]
        jne["🗳️ <b>fetch_jne_hoja_vida</b><br/>JNE — Hojas de vida de candidatos<br/><i>plataformaelectoral.jne.gob.pe</i><br/>TTL: 30d · 1 req/s"]
        peruano["📜 <b>search_el_peruano</b><br/>El Peruano — Diario oficial<br/><i>busquedas.elperuano.pe</i><br/>TTL: 7d · 2 req/s"]
        news["📰 <b>search_news_archive</b><br/>IDL · OjoPúblico · Convoca · Wayback<br/>TTL: 1d · 2 req/s"]
        dni["🪪 <b>find_dni_record</b><br/>RENIEC — Identidad por DNI"]
        ruc["🏢 <b>find_ruc_record</b><br/>SUNAT — Registro tributario RUC"]
    end

    subgraph preview ["Preview — S-18"]
        cl["🇨🇱 Chile"]
        mx["🇲🇽 México"]
        sv["🇸🇻 El Salvador"]
    end

    subgraph agents ["Agentes investigadores"]
        b["🔍 El Buscador"] --> manolo & dni & ruc
        t["🏠 La Tasadora"] --> sunarp
        c["📋 El Contador"] --> seace
        l["⚖️ El Letrado"] --> jne & peruano
        d["🕵️ El Detective"]
        p["📰 El Periodista"] --> news
    end

    registry --> peru & preview
    peru --> cache --> rate

    style peru fill:#f9f5ed,stroke:#DA7756,stroke-width:2px
    style preview fill:#f5f5f5,stroke:#999,stroke-dasharray:5 5
    style registry fill:#eef4fa,stroke:#6A9BCC,stroke-width:2px
    style agents fill:#fef3ed,stroke:#DA7756,stroke-width:1px
```

## Desarrollo

```bash
# Prerrequisitos: Node >= 20, pnpm >= 9, Python >= 3.12, uv, Docker
git clone https://github.com/JosephRobles23/Sabueso
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

*Construido en 3 días para [hack@latam 2026](https://hack.indies.la/) con Emdash + Claude + Kimi 🐕‍🦺*
