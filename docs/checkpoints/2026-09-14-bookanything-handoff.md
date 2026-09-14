# Checkpoint & Handoff State: BookAnything Platform Integration

**Data do Checkpoint:** 14/09/2026 10:40 CEST  
**Tenant:** `swfabrik-europe`  
**Target Namespace:** `drr-tnt-swfabrik-europe-dev`  
**Status Atual:** 100% Operacional, Saudável e Sincronizado no ArgoCD e APISIX.

---

## 1. Repositórios e Estado do Git

| Repositório | Caminho Local | Branch | Status Git / Remotes |
| :--- | :--- | :--- | :--- |
| **Plataforma Core** | `/home/andre.nascimento/DevEnvALNS/projects/03-PoCs-And-Researches/ALNS-Azimute-R-D/darueira-privatecloud-platform` | `master` | Working tree limpa. Contém ArgoCD App, Tekton PipelineRuns, rotas APISIX e scripts de bootstrap. |
| **BookAnything App** | `.../workspace/platf-bizz-apps/swfabrik-europe/bookanything-platform` | `master` | Working tree limpa. `origin` (Forgejo) atualizado (`b3386d9`). 7 commits à frente do `github` remoto. |
| **BookAnything Chart (Sidecar)** | `.../workspace/platf-bizz-apps/swfabrik-europe/bookanything-platform-chart` | `master` | Working tree limpa. `origin` (Forgejo) sincronizado (`18f8f1e`). Módulo IntelliJ registrado. |

---

## 2. Componentes Implantados e Imagens Nexus

Padrão de release versioning adotado rigorosamente: `YYYY.MMDD.HHmmSS` (`2026.0913.225817`).

### A. Web Frontend (`bookanything-microfrontends-01`)
- **Stack:** React 19, TypeScript, Vite, Leaflet 1.9.4, React-Leaflet 5.0.0.
- **Porta:** 8080 (Nginx unprivileged, non-root UID `10001`).
- **Imagem Nexus:** `127.0.0.1:32082/swfabrik-europe/bookanything-microfrontends-01:2026.0913.225817` (e `:latest`).
- **Pod:** `bookanything-microfrontends-01-8654649bfb-r99d4` (`1/1 Running`, 0 restarts).

### B. Monolith Backend (`bookanything-monolith-backend-01`)
- **Stack:** Kotlin 2.3, Spring Boot 3.5.4, Java 21 Temurin (non-root UID `10001`).
- **Porta:** 8060.
- **Perfil Ativo:** `darueira-k8s` (Postgres 17, OpenSearch, Kafka, MinIO, Keycloak).
- **Imagem Nexus:** `127.0.0.1:32082/swfabrik-europe/bookanything-monolith-backend-01:2026.0913.225817` (e `:latest`).
- **Pod:** `bookanything-monolith-backend-01-6d445ff77f-nc2jl` (`1/1 Running`, 0 restarts).

---

## 3. Rotas APISIX Gateway e URLs `nip.io` Ativas

As rotas foram cadastradas no etcd do APISIX via Admin API e salvas em `scripts/bootstrap_apisix_routes.py` e `platform/kustomize/base/corpshared-plat/apisix-gateway.yaml`:

- **Frontend Web UI:**
  - `http://bookanything.swfabrik-europe.127.0.0.1.nip.io/`
  - `https://bookanything.swfabrik-europe.127.0.0.1.nip.io/`
- **Backend API & Swagger UI:**
  - `http://bookanything-api.swfabrik-europe.127.0.0.1.nip.io/swagger-ui/index.html`
  - `http://bookanything-api.swfabrik-europe.127.0.0.1.nip.io/management/health`
- **Path Routing Same-Origin (no host do Frontend):**
  - `http://bookanything.swfabrik-europe.127.0.0.1.nip.io/api/*` -> Backend `:8060`
  - `http://bookanything.swfabrik-europe.127.0.0.1.nip.io/swagger-ui/index.html` -> Swagger UI no mesmo domínio
  - `http://bookanything.swfabrik-europe.127.0.0.1.nip.io/management/health` -> Health Check no mesmo domínio

---

## 4. GitOps (ArgoCD & Tekton)

1. **ArgoCD Application:**
   - Nome: `swfabrik-europe-bookanything-platform` (namespace `drr-corpshared-mgmt`).
   - Manifesto: `platform/gitops/argocd-apps/apps-swfabrik-europe.yaml`.
   - Status: **Synced** / **Healthy** (Revision: `18f8f1e`).
2. **Tekton CI/CD PipelineRuns:**
   - Manifestos: `platform/gitops/tekton-pipelines/pipelineruns-swfabrik-europe.yaml`.
   - Runs prontos: `pr-swfabrik-europe-bookanything-backend-manual` e `pr-swfabrik-europe-bookanything-frontend-manual`.

---

## 5. Correções Técnicas Aplicadas na Sessão

1. **Prioridade Maven Central:** Invertida a ordem de repositórios no `pom.xml` para eliminar gargalos de timeout de rede e adicionado cache mount (`--mount=type=cache,target=/root/.m2`).
2. **Vertex AI Gemini Autoconfiguration:** Excluída a autoconfiguração default no `BookAnythingBackendApplication.kt` e parametrizada a URI de credenciais em `application.yml` (`SPRING_AI_VERTEX_AI_GEMINI_CREDENTIALS_URI`), com fallback graceful em `GeoLocationBeansConfig.kt`.
3. **OpenSearch Health Indicator Warning:** Excluídos `ElasticsearchRestHealthContributorAutoConfiguration` e `ElasticsearchReactiveHealthContributorAutoConfiguration`, e configurado `management.health.elasticsearch.enabled: false`, eliminando qualquer aviso de deserialização (`Failed to decode response`) no `/management/health`.
4. **Padrão de Versionamento:** Padronizadas as tags com o formato `YYYY.MMDD.HHmmSS` (`2026.0913.225817`) em todo o ciclo (Docker, Nexus, Helm Chart e ArgoCD).

---

## 6. Próximos Passos Imediatos ao Retornar

Ao reabrir a IDE após o reboot:
1. Executar `microk8s status` para garantir que o cluster e pods subiram normalmente.
2. (Opcional) Sincronizar o repositório remoto `github` com o `origin` (Forgejo) autenticando suas credenciais GitHub via terminal (`git push github master`).
3. Prosseguir para o **Item 3** do roadmap do BookAnything ou qualquer novo ticket priorizado da sprint.
