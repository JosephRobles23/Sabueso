# S-05 · Investigator framework + LLM client — Resumen de implementación

> Branch: `emdash/wt-agents-9wqpz` · Fecha: 2026-05-17
> Estimate: 9 pts · Prioridad: P0 · Bloquea: S-06, S-10

Este documento resume **qué se construyó** para cerrar la tarea S-05 del plan en `docs/linear-tasks.md`. No reemplaza la spec; complementa documentando el estado real del código entregado.

---

## 1. Archivos creados

```
apps/worker/
├── pyproject.toml                       (+ [tool.hatch.build.targets.wheel])
├── src/
│   ├── investigators/
│   │   ├── __init__.py                  exporta API pública
│   │   └── base.py                      BaseInvestigator + ReWOO/ReAct
│   ├── llm/
│   │   ├── __init__.py                  re-exports
│   │   ├── client.py                    LLMClient + StateAccumulator
│   │   ├── caching.py                   apply_cache_breakpoints
│   │   ├── routing.py                   RouteResolver (OpenRouter ↔ Anthropic)
│   │   └── pricing.py                   tabla de precios por modelo
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── loader.py                    Jinja2 + frontmatter YAML
│   │   ├── sabueso_system.md
│   │   ├── buscador_system.md
│   │   ├── tasadora_system.md
│   │   ├── contador_system.md
│   │   ├── letrado_system.md
│   │   ├── detective_system.md
│   │   ├── periodista_system.md
│   │   └── jueza_moa_system.md
│   └── tools/
│       └── registry.py                  stub MCP-ready (drop-in para S-04)
└── tests/
    ├── conftest.py                      sys.path para `src.*`
    ├── investigators/test_base.py       21 tests
    ├── llm/test_caching.py              9 tests
    ├── llm/test_client.py               9 tests
    ├── llm/test_pricing.py              6 tests
    ├── llm/test_routing.py              6 tests
    ├── prompts/test_loader.py           9 tests
    └── test_tools_registry.py           4 tests
```

---

## 2. Base + estrategias

**`apps/worker/src/investigators/base.py`**

- `Strategy(StrEnum)` con dos miembros: `REWOO` y `REACT`.
- `BaseInvestigator(ABC)` con atributos de clase obligatorios validados en `__init__`:
  `callsign`, `role`, `color`, `model`, `strategy`, `allowed_tools`, `system_prompt_path`.
- `run(task, state)`:
  1. Emite `agent_started`.
  2. Despacha a `_run_rewoo` o `_run_react` según `strategy`.
  3. Captura excepciones y emite `agent_error`; al cierre emite `agent_finished` con conteo de claims.
- `_run_rewoo`: una llamada LLM al plan → `asyncio.gather(*[invoke_tool(s)])` en paralelo → hook opcional `_synthesize_prompt` para una segunda llamada agregadora → `_claims_from_results`.
- `_run_react`: loop hasta `max_steps=15` con **deadline duro `60 s`** (`time.monotonic` + `asyncio.wait_for`). Cuando se vence emite `react_timeout` y deja que `_claims_from_results` extraiga claims de las observaciones acumuladas.
- **Permission gate**: `_invoke_tool` lanza `ToolPermissionError` si la tool no figura en `allowed_tools` o no está registrada para el país.
- `_emit_event(state, type, payload)` agrega al `state.events` y delega en el `EventEmitter` (interfaz inyectable; en S-06 se conecta a `investigation_events`).

### Parseo JSON tolerante

`parse_tolerant_json(text)` intenta, en orden:

1. Bloque markdown ` ```json … ``` `.
2. Extracción por **balanceo de llaves/corchetes** (respetando strings con `"` escapados).
3. `json.loads` del texto crudo.

Si todos fallan, lanza `JSONParseError`. `BaseInvestigator._llm_json_with_retry` reintenta **una vez** con el mensaje original + assistant turn + un user turn que cita el error y pide JSON estricto.

---

## 3. LLM client

**`apps/worker/src/llm/client.py`**

- `LLMClient.complete(model, messages, tools=None, breakpoints=None, state=None)` apuntado por defecto a `https://openrouter.ai/api/v1`.
- **Transports inyectables** (`openrouter_transport`, `anthropic_transport`, `sleep`) → tests sin red ni mocks de monkeypatch.
- **Retry exponencial con jitter decorrelacionado** en `429` y `503` hasta `max_retries` (default 5). Otros 4xx propagan inmediatamente como `TransportError`.
- **`StateAccumulator`** lee/escribe sobre el dict del state de LangGraph:
  - `state["token_usage"]` con buckets `input`, `output`, `cache_write`, `cache_read`, y `by_model[<model>]`.
  - `state["cost_usd"]` acumulado con `pricing.estimate_cost`.
- Soporta payloads tanto OpenAI-style (`choices[0].message`) como Anthropic-style (`content: [{type:"text"|"tool_use"}]`).

### Pricing (`llm/pricing.py`)

| Modelo                            | Input $/Mtok | Output $/Mtok | Cache write | Cache read |
|-----------------------------------|--------------|---------------|-------------|------------|
| `anthropic/claude-sonnet-4.6`     | 3.00         | 15.00         | 3.75        | 0.30       |
| `anthropic/claude-opus-4.7`       | 15.00        | 75.00         | 18.75       | 1.50       |
| `moonshot/kimi-k2.6`              | 0.74         | 3.50          | —           | —          |
| `deepseek/deepseek-v4-flash`      | 0.14         | 0.28          | —           | —          |
| `deepseek/deepseek-v4-pro` (promo)| 0.435        | 0.87          | —           | —          |
| `openai/gpt-4o`                   | 2.50         | 10.00         | —           | —          |

Modelos no listados → costo 0. `register_price()` permite extender en runtime/tests.

---

## 4. Prompt caching + routing

**`apps/worker/src/llm/caching.py`**

- `apply_cache_breakpoints(messages, breakpoints)` inyecta `cache_control: {type: "ephemeral"}` en el **último bloque** de los mensajes indicados.
- Normaliza `content` a lista de bloques estructurados aunque el original sea `str`.
- Hace `deepcopy` para no mutar el input.
- Máximo 4 breakpoints (límite Anthropic) → `CacheBreakpointError`.
- `openrouter_respects_cache(usage)` detecta si la respuesta trae `cache_creation_input_tokens` o `cache_read_input_tokens`.

**`apps/worker/src/llm/routing.py`**

- `RouteResolver` con estado **sticky**:
  - Si OpenRouter responde con cache stats para algún `anthropic/*` → marca OK.
  - Si no las trae y aún no se observó OK → marca broken.
  - Una vez OK, futuras observaciones sin cache stats no revierten.
- `resolve(model, needs_cache=True)` para `anthropic/*` con resolver broken devuelve `RouteDecision(provider="anthropic", model="claude-sonnet-4.6")` (sin prefijo) y `LLMClient` invoca el SDK Anthropic directo.
- Para tools sin necesidad de cache (`needs_cache=False`) siempre va a OpenRouter, aunque el resolver esté broken.

---

## 5. Prompt loader

**`apps/worker/src/prompts/loader.py`**

- `PromptLoader.load(name, variables, locale)` busca, en orden:
  1. `prompts_dir/<locale>/<name>_system.md`
  2. `prompts_dir/<name>_system.md`
- Parsea frontmatter YAML delimitado por `---`. Si no hay frontmatter, devuelve metadata vacía. YAML inválido o que no sea mapping → `PromptError`.
- Renderiza el body con Jinja2 en modo `StrictUndefined` (variable faltante → `PromptError` explícito).
- `LoadedPrompt` expone helpers `.callsign`, `.model`, `.strategy`, `.breakpoints`, `.allowed_tools`.

### Placeholders entregados

Los 8 prompts viven en `apps/worker/src/prompts/` con la misma estructura de 4 cache breakpoints documentada en el Apéndice B de `architecture.md`:

| Archivo                  | Callsign  | Color         | Model                         | Strategy |
|--------------------------|-----------|---------------|-------------------------------|----------|
| `sabueso_system.md`      | sabueso   | amber-500     | `anthropic/claude-sonnet-4.6` | rewoo    |
| `buscador_system.md`     | buscador  | slate-400     | `moonshot/kimi-k2.6`          | rewoo    |
| `tasadora_system.md`     | tasadora  | emerald-500   | `moonshot/kimi-k2.6`          | react    |
| `contador_system.md`     | contador  | violet-500    | `moonshot/kimi-k2.6`          | rewoo    |
| `letrado_system.md`      | letrado   | sky-500       | `moonshot/kimi-k2.6`          | rewoo    |
| `detective_system.md`    | detective | rose-500      | `deepseek/deepseek-v4-flash`  | react    |
| `periodista_system.md`   | periodista| orange-500    | `deepseek/deepseek-v4-flash`  | react    |
| `jueza_moa_system.md`    | jueza_moa | red-600       | `anthropic/claude-sonnet-4.6` | rewoo    |

Cada uno con secciones `[BREAKPOINT 1..4]` para identidad / roster / tool catalog / few-shot, y una sección `[VARIABLE]` con los hooks Jinja (`{{ entity_name }}`, `{{ task }}`, `{{ country }}`, `{{ locale }}`, etc.).

---

## 6. ToolRegistry stub (puente con S-04)

**`apps/worker/src/tools/registry.py`** — stub mínimo compatible con la interfaz final de S-04:

- `ToolDef` (pydantic) con `name`, `country`, `description`, `input_schema`, `output_schema`, `handler`, `cache_ttl`.
- `ToolRegistry.register(country, ...)` decorator.
- `ToolRegistry.register_tool(tool)`, `.get(country, name)`, `.get_tools_for(country, allowed)`, `.clear()`, `.all()`.

Cuando S-04 esté listo, este archivo se reemplaza por la versión completa (cache TTL real, MCP manifest export) sin tocar `BaseInvestigator`.

---

## 7. Acceptance criteria — checklist

| Criterio                                                                       | Estado |
|--------------------------------------------------------------------------------|--------|
| `BaseInvestigator` abstracto, no instanciable, métodos abstractos definidos    | ✅     |
| `Strategy.REWOO` y `Strategy.REACT`                                            | ✅     |
| ReWOO ejecuta 3 tools en paralelo (test con barrier)                           | ✅     |
| ReAct hace 3 iteraciones (test cuenta observaciones)                           | ✅     |
| ReAct respeta `max_steps`                                                      | ✅     |
| ReAct respeta hard timeout 60 s (test con timeout 0.3 s)                       | ✅     |
| Parseo JSON tolerante con retry on malformed                                   | ✅     |
| Permission gate impide tools fuera de `allowed_tools`                          | ✅     |
| `LLMClient` retry exponencial en 429/503 + no-retry en 4xx no-retryable        | ✅     |
| Token tracking: 5 llamadas acumulan correctamente en `state.token_usage` y `cost_usd` | ✅ |
| `apply_cache_breakpoints` inyecta `cache_control` en 4 puntos                  | ✅     |
| Detección automática de OpenRouter cache + fallback a Anthropic SDK            | ✅     |
| Prompt loader carga frontmatter, parsea variables, devuelve string final       | ✅     |
| Cobertura ≥ 75 %                                                               | ✅ **87 %** |

---

## 8. Métricas de calidad

```
pytest:  64 passed in 0.81s
ruff:    All checks passed!
coverage:
  src\investigators\base.py         88 %
  src\llm\caching.py               100 %
  src\llm\client.py                 73 %   (transports HTTP cubiertos vía inyección)
  src\llm\pricing.py               100 %
  src\llm\routing.py                96 %
  src\prompts\loader.py             97 %
  src\tools\registry.py            100 %
  ─────────────────────────────────────
  TOTAL                             87 %
```

---

## 9. Cómo se conecta con S-06 (siguiente)

S-06 (LangGraph orchestrator) consumirá esto así:

1. **`InvestigationState`** (TypedDict) tendrá los campos `token_usage: dict` y `cost_usd: float` que `LLMClient.StateAccumulator` ya escribe.
2. **Nodos `buscador`, `tasadora`, `contador`, `letrado`, `detective`, `periodista`** instanciarán subclases concretas de `BaseInvestigator` (cookie-cutter desde S-10/S-11) y harán `await agent.run(task, state)`.
3. **`sabueso_plan`** usará `PromptLoader.load("sabueso", {country, locale, entity_name, ...})` + `LLMClient.complete(..., breakpoints=[0,1,2,3])` con el modelo Sonnet 4.6.
4. **`jueza_moa`** usará `PromptLoader.load("jueza_moa", ...)` y disparará las 3 propuestas + 1 agregador.

No hace falta tocar nada del framework para arrancar S-06.

---

## 10. Notas de implementación

- **`StrEnum`** en lugar de `str + Enum` para `Strategy` (compatibilidad py3.11+, evita warning ruff UP042).
- **`ToolPermissionError`** en vez del `PermissionDenied` original — sigue convención N818 de ruff y no colisiona con el builtin `PermissionError`.
- **`asyncio.wait_for` sobre `_llm_json_with_retry`** en ReAct: el deadline interrumpe tanto la decisión LLM como el reintento JSON. Si vence durante la decisión, se sale del loop con `react_timeout`.
- **`StateAccumulator.from_state(None)`** soporta pruebas y llamadas standalone sin LangGraph.
- **Transports inyectables**: la separación entre el método `complete()` y los transports HTTP permite tests determinísticos sin `respx`/`httpx-mock`.
- **`pyproject.toml`** ahora declara `[tool.hatch.build.targets.wheel] packages = ["src"]` para que `uv sync` construya correctamente (la convención por defecto de hatchling esperaba `src/sabueso_worker/`).
