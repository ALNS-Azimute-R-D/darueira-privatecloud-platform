# Runbook: Backup completo do cluster e migração para um disco novo

**Status:** a parte de backup (seções 1 a 3) foi executada em 2026-11-23. A parte de restauração no disco novo (seção 5) é um **roteiro ainda não testado**: ajustar conforme a execução.

## 1. O que é salvo e por quem

| Parte | Ferramenta | Parada? | Conteúdo |
|---|---|---|---|
| Volumes persistentes (22 PVs `darueira-host-storage` em `/mnt/FileBuckets01/darueira-platform/data`) | `make backup-pvc` (`scripts/backup_pvc.sh`) | **Sim**, a frio: escala as cargas a 0, grava um `.tar.gz` por volume, restaura as réplicas (também em erro, por `trap`) | PostgreSQL x3, MinIO x3, OpenBao x3, Forgejo, NiFi, etcd do APISIX, RabbitMQ, Kafka, Stalwart, Nexus (com `--include-nexus`), etc. |
| Estado fora dos PVs | `make backup-state` (`scripts/backup_cluster_state.sh`) | Não | todos os objetos do Kubernetes (**Secrets inclusos**) e CRDs; `pg_dump -Fc` de cada banco dos 3 PostgreSQL; imagens que só existem no cache do nó (`localhost:8082/*`, 1,1 GB); versões e config do MicroK8s/Docker |

Fora do backup por escolha: `ephemeral/` (workspaces do Tekton) e, por padrão, `corpshared-obs/` (Prometheus, OpenSearch com 3 dias de logs, Grafana): recriáveis. Use `FLAGS="--include-obs"` para incluí-los.

O cache do Maven e as imagens públicas se recriam sozinhos. As imagens que passam pelo Nexus estão no PV do Nexus.

## 2. Como gerar

```bash
make backup-state                              # sem parada; rode primeiro
make backup-pvc FLAGS="--dry-run --include-nexus"   # mostra volumes e cargas que serão paradas
make backup-pvc FLAGS="--include-nexus"        # para o cluster por alguns minutos
make backup-verify                             # checksums + tar -t do último backup de PVs
```

Destinos padrão: `~/Backups/darueira-platform/<timestamp>/` (PVs) e `~/Backups/darueira-platform-state/<timestamp>/` (estado, modo 700).

Depois do backup a frio, o RabbitMQ e o Kafka voltam com as filas, mas os consumidores `food-market-01-service` e `food-market-05-service` podem precisar de restart (backlog item 39).

## 3. Segredos: cifrar antes de copiar para outro computador

O diretório de estado contém `k8s/secrets.yaml` (todas as credenciais do cluster) e os backups dos PVs contêm o OpenBao, cuja chave de unseal está em `.vault-keys.env` dentro do próprio volume. Cifre antes de sair desta máquina:

```bash
cd ~/Backups
tar -cf - darueira-platform-state/<ts> darueira-platform/<ts> | gpg --symmetric --cipher-algo AES256 -o darueira-backup-<ts>.tar.gpg
sha256sum darueira-backup-<ts>.tar.gpg > darueira-backup-<ts>.tar.gpg.sha256
```

A senha é digitada no terminal e guardada fora do disco. Para abrir: `gpg -d darueira-backup-<ts>.tar.gpg | tar -xf -`.

## 4. Conferir uma cópia

- `sha256sum -c` do `.sha256`, e depois `make backup-verify` com o conteúdo aberto.
- Um dump lógico se confere com `pg_restore -l arquivo.dump` (lista tabelas e extensões).

## 5. Restaurar num disco novo (roteiro, não testado)

Como os PVs são `hostPath` em `/mnt/FileBuckets01/darueira-platform/data`, a migração dos dados é só montar o disco novo nesse caminho. O MicroK8s (`/var/snap/microk8s`, containerd, dqlite) continua no disco do sistema, a menos que se decida mover.

1. Particionar e formatar o SSD novo (ext4) e montar em `/mnt/FileBuckets01` (entrada no `/etc/fstab` por UUID). Exige root: é com o André.
2. Cluster no ar e com o disco montado vazio: `make restore-pvc ID=<timestamp>` (preserva o que existir como `*.pre-restore-*`). Alternativa em máquina nova: instalar MicroK8s, aplicar os manifests do Git (`make deploy-...`) e restaurar os PVs antes de subir as cargas.
3. Imagens do nó: `ctr -n k8s.io images import images/node-local-images.tar` (com o `ctr` do MicroK8s). O restante vem do Nexus (depois de restaurado) ou dos registries públicos.
4. Objetos que não estão no Git (Secrets criados por script): `k8s/secrets.yaml` do backup de estado, aplicando só os que faltarem (revisar antes de aplicar: nada de `kubectl apply` cego, para não sobrescrever o que o Git gerencia).
5. Bancos: se o diretório de dados restaurado não subir, restaurar a partir do dump: `pg_restore -d <banco> --clean --if-exists` (com `_globals.sql` primeiro, para criar roles).
6. Conferir: `make cluster-health`, o OpenBao destravado (a chave está no volume), o OpenFGA com store/modelo (ConfigMap `openfga-ids`) e os workflows do Temporal.

## 6. Pegadinhas

- O `scripts/systemd/darueira-backup.service` aponta para um caminho antigo do repositório (`03-PoCs-And-Researches/...`); o timer semanal **não está instalado**. Corrigir o caminho antes de `make backup-schedule`.
- `backup_pvc.sh` roda o `tar` num pod root em `kube-system` (os namespaces `drr-*` proíbem `hostPath`), então não precisa de `sudo`.
- Os backups antigos (`20261109-*`, `20261114-*`) incluem os volumes de `tenant-mysql` e `tenant-mongodb`, já descomissionados.
