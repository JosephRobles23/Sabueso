# Demo targets — S-17 pre-cache

Cinco objetivos cacheados que se reproducen en `mode=replay` durante el pitch del
lunes. La selección sigue los criterios de `docs/architecture.md` §12.1
(diversidad política, mezcla abierto/cerrado, accesibilidad de fuentes).

> ⚠️ **Estos nombres son sugerencias con criterio neutral. Antes de hacer el
> pre-cache en producción debe firmarlos un editor con la lista oficial de
> candidatos JNE 2026 a mano y verificar que ninguno tenga orden judicial de
> protección activa.** Si alguno cae, ver §"Reemplazos rápidos" abajo.

## Criterios duros

- Toda información cruzada debe ser pública y verificable.
- Mezcla deliberada de espectro político (mínimo 2 partidos distintos).
- Al menos 1 caso "abierto" + 1 caso "cerrado/sentenciado".
- Al menos 1 candidato 2026 (carga electoral).
- Evitar nombres con orden judicial activa de protección.
- Disclaimer obligatorio en cada dossier.

## Los cinco

| # | Tipo | Nombre | Partido / sector | Caso visible | Estado | Fuentes principales | Riesgo |
|---|------|--------|------------------|--------------|--------|---------------------|--------|
| 1 | Candidato presidencial 2026 | **Keiko Fujimori Higuchi** | Fuerza Popular | Caso *Cócteles* — aportes no declarados a campañas 2011 y 2016 | Abierto (en juicio oral) | OjoPúblico (serie 2017-2024), IDL Reporteros, sentencias publicadas Poder Judicial, JNE hoja de vida 2026 | Hay coberturas adversariales en ambos sentidos — el dossier debe citar **ambas** acusaciones y descargos |
| 2 | Congresista actual | **Edgar Tello Montes** | Perú Libre | *Mochasueldos* — investigación periodística por descuentos no autorizados a personal del despacho | Abierto (Comisión de Ética) | Convoca (2023), IDL Reporteros (2024), Congreso — declaraciones juradas | Caso documentado pero no sentenciado: usar lenguaje cuidadoso ("denuncia", "indicios"), nunca afirmar culpabilidad |
| 3 | Ex-presidente con sentencia firme | **Alejandro Toledo Manrique** | Perú Posible (extinto) | Caso *Odebrecht* — sentencia condenatoria 2024 por colusión y lavado de activos | Cerrado / sentenciado | OjoPúblico (serie), Poder Judicial — expediente público, IDL Reporteros, Convoca | Bajo: caso firme, fuentes saturadas. Útil para mostrar saturación de hallazgos rojos |
| 4 | Gobernador regional | **Wilfredo Oscorima Núñez** | Alianza para el Progreso (Ayacucho) | Caso *Rolex* (2024) + denuncias de Contraloría sobre obras regionales | Abierto (Fiscalía + JNE) | IDL Reporteros (2024), OjoPúblico, Contraloría (informes públicos), SEACE | Bajo: declaraciones públicas + documentos oficiales |
| 5 | Funcionario técnico / entidad MINSA | **Ministerio de Salud del Perú** (RUC 20131373237) | Entidad estatal | Análisis de patrones SEACE 2014-2024 (no se acusa a una persona) | Demo SEACE (sin imputación) | Migration `008_seed_demo_entity.sql`, SEACE, Plataforma de Contrataciones del Estado | Mínimo: entidad pública sin individualización |

Diversidad política resultante: **FP / PL / PP (extinto) / APP / entidad estatal**
— cubre derecha-izquierda-centro + un caso institucional. Cumple el "mínimo 2
partidos distintos" del C4.

Estado abierto vs cerrado: 3 abiertos (Fujimori, Tello, Oscorima), 1 cerrado
(Toledo), 1 institucional (MINSA). Cumple "al menos 1 abierto + 1 cerrado".

## Reemplazos rápidos (si alguno cae)

- Candidato 2026 caído → revisar la lista JNE oficial y elegir uno con
  declaración jurada publicada y cobertura masiva.
- Congresista caído → otro caso Mochasueldos documentado en Convoca/IDL del
  último año (hay >10 candidatos sin acción judicial de protección).
- Ex-presidente caído → cambiar a **Pedro Castillo Terrones** (caso en curso,
  documentación amplia) o **Ollanta Humala** (sentenciado 2024).
- Gobernador caído → revisar últimos informes de Contraloría a gobernadores
  regionales y elegir uno con denuncia firme publicada.
- MINSA es estable; usar como ancla si todo lo demás se mueve.

## Disclaimer estándar (incluir en cada dossier)

> Este dossier consolida información pública verificable a la fecha de
> publicación. Las menciones a personas naturales y jurídicas se basan en
> registros gubernamentales y cobertura periodística citada. Ninguna afirmación
> de este documento sustituye a una sentencia firme; los procesos abiertos
> deben tratarse bajo principio de presunción de inocencia.

## Ejecutar el pre-cache

```bash
# 1) Verificar env vars (worker + api + Supabase + OpenRouter)
cat apps/worker/.env | grep -E "OPENROUTER|SUPABASE|LANGCHAIN"

# 2) Levantar API + worker en local con DB Supabase prod (o staging)
pnpm dev

# 3) Lanzar las 5 investigaciones
pnpm tsx scripts/record-demos.ts

# 4) Validar editorialmente cada dossier en /i/<id>/dossier
# 5) Si alguno tiene contenido problemático: re-correr o reemplazar

# 6) Snapshot SQL (Linux/WSL con pg_dump 16+)
bash scripts/dump-demo-investigations.sh

# 7) Confirmar
ls -la infra/supabase/seed/demo_investigations.sql
```

Las ids cacheadas se persisten en `apps/web/lib/demos.ts` (constante
`DEMO_TARGETS`). El `LiveOrReplayToggle` lee de ahí.

## Videos de respaldo (60s por demo, screen recording)

Si Vercel/Supabase falla mid-demo, el video local es el fallback. Subir a
`apps/web/public/demos/<slug>.webm` o a Vercel Blob.

| # | Slug | Path local | Vercel Blob URL |
|---|------|------------|------------------|
| 1 | keiko-fujimori | `apps/web/public/demos/keiko-fujimori.webm` | _pendiente — completar tras grabar_ |
| 2 | edgar-tello | `apps/web/public/demos/edgar-tello.webm` | _pendiente_ |
| 3 | alejandro-toledo | `apps/web/public/demos/alejandro-toledo.webm` | _pendiente_ |
| 4 | wilfredo-oscorima | `apps/web/public/demos/wilfredo-oscorima.webm` | _pendiente_ |
| 5 | minsa | `apps/web/public/demos/minsa.webm` | _pendiente_ |

Recomendado: OBS Studio · 1920×1080 · 30fps · 60s por demo · zoom moderado al
panel donde aparece el primer hallazgo rojo (time-to-wow <8s).
