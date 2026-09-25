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

### 21. Backend como GraalVM native image `[dono: Claude — status: em andamento, pausado para reboot em 25/09 ~15:40]`
O Pod JVM usava ~930 MiB. O `Dockerfile` agora gera um executável native (o JVM ficou em
`Dockerfile.jvm`): 144–297 MiB e startup de 1,2–2,5 s no cluster.

**PRs no `bookanything-platform` (Forgejo):**
- #13 (build native), #14 (epoll do gRPC) e #15 (proxies dos stubs do Temporal e errordetails do
  protobuf): mergeados e em produção, imagem `2026.0925.144234`.
- **Próximo:** branch `fix/backend-native-minio-reflection` (commit `6750d86`, já no Forgejo, **sem PR
  ainda**). Varre `io.minio` e registra construtores, métodos e campos. **Não foi compilado nem
  testado**: a build local foi interrompida para o reboot.

**Último teste real, o import DEU `geo-import-a3a47b81…`** (falhou no MinIO):
- funcionaram o Temporal, o gatilho do NiFi via Kafka, a resposta do NiFi (`Updated=1`), o consumer
  de enriquecimento e o PDF do JSReport (63 KB);
- falhou o upload no MinIO: `class io.minio.BucketExistsArgs must have no argument constructor`;
- memória durante o import: 297 MiB.

**Retomar assim:**
1. Depois do reboot, conferir o cluster: IPAM do Cilium (item 16) e
   `journalctl -t cilium-state-cleanup`.
2. Compilar o native da branch **com limite de recursos** (a build sem limite travou a máquina em
   25/09), a partir de `1-backends/bookanything-monolith-backend-01`:
   `NATIVE_IMAGE_OPTIONS="--parallelism=8 -J-Xmx8g" nice -n 10 ./mvnw -Pnative native:compile -DskipTests -Dkotlin.compiler.daemon=false "-Dspring-boot.aot.jvmArguments=-Dspring.profiles.active=darueira-k8s"`
   com o JAVA_HOME em `~/.sdkman/candidates/java/25.2.4-graalce`. Não rodar enquanto o Kaniko do
   Tekton estiver buildando.
3. Teste local de ponta a ponta com o binário native, contra estes serviços:
   - Postgres (`svc/tenant-postgres` 15432) e Keycloak (`svc/tenant-keycloak` 18080) do tenant, via
     port-forward;
   - MinIO do tenant (`MINIO_URL`), MinIO corporativo (`CORPORATE_MINIO_ENDPOINT`) e JSReport
     (`JSREPORT_BASE_URL`), via port-forward;
   - Temporal local: `temporal server start-dev --headless --port 17233 -n corporate-core` (o CLI é
     copiado do pod do temporal-server);
   - exercitar `POST /api/v1/geolocations/workflows/{geoLocationId}/artifacts-and-report` (DEU = #82).

   Procurar nos logs `MissingReflection|MissingResource|Panic|InstantiationException|must have no
   argument constructor`, e não só o resultado HTTP.
4. Se passar: abrir o PR, André faz o merge (a pipeline leva ~26 min) e dispara o DEU de novo.
5. Depois: reduzir o limite de memória do chart (2Gi → ~1Gi) e remover o `JAVA_TOOL_OPTIONS`.

**Lições:**
- Cada tipo que falta registrar para reflection só aparece em runtime. O teste local de ponta a
  ponta pega a maioria antes do cluster.
- O Spring AOT sobrescreve o `reachability-metadata.json` de `<group>/<artifact>`; os hints manuais
  ficam em `native-overrides/` ou no `NativeRuntimeHints`.

### 23. Probe do tenant-mongodb pesada
A probe abre um `mongosh` inteiro a cada verificação (275% de CPU observado em 25/09; 39 e 31
restarts). Trocar por uma probe TCP ou por um comando mais leve.

### 22. Handler global de exceções do backend não loga
Os erros 500 voltam com a mensagem no corpo, mas nada aparece no log do Pod: foi assim que o disparo
do DEU falhou em silêncio no native. Logar a exceção (com stack) no handler.

---

## 🟠 Média prioridade

### 4. Demais passos do NiFi com falha silenciosa
- Passo 3 (download do GADM, `InvokeHTTP`): auto-termina `Failure`, `Retry` e `No Retry`. Se o
  download falhar, o workflow espera 25 minutos em silêncio.
- Passos 4, 6 e 7 (MinIO / conversão XML): auto-terminam `failure`.

Aplicar o mesmo padrão do passo 8: sempre responder ao workflow com um `errorMessage`, e versionar
os scripts em `platform/nifi/`.

### 5. Restarts em massa dos pods `[dono: Claude — status: parcial]`
temporal-server (63), central-postgres (38), Forgejo/Tekton (~46), entre outros. Parte vem dos
stop/start do MicroK8s, mas é preciso checar OOM e liveness probes agressivas. Foi um restart do
Temporal que deixou o worker sem pollers em 24/09.

**Handoff (2026-09-25, Claude):** tratadas as causas de memória e de conexões (itens 17 e 18). Ainda
não foram revisadas as liveness probes nem os restarts do Forgejo e do Tekton.

### 6. Backend reagir a falhas parciais do import
- Logar `errorMessage` / `failedCount` (novos no resumo do NiFi) no log "Ingestion finished".
- Marcar o workflow como parcial/falho quando `failedCount > 0`, em vez de `COMPLETED`.

### 7. Backlog do enriquecimento (fase 2)
- Tirar o trabalho de enriquecimento do `@Transactional` do consumer Kafka.
- Persistir a fonte usada (Wikidata / flagcdn / Gemini / tabela) e criar um endpoint de re-enriquecimento.
- Fallback de resumo a partir dos fatos do Wikidata.
- Revisar quota/plano do Gemini (considerar `gemini-2.5-flash-lite` para resumos).
- Detalhe: Bayern veio com a bandeira listrada (1ª do Wikidata); a losangulada também é oficial.
  Decidir se fixa uma.

### 8. JSReport: `Protocol error (Page.printToPDF): Target closed`
Falhas ocasionais, hoje cobertas pelo retry. Investigar memória/concorrência do Chrome no pod do
JSReport antes que excedam os retries.

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
