# Backlog de melhorias — darueira-privatecloud-platform + BookAnything

Levantado em 2026-09-24, a partir do que as sessões de troubleshooting de 23 e 24/09 revelaram
(acesso às UIs, OpenSearch, rotas do APISIX, workflow de GeoLocation, enriquecimento, vazamento
de IPs do Cilium, passo 8 do NiFi).

**Próximo passo**: agregar as ideias de melhoria do André e transformar isto num roadmap com
prioridades, dependências e fases.

**Quadro compartilhado (Claude + Antigravity + André)**: antes de começar um item, marque no
título `[dono: Claude|AGY|André — status: em andamento|feito|bloqueado]`. Ao terminar, anote
abaixo do item o que mudou, os commits e o que falta validar. Regras completas no `CLAUDE.md`
(seção "Multi-agent collaboration").

---

## Estado em 2026-09-24 (fim do dia)

- Imports BRA e DEU funcionando de ponta a ponta (Temporal → Kafka → NiFi → backend → enriquecimento).
- Enriquecimento DEU: 17/17 bandeiras (Wikidata/Commons + flagcdn) e 17/17 resumos (Wikipedia pt), sem Gemini.
- `bookanything-platform` PR #12 em produção: nova `WorkerFactory` a cada tentativa de start do
  worker Temporal + timeouts por activity (1 min / 5 min / 30 min com heartbeat de 1 min).
- Passo 8 do NiFi corrigido e versionado (`platform/nifi/...`, aplicado via `scripts/apply_nifi_script_body.py`).
- Vazamento de IPs do Cilium limpo (IPAM 85/254) e limpeza automática instalada no host
  (`scripts/setup_host_cilium_state_cleanup.sh`), **ainda não validada num stop/start real**.

---

## 🔴 Alta prioridade

### 1. Segredos hardcoded no repositório (agora publicado no GitHub)
Credenciais em texto no repo:
- admin key do APISIX em `scripts/bootstrap_apisix_routes.py`;
- senha do keystore do NiFi em `platform/kustomize/base/corpshared-plat/apache-nifi.yaml`
  (também usada por `scripts/apply_nifi_script_body.py`);
- senhas default de Postgres / MinIO / Keycloak em `application-darueira-k8s.yml` do backend.

Se o repositório for público, considerar essas credenciais **comprometidas**: rotacionar, e não
apenas remover do código. Migrar para OpenBao/Secrets. Faz parte da Fase E original (junto com o
logging de tokens).

### 2. Seed dos dados de referência (continentes / regiões) `[dono: Claude — status: feito]`
A limpeza de 23/09 apagou todo o `tb_geo_location`, inclusive continentes e regiões. Sem a região
pai, todo `POST /country` dava HTTP 500 e o NiFi reportava `createdCount=0` como sucesso. Hoje a
hierarquia existe só porque foi recriada à mão via API:
`South America (SA) → Southern Cone (SAM)` e `Europe (EU) → Western Europe (WEU)`.

A fazer:
- seed idempotente (migração ou script de bootstrap);
- procedimento de limpeza de dados de teste que preserve os dados de referência.

**Handoff (2026-09-25, Claude):** hierarquia completa pelo geoscheme UN M49 em
`platform/data/geolocation/continents-regions-un-m49.json`: 6 continentes (AFR, AME, ANT, ASI, EUR,
OCE) e 23 regiões, cobrindo os 249 códigos ISO 3166-1 alpha-3 mais 16 códigos exclusivos do GADM
(XKO, Z01–Z09 etc.). Cada região guarda `m49Code` e `memberCountriesIso3`. Seed idempotente:
`make seed-geolocation-reference` (`scripts/seed_geolocation_reference_data.py`, com `--dry-run`).
Aplicado: 25 criados e 4 atualizados. `AME` foi renomeado de "South America" para "Americas", e `SAM`
de "Southern Cone" para "South America". Um re-run deu 29 inalterados.
Pendente: o país USA (#99) está sob SAM. O PUT do backend ignora `parentId` (item 19), e a correção
por SQL ficou com o André:
`UPDATE tb_geo_location SET parent_id = 107 WHERE id = 99;` (tenant-postgres, DB `DBBookAnythingPlatform`).
Falta também o procedimento de limpeza que preserve os dados de referência.

### 3. Disco dos PVs (HDD `/dev/sda2`, 83% — 458G/585G)
Os 24 PVs stateful estão nesse disco. O NiFi já está segurando escritas
(`nifi.content.repository.archive.max.usage.percentage=50%`: "waiting for archive cleanup").
Falta investigar o que está consumindo o disco antes que algum serviço pare.

**2026-09-25 (Claude):** isso já parou um serviço. O limite de 50% é medido contra a partição
inteira, e o NiFi bloqueou todas as gravações de conteúdo ("waiting for archive cleanup"). O
ConsumeKafka travou, foi expulso do consumer group (`max.poll.interval.ms`) e o workflow USA ficou
parado 10 min. Paliativo: `archive.max.usage.percentage=90%` no `apache-nifi.yaml`. Falta a causa de
fundo: descobrir quem ocupa os 459G e migrar os PVs para o NVMe (item 10).

### 17. Conexões esgotadas no central-postgres `[dono: Claude — status: feito]`
Em 25/09 o Backstage entrou em CrashLoopBackOff com `FATAL 53300 too_many_connections`:
`max_connections=100` e 103 conexões abertas, 61 delas idle do Temporal (pool SQL sem limite
efetivo: 20 conexões por serviço × 4 serviços no mesmo processo).

**Handoff (2026-09-25, Claude):** commit `f62f1f5`. O Temporal agora usa `SQL_MAX_CONNS=15`,
`SQL_MAX_IDLE_CONNS=3` e `SQL_MAX_CONN_TIME=15m` (visibility: 5/1/15m), e o central-postgres tem
`max_connections=200`. Aplicado: 54 de 200 conexões depois do rollout, e o Backstage voltou.

### 18. Backend OOMKilled durante imports grandes `[dono: Claude — status: aguardando merge]`
Import USA de 25/09 falhou: o backend (limite 1Gi, heap 256 MB por `MaxRAMPercentage=25%`) foi
OOMKilled no meio dos 51 POSTs do NiFi (4 restarts desde 24/09). A resposta do NiFi chegou a um
pod novo sem o "pending future" em memória, e a activity morreu por heartbeat timeout.

**Handoff (2026-09-25, Claude):**
- Backend: PR #1 no chart `swfabrik-europe/bookanything-platform-chart`
  (branch `fix/backend-memory-headroom`): limite 2Gi, request 768Mi e
  `JAVA_TOOL_OPTIONS=-XX:MaxRAMPercentage=55.0 -XX:InitialRAMPercentage=20.0 -XX:+ExitOnOutOfMemoryError`.
  **Precisa do merge do André** (o merge sem revisão foi bloqueado para o agente).
- NiFi: commit `1ac8ad0`, heap 3g, request 2Gi, limite 4Gi. Aplicado.
- Temporal, JSReport, Redpanda e maps-generator estão com folga; não mudaram.
- Pendente: o "pending future" em memória não sobrevive a um restart do backend (item 20).

### 19. PUT do backend ignora `parentId`
`GeoLocationCRUDService.update` copia name, alias, friendlyId, details e boundary, mas não o pai.
Não dá para corrigir a hierarquia pela API; hoje isso só se faz por SQL.

### 20. Resposta do NiFi se perde se o backend reiniciar
A activity `processCountryLocationViaNiFi` espera um `CompletableFuture` em memória, indexado por
`correlationKey`. Se o pod reinicia, a resposta chega com "No pending future found" e a activity
morre por heartbeat timeout. Alternativas: activity assíncrona com completion por task token, ou
um signal no workflow a partir do consumer Kafka.

### 21. Backend como GraalVM native image `[dono: Claude — status: feito e validado no cluster; falta só o ajuste de memória do chart]`
O Pod JVM usava ~930 MiB. O `Dockerfile` agora gera um executável native (o JVM ficou em
`Dockerfile.jvm`): 144–297 MiB e startup de 1,2–2,5 s no cluster.

**PRs no `bookanything-platform` (Forgejo):**
- #13 (build native), #14 (epoll do gRPC) e #15 (proxies dos stubs do Temporal e errordetails do
  protobuf): mergeados e em produção, imagem `2026.0925.144234`.
- #16 (`fix/backend-native-minio-reflection`, commits `6750d86` e `9268784`): registra para
  reflection o cliente MinIO (`io.minio`) e o simple-xml que ele usa para ler as respostas S3
  (`org.simpleframework.xml`). Mergeado em 26/09 (merge `4554375`), imagem `2026.0926.125910`.
  Antes do merge foi testada localmente com o binário native, pelo endpoint síncrono
  `POST /api/v1/geolocations/workflows/82/artifacts-and-report`.

**Validação no cluster (26/09, Pod `...-55f755fb6f-65hjn`, 0 restarts):**
- **DEU (nível 0):** workflow completo em ~42 s (Temporal, gatilho do NiFi via Kafka, resposta
  `Created=0, Updated=1`, enriquecimento, upload no MinIO, PDFs do JSReport, evento
  `geolocation.batch-import.completed`).
- **BRA (níveis 0 e 1), após limpar a base:** 1 país + 27 estados (`Created=1` e `Created=27`),
  28 itens em ~3 min (11:53:54 a 11:56:51). Contagens conferidas: 84 imagens e 28 documentos no
  banco e no MinIO do tenant, 29 objetos em `darueira-reports` (28 relatórios + o resumo do job)
  e os 4 arquivos do GADM em `darueira-geodata`. Nenhum item sem geometria, mapa ou relatório.
- **DEU + USA juntos (mesmo workflow, ~12:05 a 12:16 UTC):** DEU 1 + 16 estados e USA 1 + 51 estados,
  69 itens em ~11 min. Contagens finais conferidas com o BRA: **97 GeoLocations** (3 países, 94
  estados), 291 imagens e 97 documentos no banco e no MinIO do tenant, 99 objetos em
  `darueira-reports` (97 relatórios + 2 resumos de job) e 12 em `darueira-geodata`. Nenhum item sem
  geometria, mapa ou relatório. **Atenção:** o resumo do NiFi do USA nível 1 veio com
  `createdCount=36, failedCount=15` (`SocketTimeoutException: Read timed out` no POST dos estados), mas
  os 51 estados foram gravados: ver item 6.
- Nenhum `MissingReflection|NoSuchMethod|no argument constructor|ERROR` nas consultas de log feitas
  durante os imports.
- **Memória do Pod:** 297–308 MiB nos imports do DEU e do BRA; **pico de 676 MiB** com DEU e USA em
  paralelo (~165–205 MiB em repouso; o JVM usava ~930 MiB). 0 restarts. CPU chegou a 1,2–1,4 núcleo
  (limite 1500m).

**Estado da base para os próximos testes:** BRA, DEU e USA completos (97 GeoLocations, mais os 6
continentes e 23 regiões UN M49 de referência). Em 26/09, antes desses imports, a base foi limpa: 97
GeoLocations (3 países e 94 estados) e 388 assets apagados, com os objetos correspondentes nos MinIOs
e todo o conteúdo de `darueira-geodata` e `drr-corporate-reports` (este tinha logs de perfil do
JSReport e PDFs de `swfabrik-latam/billing-summary`, sem backup). O JSReport volta a preencher o
`drr-corporate-reports` a cada renderização (103 objetos após o import). O dump só de dados das
duas tabelas antes da limpeza está em `/tmp` (some no reboot).

**Como repetir o teste local** (sem NiFi e sem tocar o cluster):
1. Compilar (a partir de `1-backends/bookanything-monolith-backend-01`, JAVA_HOME em
   `~/.sdkman/candidates/java/25.2.4-graalce`, nada de Kaniko rodando; pico de 12,4 GiB de RSS,
   ~15 min):
   `NATIVE_IMAGE_OPTIONS="--parallelism=8 -J-Xmx16g" nice -n 10 ./mvnw -Pnative native:compile -DskipTests -Dkotlin.compiler.daemon=false "-Dspring-boot.aot.jvmArguments=-Dspring.profiles.active=darueira-k8s"`
   Com `-J-Xmx8g` a build estoura `OutOfMemoryError` após 55 min.
2. Port-forwards para: Postgres e Keycloak do tenant, MinIO do tenant, `central-minio`,
   `jsreport` e o `opensearch` do `drr-corpshared-obs` (o backend exige o Elasticsearch no
   startup). O Temporal é local: `temporal server start-dev --headless --port 17233 -n corporate-core`
   (o CLI é copiado do pod do temporal-server).
3. Subir o binário com as variáveis do Deployment, trocando os endpoints pelos túneis locais e
   `TEMPORAL_SERVICE_ADDRESS=localhost:17233`.
4. **Kafka em `localhost:9092` (sem broker).** Os group ids dos `@KafkaListener` são fixos no
   código (`bookanything-nifi-reply-group`, `geolocation-enricher`, ...): se o binário local usar o
   Kafka do cluster ele disputa partições com o Pod em produção. Do mesmo modo, nunca apontar o
   worker local para o Temporal do cluster.
5. Chamar o endpoint e procurar nos logs
   `MissingReflection|MissingResource|Panic|InstantiationException|NoSuchMethod|must have no argument constructor`,
   e não só o resultado HTTP.

**Pendente:** reduzir o limite de memória do chart (2Gi → ~1Gi) e remover o `JAVA_TOOL_OPTIONS`
(repositório do chart, via PR no Forgejo). O pico observado foi de 676 MiB com dois países em paralelo,
então 1Gi deixa ~350 MiB de folga (com um país por vez o pico é ~310 MiB). Decidir entre 1Gi e ~1,5Gi.

**Lições:**
- Cada tipo que falta registrar para reflection só aparece em runtime, e um por vez. O teste local
  com o endpoint síncrono acha o próximo em ~10 s, contra ~26 min de pipeline no cluster.
- Bibliotecas sem metadata nativa (MinIO) puxam dependências que também usam reflection
  (simple-xml): registrar só o pacote da biblioteca não basta.
- Sob import os logs do Pod rotacionam em ~2 min (~14 mil linhas): consultas posteriores a `kubectl logs
  --since` só enxergam o final. Para acompanhar um import, usar `logs -f` com `grep --line-buffered` e
  sem `sed`/`cut` no pipeline (eles seguram a saída em buffer e o monitor não emite nada).
- O Spring AOT sobrescreve o `reachability-metadata.json` de `<group>/<artifact>`; os hints manuais
  ficam em `native-overrides/` ou no `NativeRuntimeHints`.

### 23. Probe do tenant-mongodb pesada
A probe abre um `mongosh` inteiro a cada verificação (275% de CPU observado em 25/09; 39 e 31
restarts). Trocar por uma probe TCP ou por um comando mais leve.

### 24. Endpoint `artifacts-and-report` respondeu sem token
No teste local de 26/09, `POST /api/v1/geolocations/workflows/{id}/artifacts-and-report` respondeu sem
`Authorization` (500/200, nunca 401). Conferir o `SecurityConfig`: se o endpoint estiver aberto, ele
viola a regra de não expor endpoints administrativos sem OIDC. Verificar também os demais
`/api/v1/geolocations/workflows/**`.

### 25. Credenciais em texto puro no Deployment do backend
As 17 variáveis do Deployment `bookanything-monolith-backend-01` (senha do Postgres, chaves do MinIO,
`KEYCLOAK_CLIENT_SECRET`) são valores literais, sem `secretKeyRef`, e os padrões do
`application.yml` (`CORPORATE_MINIO_*`, `JSREPORT_PASSWORD`) também estão no código. Relacionado ao
item 1: mover para Secrets/OpenBao. Em 26/09 essas variáveis foram impressas uma vez no terminal
de uma sessão do Claude.

Achado em 26/09: `platform/gitops/tekton-pipelines/task-gitops-helm-promote.yaml` tem o usuário e a
senha do Git (`drradmin`) escritos no script para clonar o repositório do chart. Mover para um
Secret do Tekton (relacionado ao item 1).

### 22. Handler global de exceções do backend não loga
Os erros 500 voltam com a mensagem no corpo, mas nada aparece no log do Pod: foi assim que o disparo
do DEU falhou em silêncio no native. Logar a exceção (com stack) no handler.

### 26. Build do backend em duas variantes: JVM (padrão) e native `[dono: Claude — status: feito]`
Decidido com o André em 26/09. O build native leva ~26 min na pipeline e ~12 GiB de RAM; para testar
funcionalidade em desenvolvimento isso é caro demais.
- **Regra:** push na `master` do `bookanything-platform` gera a imagem **JVM** (`Dockerfile.jvm`). Se o
  **assunto** (primeira linha) do commit de merge tiver `[native]` (o Forgejo copia o título do PR
  para lá em merge commit e squash; em rebase se perde), gera a **native** (`Dockerfile.native`).
  Um CEL no `forgejo-events`/`bookanything-events` decide, sem reconfigurar o webhook.
- **Tag** com sufixo da variante (`YYYY.MMDD.HHMMSS-jvm|-native`), e o **chart deduz a variante pelo
  sufixo da tag**: a imagem em execução e a configuração do Pod (memória, `JAVA_TOOL_OPTIONS`) nunca
  divergem. Isso também resolve o "pendente" do item 21 por variante.
- **Limpeza:** o `Dockerfile` atual (native) vira `Dockerfile.native`; o `Dockerfile-native` antigo
  (sem o perfil AOT, imagem `:latest`) é apagado. `Dockerfile.fast` fica para uso local.
- **Ordem obrigatória** (a task do Kaniko gera uma imagem Alpine de exemplo, em vez de falhar, quando
  o Dockerfile não existe): 1) PR no app com `Dockerfile.native` (mantendo `Dockerfile`); 2) PR no
  chart; 3) `kubectl apply` do gatilho/pipeline; 4) só então remover o `Dockerfile` antigo.
- **Regra de qualidade:** JVM esconde bugs do native (a sessão de 25–26/09 foi isso). Nenhuma fase
  fica pronta sem um build native e um teste local com ele.

**Andamento (26/09):**
- Gatilho e task do Kaniko aplicados no cluster (commit `b1426ad`), depois de validar a expressão CEL
  contra o interceptor real com um payload de push do Forgejo (6 casos + o filtro de branch).
- `Dockerfile.native` adicionado e `Dockerfile-native` (antigo) removido (`cea19d4`). Esse commit
  foi para a `master` do Forgejo **direto, sem PR**: a branch foi criada com upstream em
  `origin/master`, e um `git push` simples empurrou para lá. Nas próximas branches criar com
  `--no-track`.
- **Primeira pipeline JVM validada** (`forgejo-ci-bookanything-backend-2qh9f`, tag
  `2026.0926.153057-jvm`): 5 min 52 s de ponta a ponta, contra ~26 min do native. Pod JVM: startup de
  **40,8 s** (native: 1–2 s) e **729 MiB** logo após subir (native: ~165–205 MiB em repouso), com o
  limite de 2Gi. As probes do chart (readiness 30 s, liveness 45 s) cobrem o startup do JVM com pouca
  folga: revisar ao tratar as variantes no chart.
- O PipelineRun manual `pr-swfabrik-europe-bookanything-backend-manual` (modelo, não aplicado no
  cluster) passou a usar `Dockerfile.jvm` e `auto-jvm`, porque o `Dockerfile` vai sair.
- **Rota native validada** (PR #17 com `[native]` no título, merge `4345514`): PipelineRun com
  `auto-native` + `Dockerfile.native`, tag `2026.0926.154226-native`, pipeline em 3 min 54 s (o Kaniko
  reaproveitou a camada do `native-image` porque o `src/` não mudou; com código alterado contar ~20
  min a mais). Pod native: startup de **2,2 s** e **154 MiB** logo após subir. O `Dockerfile`
  transitório foi removido.
- **README** do `tekton-pipelines` documentando a regra `[native]`, a tag e o risco do Alpine.
- **Chart** (`bookanything-platform-chart`, branch `feat/backend-image-variants`, commit `ae14681`,
  ainda **sem push nem PR**): a variante sai do sufixo da tag; native = 384Mi → 1536Mi, sem
  `JAVA_TOOL_OPTIONS`, `startupProbe` de até 60 s; jvm = 768Mi → 2048Mi (como antes), com
  `startupProbe` de até 180 s; label `darueira.io/image-variant` no Pod. Testado com `helm lint` e
  `helm template` (tags `-native`, `-jvm`, `latest` e sem sufixo): só o Deployment do backend muda.
  **O ArgoCD sincroniza o chart sozinho (`automated`), então o merge reinicia o Pod do backend**
  (`Recreate`, indisponibilidade curta). O limite de 1536Mi do native é conservador: baixar depois de
  medir o workflow da fase A (janela de 4 itens em paralelo). Isso fecha o "pendente" de memória
  do item 21.
- **Entregue e confirmado** (chart PR #2, merge `d45b0dd`; o ArgoCD levou ~5 min para detectar): Pod
  native com a label `darueira.io/image-variant: native`, limite de **1536Mi** (request 384Mi), sem
  `JAVA_TOOL_OPTIONS`, `startupProbe` de 30 × 2 s, startup de 2,0 s e ~80 MiB em repouso, 0 restarts.

### 27. Visibilidade dos SVGs e relatórios na UI do Temporal `[dono: Claude — status: feito e validado no cluster (PR #18)]`
Hoje a geração por GeoLocation (SVGs, bandeira, resumo de IA, PDF) roda no
`GeoLocationEnrichmentKafkaConsumer`, chamando a atividade como método comum: o Temporal não a vê, e o
workflow "termina" quando acaba a ingestão. Decidido: **um workflow filho por GeoLocation**
(`GeoLocationArtifactsWorkflow`), com as etapas como atividades separadas (mapas, upload dos SVGs,
bandeira, resumo de IA, relatório, cópia no MinIO corporativo), **janela de concorrência de 4** no pai,
ids listados do **banco** (`listGeoLocationIds`) e não do resumo do NiFi, search attributes
(`GeoLocationId`, `CountrySlug`) e o pai só termina quando todos os filhos terminam. O consumer Kafka
mantém só a parte de IA/boundary e inicia o mesmo workflow (id `geo-artifacts-<id>`) para
GeoLocations criadas fora do import. Atenção: novas interfaces do Temporal precisam de hints no
native (`NativeRuntimeHints`), como no PR #15. Relacionado aos itens 6 e 8.

**Desenho final (ADR-0014, 26/09):** o desenho inicial (filhos reais com janela no pai) foi trocado,
com o André, por **um workflow por GeoLocation (`geo-artifacts-<id>`) numa fila própria cujo worker
executa no máximo 4 atividades ao mesmo tempo**, iniciado pelo consumer Kafka de enriquecimento (sem
mudar o NiFi e cobrindo GeoLocations criadas pela API). O workflow de import aguarda todos os ids
(lidos do banco) num estágio `ARTIFACTS`. Motivo da troca: o consumer já gera os artefatos durante a
ingestão, e evitar a duplicidade com filhos reais exigiria uma marca no NiFi e no evento. Restrição
descoberta: as etapas trocam SVGs/bandeira/PDF em memória, e o Temporal limita cada payload a 2 MB
(aviso a partir de 256 KB), então as atividades trocam **referências** (assets no MinIO) e o relatório
relê os SVGs e a bandeira do storage. As atividades passam a lançar exceção (a função atual captura
tudo e devolve `status=ERROR`, e o Temporal nunca retenta). Search attributes ficam para depois
(exigem registrar no namespace do Temporal); por ora vale o prefixo do id e o memo.

**Handoff (26/09, branch `feat/geolocation-artifacts-workflow` do `bookanything-platform`, commits
`604839b`, `9e419ed`, `91c0075`, ainda sem push):**
- **Feito:** `GeoLocationArtifactsWorkflow` (`geo-artifacts-<id>`, fila `GEOLOCATION_ARTIFACTS_TASK_QUEUE`,
  worker com `maxConcurrentActivityExecutionSize=4`) com 5 atividades (`GenerateAndStoreMaps`,
  `ResolveAndStoreFlag`, `EnrichWithAi`, `RenderAndStoreReport`, `CopyReportToCorporateStorage`); launcher
  sem duplicar (janela de 300 s); o consumer Kafka inicia o workflow em vez de chamar o método; o endpoint
  `.../artifacts-and-report` inicia e aguarda o mesmo workflow; o import ganhou o estágio
  `ARTIFACTS_GENERATION` (`Workflow.getVersion`, ids lidos do banco, resumo por país/nível em
  `artifactsSummaries`). Propriedades novas em `temporal.artifacts.*` (`application.yml`).
  ADR-0014, `temporal-testing` no pom, `StorageProviderPort.readBytes`.
- **Testes:** 10 testes novos no servidor de teste do Temporal (ordem das etapas, retry só do relatório,
  cópia corporativa tolerante, falha não retentável, regras do launcher) + suíte completa: 87 unitários e
  26 de integração (Testcontainers) sem falhas.
- **Validado localmente com o binário native e com o JVM** (Temporal local, Kafka em `localhost:9092`):
  província (#177) e país (#204) `SUCCESS`; 9 itens em paralelo mantiveram no máximo **4 atividades
  simultâneas**; 0 erros de reflection. A história do workflow mostra cada etapa com início e fim.
- **Dois erros que só o teste local achou** (não aparecem em teste unitário nem em JVM): (1)
  `@Lazy` sobre uma classe concreta no consumer gera um proxy CGLIB e o native quebra no startup
  (`MissingReflectionRegistrationError ...$$SpringCGLIB$$0.CGLIB$FACTORY_DATA`); (2) as atividades rodam
  em threads do worker do Temporal, sem sessão do Hibernate, e o mapper de **província** lê uma coleção
  lazy (`LazyInitializationException`); um país não tem essa coleção, por isso o primeiro teste local
  (DEU) passou. Corrigido com transações curtas só nas leituras. Um `mvn` sem `clean` também deixa
  proxies CGLIB antigos em `target/` e quebra o `process-aot`: usar `clean`.
- **Ainda não validado (só no cluster):** o estágio `ARTIFACTS_GENERATION` do workflow de import (precisa
  do NiFi) e o caminho do consumer Kafka disparado pela criação/atualização via NiFi. Depois do merge:
  reimportar um país e conferir na UI do Temporal `geo-artifacts-*` com as 5 etapas, o pai só terminando
  quando todos terminam e `artifactsSummaries` no resultado.
- **Limites conhecidos:** a janela de 4 é por Pod (com mais réplicas multiplica); search attributes
  (`GeoLocationId`, `CountrySlug`) ficam para depois, pois registrar exige mudar o namespace do Temporal;
  filtrar na UI pelo prefixo `geo-artifacts-`. O PDF do JSReport local levou até 18 s em uma chamada
  isolada (item 8).

**Validação no cluster (26/09, PR #18 mergeado com `[native]`, imagem `2026.0926.203739-native`):**
- Pipeline com o `native-image` dentro do Kaniko, sem cache (o código mudou): ~22 min; o ponto mais baixo de
  memória da máquina foi 13 GiB disponíveis. Pod novo: startup de 2,1 s, ~170 MiB em repouso.
- **Import de Portugal (`PRT`, níveis 0 e 1), 2 min 35 s de ponta a ponta:** o consumer Kafka iniciou os
  `geo-artifacts-*` durante a ingestão, o workflow de import entrou em `ARTIFACTS_GENERATION` (80–84%) e só
  completou depois do 21º filho. Resultado `COMPLETED` com `totalCreated=21` e
  `artifactsSummaries`: PRT nível 0 = 1/1 e nível 1 = 20/20 (0 falhas).
- **21 workflows, 105 atividades** (5 por item), **no máximo 4 simultâneas** (janela do worker), memória do Pod
  com pico de 376 MiB (limite 1536Mi), 0 restarts. Só 2 reexecuções, ambas de `RenderAndStoreReport` (erro
  do JSReport, ver item 8): as demais etapas do item não foram refeitas.
- Contagens conferidas: 118 GeoLocations (4 países e 114 estados; 0 sem geometria, mapa ou relatório),
  354 imagens e 118 documentos no banco e no MinIO do tenant, 121 objetos em `darueira-reports` (118
  relatórios + 3 resumos de job), 16 arquivos em `darueira-geodata`.
- **Lição do teste:** um import disparado com o código errado (`POR`; o ISO3 de Portugal é `PRT`) não cria
  nenhuma GeoLocation e ficaria 25 min esperando: ver o caso real no item 4.


### 28. Endpoint e workflow de limpeza de GeoLocations `[dono: Claude — status: planejado (fase B)]`
`POST` assíncrono (padrão do `batch-import`) com uma coleção de
`{countrySlug, locationLevel, shouldDeleteJsonFile, shouldDeleteXmlFile}` e **`dryRun=true` por
padrão**. Decisões do André (26/09):
- Nível 0 com filhos no banco: **bloquear** (o dry-run mostra o motivo). Nunca apagar `CONTINENT` nem
  `REGION`.
- Apagar também `darueira-reports/geolocations/geolocation-detail-report-<friendlyId>.pdf`; **não**
  apagar os resumos de job (`job-geo-import-*-summary.pdf`).
- **Sem OIDC/OpenFGA por enquanto**: entra depois que tudo estiver rodando 100% (registrar no item 24
  e em `authz/schema.fga`).
- Divisão: o **backend** apaga banco e assets (tenant) e as cópias no corporativo (atividades
  `montarPlano`, `apagarAssetsEGeoLocations`, `verificar`); o **NiFi** apaga `raw/*.json` e
  `xml/*.xml` do `darueira-geodata` conforme as flags, com o padrão pedido/resposta via Kafka
  (`geolocation.nifi-delete.requested|completed`). Fluxo do NiFi versionado em `platform/nifi/` com
  harness de teste, como o passo 8.
- Depende da fase A (mesmo padrão de visibilidade por item) e de um ADR novo em `specs/adr/`.

### 29. Testes de integração falam com o Temporal do cluster `[dono: Claude — status: em andamento]`
O `application.yml` tem o ClusterIP do Temporal como endereço padrão (`10.152.183.189:7233`), alcançável da
máquina. Depois que o consumer Kafka passou a **iniciar** o workflow de artefatos (PR #18), os testes de
integração (Testcontainers) criaram GeoLocations e iniciaram `geo-artifacts-1..34` no Temporal **real**
(namespace `corporate-core`, 26/09 ~17:45): ficaram na fila sem worker e, quando o Pod novo subiu (19:00),
falharam com "GeoLocation not found" (ids do banco de teste; nenhum dado real afetado). Corrigir: o perfil de
teste deve apontar o Temporal para um endereço inerte (ou trocar o launcher por um dublê) e nenhum teste pode
alcançar o cluster. Os 34 workflows `Failed` ficam no histórico até a retenção do namespace.

---

## 🟠 Média prioridade

### 4. Demais passos do NiFi com falha silenciosa
- Passo 3 (download do GADM, `InvokeHTTP`): auto-termina `Failure`, `Retry` e `No Retry`. Se o
  download falhar, o workflow espera 25 minutos em silêncio.
- Passos 4, 6 e 7 (MinIO / conversão XML): auto-terminam `failure`.

Aplicar o mesmo padrão do passo 8: sempre responder ao workflow com um `errorMessage`, e versionar
os scripts em `platform/nifi/`.

**Caso real (26/09):** um import disparado com `countrySlug=POR` (o ISO3 de Portugal no GADM é `PRT`) fez o
passo 3 receber HTTP 404 em `gadm41_POR_0.json`; o NiFi descartou o erro e o workflow ficou esperando o
timeout de 25 min, sem nenhuma mensagem. Com `errorMessage` na resposta o workflow falharia em segundos. O
backend também poderia validar o código do país antes de iniciar o workflow.

### 5. Restarts em massa dos pods `[dono: Claude — status: parcial]`
temporal-server (63), central-postgres (38), Forgejo/Tekton (~46), entre outros. Parte vem dos
stop/start do MicroK8s, mas é preciso checar OOM e liveness probes agressivas. Foi um restart do
Temporal que deixou o worker sem pollers em 24/09.

**Handoff (2026-09-25, Claude):** tratadas as causas de memória e de conexões (itens 17 e 18). Ainda
não foram revisadas as liveness probes nem os restarts do Forgejo e do Tekton.

### 6. Backend reagir a falhas parciais do import
- Logar `errorMessage` / `failedCount` (novos no resumo do NiFi) no log "Ingestion finished".
- Marcar o workflow como parcial/falho quando `failedCount > 0`, em vez de `COMPLETED`.

**Caso real (26/09, USA nível 1):** o NiFi respondeu `createdCount=36, failedCount=15` com
`POST province US-XX -> HTTP -1: SocketTimeoutException: Read timed out` (o log mostra só 5 dos 15
estados: AK, MA, NH, NJ, NM). O backend logou `Created=36` e publicou
`geolocation.batch-import.completed`, e **os 51 estados estavam gravados no banco**: o NiFi desistiu
de esperar, mas o backend concluiu os POSTs. Ou seja, `failedCount` por timeout **não significa que o
registro não foi criado**, e `createdCount` subestimou o resultado. Além de reagir a `failedCount`,
o resumo deveria conciliar com o banco (ou o NiFi deveria tolerar timeouts com um read timeout maior /
tratar HTTP -1 como "incerto"). Hipótese não verificada para os timeouts: o Pod (limite de CPU de
1500m) estava gerando os mapas do DEU com o GeoPandas ao mesmo tempo que recebia os POSTs dos 51
estados; com um país por vez (BRA) não ocorreu.

### 7. Backlog do enriquecimento (fase 2)
- Tirar o trabalho de enriquecimento do `@Transactional` do consumer Kafka.
- Persistir a fonte usada (Wikidata / flagcdn / Gemini / tabela) e criar um endpoint de re-enriquecimento.
- Fallback de resumo a partir dos fatos do Wikidata.
- Revisar quota/plano do Gemini (considerar `gemini-2.5-flash-lite` para resumos).
- Detalhe: Bayern veio com a bandeira listrada (1ª do Wikidata); a losangulada também é oficial.
  Decidir se fixa uma.

### 8. JSReport: `Protocol error (Page.printToPDF): Target closed`
Falhas ocasionais, hoje cobertas pelo retry. Em 26/09, todas `HTTP 500` (`Target closed`): 2 no
import do DEU sozinho (o relatório só passou na 3ª tentativa), 2 no do BRA (cada uma passou na 2ª) e
mais 2 no início do DEU+USA. Depois disso não foi possível contar (o log do Pod rotacionou). Nenhum
item falhou de vez nos 97. Investigar memória/concorrência do Chrome no pod do JSReport antes que
excedam os retries.

**Atualização (26/09, import de PRT):** 2 falhas `HTTP 500` em 21 relatórios
(`Navigating frame was detached` e `Protocol error (Page.printToPDF)`). Com o workflow por item, cada uma foi
retentada só na etapa `RenderAndStoreReport` (5 tentativas configuradas) e passou na 2ª; agora as tentativas
aparecem na UI do Temporal.

### 9. Debug do cilium-cni ligado
`05-cilium-cni.conf` tem `enable-debug: true` e escreve `/run/cilium/cilium-cni.log`, já com 55 MB
em tmpfs (RAM), só limpo no reboot. Desligar o debug ou rotacionar o log.

---

## 🟡 Baixa prioridade / estrutural

10. **Migrar os PVs do HDD para o NVMe.** O HDD 5400rpm é o gargalo do Postgres (~4 min de fsync
    de recuperação) e do OpenSearch.
11. **Testes de workflow do Temporal** (hoje não há nenhum). Os dois bugs de 24/09 (worker sem
    pollers, timeout único de 30 min) seriam pegos com `TestWorkflowEnvironment`.
12. **Upgrade do Cilium para ≥ 1.16**: `endPort` nas CiliumNetworkPolicies (hoje lista explícita de
    portas, com TODO) e possivelmente melhor tratamento de endpoints restaurados.
13. **DNS rebind da FritzBox**: `*.nip.io` não resolve no host (Fase E).
14. **Inventário de chamadas plataforma → tenant**, para revisar as network policies.
15. `[dono: Claude — status: feito]` **Tirar dados fixos do passo 8 do NiFi**: mapa país→região (WEU/SAM) e nomes de país hardcoded.
    **Handoff (2026-09-25, Claude):** o passo 8 agora resolve o pai pelos dados do backend:
    - país → REGION: atributo `parentFriendlyId`, senão `memberCountriesIso3`, senão o pai atual;
    - província → COUNTRY por friendlyId exato; se o país não existir, é criado com o nome do GADM;
    - cidade/distrito → província/cidade **do mesmo país**, por GID, depois HASC, depois nome
      normalizado (sem acentos e espaços). Chaves ambíguas são descartadas.

    Registros sem pai contam como falha, em vez de serem criados órfãos. Os registros novos guardam
    `gid`. Antes, o nível 3 (distritos) nem tinha pai, e o nível 2 só olhava as primeiras 200
    províncias do sistema inteiro.
    Teste offline: `make test-nifi-scripts`, 14 cenários, passando no Groovy 3.0.23 do NiFi.
    Aplicado e verificado com `make check-nifi-scripts`.
    Validado em 25/09 com o workflow USA `geo-import-3400f097…`: COMPLETED, nível 1 com 50 criados,
    1 atualizado e 0 falhas. Os 51 estados ficaram sob o USA com `gid`, e o backend não reiniciou
    (pico de ~980Mi de 2Gi).
16. **Validar o cleanup do Cilium** no próximo `microk8s stop` / `start`:
    `journalctl -t cilium-state-cleanup` deve mostrar "removed N stale Cilium endpoint state dirs",
    e `cilium status | grep IPAM` deve ficar em torno de 85, não 168.
    Runbook: `docs/runbooks/cilium-cni-migration.md`, achado crítico #7.

---

## Ideias adicionais do André

_(a agregar em 2026-09-25)_
