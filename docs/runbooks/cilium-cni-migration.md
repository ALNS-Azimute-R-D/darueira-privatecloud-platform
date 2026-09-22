# Runbook: Migração de CNI — Calico → Cilium

**Status:** Fase 0 e Fase 1 executadas e validadas em 2026-09-22. Fases 2–4 (Hubble contínuo, rollout de política em audit, enforcement) ainda pendentes.
**Objetivo:** Fechar a Deviation #1 do `specs/01-initial-spec.md` (§11) — isolamento de rede declarado (5 `CiliumNetworkPolicy` já versionadas) mas não aplicado, porque o cluster roda Calico e não há agente Cilium ativo.
**Escopo:** Cluster single-node MicroK8s (`darueira-privatecloud-platform`), uso de estudo pessoal, sem outros consumidores.

---

## 0. Premissas e por que este roteiro existe

- **Storage é independente do CNI.** Todo o storage do cluster usa `hostpath-storage` (`microk8s.io/hostpath` e `kubernetes.io/no-provisioner`, `ReclaimPolicy: Retain`) — dados vivem em disco local, montados diretamente. Trocar o CNI **não toca em PV/PVC nem em arquivos em disco**. O risco de perda de dado nesta migração é essencialmente zero.
- **O risco real é de conectividade**, não de dado: pods podem precisar reiniciar pra pegar IP do novo CNI, e um `default-deny` ligado cedo demais pode cortar uma integração legítima.
- **Nenhuma das 5 políticas já escritas usa L7 (`rules: http`) ou FQDN (`toFQDNs`)** — confirmado por leitura de:
  - `platform/kustomize/base/corpshared-plat/network-policy.yaml`
  - `platform/kustomize/base/corpshared-mgmt/network-policy.yaml`
  - `platform/kustomize/base/corpshared-obs/network-policy.yaml`
  - `platform/kustomize/base/corpshared-secr-internal/network-policy.yaml`
  - `platform/kustomize/base/tnt-tenant-base/network-policy-template.yaml`
- Elas usam `fromEndpoints`/`toEndpoints` com `matchLabels` (`darueira.io/tier`, `darueira.io/subsystem`) que **cruzam namespace** (modelo de identidade "flat" do Cilium) e entidades especiais (`fromEntities`/`toEntities`: `host`, `cluster`, `kube-apiserver`, `world`) que só existem no Cilium.
- Os labels usados nessas políticas **já existem** tanto em pods quanto nos `namespace.yaml` (`darueira.io/tier: enterprise-shared` em `corpshared-{plat,mgmt,obs,secr-internal}`, `darueira.io/tier: tenant-workload` no template de tenant) — não é preciso reetiquetar nada antes de aplicar.
- A regra `fromEntities: host` no `tnt-tenant-base` (pensada pro agente SPIRE) é hoje **letra morta**: SPIRE ainda é só `spire-server-placeholder`, sem agente. Não afeta esta migração, mas fica registrado pra quando SPIRE for implementado de verdade.

**Itens conscientemente adiados** (não fazem parte deste roteiro):
- WireGuard (transparent encryption) — sem benefício em nó único.
- kube-proxy replacement — tratar como passo de aprendizado separado, depois da migração de política estar estável.

---

## Fase 0 — Backup e registro do estado atual

Não é estritamente necessário pro storage (ver premissa acima), mas é boa prática e reduz ansiedade.

```bash
# Dumps lógicos dos bancos críticos (ajustar credenciais/pods reais)
microk8s kubectl exec -n drr-corpshared-plat <pod-central-postgres> -- \
  pg_dumpall -U postgres > ~/backups/darueira-central-postgres-$(date +%F).sql

microk8s kubectl exec -n drr-tnt-<tenant> <pod-tenant-mongo> -- \
  mongodump --archive > ~/backups/darueira-<tenant>-mongo-$(date +%F).archive

# Estado atual do cluster, pra comparar "antes/depois"
microk8s kubectl get pods -A -o wide > ~/backups/pods-before-$(date +%F).txt
microk8s status > ~/backups/microk8s-status-before-$(date +%F).txt
microk8s kubectl get applications -n argocd -o wide > ~/backups/argocd-apps-before-$(date +%F).txt 2>/dev/null
```

Checklist:
- [x] Dump Postgres central (76MB, sem erro)
- [x] Dump(s) Mongo por tenant relevante — **cuidado**: `MONGO_INITDB_ROOT_*` só se aplica na primeira inicialização do volume; se o secret for rotacionado depois, `mongodump` autenticado com o secret atual pode falhar mesmo o pod usando `secretKeyRef` corretamente. Aconteceu com um dos dois tenants nesta execução; não bloqueou a migração (dado físico é o que importa, ver premissas), mas fica registrado.
- [x] Dump Postgres **por tenant**, não só o central — achado nesta execução: tem `tenant-postgres` rodando em pelo menos 2 namespaces de tenant além do banco central; varra `kubectl get pods -A | grep -i postgres` antes de dar a Fase 0 por concluída, não confie só no óbvio.
- [x] `pods-before.txt`, `microk8s-status-before.txt` salvos
- [x] Estado ArgoCD (Synced/Healthy) registrado como baseline

---

## Fase 1 — Cutover do CNI

> ⚠️ **`microk8s disable calico` não existe neste cluster.** No MicroK8s, o Calico dessa instalação não é um addon separado — é o CNI padrão embutido, ligado no init do cluster. Não há o que desabilitar por nome; o próprio addon `cilium` cuida de remover o `cni.yaml` do Calico como parte do `microk8s enable cilium` (só quando `$SNAP_DATA/var/lock/ha-cluster` e `$SNAP_DATA/args/cni-network/cni.yaml` existem — confirme os dois antes de rodar, senão o Cilium sobe **junto** com o Calico ainda ativo).

```bash
microk8s status | grep -iE "cilium|calico"   # confirmar estado atual

# Pré-checagem obrigatória (evita rodar com os dois CNIs ativos ao mesmo tempo):
ls /var/snap/microk8s/current/var/lock/ha-cluster
ls /var/snap/microk8s/current/args/cni-network/cni.yaml

microk8s enable cilium
```

`microk8s enable cilium` chama `sudo` internamente (pra mexer nas flags do `kube-apiserver`). **Isso precisa rodar num terminal interativo de verdade** — nem o Bash do Claude Code nem o `!` do chat têm TTY suficiente pro `sudo` pedir senha; ambos falham com `sudo: a terminal is required`. Rode num terminal separado.

Esperado: reinício em cascata de boa parte dos pods (IP de pod muda com o CNI). **Na prática (execução real), isso não aconteceu** — o Cilium conseguiu "adotar" os veths já existentes do Calico (endpoint restore), então a maioria dos pods manteve o mesmo `AGE`/`RESTARTS` sem reiniciar. Confirme via `CiliumEndpoints`:

```bash
microk8s kubectl get pods -A -o wide -w   # observar até tudo voltar a Running
cilium status --wait                       # se o Cilium CLI estiver instalado
microk8s kubectl get ciliumendpoints -A --no-headers | wc -l   # deve bater com a contagem de pods reais (exclui cilium/cilium-operator)
```

**Neste ponto, sem nenhuma `CiliumNetworkPolicy` aplicada, o comportamento default é "permite tudo"** — equivalente ao que já temos hoje efetivamente com o Calico. Prioridade aqui é só restaurar conectividade total, não aplicar isolamento ainda.

### Gotchas confirmados na execução real (2026-09-22)

1. **Interface `vxlan.calico` órfã.** O addon do Cilium remove o manifesto K8s do Calico, mas não remove a interface de rede `vxlan.calico` que fica no host. Ela aparecia na lista de dispositivos de "Direct Routing" do Cilium e quebrava rotas específicas pod→host (ex.: Hubble Relay não conseguia falar com o agente). Fix:
   ```bash
   sudo ip link delete vxlan.calico
   microk8s kubectl delete pod -n kube-system -l k8s-app=cilium   # força o agente redetectar os devices
   ```
2. **UFW bloqueia portas novas do Hubble.** Este host usa UFW com allowlist explícita por porta (padrão: cada porta do MicroK8s tem sua própria regra `<porta>/tcp ALLOW IN Anywhere`). O addon do Cilium **não** adiciona regras de UFW pras portas que introduz. Sem isso, tráfego pod→host pra essas portas cai no deny padrão (sintoma: `nc -zv` trava em "Connection timed out", não "refused" — indica firewall, não porta fechada). Fix:
   ```bash
   sudo ufw allow 4244/tcp comment 'Cilium Hubble peer service'
   sudo ufw allow 4245/tcp comment 'Cilium Hubble relay gRPC API'
   ```
   Regras antigas com `on vxlan.calico`/`on cali+` (interface-based) ficam órfãs/inertes depois da migração — não atrapalham, mas não servem mais pra nada.
3. **Cascata do Postgres central não é causada pelo Cilium, mas pode coincidir no tempo.** Durante a migração, o `central-postgres-0` reiniciou (padrão crônico pré-existente: dezenas de restarts ao longo de semanas, provavelmente por I/O lento em disco a 80%+ de uso) e ficou ~20 min preso num `fsync` do diretório de dados no boot. Isso derrubou em cascata tudo que depende dele (Keycloak, Forgejo, Backstage, jsreport, Temporal UI, Clavex, Stalwart) e, por tabela, o ArgoCD (`Unknown` sync status por não alcançar o Forgejo interno). **Não force restart do Postgres nesse estado** — pode corromper o `fsync` em andamento. Deixe terminar sozinho; os dependentes se recuperam automaticamente quando ele volta (exceto pods presos em `CrashLoopBackOff` com backoff longo, que se beneficiam de um restart manual pra pular a espera).

Checklist:
- [x] Todos os pods voltaram a `Running`/`Ready` (exceto 2 pods com problema crônico pré-existente, não relacionado à migração)
- [x] `cilium status` saudável (`Controller Status: 521/521 healthy`)
- [x] Smoke test manual: ArgoCD com todas as 25 apps `Synced`/`Healthy`, Forgejo respondendo `200 OK`

---

## Fase 2 — Observabilidade com Hubble

```bash
cilium hubble enable --ui
cilium hubble ui   # abre port-forward local pra UI
```

Deixar rodando um tempo e observar os fluxos reais entre namespaces antes de aplicar qualquer política — isso valida (ou contradiz) as suposições que já estão escritas nos 5 arquivos de `network-policy.yaml`.

Checklist:
- [ ] Hubble relay + UI rodando
- [ ] Fluxos entre `corpshared-plat` ↔ tenants ↔ `corpshared-obs` observados por pelo menos algumas horas de uso normal

---

## Fase 3 — Rollout das políticas em modo audit

O modo audit do Cilium é global ao agente (não é por-namespace), mas como cada `CiliumNetworkPolicy` só passa a ser avaliada nos endpoints que ela seleciona, dá pra fazer rollout incremental por namespace **mesmo com audit ligado globalmente**: sem política, o namespace continua em "allow all"; com política + audit, ele começa a logar o que *seria* bloqueado, sem bloquear de fato.

```bash
# Ligar audit mode globalmente (verificar sintaxe exata pra versão instalada do addon)
cilium config set policy-audit-mode Enabled
# ou, via Helm values do addon: policyAuditMode: true
```

Ordem de rollout sugerida (do menos crítico pro mais crítico):

1. `corpshared-obs` (observabilidade — menor impacto se algo falhar)
2. `corpshared-mgmt` (Backstage, ArgoCD, Tekton)
3. `corpshared-secr-internal` (OpenBao — atenção redobrada, é o cofre de segredos)
4. `corpshared-plat` (maior superfície: Postgres, MinIO, Redpanda, RabbitMQ, Temporal, NiFi, jsreport, Clavex, Roundcube)
5. Namespaces de tenant (`drr-tnt-<tenant>-<env>`), um de cada vez, começando pelo menos usado

Pra cada namespace:

```bash
microk8s kubectl apply -f platform/kustomize/base/<namespace>/network-policy.yaml

# Observar no Hubble (CLI ou UI) por "would-drop" / policy-verdict
hubble observe --namespace <namespace> --verdict AUDIT
```

Ajustar a política se algo aparecer bloqueado indevidamente (porta faltando, label errado, entidade faltando) e reaplicar.

Checklist por namespace:
- [ ] `corpshared-obs`
- [ ] `corpshared-mgmt`
- [ ] `corpshared-secr-internal`
- [ ] `corpshared-plat`
- [ ] Tenants (listar conforme forem migrados)

---

## Fase 4 — Enforcement

Depois que **todos** os namespaces tiverem passado pela Fase 3 sem "would-drop" inesperado:

```bash
cilium config set policy-audit-mode Disabled
```

Isso ativa o enforcement real (`default-deny` + regras) em todos os namespaces com política de uma vez.

Checklist:
- [ ] Todos os namespaces revisados sem drops inesperados em audit
- [ ] Audit mode desligado
- [ ] Smoke test completo pós-enforcement (repetir os mesmos testes manuais da Fase 1)
- [ ] Hubble continua mostrando fluxos normais como `FORWARDED`, não `DROPPED`

---

## Plano de rollback

Se algo quebrar de forma não contornável em qualquer fase:

```bash
# Reverter enforcement sem remover Cilium
cilium config set policy-audit-mode Enabled   # volta a só logar, para de bloquear

# Ou remover uma política específica que está causando problema
microk8s kubectl delete -f platform/kustomize/base/<namespace>/network-policy.yaml

# Rollback completo de CNI (último recurso)
# Não existe "microk8s enable calico" como addon — Calico é o CNI padrão de fábrica.
# Reverter de verdade exigiria reinstalar o cluster ou restaurar o cni.yaml.disabled
# manualmente (movido para args/cni-network/cni.yaml.disabled pelo próprio addon do
# Cilium durante o cutover) e reaplicar. Não testado nesta execução — se precisar,
# tratar como reconstrução de cluster, não como um "disable/enable" simétrico.
microk8s disable cilium
```

Como o storage é independente do CNI, o rollback de CNI não arrisca dado — só reconectividade, mesma lógica do cutover inicial.

---

## Pós-migração: atualizar documentação

- [ ] `specs/01-initial-spec.md` §11 — marcar Deviation #1 (network isolation) como resolvida, com data.
- [ ] Revisar ADR-0004 se o comportamento final divergir do que está descrito.
- [ ] Registrar neste runbook a data real de execução e qualquer ajuste feito nas políticas durante o audit mode, pra virar histórico.
