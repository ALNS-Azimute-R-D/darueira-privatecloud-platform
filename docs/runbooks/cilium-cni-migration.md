# Runbook: Migração de CNI — Calico → Cilium

**Status:** Fases 0, 1 e 2 executadas e validadas em 2026-09-22. Enforcement das 4 políticas de controle (`obs`/`mgmt`/`plat`/`secr-internal`) já está **live** (aconteceu sem querer na Fase 1, debugado e corrigido na Fase 2 — ver achado crítico abaixo). `policy-audit-mode` está `Disabled` globalmente desde a Fase 1 (nunca chegou a ser ligado formalmente) — ou seja, todo rollout de tenant na Fase 3 já está indo direto pra enforcement real, não pra um modo audit de verdade; tratar cada apply de tenant como enforcement ao vivo. Fase 3 em andamento: 1 de 9 namespaces de tenant migrado (`drr-tnt-swfabrik-latam-dev`, validado). Falta o restante dos tenants (Fase 3) e o enforcement formal (Fase 4, que na prática já vale pras 4 namespaces de controle e para o tenant já migrado).
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
# UI via helm upgrade (não precisa de sudo, é só chamada à API do cluster):
microk8s helm3 upgrade cilium cilium/cilium --version v1.15.2 --namespace kube-system \
  --reuse-values --set hubble.ui.enabled=true

# hubble CLI já vem embutido no pod do agente, não depende do plugin do addon
# (que fica com permissão só pra root):
CIL_POD=$(microk8s kubectl get pods -n kube-system -l k8s-app=cilium -o jsonpath='{.items[0].metadata.name}')
microk8s kubectl exec -n kube-system "$CIL_POD" -- hubble observe --last 40
```

### 🔴 Achado crítico (2026-09-22): políticas antigas já estavam em enforcement

**As 4 `CiliumNetworkPolicy` de `corpshared-{mgmt,obs,plat,secr-internal}` já existiam no cluster há 35 dias** (aplicadas via GitOps/kustomize muito antes desta migração), mas ficaram **dormentes** o tempo todo porque Calico não entende esse CRD. **No instante em que o Cilium ficou ativo na Fase 1, essas 4 políticas entraram em enforcement real — sem passar por nenhum modo audit.** A Fase 3 planejada (rollout controlado) foi pulada sem querer pra essas 4 namespaces; só a política de tenant (`tnt-tenant-base/network-policy-template.yaml`) continua genuinamente não aplicada.

**Ação obrigatória antes da Fase 1 em qualquer repetição futura**: rodar `kubectl get ciliumnetworkpolicies -A` **antes** do cutover. Se já existir alguma, ela vai "ligar" sozinha assim que o agente subir — trate isso como parte da Fase 1, não da Fase 3.

**Bug real encontrado e corrigido**: a política do `corpshared-obs` tinha egress **só** com uma regra específica pro CoreDNS (`toEndpoints` com `matchLabels` exatos de namespace+k8s-app) — e essa regra, apesar de labels batendo certinho, **não casava** (confirmado via `hubble observe --verdict DROPPED`: `policy-verdict:none EGRESS DENIED`, destino classificado como `world` mesmo sendo um IP de pod do cluster). As outras 3 políticas "funcionavam" só porque tinham, de brinde, uma regra ampla `toEntities: [cluster, world]` que cobre DNS como efeito colateral.

Isolei a causa com um teste mínimo (`endpointSelector: {}` + só `egress: toEntities: cluster`, pod novo, nunca tocado pelo Calico): **`toEntities: [cluster]` sozinho não é suficiente** pra alcançar o ClusterIP do CoreDNS — precisa de `[cluster, world]` juntos. Motivo provável: este cluster roda com `KubeProxyReplacement: False` (kube-proxy faz o DNAT do ClusterIP via iptables, não o Cilium nativamente), e o Cilium não reconhece o IP pré-NAT como identidade `cluster` sozinha nesse cenário.

**Fix aplicado**: `platform/kustomize/base/corpshared-obs/network-policy.yaml` ganhou uma 3ª regra de egress `toEntities: [cluster, world]`, igual ao padrão já usado (sem essa dor) nas outras 3 políticas. Restaurou DNS pro `prometheus`, `fluent-bit` e, como bônus, **tirou o `opensearch-dashboards` de um `CrashLoopBackOff` que já durava 35 dias** (não era a causa histórica — Calico não aplicava nada — mas piorava/travava os restarts de hoje).

Checklist:
- [x] Hubble relay + UI rodando
- [x] Fluxos observados e política pré-existente auditada em produção real (via debug ao vivo, não modo audit formal)
- [x] Bug de DNS no `corpshared-obs` encontrado e corrigido

---

## Fase 3 — Rollout das políticas em modo audit

**Status (2026-09-22): as 4 políticas de controle (`obs`, `mgmt`, `plat`, `secr-internal`) já estão live e validadas** (ver achado na Fase 2 — entraram em enforcement direto na Fase 1, sem audit mode formal, e foram debugadas/corrigidas ao vivo). O que falta desta fase é só a política de tenant (`tnt-tenant-base/network-policy-template.yaml`), que nunca foi aplicada em nenhum namespace `drr-tnt-*` e continua genuinamente pendente — essa sim deve seguir o processo formal de audit mode abaixo, já que é território não testado.

O modo audit do Cilium é global ao agente (não é por-namespace), mas como cada `CiliumNetworkPolicy` só passa a ser avaliada nos endpoints que ela seleciona, dá pra fazer rollout incremental por namespace **mesmo com audit ligado globalmente**: sem política, o namespace continua em "allow all"; com política + audit, ele começa a logar o que *seria* bloqueado, sem bloquear de fato.

```bash
# Ligar audit mode globalmente (verificar sintaxe exata pra versão instalada do addon)
cilium config set policy-audit-mode Enabled
# ou, via Helm values do addon: policyAuditMode: true
```

Ordem de rollout restante:

1. ~~`corpshared-obs`~~ — feito (Fase 2)
2. ~~`corpshared-mgmt`~~ — já estava live, sem drop encontrado
3. ~~`corpshared-secr-internal`~~ — já estava live, sem drop encontrado
4. ~~`corpshared-plat`~~ — já estava live, sem drop encontrado
5. **Namespaces de tenant (`drr-tnt-<tenant>-<env>`)** — pendente, um de cada vez, começando pelo menos usado. **Atenção**: a política de tenant tem a mesma estrutura de egress "só endpoints específicos" que causou o bug do `corpshared-obs` (sem `toEntities: [cluster, world]` de fallback) — bem provável que precise do mesmo fix antes de aplicar. Testar em audit mode primeiro, não assumir que vai funcionar.

Pra cada namespace de tenant:

```bash
microk8s kubectl apply -f platform/kustomize/base/tnt-tenant-base/network-policy-template.yaml

# Observar no Hubble (CLI ou UI) por "would-drop" / policy-verdict
CIL_POD=$(microk8s kubectl get pods -n kube-system -l k8s-app=cilium -o jsonpath='{.items[0].metadata.name}')
microk8s kubectl exec -n kube-system "$CIL_POD" -- hubble observe --namespace <namespace> --verdict DROPPED
```

Ajustar a política se algo aparecer bloqueado indevidamente (porta faltando, label errado, entidade faltando) e reaplicar. Testar DNS explicitamente com um pod novo (`nslookup kubernetes.default.svc.cluster.local`) antes de considerar o namespace validado — não confiar só na ausência de drops na amostra do Hubble, como o caso do `obs` provou.

### `drr-tnt-swfabrik-latam-dev` (2026-09-22)

Primeiro namespace de tenant migrado. Confirmou a suspeita da linha acima: a política de tenant sofria do mesmo bug do `corpshared-obs` (DNS só com `toEndpoints` específico, sem fallback). Aplicado o mesmo fix (`toEntities: [cluster, world]`) em `tnt-tenant-base/network-policy-template.yaml` antes de aplicar no cluster.

- Nota: `policy-audit-mode` já estava `Disabled` globalmente (enforcement real, não audit) — mesma situação "sem querer" descrita no achado crítico da Fase 2. Não há modo audit formal rodando neste cluster desde a Fase 1; todo rollout de tenant está, na prática, indo direto pra enforcement.
- `hubble observe --namespace drr-tnt-swfabrik-latam-dev --verdict DROPPED` (amostra de ~2h pós-apply): nenhum drop.
- Pod de teste novo (`dns-test-latam`, `busybox:1.36`, `securityContext` compatível com PodSecurity `restricted`) resolveu `kubernetes.default.svc.cluster.local` com sucesso.
- Hubble confirmou o fluxo: `dns-test-latam -> kube-system/coredns-...:53 policy-verdict:L3-L4 EGRESS ALLOWED (UDP)`, `FORWARDED` nos dois sentidos.
- `tenant-keycloak` nesse namespace tem histórico crônico de restarts (139 em 19 dias, não relacionado — ver padrão similar ao Postgres central na Fase 1); o restart mais próximo da aplicação da política (16:06-16:09) já estava ~45min depois do apply (15:21) e o boot seguinte completou normalmente (DB conectado, Keycloak `started`), então não foi causado pela política.

Checklist por namespace:
- [x] `corpshared-obs`
- [x] `corpshared-mgmt`
- [x] `corpshared-secr-internal`
- [x] `corpshared-plat`
- [x] `drr-tnt-swfabrik-latam-dev`
- [ ] `drr-tnt-swfabrik-europe-dev`
- [ ] `drr-tnt-swfabrik-europe-marketplaces-dev`
- [ ] `drr-tnt-acme-storefront-dev`
- [ ] `drr-tnt-acme-storefront-staging`
- [ ] `drr-tnt-acme-storefront-prod`
- [ ] `drr-tnt-globex-logistics-dev`
- [ ] `drr-tnt-globex-logistics-prod`
- [ ] `drr-tnt-darueira-corp-platform-core-prod`
- [ ] `drr-tnt-base-template` (template namespace — confirmar se recebe workload real ou pode ser pulado)

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
