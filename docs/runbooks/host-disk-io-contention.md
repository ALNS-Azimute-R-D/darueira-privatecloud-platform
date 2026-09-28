# Host disk I/O contention (chronic) — `central-postgres` and friends

**Status:** achado confirmado em 2026-09-28. Sem correção aplicada (precisa de `sudo` e uma
decisão de infraestrutura do usuário); só mitigações paliativas no lado do Kubernetes.

## O sintoma

`central-postgres-0` reinicia com frequência (padrão crônico, já notado várias vezes ao longo de
semanas — ver `cilium-cni-migration.md` linhas 97, 206, 274, 374) e, a cada boot, fica preso vários
minutos num `syncing data directory (fsync)` antes de aceitar conexões:

```
2026-09-28 08:52:45.575 UTC [22] LOG:  syncing data directory (fsync), elapsed time: 60.06 s, ...
2026-09-28 08:53:55.826 UTC [22] LOG:  syncing data directory (fsync), elapsed time: 130.31 s, ...
2026-09-28 08:56:26.293 UTC [22] LOG:  syncing data directory (fsync), elapsed time: 280.78 s, ...
```

Isso derruba em cascata tudo que depende dele (Forgejo, JSReport, Stalwart Mail, Temporal Server,
Temporal UI, Backstage, Authentik) até o Postgres voltar. O runbook do Cilium já suspeitava de
"I/O lento em disco a 80%+ de uso", mas sem identificar a causa física.

## Causa raiz confirmada hoje

O host tem dois discos com características muito diferentes, e o Kubernetes só usa o lento:

```
nvme0n1 (SSD, rápido, ROTA=0)  → apenas "/" (sistema, containerd)      — 76% usado, 106 GiB livres
sda     (HD mecânico, ROTA=1)  → /home, /mnt/FileBuckets01, [SWAP]     — tudo no mesmo spindle
```

A `StorageClass darueira-host-storage` — usada por **todos** os volumes persistentes do cluster
(Postgres central, MinIO, NiFi, Nexus, Kafka, os Postgres/Mongo de tenant etc.) — resolve para
`hostPath` sob `/mnt/FileBuckets01/...`, que é uma partição (`/dev/sda2`) do **mesmo disco
mecânico** que hospeda o **swap** (`/dev/sda3`) e o `/home` (workspace, IDE, perfil do browser).

Quando a memória do host aperta e o swap entra em ação, cada página trocada disputa o mesmo braço
de disco que o Postgres (e qualquer outro pod) está usando para gravar e sincronizar seus dados.
Confirmado com `vmstat` durante o incidente: `wa` (I/O wait) entre 22% e 47%, com 7 a 17 processos
bloqueados em disco por amostra — sinal claro de fila de I/O, não de falta de CPU ou memória (o
cgroup do `central-postgres` estava usando só 293 MiB dos 2 GiB permitidos no momento do incidente).

## Mitigações já aplicadas (paliativas, não resolvem a causa)

Commit `platform/kustomize/base/corpshared-plat/central-postgres.yaml` (2026-09-28):
- `resources.limits.cpu`: `1000m` → `2000m` (o node tem folga; evita que uma disputa de CPU some
  ao problema de disco).
- `livenessProbe`/`readinessProbe`: `timeoutSeconds` `5` → `10`, `failureThreshold` alargado
  (`3`→`6` no readiness, `6`→`10` no liveness) — evita que um `pg_isready` que não conseguiu CPU/IO
  a tempo derrube um Postgres que na verdade está saudável.

Essas mudanças reduzem a chance de o Kubernetes **matar** o Postgres por falso-negativo de saúde,
mas não aceleram o `fsync` em si — um boot legítimo do Postgres neste disco continua levando
minutos.

## Remediações possíveis (decisão do usuário, precisam de `sudo`)

1. **Mover o swap para o NVMe** (`nvme0n1p2`/`vgmint`, que tem ~106 GiB livres) — tira a maior
   fonte de contenção do HD sem precisar migrar dados.
2. **Migrar a `StorageClass darueira-host-storage`** (ou pelo menos os volumes mais sensíveis a
   latência, como o Postgres central) para um caminho no NVMe.
3. Reduzir o número de serviços que dependem deste único Postgres compartilhado (hoje 16 bancos:
   Temporal, Forgejo, Authentik, Keycloak, Backstage×5, JSReport, Stalwart, Clavex...) — fora de
   escopo aqui, mas reduz o "blast radius" de cada restart.

## Regra operacional (já valia antes, reforçada aqui)

**Nunca force um restart/delete do `central-postgres-0` enquanto ele já estiver em `fsync`** —
pode corromper a sincronização em andamento. Se ele já estiver reiniciando sozinho, deixe terminar;
os dependentes se recuperam automaticamente quando ele volta. Restart manual só ajuda em pods
**dependentes** presos em backoff longo, não no Postgres em si.
