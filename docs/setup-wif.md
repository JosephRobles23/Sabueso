# Setup · Workload Identity Federation (GitHub Actions ↔ GCP)

Esta guía configura **Workload Identity Federation (WIF)** para que los workflows de GitHub Actions de Sabueso desplieguen a Cloud Run **sin secretos de larga duración** (no `GOOGLE_APPLICATION_CREDENTIALS_JSON`, no service account keys subidas a Secrets).

GitHub presenta un OIDC token firmado a Google STS, que lo cambia por un access token efímero (1h) de una service account de GCP. Estándar de la industria para CI/CD a GCP.

> Una sola vez por proyecto GCP. Si ya existe un Workload Identity Pool, saltá a la sección **5. Service accounts**.

---

## Variables que usaremos

Definí estas variables en tu shell antes de ejecutar los comandos:

```bash
export PROJECT_ID="sabueso-hack-2026"            # vars.GCP_PROJECT_ID en GH
export PROJECT_NUMBER="$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')"
export REGION="southamerica-east1"               # vars.GCP_REGION
export REPO="sabueso"                            # Artifact Registry repo
export GITHUB_ORG="tu-org-github"                # ej: sabueso-team
export GITHUB_REPO="sabueso"                     # repositorio
export POOL_ID="github-actions-pool"
export PROVIDER_ID="github-actions-provider"
export DEPLOYER_SA="sabueso-deployer"
export RUNTIME_SA="sabueso-runtime"
```

---

## 1. Habilitar APIs

```bash
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  --project="${PROJECT_ID}"
```

---

## 2. Crear el Artifact Registry repo

```bash
gcloud artifacts repositories create "${REPO}" \
  --project="${PROJECT_ID}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="Sabueso container images"
```

---

## 3. Crear el Workload Identity Pool

```bash
gcloud iam workload-identity-pools create "${POOL_ID}" \
  --project="${PROJECT_ID}" \
  --location=global \
  --display-name="GitHub Actions Pool"
```

---

## 4. Crear el OIDC Provider apuntando a GitHub

El `--attribute-condition` es **crítico**: limita qué repositorios pueden federarse contra esta pool. Sin él, **cualquier** repo de GitHub podría intentar autenticar.

```bash
gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
  --project="${PROJECT_ID}" \
  --location=global \
  --workload-identity-pool="${POOL_ID}" \
  --display-name="GitHub Actions OIDC" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref,attribute.environment=assertion.environment" \
  --attribute-condition="assertion.repository_owner == '${GITHUB_ORG}'"
```

Capturá el nombre completo del provider — lo necesitarás como secret:

```bash
gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" \
  --project="${PROJECT_ID}" \
  --location=global \
  --workload-identity-pool="${POOL_ID}" \
  --format='value(name)'
# -> projects/<NUMBER>/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider
```

---

## 5. Service accounts

### 5.1 Deployer SA (la que asume GitHub Actions)

```bash
gcloud iam service-accounts create "${DEPLOYER_SA}" \
  --project="${PROJECT_ID}" \
  --display-name="Sabueso GitHub Actions deployer"

DEPLOYER_EMAIL="${DEPLOYER_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

# Permisos mínimos: build y push a Artifact Registry, deploy a Cloud Run,
# leer secrets para pasarlos como --set-secrets.
for ROLE in \
  roles/artifactregistry.writer \
  roles/run.admin \
  roles/iam.serviceAccountUser \
  roles/secretmanager.secretAccessor \
  roles/cloudbuild.builds.editor; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${DEPLOYER_EMAIL}" \
    --role="${ROLE}" \
    --condition=None
done
```

### 5.2 Runtime SA (la que ejecuta los contenedores en Cloud Run)

Separada del deployer: el runtime no necesita poder desplegar — solo leer secrets, escribir logs, opcionalmente leer/escribir GCS, etc.

```bash
gcloud iam service-accounts create "${RUNTIME_SA}" \
  --project="${PROJECT_ID}" \
  --display-name="Sabueso Cloud Run runtime"

RUNTIME_EMAIL="${RUNTIME_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

for ROLE in \
  roles/secretmanager.secretAccessor \
  roles/logging.logWriter \
  roles/monitoring.metricWriter \
  roles/cloudtrace.agent \
  roles/storage.objectAdmin; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${RUNTIME_EMAIL}" \
    --role="${ROLE}" \
    --condition=None
done
```

> Para que el deployer pueda **actAs** el runtime al desplegar (`--service-account`), también:
>
> ```bash
> gcloud iam service-accounts add-iam-policy-binding "${RUNTIME_EMAIL}" \
>   --project="${PROJECT_ID}" \
>   --member="serviceAccount:${DEPLOYER_EMAIL}" \
>   --role="roles/iam.serviceAccountUser"
> ```

---

## 6. Federar el repo contra el deployer SA

Este es el binding que dice _"el workflow corriendo en `${GITHUB_ORG}/${GITHUB_REPO}` puede impersonar `sabueso-deployer`"_. Sin ramificarse por environment, vale cualquier branch — para producción endurecé el `--member` (ver más abajo).

```bash
WIF_POOL="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"

gcloud iam service-accounts add-iam-policy-binding "${DEPLOYER_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${WIF_POOL}/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}"
```

### Endurecimiento opcional (recomendado para producción)

Limitá a un environment de GitHub específico (los workflows ya lo usan: `environment: production`):

```bash
gcloud iam service-accounts add-iam-policy-binding "${DEPLOYER_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${WIF_POOL}/attribute.environment/production"
```

O por ref específica (sólo `main`):

```bash
gcloud iam service-accounts add-iam-policy-binding "${DEPLOYER_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${WIF_POOL}/attribute.ref/refs/heads/main"
```

---

## 7. Configurar GitHub: variables y secrets

En el repo, **Settings → Secrets and variables → Actions**:

### Variables (no sensibles, visibles en logs)

| Nombre                    | Valor ejemplo            |
| ------------------------- | ------------------------ |
| `GCP_PROJECT_ID`          | `sabueso-hack-2026`      |
| `GCP_REGION`              | `southamerica-east1`     |
| `ARTIFACT_REGISTRY_REPO`  | `sabueso`                |

### Secrets (sensibles)

| Nombre              | Cómo obtenerlo                                                                                         |
| ------------------- | ------------------------------------------------------------------------------------------------------ |
| `GCP_WIF_PROVIDER`  | Output del paso **4** (formato `projects/.../providers/github-actions-provider`)                       |
| `GCP_DEPLOYER_SA`   | `sabueso-deployer@${PROJECT_ID}.iam.gserviceaccount.com`                                               |
| `GCP_RUNTIME_SA`    | `sabueso-runtime@${PROJECT_ID}.iam.gserviceaccount.com`                                                |

### Environment (`production`)

Crear el environment `production` en **Settings → Environments → New environment**. Opcional: agregar required reviewers para gating manual antes del deploy.

---

## 8. Provisionar secrets en Secret Manager

Los workflows referencian estos secret names en `--set-secrets`:

```bash
echo -n "${SUPABASE_DB_URL}" | gcloud secrets create supabase-db-url \
  --project="${PROJECT_ID}" --data-file=- --replication-policy=automatic

echo -n "${SUPABASE_SERVICE_ROLE_KEY}" | gcloud secrets create supabase-service-role-key \
  --project="${PROJECT_ID}" --data-file=- --replication-policy=automatic

echo -n "${SUPABASE_JWKS_URL}" | gcloud secrets create supabase-jwks-url \
  --project="${PROJECT_ID}" --data-file=- --replication-policy=automatic

echo -n "${OPENROUTER_API_KEY}" | gcloud secrets create openrouter-api-key \
  --project="${PROJECT_ID}" --data-file=- --replication-policy=automatic

echo -n "${ANTHROPIC_API_KEY}" | gcloud secrets create anthropic-api-key \
  --project="${PROJECT_ID}" --data-file=- --replication-policy=automatic

echo -n "${LANGCHAIN_API_KEY}" | gcloud secrets create langchain-api-key \
  --project="${PROJECT_ID}" --data-file=- --replication-policy=automatic

echo -n "${OPENAI_API_KEY}" | gcloud secrets create openai-api-key \
  --project="${PROJECT_ID}" --data-file=- --replication-policy=automatic

echo -n "${VERCEL_KV_REST_API_URL}" | gcloud secrets create vercel-kv-rest-api-url \
  --project="${PROJECT_ID}" --data-file=- --replication-policy=automatic

echo -n "${VERCEL_KV_REST_API_TOKEN}" | gcloud secrets create vercel-kv-rest-api-token \
  --project="${PROJECT_ID}" --data-file=- --replication-policy=automatic
```

Para rotación posterior:

```bash
echo -n "${NUEVO_VALOR}" | gcloud secrets versions add supabase-db-url \
  --project="${PROJECT_ID}" --data-file=-
```

---

## 9. Verificación end-to-end

1. Push a `main` con un cambio en `apps/api/src/**` (o usar workflow_dispatch en GitHub Actions).
2. El workflow `deploy-api` debería:
   - autenticar contra GCP (paso "Auth to Google Cloud (WIF)" verde),
   - construir la imagen,
   - pushear a `southamerica-east1-docker.pkg.dev/${PROJECT_ID}/sabueso/sabueso-api:<sha>`,
   - desplegar a Cloud Run y devolver la URL.
3. `curl https://sabueso-api-<hash>-tq.a.run.app/api/v1/healthz` debe responder `200`.

Si el paso de auth falla:

| Error                                                   | Causa típica                                                                  |
| ------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `unable to acquire impersonation credentials`           | Falta el binding de `roles/iam.workloadIdentityUser` para el repo (paso 6).   |
| `request matched no attribute condition`                | `assertion.repository_owner` no matchea el `--attribute-condition` del paso 4. |
| `Permission 'artifactregistry.repositories.uploadArtifacts' denied` | El deployer no tiene `roles/artifactregistry.writer` (paso 5.1).              |
| `iam.serviceaccounts.actAs denied`                      | Faltó el binding actAs del deployer sobre el runtime (paso 5.2 nota).         |

---

## 10. Limpieza / desactivación

Para revocar el acceso del repo sin tocar el resto:

```bash
gcloud iam service-accounts remove-iam-policy-binding "${DEPLOYER_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${WIF_POOL}/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}"
```

Para destruir todo:

```bash
gcloud iam workload-identity-pools delete "${POOL_ID}" \
  --project="${PROJECT_ID}" --location=global
```

---

## Referencias

- [google-github-actions/auth — WIF docs](https://github.com/google-github-actions/auth#setting-up-workload-identity-federation)
- [Cloud Run + WIF guide](https://cloud.google.com/blog/products/identity-security/enabling-keyless-authentication-from-github-actions)
- [Attribute conditions en CEL](https://cloud.google.com/iam/docs/workload-identity-federation#conditions)
