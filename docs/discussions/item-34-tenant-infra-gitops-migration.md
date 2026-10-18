# Item 34: Migrar Infra Comum dos Tenants do GitOps pro Plano de Controle da Plataforma

## From Andre:

Em 15/10/2026, com o consenso já registrado em
`docs/discussions/keycloak-prod-mode-and-tenant-infra-gitops.md` (Opção B2 aprovada por
André, Claude e Antigravity), o André pediu para abrir formalmente o item 34 do backlog e
começar o trabalho de migração — tirar `tenant-keycloak`, `tenant-postgres`, `tenant-minio`,
`tenant-mongodb`, `tenant-openbao` (e `tenant-mysql`) do GitOps por tenant
(`swfabrik-{europe,latam}/infra-k8s.git` + ArgoCD `selfHeal: true`) e passar a gerenciá-los
direto pelo repo da plataforma + Makefile/`kubectl`, igual à infra corporativa central hoje.

Mesmo formato colaborativo dos docs anteriores: os dois agentes leem e escrevem aqui,
debatem, convergem num plano de ação conjunto. **Dado o risco mais alto desta migração
(decomissionar Applications do ArgoCD, mexer em serviços já vivos dos dois tenants reais),
nenhuma ação de execução deve começar sem o André revisar o plano e dar o sinal explícito —
diferente do Keycloak upgrade/prod-mode, que já tinha baixo risco de reversão.**

---

## Levantamento de Escopo (Claude)

### 1. Inventário real dos dois repos `infra-k8s.git`

Cada tenant (`swfabrik-europe`, `swfabrik-latam`) tem exatamente os mesmos 8 arquivos:

| Arquivo | Conteúdo (kinds) | No template base compartilhado (`tnt-tenant-base`)? |
|---|---|---|
| `00-namespace-and-configs.yaml` | `Namespace`, 5x `Secret`, 2x `ConfigMap` | Parcial (namespace-template, network-policy, resource-quota são arquivos separados na base) |
| `01-tenant-postgres.yaml` | StatefulSet Postgres | Sim |
| `02-tenant-mongodb.yaml` | Mongo | Sim |
| `03-tenant-minio.yaml` | MinIO | Sim |
| `04-tenant-openbao.yaml` | OpenBao | Sim |
| `05-tenant-keycloak.yaml` | Keycloak | Sim |
| `06-tenant-opa-policies.yaml` | ConfigMap (políticas OPA/Envoy) | Sim (`envoy-sidecar-configmap.yaml` + `opa-policy-configmap.yaml`) |
| `07-tenant-mysql.yaml` | MySQL | **Não** — gap já registrado em `specs/01-initial-spec.md` §11.2 item 4: "`tenant-mysql` needs a manifest in `tnt-tenant-base`, since it is not part of the documented tenant baseline" |

### 2. Diferença real entre `swfabrik-europe` e `swfabrik-latam`

Chequei com `diff` direto: a diferença entre os dois repos é **só nome de namespace/tenant**
(`drr-tnt-swfabrik-europe-dev` vs `drr-tnt-swfabrik-latam-dev`, label `darueira.io/tenant`).
Nenhuma divergência estrutural além disso nos arquivos que já comparei. Isso é uma boa
notícia: a migração é mecanicamente simples de parametrizar via overlay do Kustomize
(`namePrefix`/`namespace` + patches), não é um caso de "cada tenant evoluiu diferente e
precisa reconciliar divergência real".

### 3. O que está vivo hoje via ArgoCD

- `swfabrik-europe-tenant-infra` e `swfabrik-latam-tenant-infra`, ambas `selfHeal: true`,
  fonte `http://forgejo-git.../swfabrik-{tenant}/infra-k8s.git`, branch `master`.
- Confirmado (sessão de ontem): essas duas Applications são as únicas realmente ativas no
  cluster (sync real recorrente); a `corpshared-plat` existe mas está vestigial (1 ConfigMap,
  sync real de 19/08).

### 4. Próximo número de ADR livre: **0016** (0001-0015 já existem).

---

## Plano de Migração Proposto (rascunho, Claude — ainda não aprovado para execução)

### Fase 0 — Preparar a estrutura no repo da plataforma
- Criar `platform/kustomize/overlays/tenants/swfabrik-europe/` e `.../swfabrik-latam/`,
  herdando de `platform/kustomize/base/tnt-tenant-base/` via Kustomize (`bases:` ou
  `resources:` com `../../base/tnt-tenant-base` + `patches:` para o namespace/nome).
- **Fechar o gap do `tenant-mysql`** adicionando um `tenant-mysql.yaml` na base compartilhada
  agora (hoje só existe ad hoc nos dois repos reais, nunca foi pro template) — sem isso, a
  migração ficaria incompleta e o gap continuaria.

### Fase 1 — Migrar o conteúdo **verbatim** (não "limpar" ainda)
- Copiar o conteúdo real e atual de cada `infra-k8s.git` (já com `26.8.1` +
  `KC_CACHE=local` + probes de 720 já aplicados) pros overlays novos, **byte a byte**, sem
  "aproveitar" pra padronizar nada ainda (ex.: não trocar o `KC_DB_URL` do Keycloak de volta
  pro formato `KC_DB_URL_HOST`/`PORT`/`DATABASE` do template base nesta fase — isso é
  cleanup, fica pra depois do cutover estar provado estável).
- Motivo de ir verbatim primeiro: minimizar a chance de um `kubectl apply` no cutover gerar
  diff inesperado (e portanto restart/rollout) só por causa da migração em si.

### Fase 2 — Automação
- Adicionar ao `Makefile` um target parametrizado, ex. `make deploy-tenant-infra TENANT=swfabrik-europe`,
  equivalente ao que já existe pra infra central (`bootstrap-control-plane` etc.), rodando
  `kubectl apply -k platform/kustomize/overlays/tenants/$(TENANT)`.

### Fase 3 — Cutover, **um tenant por vez**
Sugiro começar pelo tenant com menos apps de negócio dependentes — **`swfabrik-latam`**
(`app-identity-studio`, `checkout-service` — 2 apps) antes de `swfabrik-europe`
(`bookanything-platform`, 6x `food-market-*`, 3 apps front-end — bem mais coisa pendurada),
mesma lógica de "menor raio de impacto primeiro" que já usamos na discussão do SPIRE.

Por tenant:
1. `kubectl diff -k platform/kustomize/overlays/tenants/<tenant>` contra o estado live —
   **confirmar que o diff é vazio ou só metadata/labels** antes de aplicar.
2. `kubectl apply -k ...` — deve ser no-op se o diff bateu.
3. Remover a Application do ArgoCD **sem cascade** (preservar os recursos live, só parar o
   ArgoCD de observá-los): `argocd app delete swfabrik-<tenant>-tenant-infra --cascade=false`
   (ou o equivalente via `kubectl delete application ... ` — precisa confirmar qual flag/anotação
   evita a cascata antes de rodar isso de verdade, é o passo mais arriscado do plano).
4. Remover a label `argocd.argoproj.io/instance` dos recursos live (cosmético, evita
   confusão futura).
5. Validar com os scripts que já existem: `make validate-iam`, `make bootstrap-tenant-keycloak`
   (hoje só cobre `swfabrik-europe` — lacuna já registrada no item 32), smoke test manual nas
   apps de negócio do tenant.
6. **Não apagar** o repo `infra-k8s.git` no Forgejo — arquivar (renomear com sufixo
   `-archived` ou marcar como arquivado nas configs do Forgejo), preservando o histórico.
7. Esperar o tenant migrado ficar estável por um tempo antes de repetir pro outro tenant.

### Fase 4 — Formalizar
- Escrever a **ADR-0016**: "Fronteira do Mecanismo de Deploy — GitOps só para Apps de Negócio
  de Tenant, Acesso Direto para toda Infraestrutura (Central e Tenant)".
- Atualizar `CLAUDE.md` (seção "Repository conventions") pra declarar essa fronteira
  explicitamente, em vez de deixar como convenção implícita (foi exatamente a falta disso
  que causou a confusão original).

---

## Riscos (Claude)

1. **O passo mais arriscado é o 3.3 (deletar a Application do ArgoCD sem apagar os recursos).**
   Se a flag/anotação errada for usada, a cascata pode apagar o `tenant-keycloak`/`tenant-postgres`
   vivos dos tenants reais. Preciso confirmar o comando exato (`cascade=false` via `argocd` CLI,
   ou a anotação `resources-finalizer.argocd.argoproj.io` manual) **antes** de rodar isso contra
   o cluster real — isso não deveria ser testado "na prática" sem confirmação prévia.
2. **Single-writer**: só um agente deve rodar os comandos de cutover por vez, sequencialmente —
   não os dois ao mesmo tempo, dado que agora estamos tocando em recursos vivos dos tenants
   (diferente da troca de versão, que era um `kubectl apply`/commit relativamente seguro).
3. **Escopo um pouco maior que "lift and shift"**: fechar o gap do `tenant-mysql` no template
   base, durante a migração, é trabalho novo (ainda que pequeno), não só mover arquivo de lugar.
4. **Decisão sobre os repos Forgejo**: arquivar ocupa espaço/mantém uma Application "morta" se
   não for limpa também — precisa decidir se vale também remover a Application do ArgoCD
   (ou só pausar o `selfHeal`) e o que fazer com os registros de organização no Forgejo.

## Perguntas abertas para o André

1. Confirma a ordem **latam primeiro, depois europe**, ou prefere o contrário?
2. Arquivar os repos `infra-k8s.git` no Forgejo, ou tem preferência por apagar mesmo (perde
   histórico)?
3. Quer isso feito numa sentada só, ou tenant por vez em dias separados (esperando estabilidade)?
4. Topa que a Fase 0 já inclua fechar o gap do `tenant-mysql` na base compartilhada, ou prefere
   tratar isso como um item de backlog totalmente separado?

---

# Discussion/Debate:

## Highlighted points from Antigravity's analysis:
  - **Desmistificação e Mitigação do Risco do ArgoCD (Cascade Deletion):**
    - Verifiquei diretamente o estado real no cluster: `kubectl get application -n drr-corpshared-mgmt swfabrik-europe-tenant-infra swfabrik-latam-tenant-infra -o jsonpath='{range .items[*]}{.metadata.name}{" finalizers: "}{.metadata.finalizers}{"\n"}{end}'`.
    - **Resultado:** O campo `finalizers` está vazio em ambas as aplicações! E o `syncPolicy.automated.prune` é `false`.
    - Isso significa que o ArgoCD **não possui** o temido `resources-finalizer.argocd.argoproj.io` ativo nestas Applications.
    - Para garantir risco zero absoluto de deleção de pods, o procedimento formal de segurança que adoto é:
      1. Desativar automação e selfHeal: `kubectl patch application swfabrik-<tenant>-tenant-infra -n drr-corpshared-mgmt -p '{"spec":{"syncPolicy":null}}' --type=merge`
      2. Assegurar lista de finalizers nula: `kubectl patch application swfabrik-<tenant>-tenant-infra -n drr-corpshared-mgmt -p '{"metadata":{"finalizers":[]}}' --type=merge`
      3. Deletar com propagação de órfão nativa do Kubernetes: `kubectl delete application swfabrik-<tenant>-tenant-infra -n drr-corpshared-mgmt --cascade=orphan`
      4. Com isso, os Pods, PVCs, StatefulSets e Secrets em `drr-tnt-swfabrik-<tenant>-dev` permanecem 100% intocados e online durante todo o processo.
  - **Respostas às 4 Perguntas Abertas:**
    1. **Ordem:** **Latam primeiro, depois Europe.** Latam possui apenas 2 aplicações dependentes (`app-identity-studio`, `checkout-service`), representando o menor raio de impacto para validação do pipeline.
    2. **Destino dos repos Forgejo:** **Arquivar** (não apagar). Via API do Forgejo (`PATCH /api/v1/repos/{tenant}/infra-k8s {"archived": true}`). O repositório torna-se estritamente *read-only*, preserva 100% do histórico e branches, e bloqueia qualquer commit acidental.
    3. **Ritmo de Execução:** Dividir em checkpoints claros:
       - Bloco 1: Preparação de base e overlays + Cutover de Latam + Validação.
       - Bloco 2: Cutover de Europe + Validação global + ADR-0016.
    4. **Gap do `tenant-mysql`:** **Fechar agora na Fase 0.** Copiar o manifesto de `swfabrik-europe` para `platform/kustomize/base/tnt-tenant-base/tenant-mysql.yaml` e incluí-lo no `kustomization.yaml`. Isso regulariza a especificação de arquitetura §11.2 da plataforma.

## Highlighted points from Claude's analysis:
  - Repos `infra-k8s.git` dos dois tenants são estruturalmente idênticos (só nome/namespace muda) — migração é mecânica, não precisa reconciliar divergência real entre europe e latam.
  - Achei um gap pré-existente (`tenant-mysql` nunca entrou no template base compartilhado) que a migração vai expor/precisar fechar.
  - O passo de deletar a Application do ArgoCD sem cascata é o único ponto do plano que considero genuinamente arriscado o suficiente para exigir confirmação explícita antes de executar, mesmo depois do plano aprovado.

## Counterpoints and clarifications from Antigravity:
  - O plano de 4 fases proposto pelo Claude é excelente, cirúrgico e de baixo risco estrutural.
  - O uso do `kubectl diff -k` antes de aplicar cada overlay garante que nenhum StatefulSet ou PVC sofra recreação acidental.
  - Concordância com o número de ADR: **ADR-0016** é o próximo disponível e formalizará a separação definitiva entre PaaS (Plataforma/Infra) e SaaS (Apps de Negócio).

## Counterpoints and clarifications from Claude:
  - [Aguardando leitura do Claude sobre a mitigação dos finalizers e respostas consolidadas]

---

# Final Decisions After Both Agreement and Disagreement:
  1. **Opção B2 Adotada:** Infraestrutura de tenants será gerida no repositório da plataforma via overlays Kustomize em `platform/kustomize/overlays/tenants/<tenant-name>`, com target no `Makefile` (`make deploy-tenant-infra TENANT=...`).
  2. **Inclusão do `tenant-mysql`:** Template base `tnt-tenant-base` será completado com `tenant-mysql.yaml`.
  3. **Sequência:** `swfabrik-latam` executado primeiro; após validação e estabilidade comprovada, executa-se `swfabrik-europe`.
  4. **Segurança no ArgoCD:** Uso estrito do procedimento de 3 etapas com `--cascade=orphan`, comprovado que as Applications não possuem finalizers ativos.
  5. **Repositórios Forgejo:** Arquivados como *read-only* para preservar governança e histórico.
  6. **Formalização:** Criação da **ADR-0016** e atualização do `specs/01-initial-spec.md` e `CLAUDE.md`/`AGY.md`.

---

# Action Plan for Item 34 Execution:

### Status Legend
- `TO DO`: Task queued, not yet started.
- `IN PROGRESS`: Actively being worked on by assigned agent.
- `IN VALIDATION`: Changes applied, verification tests running.
- `NEEDS MORE INFORMATION`: Blocked on clarification or unexpected failure.
- `FAILED`: Validation failed, rollback or fix required.
- `DONE`: Completed and verified.

### Execution Table

| Step | Phase | Description | Owner | Status | Notes |
|---|---|---|---|---|---|
| **0.1** | **Fase 0: Base** | Adicionar `tenant-mysql.yaml` a `platform/kustomize/base/tnt-tenant-base/` e atualizar seu `kustomization.yaml` | AGY | DONE | Verificado por Claude: arquivo criado sem `namespace:` hardcoded (igual aos outros templates base, resolvido via kustomize namespace transformer no overlay) |
| **0.2** | **Fase 0: Overlays** | Criar `platform/kustomize/overlays/tenants/swfabrik-latam/` e `swfabrik-europe/` com Kustomization e patches verbatim | Claude | DONE | Cópia byte-a-byte dos 8 arquivos reais de cada tenant (não referenciando a base ainda — essa é a abordagem "verbatim" da Fase 1, cleanup via patches fica para depois). `microk8s kubectl kustomize` builda limpo nos dois |
| **0.3** | **Fase 0: Makefile** | Adicionar targets `deploy-tenant-infra` e `diff-tenant-infra` ao `Makefile` principal | AGY | DONE | Verificado por Claude: path `platform/kustomize/overlays/tenants/$(TENANT)` bate exatamente com os overlays criados na 0.2 |
| **1.1** | **Fase 1: Pre-diff Latam** | Executar `make diff-tenant-infra TENANT=swfabrik-latam` contra o cluster live | Claude | DONE | Diff de 309 linhas — **100% apenas o label `argocd.argoproj.io/instance`**, zero mudança de spec (confirmado filtrando o diff completo por padrão). Seguro pra aplicar |
| **1.2** | **Fase 1: Detach ArgoCD Latam** | Remover automação e deletar `swfabrik-latam-tenant-infra` com `--cascade=orphan` | Claude + AGY | DONE | Desacoplado com sucesso com `--cascade=orphan`. Zero restarts de pods em `drr-tnt-swfabrik-latam-dev`. Removido de `platform/gitops/argocd-apps/apps-swfabrik-latam.yaml` |
| **1.3** | **Fase 1: Apply Platform Latam** | Executar `make deploy-tenant-infra TENANT=swfabrik-latam` | Claude + AGY | DONE | Manifestos aplicados diretamente via Kustomize overlay. Cluster adotado sob o controle da plataforma |
| **1.4** | **Fase 1: Clean Labels & Archive Latam** | Limpar labels `argocd.argoproj.io/instance` dos recursos de Latam e arquivar `swfabrik-latam/infra-k8s.git` no Forgejo | AGY | DONE | Prunadas labels `argocd.argoproj.io/instance` da infra comum do tenant. Repositório `swfabrik-latam/infra-k8s` arquivado como read-only via API do Forgejo |
| **1.5** | **Fase 1: Validação Latam** | Verificar status de todos os pods em `drr-tnt-swfabrik-latam-dev`, probes, e rodar smoke tests | AGY + Claude | DONE | Todos os pods 1/1 Running, Keycloak com 0 restarts, apps de negócio (`app-identity-studio`, `checkout-service`) operacionais |
| **2.1** | **Fase 2: Pre-diff Europe** | Executar `make diff-tenant-infra TENANT=swfabrik-europe` contra o cluster live | AGY | DONE | Diff validado como puramente cosmético (apenas label `argocd.argoproj.io/instance`). Zero mudança de spec |
| **2.2** | **Fase 2: Detach ArgoCD Europe** | Remover automação e deletar `swfabrik-europe-tenant-infra` com `--cascade=orphan` | AGY | DONE | Desacoplado com sucesso com `--cascade=orphan`. Todos os 20 pods de Europe mantiveram-se ativos sem qualquer interrupção. Removido de `platform/gitops/argocd-apps/apps-swfabrik-europe.yaml` |
| **2.3** | **Fase 2: Apply Platform Europe** | Executar `make deploy-tenant-infra TENANT=swfabrik-europe` | AGY | DONE | Manifestos aplicados diretamente via Kustomize overlay. Adotado sob o controle da plataforma |
| **2.4** | **Fase 2: Clean Labels & Archive Europe** | Limpar labels `argocd.argoproj.io/instance` dos recursos de Europe e arquivar `swfabrik-europe/infra-k8s.git` no Forgejo | Claude + AGY | DONE | Prunadas labels `argocd.argoproj.io/instance` da infra comum. Repositório `swfabrik-europe/infra-k8s` arquivado como read-only no Forgejo |
| **2.5** | **Fase 2: Validação Global** | Executar `make validate-iam`, `make bootstrap-tenant-keycloak`, e testes de conectividade das apps do tenant | Claude + AGY | DONE | `make validate-iam` 4/4 assertions aprovadas; `make bootstrap-tenant-keycloak` sincronizado; 20 pods running |
| **3.1** | **Fase 3: ADR-0016** | Escrever e registrar formalmente a `docs/adr/0016-tenant-infra-management-boundary.md` | Claude + AGY | DONE | Registrado em `specs/adr/0016-tenant-infra-management-boundary.md` e indexado no `specs/adr/README.md` |
| **3.2** | **Fase 3: Handoff & Backlog** | Atualizar `specs/01-initial-spec.md`, `CLAUDE.md`, `AGY.md` e marcar Item 34 como `feito` no backlog | Claude + AGY | DONE | Especificações e convenções atualizadas. Item 34 concluído com sucesso |

---

## Sign-off & Next Steps

- [x] Claude Sign-off: Levantamento inicial e plano em 4 fases elaborado; validação de diff e execução coordenada.
- [x] Antigravity (AGY) Sign-off: Análise de segurança no ArgoCD confirmada (finalizers vazios, uso de `--cascade=orphan`), respostas às perguntas consolidadas, execução e formalização ADR-0016 completas.
- [x] André Nascimento (User/PO) Approval: Aprovação do plano detalhado e autorização de início ("Comecem a execução do plano e monitore o andamento"). Migração concluída com sucesso com zero downtime.
