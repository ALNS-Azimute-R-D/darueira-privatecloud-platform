# Runbook: pipeline de logs (Fluent Bit → OpenSearch → Dashboards)

> **2026-09-23.** Correção do OpenSearch corporativo "inacessível". A rede estava ok (a porta `5601` estava aberta desde o achado crítico #3 em `cilium-cni-migration.md`). O problema era o índice e o disco.

## Sintomas

- No browser, o OpenSearch Dashboards travava. Os `PUT /api/saved_objects/index-pattern/darueira-k8s-logs` levavam ~25 s e terminavam em **409 `version_conflict`**, em paralelo, ou em 499 (o browser desistia).
- O index-pattern `darueira-k8s-logs-*` tinha **1603 campos (359 KB)**, contra um limite de 1000 campos por índice.
- Ingestão atrasada: o `@timestamp` mais recente ficava minutos atrás do relógio, e o pool `write` tinha **~2000 bulks na fila**, 1 thread ativa e CPU ociosa.
- Cluster `yellow`: 34 réplicas sem alocação num cluster de nó único.

## Causas

1. **Explosão de mapeamento.** O filtro `kubernetes` do Fluent Bit usava `Merge_Log On` sem `Merge_Log_Key`, então o JSON de cada app (MongoDB `attr.*`, `raw_request.*`, `config.*`, …) ia para a raiz do documento, e cada chave nova virava campo novo.
2. **Disco.** Os dados do OpenSearch, e dos **24 serviços com estado do cluster**, ficam em `/mnt/FileBuckets01` (`/dev/sda2`). É um **HDD de notebook de 5400 rpm** (Seagate ST2000LM015), o mesmo disco do `/home`. Medido: 100% ocupado movendo ~3 MB/s, ou seja, preso em I/O aleatório e fsync. A única thread de escrita do OpenSearch (`allocated_processors: 1`) ficava parada no fsync do translog, que por padrão acontece a cada requisição.
3. **Réplicas:** `number_of_replicas: 1` (padrão) num nó único.

## Correções

| O quê | Onde |
| :--- | :--- |
| `Merge_Log_Key log_processed`: o JSON dos apps vai para uma chave única | `platform/kustomize/base/corpshared-obs/fluent-bit.yaml` |
| Index template `darueira-k8s-logs`: `log_processed` como `flat_object` (conta como 1 campo), `replicas: 0`, `translog.durability: async`, `sync_interval`/`refresh_interval` de 30 s | `platform/kustomize/base/corpshared-obs/opensearch-index-config/index-template-darueira-k8s-logs.json` |
| Política ISM `darueira-k8s-logs-retention`: **apaga índices com mais de 2 dias** (retenção escolhida pelo usuário) | `…/opensearch-index-config/ism-policy-darueira-k8s-logs-retention.json` |
| Provisionamento idempotente: template + ISM, e nos índices existentes anexa a política, aplica os settings e mapeia `log_processed` | `scripts/bootstrap_observability.py` → `provision_opensearch_indices()`, chamado pelo `make bootstrap-observability` |

As buscas e visualizações provisionadas (`scripts/generate_opensearch_saved_objects.py`) só usam `kubernetes.*`, `stream`, `log` e `@timestamp`. O `Keep_Log On` preserva o `log` original, então nenhuma delas quebrou. O JSON estruturado dos apps agora se consulta como `log_processed.<chave>`.

**Ordem importa:** o template só vale para índices novos. Por isso o provisionamento também mapeia `log_processed` como `flat_object` nos índices **já existentes**. Sem isso, o índice do dia ganharia `log_processed.*` dinâmico ao virar a config do Fluent Bit, passaria dos 1000 campos e **rejeitaria logs até a meia-noite UTC**. Índices antigos que já estão no limite são pulados (ficam só para leitura e a retenção os apaga).

## Validação (2026-09-23)

- Fila `write`: de 1958 para 0 em ~30 s depois do translog assíncrono. Fluent Bit com entrada ≈ saída e 0 erros.
- Atraso da ingestão: de ~8 min para ~5 s.
- Documentos novos com `log_processed` (ex.: MongoDB). Campos do índice do dia estáveis (834 → 835).
- ISM: 31 índices apagados em ~8 min. Ficam `2026.09.22` e `2026.09.23`, ambos `green`, com ~1,1 GB (antes eram 11,5 GB).
- Os índices internos do ISM e do job-scheduler (`.opendistro-*`) também nascem com 1 réplica, e o histórico do ISM é recriado todo dia. O provisionamento zera as réplicas deles e grava `plugins.index_state_management.history.number_of_replicas: 0` no cluster.
- Index-pattern reimportado só com a definição provisionada (sem `fields`): de 359 KB para 274 bytes. O Dashboards calcula 884 campos a partir dos índices atuais (antes eram 1603). Esse número cai de novo quando o índice pré-correção (`2026.09.22`) sair pela retenção.

## Pendências

- **Mover os volumes com estado do HDD para o NVMe** (`/`, SSD Samsung 970 EVO Plus, com ~112 GB livres). É a correção de fundo: Postgres, Kafka, MongoDB, MySQL, Prometheus e os demais competem pelo mesmo disco de ~100 IOPS. O ajuste do translog só alivia o OpenSearch.
- `doc_localizable_places` (índice de um app, não do pipeline de logs) ainda tem 1 réplica, e isso mantém o cluster `yellow`.
