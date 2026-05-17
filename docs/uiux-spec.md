# Sabueso — UI/UX Specification v1

> *"Sabueso: agente multi-equipo de investigación periodística para combatir la corrupción en LATAM."*

Este documento define la identidad visual y los patrones de interacción de Sabueso, integrando lo mejor del **Investigation Cinema** original con los patrones de **operaciones en vivo** robados con cariño de Hermes War Room. Es ejecutable: cada sección puede pasarse como prompt a un coding agent en Emdash.

---

## 0. Filosofía visual

Sabueso no es ni un "chatbot serio" ni una "sala de guerra militar". Es una **redacción de periodismo investigativo en vivo** — el espacio donde un equipo de investigadores especializados trabaja en paralelo, y tú (el editor jefe) ves todo lo que pasa en tiempo real.

Tres referencias estéticas a tener presentes mientras se diseña:

1. **Claude / Anthropic** — paleta cálida (terra cotta + cremas), tipografía serif editorial (Copernicus), sans humanista (Styrene B), minimalismo con calidez. Base de toda la identidad visual.
2. **NYT The Daily / ProPublica** — hierarchy clara, datos en mono, seriedad periodística.
3. **Hermes War Room** — la idea de operativos visibles, drill-downs, delegación dibujada.

El tono: *forense pero humano*. Los agentes tienen personalidad (nombres, especialidades, color asignado) pero los datos son fríos y trazables.

---

## 1. Mapeo conceptual: Hermes → Sabueso

| Hermes War Room | Sabueso | Por qué |
|---|---|---|
| Mission | Investigación | Lo que el usuario inicia |
| Orchestrator (lider) | Sabueso (jefe) | Personaje narrador único |
| Operative / Profile | Investigador | Subagente con rol y carácter |
| Workstation | Cubículo | Estación visual de cada investigador |
| SOUL.md | Expediente | Perfil editable del investigador |
| Kanban task | Pista (lead) | Unidad de trabajo investigativo |
| `delegate_task` | Asignar pista | Sabueso pasa una pista a un investigador |
| `kanban_complete` | Cierre con hallazgo | Investigador devuelve evidencia + confianza |
| Auto-nudge | Consolidación | Sabueso integra hallazgos en el dossier |
| Mission archive | Hemeroteca | Histórico de investigaciones |
| The Team | La Redacción | Página del equipo de investigadores |

---

## 2. El cast: los 7 investigadores

Cada subagente es un personaje con nombre, especialidad, color asignado y avatar. Esto es el cambio más importante respecto al Investigation Cinema original: en vez de "Subagent: contracts_check", ves a **El Contador**, y la gente lo recuerda.

| Callsign | Rol técnico | Especialidad | Color | Tools |
|---|---|---|---|---|
| **Sabueso** | Orquestador | Decompone, planifica, integra, escribe el dossier | `amber-500` | LangGraph state, all subagents |
| **El Buscador** | Recon agent | Encuentra la entidad en registros públicos (RENIEC, JNE, SUNAT) | `slate-400` | `find_dni`, `find_ruc`, `find_party_record` |
| **La Tasadora** | Patrimony agent | Cruza declaración jurada con propiedades reales (SUNARP, SBS) | `emerald-500` | `get_jne_declaration`, `query_sunarp`, `appraise_assets` |
| **El Contador** | Contracts agent | Recorre SEACE/OECE, detecta adjudicaciones, traza flujos | `violet-500` | `search_seace`, `get_contract_detail`, `trace_payment` |
| **El Letrado** | Legal agent | Busca leyes votadas, conflictos normativos, sentencias judiciales | `sky-500` | `query_legalize_pe`, `search_sentences`, `cross_vote_interest` |
| **El Detective** | Relationships agent | Mapea familia, socios, directorios de empresas | `rose-500` | `find_relatives`, `query_sunarp_board`, `expand_network` |
| **El Periodista** | News & social agent | Archivos de prensa, redes sociales, escándalos previos | `orange-500` | `search_newspapers`, `query_twitter_archive`, `wayback_machine` |
| **La Jueza** | Verifier (MoA) | Critica claims, asigna confianza, marca contradicciones | `red-600` | `verify_claim`, `cross_check_sources`, `confidence_score` |

**Avatares:** usar Dicebear `notionists` o `lorelei` (Sabueso es LATAM, tonos cálidos). Cada investigador tiene una *seed* fija, así que su cara es siempre la misma. Sabueso tiene avatar especial (perro detective con lupa) generado a mano o vía Midjourney/SDXL como SVG.

**Naming en español es deliberado.** Crafter Station y los jurados son LATAM. El "personaje detective" en español tiene weight cultural. Si querés sumar guiño, agregá un investigador rotativo opcional **El Pituco** que mira solo cuentas offshore y empresas fantasma — ese cameo es opcional para el demo.

---

## 3. Sistema de diseño

> **Identidad visual base: Anthropic (Claude).** Sabueso adopta la paleta cálida, la tipografía editorial y el branding de Claude/Anthropic como fundación. Los tokens se extienden con colores semánticos propios para la capa de investigación.

### 3.1 Branding

- **Color primario de marca:** Terra Cotta `#DA7756` — el naranja cálido característico de Claude.
- **Filosofía cromática:** tonos terrosos, cálidos y humanistas. Nada frío ni clínico. El modo oscuro se siente como "conversación de noche", no como terminal.
- **Logo:** el ícono de Sabueso (perro detective con lupa) usa como acento principal el terra cotta `#DA7756` para mantener coherencia con el ecosistema Claude.

### 3.2 Paleta de colores

**Modo claro (default):**

```
bg-canvas        #FAF9F5   /* fondo principal — off-white cálido (Claude light) */
bg-surface       #FFFFFF   /* paneles, cards elevadas */
bg-surface-2     #F5F3EE   /* paneles anidados, sidebar */
bg-paper         #EEECE2   /* "paper texture" para badges, evidencia */
border-default   #E8E6DC   /* borders neutros */
border-strong    #D4D2CA   /* borders énfasis */
text-primary     #141413   /* near-black con subtono cálido */
text-secondary   #5A5750   /* gris oscuro cálido */
text-muted       #B0AEA5   /* terciario */
text-paper       #3D3929   /* texto sobre bg-paper */
accent           #DA7756   /* terra cotta — acento principal Claude */
accent-hover     #BD5D3A   /* terra cotta profundo — hover/active */
accent-subtle    #DA775620 /* terra cotta 12% — tint de fondo */
```

**Modo oscuro:**

```
bg-canvas        #141413   /* fondo principal — near-black cálido (Claude dark) */
bg-surface       #1D1D1B   /* paneles principales */
bg-surface-2     #262623   /* paneles anidados, cards */
bg-paper         #2E2C28   /* "paper texture" adaptado a dark */
border-default   #3D3A35   /* borders neutros */
border-strong    #4A4944   /* borders énfasis */
text-primary     #FAF9F5   /* off-white cálido (light invertido) */
text-secondary   #B0AEA5   /* gris medio cálido */
text-muted       #706E68   /* terciario */
text-paper       #E8E6DC   /* texto sobre bg-paper (dark) */
accent           #DA7756   /* terra cotta — consistente en ambos temas */
accent-hover     #E8956F   /* terra cotta claro — hover en fondo oscuro */
accent-subtle    #DA775620 /* terra cotta 12% — tint de fondo */
```

**Semánticos de investigación (mismos en ambos modos, ajustados para contraste):**

```
declared        #788C5D   /* verde bosque Anthropic — declarado por el funcionario */
discovered      #6A9BCC   /* azul Anthropic — cross-reference de fuente pública */
ambiguous       #D4A843   /* ámbar terroso — requiere verificación */
suspicious      #C4583A   /* rojo terracota — patrón anómalo detectado */
conflict        #9B2C2C   /* rojo profundo — conflicto de interés confirmado */
verified        #6A9BCC   /* azul acero Anthropic — confirmado por La Jueza */
```

**De personajes:** los 7 colores listados en §2. Se usan como **acento, stripe izquierdo del card, y tinte del cubículo**. Nunca como fondo de gran área.

### 3.3 Tipografía

| Uso | Familia | Peso | Tracking | Notas |
|---|---|---|---|---|
| Display H1 (página) | **Copernicus** | 600 | -0.02em | Display serif de Claude. Fallback: **Lora** 700 |
| Section H2 | **Copernicus** | 500 | -0.01em | Fallback: **Lora** 600 |
| Callsigns (nombres de investigador) | **Lora** italic | 500 | normal | Serif editorial, coherente con la marca |
| Body text / UI labels | **Styrene B** | 400 | normal | Sans humanista de Claude. Fallback: **Poppins** 400 |
| Body emphasis | **Styrene B** | 500 | normal | Fallback: **Poppins** 500 |
| Datos: DNI, RUC, $, fechas, IDs | **JetBrains Mono** | 400 | -0.01em | Monospace oficial del ecosistema Claude |
| Code blocks (claims, JSON) | **JetBrains Mono** | 400 | normal | — |

**Stack de fallback web:**
```css
--font-display: 'Copernicus', 'Lora', ui-serif, Georgia, serif;
--font-body:    'Styrene B', 'Poppins', ui-sans-serif, system-ui, sans-serif;
--font-mono:    'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
```

**Por qué:** Copernicus es el display serif de Anthropic (gravitas editorial, tipografía seria). Styrene B es el sans humanista que Claude usa para UI (legible, cálido, no genérico). JetBrains Mono para datos forenses. Lora y Poppins son los fallbacks gratuitos recomendados en las brand guidelines de Anthropic — disponibles vía Google Fonts.

### 3.4 Espacio y radius

```
spacing: tailwind default
radius-sm:    6px   /* chips, badges — ligeramente más suave como Claude */
radius-md:    10px  /* cards, inputs */
radius-lg:    16px  /* paneles */
radius-xl:    24px  /* hero sections, modales */
radius-full:  9999px /* avatars, status LEDs, pills */
```

### 3.5 Motion

Las animaciones son **rápidas y funcionales**, nunca decorativas:

```
ease-out:    cubic-bezier(0.16, 1, 0.3, 1)   /* default */
ease-in-out: cubic-bezier(0.4, 0, 0.2, 1)
spring-soft: cubic-bezier(0.34, 1.56, 0.64, 1)  /* materializaciones */

duration-fast:    150ms  /* hover, click feedback */
duration-base:    250ms  /* aparición de cards */
duration-slow:    400ms  /* spawn de nodos en el grafo */
duration-narrate: 700ms  /* "speech bubble" entries */
```

**Marcha de hormigas** (delegación viva): SVG `stroke-dasharray` animado con `animate-marching-ants` (CSS keyframe, `stroke-dashoffset` de 0 a 20 en loop 800ms lineal).

**LED pulse** (estado activo): caja `box-shadow` animada en `@keyframes pulse-led` 1.4s ease-in-out infinite.

**Speech bubble pop**: `transform: scale(0.7)` + `opacity: 0` → `scale(1)` + `opacity: 1` con spring-soft, 200ms.

---

## 4. Arquitectura de información (rutas)

```
/                            Landing público (sin auth)
/auth/login                  Login (Supabase OAuth Google + magic link)
/app                         Shell autenticada
├── /                        Home: nueva investigación + investigaciones recientes
├── /search                  Búsqueda avanzada con autocompletado
├── /i/[id]                  Investigación (modo Cinema en vivo)
│   ├── /                    Vista por defecto: 3 paneles
│   ├── /graph               Grafo full-screen
│   ├── /sankey              Sankey de flujos de dinero
│   ├── /timeline            Timeline temporal
│   └── /dossier             Solo el dossier (vista lectura)
├── /i/[id]/agent/[callsign] Drill-down de un investigador específico
├── /redaccion               La Redacción (página del equipo)
├── /redaccion/[callsign]    Perfil editable de un investigador (expediente)
├── /hemeroteca              Archivo: lista de todas las investigaciones
├── /comparar                Comparador de N entidades lado-a-lado
└── /settings                Preferencias, API keys, notificaciones
```

---

## 5. Página: `/app` — Home

**Propósito:** punto de partida con cero fricción y atajos a investigaciones recientes.

```
┌─────────────────────────────────────────────────────────────┐
│ [Logo Sabueso 🐕‍🦺]               [🔔]  [Avatar usuario]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│              SABUESO                                        │
│         Tras la pista de la corrupción                      │
│                                                             │
│   ┌─────────────────────────────────────────────────┐      │
│   │ 🔍  Investiga a un funcionario, candidato...    │      │
│   │     Ej: "Vladimir Cerrón", "RUC 20100070970"   │      │
│   └─────────────────────────────────────────────────┘      │
│                                                             │
│   Sugerencias en tendencia hoy:                            │
│   [🏛️ Candidatos presidenciales 2026]  [🔥 MINSA contratos]│
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ TUS INVESTIGACIONES RECIENTES                               │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│ │ ⚫🟣 abierta  │ │ ⚫🟢 cerrada │ │ ⚫🔴 cerrada │ ...      │
│ │ Fulano P.    │ │ Empresa X   │ │ Ministerio Y │         │
│ │ hace 2h      │ │ hace 1d     │ │ hace 3d     │         │
│ │ 12 pistas    │ │ 28 pistas   │ │ 5 alertas   │         │
│ └──────────────┘ └──────────────┘ └──────────────┘         │
├─────────────────────────────────────────────────────────────┤
│ DE LA COMUNIDAD                                             │
│ Investigaciones públicas más visitadas esta semana...      │
└─────────────────────────────────────────────────────────────┘
```

**Detalles:**

- El input es el componente `PromptInput` de AI Elements (Vercel) modificado: lupa a la izquierda, kbd hint `⌘K` a la derecha, autocompletado en dropdown desde Supabase Postgres full-text search.
- Tendencias son chips de `shadcn/ui` con emoji + texto. Click → pre-llena el input.
- Cards de investigación: bordes finos, stripe izquierda con color del estado, footer mono con timestamp + contador de pistas.

---

## 6. Página: `/i/[id]` — Investigación en Vivo (Cinema mode)

**El centro de gravedad del producto.** Aquí roba todo lo bueno de Hermes War Room.

### 6.1 Layout general (desktop)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ← Volver   📁 #INV-2026-0142 · Vladimir Cerrón     [Compartir] [⋯]      │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 67%      │ ← progress bar
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────┬──────────────────────────┬──────────────────┐   │
│  │ MISSION CONTROL    │    INVESTIGATION FLOOR   │  DOSSIER         │   │
│  │ (28%)              │    (44%)                 │  (28%)           │   │
│  │                    │                          │                  │   │
│  │ [Chat][Pistas]     │  ┌──────────────────┐    │  # Vladimir C.   │   │
│  │                    │  │  GRAFO LIVE      │    │                  │   │
│  │ ▶ Sabueso          │  │                  │    │  ## Estudios     │   │
│  │   Plan generado:   │  │   Fulano ──┐     │    │  PUCP 2010       │   │
│  │   "Cruzaré JNE,    │  │     │      │     │    │                  │   │
│  │    SEACE, SUNARP   │  │     ├─⚪   ⚪    │    │  ## Patrimonio   │   │
│  │    y prensa..."    │  │     │   Empresa │    │  - Casa 800K     │   │
│  │                    │  │     └─🔴 conf!   │    │                  │   │
│  │ ⚪ El Buscador 🟢  │  │                  │    │  ## 🚨 Alertas   │   │
│  │   Encontró RUC y   │  │  (cosmos.gl)     │    │  Empresa Y       │   │
│  │   trayectoria      │  └──────────────────┘    │  recibió S/. 10M │   │
│  │   ✓ 0.94 conf.     │                          │                  │   │
│  │                    │  Vistas:                 │                  │   │
│  │ ⚪ La Tasadora 🟡  │  [Grafo][Sankey][Timeline]│                  │   │
│  │   Querying SUNARP  │                          │                  │   │
│  │   for properties.. │  Filtros:                │                  │   │
│  │   ⏳ 14% done       │  ☐ Solo > S/.100K       │                  │   │
│  │                    │  ☐ Solo aristas rojas   │                  │   │
│  │ ⚪ El Contador 🟢  │  ☐ Solo 2024-2026       │                  │   │
│  │   ⚠️ ALERTA        │                          │                  │   │
│  │   Empresa Y firmó  │                          │                  │   │
│  │   4 contratos con  │                          │                  │   │
│  │   MINSA en 2024    │                          │                  │   │
│  │                    │                          │                  │   │
│  └────────────────────┴──────────────────────────┴──────────────────┘   │
│                                                                          │
│  ╔══════════════════ OPERATIVES FLOOR ════════════════════════════════╗ │
│  ║                                                                    ║ │
│  ║   ⚫       ⚫       ⚫       ⚫       ⚫       ⚫       ⚫        ║ │
│  ║  ╱  ╲    ╱  ╲    ╱  ╲    ╱  ╲    ╱  ╲    ╱  ╲    ╱  ╲          ║ │
│  ║ Sabueso Buscador Tasadora Contador Letrado Detective Periodista  ║ │
│  ║ 🟢      🟢       🟡       🟢       ⚪      🔴       ⚪            ║ │
│  ║ thinking working   working  working    idle   working   idle      ║ │
│  ║                                                                    ║ │
│  ║   ↓ ↘    ↓  ↘    ↗ ↓     ↓                                        ║ │
│  ║  curvas animadas mostrando delegaciones                            ║ │
│  ╚════════════════════════════════════════════════════════════════════╝ │
│                                                                          │
│  Timeline scrubber: ▬▬▬▬▬●▬▬▬▬▬▬   2018 ──── 2022 ──── 2026             │
└──────────────────────────────────────────────────────────────────────────┘
```

Cuatro zonas en orden vertical:

1. **Header sticky** con breadcrumb, ID de investigación, target, progreso, acciones.
2. **Cuerpo de 3 columnas**: Mission Control + Investigation Floor (grafo) + Dossier.
3. **Operatives floor**: cubículos físicos de los 7 investigadores con sus delegaciones dibujadas.
4. **Timeline scrubber inferior**.

En **móvil**, las 3 columnas se apilan verticalmente y el floor pasa a ser una fila horizontal scroll con cards compactas de cada investigador.

### 6.2 Mission Control (panel izquierdo, 28%)

Replica el patrón de Hermes — dos tabs:

**Tab "Chat":**

- Stream tipo `useChat` de AI Elements, pero con un giro: cada mensaje del "asistente" es en realidad de un investigador específico, identificable por avatar + color stripe + callsign.
- Cuando Sabueso descompone, su mensaje aparece con su avatar y color ámbar.
- Cuando un investigador entrega un hallazgo, llega como mensaje suyo con su color.
- Usa el componente `Reasoning` de AI Elements (collapsible) para mostrar el thinking del orquestador o el OODA loop de un subagente, sin spamear la columna.
- Usa el componente `Tool` para renderizar las tool calls: tarjeta plegable con `tool_name(args) → result`. Ej: `search_seace_contracts(ruc="20100070970", year=2024) → 4 contracts found`.
- Bubble del usuario al final con `PromptInputTextarea` para pedir refinamiento ("también revisa a su esposa", "ignora contratos < 100K"). Esto Sabueso lo traduce en nuevas pistas y delega.

**Tab "Pistas" (kanban):**

Exactamente como el kanban de Hermes War Room: 4 columnas.

```
┌─────────┬──────────┬──────────┬─────────┐
│ POR     │ LISTAS   │ EN CURSO │ CERRADAS│
│ ASIGNAR │          │          │/BLOQUEAS│
├─────────┼──────────┼──────────┼─────────┤
│ [🟣 P3] │ [🟢 P1] │ [🟡 P5] │ [🟢 P2] │
│ Buscar  │ Cruzar  │ Trazar  │ Recon   │
│ socios  │ JNE vs  │ flujos  │ ✓ done  │
│ empresa │ patrim. │ SEACE   │         │
│ "Pesque-│         │         │         │
│  ría X" │ asignada│ asignada│ ✓ 0.94  │
│         │ a       │ a       │         │
│ sin asig│Tasadora │Contador │ El Buscador│
└─────────┴──────────┴──────────┴─────────┘
```

- Cards: stripe izquierda con color del investigador asignado. Título corto. Tiempo transcurrido en mono pequeño. Estado iconográfico.
- Drag opcional entre columnas (Sabueso humano puede reasignar manualmente).
- Click en una card → drill-down del investigador asignado (ver §7).

### 6.3 Investigation Floor (panel central, 44%)

Donde vive el grafo. Tres vistas en tabs, **animadas con transiciones cross-fade de 200ms**, no recargas duras:

- **Grafo (default)** — fuerza dirigida con cosmos.gl o react-force-graph.
- **Sankey** — `@nivo/sankey` con flujo Tesoro → Ministerio → Contrato → Empresa → Beneficiarios.
- **Timeline** — `@visx/timeline` o `lightweight-charts`. Eventos atómicos: nacimiento del candidato, postulaciones, declaraciones, contratos firmados, votos polémicos, sentencias.
- **Texto** (bonus, opcional) — Markdown rendering plano si alguien quiere ver el dossier completo sin distracciones.

**Mecánica live del grafo (mantenida del Cinema mode original):**

1. Inicio: solo el target en el centro.
2. Cuando un investigador inserta un finding en `investigation_events` (Supabase Realtime), el front recibe el evento, calcula el nuevo `(entity, edge)` y los **materializa con spring-soft animation** (scale 0.7 → 1.0, fade in, posición inicial random ±50px del padre).
3. **Color del nodo** según su origen semántico (§3.1).
4. **Grosor de arista** = `confidence` del claim que la sustenta (0.4 → 4px).
5. **Pulso rojo** sobre nodos cuando un edge nuevo los marca como sospechosos.

**Modo Sankey (toggle):**

- Solo se muestra cuando hay datos de dinero en el grafo.
- Highlight de **rojo** las rutas donde la suma final llega a un beneficiario que aparece también como relación cercana del funcionario.
- Hover sobre un nodo: tooltip con suma agregada y número de contratos.

**Filtros (rail derecho del panel, colapsable):**

```
☐ Solo monto > S/. 100K
☐ Solo aristas rojas (conflictos)
☐ Solo 2024–2026
☐ Solo familia 1er grado
☐ Mostrar nodos no verificados
```

### 6.4 Dossier (panel derecho, 28%)

El **artefacto entregable**. Markdown con secciones que se van llenando en tiempo real:

```markdown
# Vladimir Roberto Cerrón Rojas
ID: 12345678 · RUC representado: 20100070970

## Datos básicos
- Nacimiento: 1971
- Profesión: Médico, MBA
- Partido: Perú Libre

## 📚 Estudios verificados
- PUCP 2010 (verificado en JNE) ✓ 0.96

## 💰 Patrimonio declarado
| Tipo | Detalle | Monto |
|---|---|---|
| Inmueble | Casa Junín | S/. 800K |

## 📜 Cargos públicos
- Gobernador Junín 2014-2018

## 📑 Contratos en su periodo
- 4 contratos totalizando S/.10M
  con Empresa Y entre 2014-2018

## 🚨 ALERTAS DETECTADAS
1. **Vínculo conflicto:** Empresa Y comparte
   director con su esposa (verificado SUNARP)
2. **Patrón anómalo:** ingresos declarados
   S/.50K, propiedades sumadas > S/.1.2M

## Fuentes (12)
- JNE Plataforma Electoral [↗]
- SEACE OECE 2017 [↗]
- ...
```

- Cada claim tiene un **chip** al lado: `✓ 0.94` (color verde si > 0.85, ámbar 0.6-0.85, rojo < 0.6).
- Hover sobre una sección: muestra qué investigador la pobló.
- Click en una alerta: scrollea/zoom al nodo correspondiente en el grafo.
- Sección "Fuentes" usa componente `Source` de AI Elements con chips clickables.

Acción primaria al final: **`Exportar como PDF`** con cabecera oficial Sabueso, código QR para versión web, todas las citas con URLs.

### 6.5 Operatives Floor (banda inferior horizontal)

**El roba más caro y más vendedor de Hermes.** Una banda de ~140px de alto donde viven los 7 investigadores como cubículos visibles.

```
              ⚫ avatar               ┌──────────┐
            ╱       ╲                │ Sabueso  │ ← name placard
           │ stationing │             │ 🟢 LED    │
            ╲       ╱                └──────────┘
              ──────                  ┌──────────┐
            disco tinted              │"thinking"│ ← status pill
            color asignado            └──────────┘
                                      "Cruzando 4 fuentes..."  ← speech bubble (opt.)
```

**Anatomía de un cubículo:**

1. **Disco tinted** (60px diámetro, tint = color del investigador a 25% opacity, blur radial debajo simulando "luz").
2. **Avatar Notionists** (48px) "parado" encima del disco (un poco offset hacia arriba, sombra suave debajo).
3. **Speech bubble cómic** sobre la cabeza cuando el investigador está activo y reportando un step. Solo aparece si hay actividad. Bordes redondeados, cola apuntando al avatar, fondo `bg-paper` con texto `text-paper`, fuente IBM Plex Mono, max 80 caracteres. Se renueva con cada paso.
4. **Name placard** (rect rounded-md, fondo `bg-surface-2`, border-bottom 2px del color asignado): callsign en Instrument Serif italic + LED de 6px pulsando del color del estado.
5. **Status pill** (rounded-full, padding compacto, fondo translúcido con tint del estado):
   - `idle` → "En espera" gris
   - `thinking` → "Pensando..." con el dot animado de 3 puntos
   - `working` → "Trabajando: <truncated 28 chars>" 
   - `blocked` → "Bloqueado: <error>" rojo
   - `done` → "Cerrado · ✓ 0.94" verde

**Flechas de delegación entre cubículos:**

- Path SVG curvo (Bezier) desde el disco origen al disco destino.
- Cuando la pista está **en estado `running`**, el path tiene `stroke-dasharray` animado (marching ants).
- Cuando está **`done`**, queda estática y semitransparente.
- Cuando está **`blocked`**, parpadea en rojo.
- El color de la flecha es el color del **delegador**, no del receptor.

**Interacción:** click en cualquier cubículo → abre el **drill-down panel** (§7).

### 6.6 Timeline scrubber (banda inferior, 48px alto)

- Línea horizontal con marcas de año.
- **Eventos representados como puntos** del color del investigador que los descubrió.
- Drag del scrubber: el **grafo arriba se anima al estado de esa fecha** (nodos que aún no existían quedan grises o desaparecen).
- Doble-click en un evento: zoom al nodo correspondiente.

---

## 7. Drill-down Panel del Investigador

**El otro roba grande de Hermes War Room.** Slide-in desde la derecha (no modal, no oculta el resto), 400px de ancho, dismissable con `Esc`.

Contenido en orden vertical:

```
┌─────────────────────────────────────────────┐
│  ⚫ El Contador                       [×]   │
│  Especialista en contratos públicos         │
│  ──  modelo: Kimi K2.6                      │
├─────────────────────────────────────────────┤
│  ESTADO ACTUAL                              │
│  🟡 Trabajando · Pista #P5                  │
│  Iniciado hace 47s · last heartbeat 2s ago  │
│                                             │
│  PISTA EN CURSO                             │
│  ┌──────────────────────────────────────┐  │
│  │ "Trazar flujos de SEACE 2014-2018    │  │
│  │  para entidad Gobierno Regional      │  │
│  │  Junín, filtrar por RUC del 'lider'  │  │
│  │  Cerrón y su entorno"                │  │
│  │ asignada por: ⚫ Sabueso              │  │
│  │ prioridad: alta · tiempo límite 90s  │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  SUBTAREAS DELEGADAS                        │
│  ├─ ⚫ El Detective: "Buscar empresas con   │
│  │   dirección compartida con sospechoso"   │
│  │   🟢 done · 0.91 conf                    │
│  ├─ ⚫ El Letrado: "Verificar inhabilitac.  │
│  │   de Empresa Y en OSCE"                  │
│  │   🟡 working · 32% done                  │
│                                             │
│  ACTIVIDAD RECIENTE (live)                  │
│  ├─ 14:32:01 · tool · search_seace_contracts│
│  │   args: {ruc:"...", year_from:2014}     │
│  │   → 4 contracts, S/.10.2M total          │
│  ├─ 14:32:14 · reasoning · "El monto total  │
│  │   es 200x el patrimonio declarado"       │
│  ├─ 14:32:18 · finding · creó claim         │
│  │   "Empresa Y recibió S/.10M sin compet"  │
│  │   confidence: 0.88                       │
│  ├─ 14:32:22 · delegation · creó pista      │
│  │   para El Detective                      │
│  └─ ...                                     │
│                                             │
│  HILO DE MISIÓN (read-only)                 │
│  Conversación con Sabueso sobre esta pista. │
│                                             │
│  ─────────────────────────────────          │
│  [Pausar este investigador]                 │
│  [Re-asignar pista a otro]                  │
│  [Cancelar pista]                           │
└─────────────────────────────────────────────┘
```

**Patrones técnicos clave:**

- **Activity timeline en vivo** vía Supabase Realtime subscribiéndose a `investigation_events WHERE agent_callsign = ?`. Cada nuevo evento entra con un slide-in de 200ms y queda con borde izquierdo coloreado del tipo (`tool` violeta, `reasoning` slate, `finding` esmeralda, `delegation` ámbar).
- **Delegation chain hacia arriba**: si el agent está trabajando en una pista que fue delegada por otro, muestra el árbol hasta Sabueso. Click en cualquier nodo del árbol → cambia el drill-down a ese investigador.
- **Subtaskas** son cards plegables; expandir muestra la pista entera y su drill-down hijo.
- Acciones al pie son útiles para el demo en vivo: pausar un investigador es **dramático** y muestra control humano.

---

## 8. Página `/redaccion` — La Redacción

Equivalente al `/team` de Hermes pero rebautizado. La página donde el usuario ve a **los 7 investigadores como ID cards de papel de prensa**, con la opción de personalizarlos.

### 8.1 ID card (Press Pass aesthetic)

Cada card replica el patrón de Hermes (badge de identificación de papel) pero con identidad periodística:

```
        ╱╲
       ╱  ╲              ← lanyard hole
      ┌──────┐
      │      │
      ├──────┤
      │SABUESO│           ← banda superior color asignado, 
      │REDACTOR          ← etiqueta "Sabueso · Investigador"
      │      │
      │ ┌──┐ │           ← retrato cuadrado con marcas de imprenta (crop marks)
      │ │[]│ │
      │ └──┘ │
      │      │
      │ »El Contador«    ← callsign en Instrument Serif italic
      │      │
      │ ROL  · Contracts │ ← datos en IBM Plex Mono
      │ MOD  · kimi-k2.6 │
      │ ID   · 03-25     │
      │ STAT · 🟢 ACTIVE │
      │      │
      │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │ ← código de barras renderizado en CSS
      │ #SBS-0003-2026   │
      │      │
      └──────┘
```

**Renderizado del código de barras en CSS puro** (no SVG, no imagen):

```css
.barcode {
  display: flex;
  gap: 1px;
}
.barcode > i { /* cada barra */
  width: 2px;
  height: 28px;
  background: currentColor;
}
.barcode > i:nth-child(3n)   { width: 1px; }
.barcode > i:nth-child(5n+1) { width: 3px; }
.barcode > i:nth-child(7n+2) { height: 24px; }
```

Genera variación pseudoaleatoria a partir de un hash del callsign. Look auténtico.

**Marcas de imprenta** (crop marks) en cada esquina del retrato: 4 cruces pequeñas (`⊕`) de 8px en `text-muted`.

### 8.2 Hover y acciones

Hover sobre un badge:
- El card sube 4px con shadow más profundo.
- Aparece overlay con dos botones: **`Expediente`** (ver/editar) y **`Estadísticas`**.

Click en `Expediente` → navegación a `/redaccion/[callsign]` con:

- **Identidad** (callsign, descripción, color, avatar seed).
- **Modelo** (dropdown: Claude Sonnet 4.6, Kimi K2.6, DeepSeek V4 Flash, GPT-5.5).
- **Skills** (chips toggle: cuáles tools tiene permitidas).
- **Reglas de comportamiento** (textarea con el system prompt editable).
- **Pre-aprobaciones** (lista de tools que puede usar sin confirmación).
- **Botón "Restaurar default"** (recupera el config original de Sabueso).

Click en `Estadísticas`:

- Total de pistas trabajadas.
- Confianza promedio.
- Fuentes más consultadas (pie chart pequeño).
- Tiempo promedio por pista.
- Tasa de "blocked" vs "done".

### 8.3 Acciones a nivel de página

- **`Contratar`** (botón secundario, top-right): clona un investigador existente como base, abre modal de expediente. Útil para crear roles específicos por jurisdicción (ej. "El Contador Cusco") sin tocar al base.
- **`Despedir`** (dentro del expediente): elimina el rol custom. Los 7 default no pueden eliminarse.
- **Toggle activo/inactivo** en cada badge: el roster de Sabueso se ajusta. Si "El Periodista" está inactivo, Sabueso no le delegará en investigaciones nuevas.

---

## 9. Página `/hemeroteca` — Archivo

Lista paginada de investigaciones pasadas. Replica el `/missions` de Hermes:

```
HEMEROTECA   Filter: [ Abiertas | Cerradas | Públicas | Todas ]   [🔍 buscar]

┌──────────────────────────────────────────────────────────────┐
│ #INV-2026-0142  🟣 cerrada                          hace 2h  │
│ Vladimir Cerrón                                              │
│ 12 pistas · 3 alertas · 8 fuentes                            │
│ "Patrimonio incongruente con cargo público"                  │
├──────────────────────────────────────────────────────────────┤
│ #INV-2026-0141  🟢 cerrada                          hace 1d  │
│ Empresa Constructora XYZ S.A.C.                              │
│ 28 pistas · 5 alertas · 14 fuentes                           │
├──────────────────────────────────────────────────────────────┤
│ ...                                                           │
└──────────────────────────────────────────────────────────────┘
```

- Click en una investigación: abre en modo lectura (`/i/[id]/dossier`).
- Cada item tiene un menú `⋯` para: **Reabrir** (con nuevas pistas), **Compartir público**, **Archivar**, **Eliminar**.
- Búsqueda full-text con `pg_trgm` sobre dossiers + entidades.

---

## 10. Página `/comparar` — Comparador

Vista lado-a-lado de 2 a 4 entidades. Útil para periodistas previo a elecciones.

```
┌────────────────────┬────────────────────┬────────────────────┐
│ Candidato A         │ Candidato B        │ Candidato C        │
│ [avatar]            │ [avatar]           │ [avatar]           │
├────────────────────┼────────────────────┼────────────────────┤
│ HEATMAP DE RIESGO   │                    │                    │
│ Patrimonio  🟢      │ Patrimonio  🟡    │ Patrimonio  🔴    │
│ Contratos   🟢      │ Contratos   🔴    │ Contratos   🟡    │
│ Conflictos  🟢      │ Conflictos   🟡    │ Conflictos  🟢    │
│ Antecedentes 🟢     │ Antecedentes 🟢   │ Antecedentes 🔴   │
│                    │                    │                    │
│ Score 8.4/10        │ Score 5.2/10      │ Score 3.1/10      │
│                    │                    │                    │
│ Patrimonio decl.    │                    │                    │
│ S/. 1.2M             │ S/. 800K          │ S/. 3.5M          │
└────────────────────┴────────────────────┴────────────────────┘
```

El **heatmap** es el feature más rápido de "leer" un perfil completo. Cada dimensión 0-10 calculada por La Jueza.

---

## 11. Componentes de librería (registro de implementación)

Para que Emdash + agentes lo construyan ordenadamente, listo cada componente con prop signature en TypeScript:

```typescript
// /packages/ui/components/investigation/

<InvestigatorAvatar 
  callsign={"el-contador"} 
  size={48 | 64 | 96}
  status={"idle"|"thinking"|"working"|"blocked"|"done"}
  withSpeechBubble?={boolean}
  speechText?={string}
/>

<InvestigatorWorkstation
  callsign={...}
  status={...}
  currentTask?={Task}
  onClick={() => openDrilldown(callsign)}
/>

<DelegationArrow
  from={callsign}
  to={callsign}
  status={"running"|"done"|"blocked"}
  // SVG path calculado en base a posiciones
/>

<InvestigatorBadge        // ID card de prensa
  callsign={...}
  active={boolean}
  onClickExpediente={...}
  onClickStats={...}
/>

<StatusPill
  status={...}
  text?={string}
/>

<TaskCard               // card del kanban
  task={Task}
  compact?={boolean}
  onClick={...}
/>

<DrilldownPanel
  investigator={callsign}
  onClose={...}
/>

<FindingMessage         // mensaje en el chat estilo "hallazgo"
  investigator={callsign}
  claim={Claim}
  confidence={number}
/>

<InvestigationGraph
  investigationId={uuid}
  mode={"force"|"sankey"|"timeline"}
  filters={Filters}
  onNodeClick={...}
  onEdgeClick={...}
/>

<DossierPanel
  investigationId={uuid}
  liveUpdates?={boolean}
/>

<TimelineScrubber
  events={Event[]}
  current={Date}
  onChange={(d) => snapshotGraphAt(d)}
/>

<EvidenceChip          // pequeño chip de fuente con link
  sourceUrl={string}
  sourceType={"jne"|"seace"|"sunarp"|"news"|"legalize"}
/>

<ConfidenceBadge      // badge "✓ 0.94"
  value={number}      // 0..1
/>
```

Todos usan **shadcn/ui como base** + tokens del sistema de diseño + AI Elements para chat/reasoning/tools.

---

## 12. Estados especiales

### 12.1 Empty state (cuando entra a `/i/[id]` antes que el orquestador haya producido el plan)

```
[avatar Sabueso grande pensativo]

  El Sabueso está armando el plan...
  
  ⏳ Identificando entidad
  ⏳ Cargando contexto histórico
  ⏳ Convocando al equipo

```

### 12.2 Loading state de un investigador

Cuando un cubículo está esperando a que arranque (provisioning del subagente):

- Avatar en silueta gris
- LED amarillo parpadeante
- Status pill "Preparándose..."
- No clickable

### 12.3 Error state de una pista

Si un tool falla 3 veces:
- Pista pasa a columna "Bloqueadas"
- Card en rojo con icono ⚠️
- En el drill-down, badge rojo "Atascado en `search_sunarp` — 403 Forbidden"
- Acción "Reintentar con otro IP/región"

### 12.4 Investigación cerrada exitosa

Cuando todas las pistas se cierran y La Jueza firma:

- Animation: por encima del grafo aparece overlay tenue
- Mensaje: "🎯 Investigación completada · 12 hallazgos · 3 alertas detectadas"
- CTA: `Ver dossier final` + `Compartir`
- Confeti **solo si** hay alertas de conflicto (es un hallazgo significativo). Si no, animación más sobria.

---

## 13. Accesibilidad

- **Contraste mínimo 4.5:1** en todo texto sobre fondos. El gris #71717A está al borde — usado solo para texto secundario.
- **Estados no solo por color**: cada estado tiene también un icono y/o texto. Daltónicos leen el LED + el texto del pill.
- **Foco visible**: todos los elementos interactivos tienen `:focus-visible` con ring de 2px en `accent` (`#DA7756` terra cotta Claude).
- **Reduced motion**: `prefers-reduced-motion: reduce` → desactiva marching ants, materialización de nodos, pulse LEDs. Solo cross-fades.
- **Aria-live regions** en el chat, en el kanban, y en el activity timeline del drill-down — para lectores de pantalla cuando entran eventos nuevos.
- **Navegación por teclado**:
  - `⌘K` — abrir búsqueda
  - `1-7` — focus al cubículo del investigador N
  - `G` / `S` / `T` — cambiar vista a Graph / Sankey / Timeline
  - `D` — toggle dossier panel
  - `Esc` — cerrar drill-down / modal
  - `↑↓` en chat — historia de mensajes

---

## 14. Audio (opcional, toggleable, off por default)

Hermes War Room no tiene sonido, pero un proyecto cinematográfico se beneficia. Sutil:

- **`finding-detected.mp3`** (~200ms, sci-fi click suave) cuando aparece un hallazgo nuevo
- **`alert-conflict.mp3`** (~400ms, alarma muy corta) cuando se materializa un nodo rojo
- **`investigation-complete.mp3`** (~1.5s, campana de redacción/breaking news) al cerrar

Todos toggleables en settings. Off por default para no asustar en demo si llega un audio inesperado.

---

## 15. Específico para el demo de hackathon (Lun 17 May)

Tres ajustes para que el demo no falle:

1. **Pre-cachear** las 5 investigaciones de tus funcionarios objetivo. Las "investigaciones en vivo" durante el demo son replay desde Supabase Realtime con timing artificial → el jurado ve los nodos materializarse, los agentes pensar, las alertas surgir. No esperás API externa.
2. **Modo "Director"** (debug, hidden, accesible por `⌘⌥D`): te permite pausar el replay, scrollear adelante, hacer click en cosas específicas. Útil si el jurado interrumpe con pregunta.
3. **Easter egg fínalista**: en el footer un pequeño "🐕‍🦺 Construido en 4 días con Emdash + Claude + Kimi". Honesto. Vendedor.

---

## 16. Open questions y trade-offs reconocidos

- **Cosmograph (CC BY-NC 4.0) vs react-force-graph (MIT)**: para hackathon usa Cosmograph (más bonito), si el proyecto se vuelve comercial migra a react-force-graph.
- **Avatares Notionists**: bonitos pero genéricos. Si tenés 2 horas extras, encarga a un ilustrador 7 retratos para los investigadores. Eleva la marca brutalmente.
- **Spanish naming vs English**: el doc está en español. Los componentes de código mantenelos en inglés (`InvestigatorAvatar`), las strings UI en español. i18n con `next-intl` para futuro.
- **Lighthouse**: el grafo en cosmos.gl es GPU-heavy. En el demo, monitor del jurado puede ser pobre. Ten un fallback "modo lite" con grafo D3 estático en SVG si detectas baja performance.

---

## Fin

Construye en este orden:

1. Design system tokens Claude/Anthropic + tipografía + paleta (`packages/ui/tokens`)
2. Componentes atómicos (Avatar, StatusPill, ConfidenceBadge, Badge)
3. Componentes de investigación (Workstation, DelegationArrow, DrilldownPanel)
4. Layout de `/i/[id]` con 3 paneles
5. Operatives floor y arrows
6. Grafo con cosmos.gl (modo force)
7. Sankey y Timeline modes
8. La Redacción (badges + expedientes)
9. Hemeroteca + Comparar
10. Estados especiales y pulido

> *"Hermes mostró cómo se ven los agentes trabajando. Sabueso muestra cómo se ve la verdad siendo descubierta."*
