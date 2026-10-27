# Environment Tuning, Cleanup and New `make` Helpers: Discussion and Action Plan

## From Andre:

On 23.10.2026, André asked both Claude and Antigravity to work together on the local environment: tools,
cluster, infra, disk, cleaning, optimizations and new facilitators in the `Makefile`. Same collaborative
format as the previous discussions: each agent writes only its own sections, then we debate (arguments,
counterarguments, counterpoints) and converge on a final decision and action plan.

Context: the machine crashed and had to be force-rebooted on 22/23.10. The platform is a PoC/lab, so
destructive cleanup inside it is acceptable, but host-level changes (journal, `/var/log`, sudo) are handed
to André.

**Addendum (23.10.2026, same day):** André added two items to this front:

1. Helpers to **generate/restore a backup of all persistent volumes (PVCs)**, whose data lives under
   `/mnt/FileBuckets01/darueira-platform/data`.
2. `make` targets that **keep running only what is necessary, per tenant**: if André works only on Tenant X,
   the other tenants and the corporate services not needed by X must be stopped to save host resources.
   Both agents should think through and evaluate the possibilities.

---

## Analysis and Evaluation by Claude:

### 1. Snapshot taken on 2026-10-23 (read-only, verified)

| Item | Value | Note |
|---|---|---|
| MicroK8s | running, single node `nbalns-mifcom-lnx-01` | all pods `Running`/`Completed`, none failing |
| Node memory | 43.5 GiB used of 62 GiB (68%) | host `free`: 34 GiB used, 28 GiB cache, 27 GiB available |
| Node CPU | ~2.9 cores (14%) | host load avg ~4.4 |
| `/` | 79% (93G free of 456G) | |
| `/home` | 81% (228G free of 1.2T, 927G used) | **not yet broken down**: the `du` timed out |
| `/var/log` | 7.5 GB | `/var/log/pods` 3.6 GB, `/var/log/journal` 3.4 GB |
| `/var/snap/microk8s` | 2.4 GB | two revisions present (8565, 8456) |
| Top memory pods | Nexus 2.0 GiB, NiFi 1.4 GiB, OpenSearch 0.8 GiB, Kafka 0.8 GiB, Authentik 0.8 GiB | |
| Pods per namespace | plat 23, europe-dev 19, mgmt 17, latam-dev 7, obs 7, secr-internal 3, kube-system 7 | |
| Docker | `docker ps` empty | the cluster uses containerd, not Docker |

The `Makefile` already has ~70 targets (`cluster-*`, `bootstrap-*`, `validate-*`, `port-forward-*`, `proxy*`,
`check-*`). What it lacks is a **host/disk/health** group.

### 2. Proposed items (all open for debate)

1. **`make disk-report`**: read-only. `df`, top consumers of `/home` (run `du` with a timeout and `ionice`),
   `/var/log`, containerd image store, Maven `~/.m2`, Gradle, npm, IntelliJ caches. Output sorted, one screen.
2. **`make cluster-health`**: one-shot read-only: non-Running pods, restart counts above a threshold,
   node memory/CPU, PVC usage, expired certificates, Cilium IPAM usage (the leak fixed on 24/09).
3. **`make clean-logs`** (mutating, needs sudo): `journalctl --vacuum-size=500M` and rotation of pod logs.
   Printed as a command for André to run, since the agent has no TTY for sudo.
4. **`make clean-images`**: prune unused images in the MicroK8s containerd (`microk8s ctr images prune`
   or `crictl rmi --prune`), keeping the images used by running pods.
5. **`make post-boot-check`**: after a reboot/crash, wait for Postgres/Keycloak/Temporal to become ready in
   dependency order and print what is still failing (history: the 14/10 restart storm, see
   `keycloak-upgrade-26.8.1.md`).
6. **Memory right-sizing**: only after measuring over a few days; do not guess requests/limits.
7. **Tooling inventory**: `make tools-check` listing required CLIs and versions (kubectl, helm, kustomize,
   mvn/JDK 25, groovy, potrace/vtracer once chosen, temporal CLI).

### 3. Risks and open questions (Claude)

- Anything under `/var/log` and the journal is outside the repo and needs `sudo`: André runs it.
- Pruning images can force re-pulls and slow the next start; Nexus holds the Kaniko cache, so confirm
  nothing in-cluster depends on a locally cached image before pruning.
- Is 79-81% disk usage actually a problem now, or only a trend? Needs the `/home` breakdown first.
- Is the cleanup in `scripts/setup_host_cilium_state_cleanup.sh` (installed 24/09, "not validated in a real
  stop/start") still working after this crash? Verify before adding more cleanup logic.

### 4. PVC backup and restore (addendum, verified read-only on 2026-10-23)

**What the cluster really has** (`kubectl get pv`):

| Class | Provisioner / reclaim | Where the data lives | Count |
|---|---|---|---|
| `darueira-host-storage` | no-provisioner, **Retain** | `/mnt/FileBuckets01/darueira-platform/data/<tier>/<name>` (static PVs `pv-drr-*`) | 24: platform (NiFi, central MinIO, central Postgres, Forgejo, JSReport, Kafka, RabbitMQ, Nexus, Stalwart, Temporal), obs (Grafana, OpenSearch, Prometheus), secr (OpenBao), and per tenant (MinIO, MongoDB, MySQL, OpenBao, Postgres) |
| `microk8s-hostpath` (default) | dynamic, **Delete** | `/var/snap/microk8s/common/default-storage/...` | 29 Bound + 1 Released: ArgoCD/Tekton/Backstage workspaces in `drr-corpshared-mgmt`, `apisix-etcd-pvc`, `webmail-data-pvc`, `maven-repo-cache`. The Released one is `registry-claim` (20Gi), an **orphan of the old MicroK8s `registry` addon**: namespace `container-registry` no longer exists and its data directory is gone (corrected 24/10; an earlier draft wrongly listed it as a live 20 Gi registry) |

**Findings that change the design:**

- **The requested folder covers only the first class.** The `microk8s-hostpath` PVCs (APISIX etcd with all routes,
  webmail, Tekton/Argo state) are outside it and have `Delete` reclaim: removing the PVC
  destroys the data. Decide whether they are in scope (most are rebuildable: routes come from
  `scripts/bootstrap_apisix_routes.py`, images from Tekton). Suggested default: back up the static `Retain`
  volumes, list the dynamic ones as "rebuildable" and offer `--include-dynamic`.
- **Nexus is the elephant**: 71 GB in `nexus-data` (the PV declares 10Gi, which hostPath does not enforce), out of
  ~75 GB total (`corpshared-plat` 73 GB, obs 2.8 GB, tenants 1.1 GB, secr/mgmt negligible). Kafka 1.3 GB,
  central Postgres 443 MB. Nexus must be opt-in (`INCLUDE_NEXUS=1`) or backed up incrementally, otherwise every
  backup is 75 GB. It is also a cache of Maven/registry content that can be repopulated (except the manually
  uploaded `jackson-datatype-jts`, see commit `9aa987a`).
- **Same-disk problem**: the data dir is on `/dev/sda2` (`/mnt/FileBuckets01`, 80% used, 114 GB free). A backup
  placed on the same disk protects against deletion and bad upgrades, not against disk loss. The destination
  should be configurable (`BACKUP_DIR`), defaulting to a different disk (candidate: `/home`, 228 GB free, but
  also 81% used) or an external drive.
- **Consistency**: copying a live Postgres/MySQL/Kafka/OpenSearch data dir can yield a corrupt backup (and
  Postgres data dirs here already needed slow fsync recovery after crashes). Options:
  (a) **cold**: scale the owning workload to 0, `tar`/`rsync`, scale back (simple, always consistent, causes
  downtime, which is acceptable in a lab); (b) **logical dumps** for databases (`pg_dump`/`mysqldump`/Mongo dump,
  as already argued in `keycloak-upgrade-26.8.1.md`) plus file copy for the rest; (c) hot rsync with a final
  cold pass. Suggested: cold by default, logical dumps for Postgres/MySQL as the portable layer.
- **Ownership**: data dirs are written by container UIDs (Postgres 999, etc.). `tar --numeric-owner` as root or
  `rsync -aHAX` is required to restore ownership. The agent has no sudo TTY, so the privileged part is a command
  for André to run.
- **Restore** must be tested, not assumed: `restore` should refuse to run while the workload is up, show a diff
  of what will be overwritten, and keep the previous data dir as `.pre-restore-<timestamp>`.

**Proposed targets:**
`make backup-pvc [SCOPE=all|platform|obs|secr|tenant:<name>] [BACKUP_DIR=...] [INCLUDE_NEXUS=0|1] [MODE=cold|dump]`,
`make backup-list`, `make backup-verify` (checksums + `tar -t` / `pg_restore --list`),
`make restore-pvc BACKUP=<id> [SCOPE=...]`, `make backup-prune KEEP=<n>`.
Implementation as a script in `scripts/` (like `setup_host_cilium_state_cleanup.sh`), the `Makefile` only wraps it.

### 5. Per-tenant "lean mode" (addendum)

**Current inventory** (Deployments/StatefulSets, replicas = 1 unless noted): corporate `drr-corpshared-plat`
(23 pods), `-mgmt` (17), `-obs` (7), `-secr-internal` (3); tenants `swfabrik-europe-dev` (19 pods, includes
BookAnything, food-market, caseforce) and `swfabrik-latam-dev` (7). Tenant MongoDB is already scaled to 0.

**Why it is feasible:** the tenant data lives in static `Retain` PVs, so scaling Deployments/StatefulSets to 0
keeps all data; `kubectl scale` is reversible; the namespace labels (`darueira.io/tier`, `darueira.io/tenant`)
allow selecting by tenant without hard-coding names.

**Proposed model: profiles with an explicit dependency graph**, kept as data (a YAML next to the Makefile, e.g.
`platform/profiles/*.yaml`), not as hard-coded `kubectl` lines:

| Profile | Runs | Stops |
|---|---|---|
| `core` (always, minimal) | `central-postgres`, `keycloak-server`, `cert-manager`, `openbao-master`, APISIX gateway + etcd | everything else |
| `tenant:<name>` | `core` + the tenant namespace + only the corporate services that tenant needs | other tenants, unneeded corporate services |
| `dev-loop` (add-on) | Forgejo, Tekton, ArgoCD, Nexus (the CI/CD path) | off by default, on when pushing code |
| `obs` (add-on) | OpenSearch, Prometheus, Grafana, Jaeger, OTel | off by default (OpenSearch alone is ~0.8 GiB) |
| `iam-lab` | `core` + Authentik + LDAP outpost + Clavex + OpenFGA | for the Keycloak/Volvo work |
| `data-eng` (BookAnything) | tenant Europe + Temporal + Kafka + NiFi + JSReport + central MinIO | for the BookAnything work |

**Hypotheses on dependencies (to verify, not assume):**
- `tenant-keycloak` is brokered through the central Keycloak, which depends on `central-postgres` and probably
  on Authentik for federation; if a tenant login path needs Authentik, `authentik-server` + LDAP outpost belong
  in the tenant profile.
- BookAnything backend needs Temporal, Kafka, NiFi, JSReport, tenant MinIO/Postgres, `maps-generator`, and
  Gemini over the internet; the Kafka/NiFi/Temporal/JSReport group is the heavy part of `corpshared-plat`.
- ArgoCD/Tekton/Backstage/Forgejo are only needed while deploying; stopping them does not affect running apps,
  but ArgoCD `selfHeal` would **fight** manual scale-downs of GitOps-managed tenant apps (the business apps are
  full GitOps). Scaling must therefore either pause auto-sync for the app or stop ArgoCD first. Tenant
  *infrastructure* (Postgres, Keycloak, MinIO, OpenBao, MySQL) is PaaS and not managed by ArgoCD (ADR-0016), so
  it is safe to scale directly. This is the main technical trap of the feature.
- Order matters: stop apps before databases, start databases before apps. Postgres has needed slow fsync
  recovery, so `start` must wait for readiness, not just apply replicas (reuse `post-boot-check`).
- The `darueira-operator`, `drr-tenant-svc` and `drr-env-orchestrator-svc` may reconcile replicas back up; check
  before relying on `kubectl scale`.
- Recovering state: record the previous replica counts in an annotation (`darueira.io/lean-prev-replicas`) on
  each scaled object so `make lean-restore` returns to exactly the prior state.

**Proposed targets:**
`make lean TENANT=<name> [WITH=dev-loop,obs,iam-lab]` (apply the profile), `make lean-status` (what is up/down,
memory freed), `make lean-restore` / `make full-up` (back to everything), `make lean-plan TENANT=<name>`
(dry run: prints what would be stopped, like `diff-tenant-infra`), `make tenant-stop TENANT=<name>` /
`make tenant-start TENANT=<name>` for single tenants.

**Estimated saving (to be measured, not promised):** from the current numbers, the `obs` tier plus `mgmt`
(Backstage, Argo, Tekton) plus the idle tenant plus Authentik/Clavex/Stalwart/NiFi are the candidates; NiFi alone
is 1.4 GiB, Nexus 2.0 GiB (but it holds the Maven proxy used by the Tekton builds). Real numbers come from
`kubectl top` before/after, recorded by `lean-status`.

### 6. Open questions added by the addendum

- Backup destination and retention: which disk, how many generations?
- Are the dynamic `microk8s-hostpath` PVCs (apisix-etcd, webmail, maven-repo-cache) in scope?
- Should Nexus (71 GB) be backed up at all, or treated as a rebuildable cache?
- Which tenant is the default working tenant, and should profiles be per tenant or per "task" (BookAnything,
  IAM lab, Volvo/Keycloak)?
- Does the Cilium state-cleanup logic (`setup_host_cilium_state_cleanup.sh`) interact with frequent
  scale-down/up cycles? Check IPAM behavior after repeated cycles.

### 7. Storage consolidation, tiers and portability (addendum 2, 24.10.2026)

**André's requirements (paraphrased):** (a) the laptop is heavy and needs a general disk cleanup/optimization;
(b) reorganize `/` (OS), `/home/*` and `/mnt/FileBuckets01`, making clear and easy what to copy to Google Drive
and/or external media; (c) the platform's data and configuration must be safe, fully separated from `/` and
`/home/*`, and the environment easily replicable on another computer; (d) inside
`/mnt/FileBuckets01/darueira-platform/data` there must be a clear split between what is **ephemeral** (not
backed up) and what is **required for uninterrupted continuity** (must be backed up); (e) the backup is generated
locally and then uploaded to external media or Google Drive. André also does not want dynamic PVs outside
that folder.

**Claude's proposal (open for debate):**

1. **Three tiers, not two.** "Ephemeral vs. required" hides a middle class that is the biggest cost:
   - `durable` (always in backup): central/tenant Postgres, MySQL, MongoDB, tenant MinIO, OpenBao (master and
     tenants), Forgejo git, Temporal, Stalwart, APISIX etcd, webmail, Kafka/RabbitMQ (if topics must survive),
     NiFi state, Grafana dashboards.
   - `rebuildable` (backup optional, flag `INCLUDE_REBUILDABLE=1`): Nexus (71 GB, except the manually uploaded
     `jackson-datatype-jts`), OpenSearch and Prometheus data, Maven cache.
   - `ephemeral` (never in backup): Tekton workspaces, build caches, temp.
   Classifying each of the ~51 volumes is a table to be agreed in the final decision; the table lives in one
   versioned file (e.g. `platform/storage/volumes.yaml`) read by both the PV generator and the backup script, so
   the classification cannot drift from what is backed up.
2. **Layout with the least churn.** Keep the existing `data/` as the **durable** tree (the 24 static PVs already
   point there, no PV rewrite) and add siblings under `darueira-platform/`:
   `data/` (durable, backed up), `rebuildable/`, `ephemeral/`, `backups/` (archives + `MANIFEST` + checksums),
   `config/` (exported host and cluster configuration), `kit/` (restore/replicate scripts).
   Alternative: nest tiers inside `data/` (`data/durable`, `data/ephemeral`); cleaner to read but requires
   recreating every static PV (the `hostPath` is effectively immutable) and downtime. Decision for the debate.
3. **Dynamic PVs in the same tree.** A new StorageClass (name e.g. `darueira-dynamic-durable` / `-ephemeral`),
   reclaim `Retain` for durable and `Delete` for ephemeral, pointing at the right subtree through the provisioner's
   directory parameter (**to verify** that the installed `microk8s.io/hostpath` honors `pvDir` per class; fallback:
   static PVs generated from `volumes.yaml`). Migration is per volume: scale to 0, copy, recreate the PVC, scale
   up. Tekton workspaces (the many 1 Gi `pvc-<hash>` claims, to be confirmed) go to the ephemeral class.
4. **Real separation from `/` and `/home`.** Today `/mnt/FileBuckets01` is a separate partition (`/dev/sda2`,
   585 GB, 80% used) but the MicroK8s data (`/var/snap/microk8s`), containerd images and `/var/log/pods` still
   live on `/`. For "totally separated" and replicable, also decide where the **containerd image store and
   MicroK8s state** live; moving them is invasive (needs sudo, a MicroK8s stop, `snap` data relocation) and
   should be a separate, careful step. Images are rebuildable from Nexus (its Docker registry also holds the Kaniko layer cache), so this is a size/performance
   question, not a data-loss one.
5. **Replicate on another computer.** The part not yet captured by the data folder: (i) repo `master` (git), (ii)
   `config/` snapshot: MicroK8s addons list and version, `/etc/hosts` entries, host scripts
   (`scripts/setup_host_*`), kernel/sysctl settings, tool versions; (iii) **secrets**: OpenBao unseal keys and
   root tokens, Keycloak/Authentik admin credentials, API keys (e.g. Gemini). They must not go in git or in an
   unencrypted archive. (iv) the durable tree. A `make replicate-kit` would produce a self-contained bundle and a
   `make restore-from-kit` on the new machine (install MicroK8s with the pinned version, create the directory
   tree, restore data, `bootstrap-*`, `validate-*`). Hardcoded paths (`/mnt/FileBuckets01/...`) must become one
   variable (`DRR_DATA_ROOT`) so the target machine can use another mount point.
6. **Backup pipeline: local first, then upload.** `make backup-pvc` writes
   `backups/<timestamp>/` (per-volume `tar.zst` or `rsync` snapshot with hard links for increments,
   `MANIFEST.json` with tier, size and SHA-256, logical dumps for the databases). `make backup-upload
   [TARGET=gdrive|usb]` ships it afterwards: `rclone` for Google Drive (supports the `crypt` remote) or
   `rsync` to a mounted external disk. **Encrypt before leaving the machine** (`age` or `gpg`), because the
   archives contain OpenBao data and credentials; Google Drive should only ever see ciphertext. Google Drive has
   upload quotas and throttling, so the 75 GB full set (with Nexus) is a poor fit; the durable set (a few GB:
   Postgres 443 MB, Kafka 1.3 GB, the rest MB) is a good fit.
7. **Host cleanup, safely.** The `/home` breakdown (924 GB) shows: `DevEnvALNS` 317 GB, `Backups` 265 GB,
   `.docker` 95 GB, `VirtualMachines` 53 GB, `.local` 53 GB, `.cache` 40 GB, `Downloads` 20 GB, `.thunderbird`
   14 GB, `.android` 14 GB, `.npm` 12 GB, `.gradle` 7.7 GB. Principles: **inventory before deletion**; a report
   (`make disk-report`) groups candidates as "regenerable cache" (`.cache`, `.npm`, `.gradle`, build output such
   as `target/`, `node_modules/`), "container leftovers" (`.docker`), "duplicates/old downloads", and "needs a
   human decision" (`Backups`, `VirtualMachines`, `DevEnvALNS` project folders). The agent proposes, André
   confirms each group; nothing under `Backups`, `Documents` or personal data is deleted without an explicit
   per-item OK. Move-instead-of-delete (to a `_to_delete_YYYYMMDD` staging dir) for the first pass.
8. **"What goes to Drive / external media" made explicit.** One manifest (`~/.config/drive-sync.yaml` or a
   repo file) listing sync sets: `platform-durable-backup` (encrypted), `projects-source` (git-tracked is
   already on GitHub/Forgejo: exclude `target/`, `node_modules/`, `.git` objects if remote is current),
   `documents`, `books-and-research`. A `make sync-plan` prints sizes per set before `make sync-run`.

**Risks and open questions:**
- Which volumes are `durable`, `rebuildable`, `ephemeral`? (first draft above; to be agreed)
- Layout: keep `data/` as durable (less churn) or nest tiers (cleaner)?
- Is moving the containerd/MicroK8s state off `/` in scope now, or later?
- Backup retention and destination: external disk model/mount point, Google Drive account and free quota.
- Encryption: `age` key management (where is the private key stored, and how is it kept off the same disk?).
- `/mnt/FileBuckets01` has 114 GB free; consolidating Nexus (71 GB) and the Maven cache there
  makes it tight. Cleaning Nexus or a larger disk may be a precondition.
- A power loss or crash corrupted Postgres recoveries before (restart counts of 29-38); durable data on the same
  disk as the cluster still needs the off-machine copy to count as a backup.

### 7b. Decisions André already made (24.10.2026)

- `data/` stays as the **durable** tree (no PV rewrite); `rebuildable/`, `ephemeral/`, `backups/`, `config/`, `kit/`
  are added as siblings.
- Moving MicroK8s state and the containerd image store off `/` comes **later**, after backups work.
- Dynamic PVs should end up under the same data root (André does not want volumes outside it).
- Correction: the 20 Gi `registry-claim` is a Released orphan of the old `registry` addon, not a live registry.
- Still open: backup destination disk, Google Drive quota, `age` private key location, which volumes are durable /
  rebuildable / ephemeral, approval to compact/clean Nexus (needs admin credentials; the reads so far were anonymous).
- State at end of day: no cluster mutations were made by Claude; André stops the cluster for the night.
  The Antigravity sections, Debate, Final Decisions and Action Plan are still `pending`.

### 8. What is inside Nexus `nexus-data` (measured read-only on 2026-10-24)

- Blob store `default`: 75.6 GB on disk, 10,395 blobs (`du` says 71 GB). 277 blobs above 100 MB hold 63 GB (Docker layers).
- **Soft-deleted but not reclaimed: 4,490 blobs = 37.5 GB** (`deleted=true` in the blob `.properties`). Nexus frees
  this only with the "Compact blob store" task, which looks like it was never scheduled. This is about half of the
  disk and is recoverable without losing anything live.
- **Active content**: `docker-hosted` 1,957 blobs = 37.5 GB (images plus Kaniko `/cache` layers: 34 repositories,
  e.g. `bookanything-monolith-backend-01` 18 image tags and 49 cache tags); `maven-central` proxy 3,931 files =
  0.49 GB; `maven-releases` 2 files (including the manually uploaded `jackson-datatype-jts`); everything else empty
  (`maven-snapshots`, `npm-hosted`, `helm-hosted`, `pypi-hosted`, `nuget-*`).
- Layout: `directpath/nexus-repository-docker/...` 36 GB and `vol-*` 36 GB; the same layer sizes appear in both.
  Whether `directpath` is a duplicate/leftover of uploads is **unconfirmed**.
- Proposed (needs André's approval, mutating): schedule "Compact blob store" and a Docker cleanup policy
  (delete old `/cache` and old image tags, keep the last N), then re-measure. Expected result: roughly halve the
  volume before any backup or move. Back up `maven-releases` (the JTS jar) first or re-upload it from source.

### 9. Progress report, 2026-10-27 (what was done and verified)

**Backup and restore tooling (already merged before this session, commits of 25-26/10):** `backup-pvc`,
`backup-list`, `backup-verify`, `backup-prune`, `restore-pvc` (with `--only` and `--dry-run`), and the weekly
systemd user timer (`backup-schedule`, Sunday 03:00). The APISIX etcd claim and the CI/stateful claims now sit on
static PVs under the data tree. The timer has not fired yet; the first run is 2026-11-01 03:00.

**Nexus (done, mutating, approved by André):**

| Item | Result |
|---|---|
| Blob store compaction | had already run on 2026-10-25 (10m37s): `nexus-data` went from 71 GB to 36 GB on disk (38.1 GB, 5,905 live blobs). Section 8 proposal 1 is therefore done |
| Cleanup policy | `drr-docker-kaniko-cache-30d` created (format docker, last downloaded > 30 days, asset regex `.*/cache/.*\|.*-cache/.*`), attached to `docker-hosted`. It covers about 170 of the 246 components (Kaniko layer cache only) |
| Image tags | deliberately **not** covered: running pods may still reference old dated tags, and deleting one breaks the next restart. A tag policy (keep `latest` and the tag in use) is a separate decision |
| Compaction schedule | the task was manual (`nextRun: null`); it is now `0 0 5 ? * SUN` (UTC), first run 2026-11-01. The "Cleanup service" task already ran daily at 01:00 |
| Manual artifact | `jackson-datatype-jts` 2.17.2 (jar + pom) saved to `~/Backups/darueira-platform/nexus-manual-artifacts/` with the Maven layout; SHA-1 matches Nexus (jar `f295b188...`, pom `cc44143a...`), jar passes `unzip -t` |

Notes: Nexus 3.68 has no public REST API for cleanup policies or for creating tasks. The policy was created through
the internal endpoint `/service/rest/internal/cleanup-policies`, and the task schedule through the UI's ExtDirect
(`coreui_Task` / `update`, which also needs `timeZoneOffset`). None of this is versioned in the repo yet. The admin
credential used is the lab default from `scripts/bootstrap_nexus_iam.py`.

**New backup (done):** `~/Backups/darueira-platform/20261027-154218`, 571 MB, `backup-verify` exit 0 (SHA-256 and
`tar -t`). Unlike `20261025-222049` it contains `apisix-etcd`. Empty archives (`temporal`, `stalwart-mail`,
`maven-repo-cache`, about 115 bytes) are genuine: the source directories are 4 KB; Temporal and Stalwart keep their
state in PostgreSQL. `webmail` is still not in the set (dynamic `microk8s-hostpath` claim).

**Incident 1: `stalwart-mail` in Error after the backup.**
- Cause: the manifest used `stalwartlabs/stalwart:latest`. On 2026-10-26 that tag moved to v1.0.0 (digest
  `baafeacd...`). `latest` is always pulled, so the scale 0 -> 1 done by the backup brought v1.0.0, which fails
  against the v0.16 schema in `drr_stalwart_mailserver_db`: `Failed to write node id to store: cannot convert
  between &[u8] and int8`. The database was not changed (v1.0.0 aborted at startup).
- Fix: both images pinned to `v0.16.27` (last v0.16, 2026-10-18), applied with `kubectl set image`, rollout OK, pod
  `1/1 Running` with a healthy log. Merged as a separate commit.
- Not done: `make validate-stalwart-iam` was not run (login and IMAP/SMTP not functionally checked), and ADR-0006
  still says `stalwart:latest`.
- Wider risk: any other `:latest` image has the same failure mode on the next restart.

**Incident 2: `food-market-01-service` restart count (133 in 42 days).**
- Not a crash loop: the "42d" is the pod age. The pod was killed (exit 143, SIGTERM) by the kubelet. Liveness and
  readiness both used `/actuator/health`, which includes the PostgreSQL and RabbitMQ indicators. When a dependency
  was down (the backup scaled RabbitMQ and PostgreSQL to 0) three failed checks (1 s timeout, 10 s period)
  restarted the pod. Nightly cluster stops and crashes cause the same thing.
- Scope: only this service. `food-market-02` is Quarkus (`/q/health/live`), 03-06 use `/healthz`. `caseforce-legalhub-mgmt`
  (266 restarts, last `Error/1`) is a different case and was not investigated.
- Fix (merged): liveness `/actuator/health/liveness`, readiness `/actuator/health/readiness` (group still includes
  `db` and `rabbit`), `startupProbe` instead of initial delays, `timeoutSeconds: 3`. The image is native, so the
  new probe paths only exist after a Tekton rebuild; the Deployment and the image must ship together.
  **Verify after the rebuild:** the pod becomes Ready and survives a RabbitMQ scale-to-zero without a restart.

**Lessons for the next items (lean mode, post-boot-check):**
- A scale-down order that stops dependencies first will restart apps whose liveness depends on them. Either fix the
  probes (as above) or scale apps down before databases, and databases up before apps.
- `backup_pvc.sh` should preferably pin or at least report image digests before scaling to 0, because a restart
  silently re-pulls every `:latest` image.
- When killing a background `kubectl port-forward`, use the PID (`$!`); `pkill -f` matches the invoking shell.

**State at end of session:**

| Item | Status |
|---|---|
| Nexus compaction, cleanup policy, schedule | done (first scheduled compaction 2026-11-01) |
| JTS jar copy | done, local disk only |
| Backup `20261027-154218` | done and verified, local disk only |
| Stalwart pin | done and merged |
| food-market-01 probes | merged, **waiting for the Tekton rebuild and deploy** |
| Restore test | not done (`restore-pvc --dry-run`, then one small volume) |
| Off-disk copy (`backup-upload`, `age`) | not done |
| `disk-report`, `cluster-health`, `post-boot-check`, `tools-check`, lean mode | not done |
| `volumes.yaml` classification, dynamic PVs into the data tree, `DRR_DATA_ROOT` | not done |
| Cilium cleanup validated in a real stop/start | not done |

---

## Analysis and Evaluation by Antigravity:

_(to be filled by Antigravity: second view on the items above, additional items, risks, priorities)_

---

# Discussion/Debate:

## Highlighted points from Antigravity's analysis:

_(pending)_

## Highlighted points from Claude's analysis:

_(pending)_

## Counterpoints and clarifications from Antigravity:

_(pending)_

## Counterpoints and clarifications from Claude:

_(pending)_

---

# Final Decisions After Both Agreement and Disagreement:

_(pending)_

# Action Plan for Environment Tuning:

_(pending: phases, owner per item, single-writer rule for cluster mutations, handoff in
`docs/roadmap/backlog-melhorias.md`)_
