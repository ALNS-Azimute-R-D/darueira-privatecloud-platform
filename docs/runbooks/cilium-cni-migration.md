# Runbook: Migração de CNI — Calico → Cilium

> **Migração concluída em 2026-09-23.** Fases 0-4 todas executadas e validadas, incluindo os achados críticos #3 e #4 pós-Fase 4 (portas administrativas e portas de apps de negócio faltando na regra do `apisix-gateway`). Nada pendente neste runbook — próximos passos de rede (WireGuard, kube-proxy replacement, L7/FQDN policies) são itens conscientemente adiados (ver seção 0), não deviations.

**Status:** **Migração completa.** Fases 0, 1 e 2 executadas e validadas em 2026-09-22; Fases 3 e 4 em 2026-09-23. Enforcement real (`policy-audit-mode Disabled`) está ativo em todos os 6 namespaces com `CiliumNetworkPolicy`: os 4 de controle (`obs`/`mgmt`/`plat`/`secr-internal`) e os 2 tenants reais (`drr-tnt-swfabrik-latam-dev`, `drr-tnt-swfabrik-europe-dev`). Seis bugs reais de política e um incidente de IPAM foram encontrados e corrigidos no processo — **achado crítico #1** (Fase 2: fallback `toEntities: [cluster, world]` faltando para DNS), **achado crítico #2** (Fase 3: bug de escopo de namespace que quebrava todo `matchLabels` cross-namespace nas 5 políticas) e **achado crítico #3** (pós-Fase 4: portas de interface administrativa — OpenSearch Dashboards, consoles de tenant — nunca tinham sido incluídas nas políticas) e **achado crítico #4** (pós-Fase 4: portas de container dos apps de negócio dos tenants, para onde o APISIX roteia direto, também faltavam) e **achado crítico #5** (NiFi da plataforma chamando o backend do tenant direto) e **achado crítico #6** (tenant sem saída para a internet, resolvido com opt-in por label) — ver seções próprias abaixo. Também foram encontrados e limpos, em duas ondas, 8 namespaces `drr-tnt-*` que não deveriam existir no cluster (6 recriados por um `ApplicationSet` do ArgoCD, 1 sem fonte identificada, e 1 — `swfabrik-europe-marketplaces-dev` — que voltou sozinho numa segunda onda por ter sido recriado por uma CRD do `darueira-operator` não mapeada na primeira limpeza) — ver seções "Cleanup de tenants fantasma". `specs/01-initial-spec.md` §11 (Deviations #1 e #5) e o status matrix foram atualizados para refletir o estado final.
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

### 🔴 Achado crítico #2 (2026-09-23): as 5 políticas nunca cruzaram namespace de verdade

Ao migrar `drr-tnt-swfabrik-europe-dev` (segundo tenant), o Hubble mostrou drops reais e ativos: `food-market-*`, `bookanything-maps-generator` e `caseforce-legalhub-mgmt` sendo bloqueados tentando alcançar RabbitMQ (`5672`) e Temporal (`7233`) em `drr-corpshared-plat`, apesar da regra de egress "Allow communication to Central Shared Services" (`toEndpoints: matchLabels: darueira.io/tier: enterprise-shared`) existir exatamente pra isso.

**Causa raiz**: um `CiliumNetworkPolicy` (recurso namespaced) escopa implicitamente todo `fromEndpoints`/`toEndpoints` com `matchLabels` ao **próprio namespace da política**, injetando automaticamente `k8s:io.kubernetes.pod.namespace: <namespace-da-política>` em cada seletor. Como nenhuma das 5 políticas (`corpshared-{obs,mgmt,plat,secr-internal}` + `tnt-tenant-base`) declarava namespace explicitamente nesses seletores, toda regra baseada em `darueira.io/tier` ou `app.kubernetes.io/name` que deveria cruzar namespace **nunca casou com nada fora do próprio namespace da política** — desde que essas políticas foram escritas, antes desta migração.

Confirmado empiricamente via `cilium endpoint get <id> -o json` → `status.policy.realized.allowed-egress-identities`: a identidade do RabbitMQ (`drr-corpshared-plat`) não aparecia na lista permitida do endpoint do tenant, mesmo os labels batendo perfeitamente.

**Por que isso não tinha sido pego nas Fases 2/3 anteriores**: as 4 políticas de controle (`obs`/`mgmt`/`plat`/`secr-internal`) têm uma regra de fallback `fromEntities: [cluster, host]` (ingress, sem restrição de porta) que mascarava o bug — qualquer coisa vinda de dentro do cluster passava por ali mesmo com a regra baseada em label quebrada. A política de tenant **não tem esse fallback genérico** (só tem `toEntities: [cluster, world]` para DNS, porta 53), então foi o primeiro lugar onde o bug causou um drop real e visível.

**Tentativa de fix errada, documentada pra não repetir**: a primeira hipótese foi usar o prefixo de label-source `any:` (ex.: `any:darueira.io/tier: enterprise-shared`), que a documentação do Cilium associa a "ignorar o namespace". **Não funcionou** — confirmado via `cilium policy selectors`, que mostrou o seletor resultante como `{any.darueira.io/tier: enterprise-shared, k8s.io.kubernetes.pod.namespace: drr-tnt-swfabrik-europe-dev}`: o namespace da política continuou sendo auto-injetado *junto* com o `any:`, não substituído por ele.

**Fix que realmente funciona**: declarar `k8s:io.kubernetes.pod.namespace: <namespace-alvo>` explicitamente dentro do próprio `matchLabels`, ao lado do label de tier/nome. Isso sobrepõe a auto-injeção do Cilium (confirmado via `cilium endpoint get` mostrando a identidade-alvo passando a aparecer em `allowed-egress-identities`/`allowed-ingress-identities`, e via tráfego real `FORWARDED` no Hubble). Como não existe um "casa com qualquer namespace" genérico nesse mecanismo, cada seletor cross-namespace vira uma lista de `matchLabels` — um item por namespace-alvo conhecido.

**Onde isso foi aplicado** (todos usando namespace explícito, decisão registrada: enumerar os namespaces atuais em vez de migrar pra `CiliumClusterwideNetworkPolicy` — ver trade-off abaixo):
- `corpshared-mgmt` e `corpshared-plat`: ingress + egress `enterprise-shared` agora enumeram os outros 3 namespaces `corpshared-*` (reutilizado via YAML anchor `&sibling-enterprise-shared` dentro de cada arquivo, já que ingress e egress precisam da mesma lista).
- `corpshared-obs`: ingress (OTLP) + egress (scrape) agora enumeram os 4 namespaces `corpshared-*` (incluindo o próprio `drr-corpshared-obs` — **regressão que eu mesmo introduzi e corrigi na hora**: a primeira versão do fix excluiu `drr-corpshared-obs` da lista assumindo que a regra separada de "intra-observability" cobriria tráfego same-namespace tipo `fluent-bit -> opensearch:9200`, mas essa regra só casa `darueira.io/subsystem: observability` como label de **pod**, que `fluent-bit` não tem — ele só carrega `darueira.io/tier: enterprise-shared`. Causou um drop real por ~1min até ser corrigido) + os 10 namespaces `drr-tnt-*` atuais (reutilizado via anchor `&cross-ns-obs-sources`).
- `tnt-tenant-base/network-policy-template.yaml`: a regra do `apisix-gateway` (ingress, porta 8000) agora fixa `k8s:io.kubernetes.pod.namespace: drr-corpshared-plat` (único namespace onde o gateway roda). A regra de `enterprise-shared` (egress) enumera os 4 namespaces `corpshared-*`. As regras `tenant-workload` (ingress/egress, tráfego intra-tenant) foram **deixadas como estavam de propósito** — o escopo automático ao próprio namespace é o comportamento correto ali, já que isola tenants diferentes entre si mesmo compartilhando o mesmo label de tier.
- `corpshared-secr-internal`: sem mudança — não usa `matchLabels` cross-namespace em nenhuma regra (só `fromEntities`/`toEntities`).

**Trade-off consciente**: enumerar namespaces funciona bem pros 4 `corpshared-*` (fixos, baixa cadência de mudança) e pro `apisix-gateway` (1 namespace fixo), mas pras 2 regras do `corpshared-obs` que precisam casar `tenant-workload` de qualquer tenant, significa que **criar um tenant novo exige lembrar de adicionar o namespace dele nessas 2 regras** (ambas usam o mesmo anchor `&cross-ns-obs-sources`, então é uma edição só). Decisão registrada (2026-09-23): manter enumeração por agora (plataforma de estudo pessoal, baixo número de tenants); migrar pra `CiliumClusterwideNetworkPolicy` fica como melhoria futura se o número de tenants crescer o suficiente pra doer.

**Também descoberto no processo, sem impacto de fix necessário agora**: a regra de ingress de `corpshared-plat` restringe portas mas nunca incluiu a porta `7233` (Temporal) nem `tenant-workload` na lista de fontes — funciona hoje só porque a regra de fallback `fromEntities: [cluster, host]` (sem restrição de porta) cobre isso. Ou seja, a intenção de "least privilege" dessa regra específica já era, na prática, só documentação, não enforcement real — registrado aqui, não corrigido (fora do escopo do bug de hoje).

**Lição de processo**: depois de um `kubectl apply` numa `CiliumNetworkPolicy`, esperar ~15-20s antes de tirar conclusão de um teste de drop/allow — o tempo de propagação até o mapa BPF do endpoint afetado gerou pelo menos um falso "ainda quebrado" nesta sessão (o `fluent-bit -> opensearch` citado acima já estava corrigido, só não tinha propagado ainda quando testei a primeira vez).

**Achado não relacionado, registrado mas não corrigido**: `bookanything-monolith-backend-01` em `drr-tnt-swfabrik-europe-dev` está em `CrashLoopBackOff` há ~7h, mas **não é causado pela política de rede** — confirmado que é timeout de aplicação (1s) contra o `opensearch.drr-corpshared-obs` cujos health checks de filesystem estão levando 5-11s (mesmo sintoma de I/O em disco saturado já registrado pro Postgres central na Fase 1). Fora do escopo desta migração; fica registrado pra investigação futura de capacidade de disco.

Checklist por namespace:
- [x] `corpshared-obs` (revalidado após achado crítico #2)
- [x] `corpshared-mgmt` (revalidado após achado crítico #2)
- [x] `corpshared-secr-internal`
- [x] `corpshared-plat` (revalidado após achado crítico #2)
- [x] `drr-tnt-swfabrik-latam-dev` (revalidado após achado crítico #2)
- [x] `drr-tnt-swfabrik-europe-dev`

Os demais namespaces `drr-tnt-*` que apareciam nesta lista (`swfabrik-europe-marketplaces-dev`, `acme-storefront-{dev,staging,prod}`, `globex-logistics-{dev,prod}`, `darueira-corp-platform-core-prod`, `base-template`) **não são tenants reais** — foram apagados em 2026-09-23, ver seção "Cleanup de tenants fantasma" abaixo. Rollout de tenant está completo com os 2 namespaces acima.

### 🔴 Cleanup de tenants fantasma (2026-09-23)

Ao validar `drr-tnt-swfabrik-europe-dev`, o usuário identificou que 8 dos 10 namespaces `drr-tnt-*` então existentes no cluster **não deveriam existir**: `drr-tnt-swfabrik-europe-marketplaces-dev`, `drr-tnt-acme-storefront-{dev,staging,prod}`, `drr-tnt-globex-logistics-{dev,prod}`, `drr-tnt-darueira-corp-platform-core-prod`, `drr-tnt-base-template`.

Investigação antes de apagar qualquer coisa (nunca destrutivo sem checar primeiro):
- Todos os 8 estavam **vazios** (0 pods, sem PVC/Secret/PV — só `ConfigMap`s de scaffold como `tenant-profile`, `envoy-sidecar-config`, `kube-root-ca.crt` auto-gerado). Confirmado com `kubectl get all,pvc,secret,configmap -n <ns>` em cada um e checagem de `claimRef` órfão em todos os PVs do cluster — nenhum.
- 6 deles (`acme-storefront-{dev,staging,prod}`, `globex-logistics-{dev,prod}`, `darueira-corp-platform-core-prod`) eram gerenciados por um `ApplicationSet` (`tenant-workloads-appset`, em `drr-corpshared-mgmt`, definido em `platform/gitops/argocd-apps/applicationset-tenants.yaml` **neste repo**) com um gerador `list` carregando 6 elementos hardcoded de tenants demo/scaffold. Como a Application resultante tem `syncPolicy.automated.selfHeal: true`, apagar a Application/namespace direto no cluster **não funciona** — o ArgoCD recria tudo em segundos.
- Os outros 2 (`swfabrik-europe-marketplaces-dev`, `base-template`) não tinham nenhuma `Application`/`ApplicationSet` associada — provavelmente criados manualmente em algum momento de experimentação. Apagar direto (`kubectl delete namespace`) foi suficiente e definitivo pra esses dois.

**Fix aplicado**: `platform/gitops/argocd-apps/applicationset-tenants.yaml` teve os 6 elementos do gerador `list` esvaziados (`elements: []`), preservando o `ApplicationSet` como mecanismo reutilizável pra onboarding de tenants futuros — só sem os 6 demo hardcoded. Aplicado no cluster via `kubectl apply`, o que fez o ArgoCD deletar as 6 `Application`s automaticamente; os namespaces por trás delas ficaram órfãos (não foram prune'd junto) e precisaram de um segundo `kubectl delete namespace` manual depois do fix na fonte.

Também corrigido no mesmo arquivo, drift encontrado entre o `ApplicationSet` ao vivo no cluster e a versão versionada neste repo: o template ao vivo já usava `name: tenant-{{tenant}}-{{project}}-{{env}}` / `namespace: drr-tnt-{{tenant}}-{{project}}-{{env}}` e `targetRevision: main`, enquanto a versão no git ainda tinha `{{tenant}}-{{env}}` (sem `{{project}}`, risco de colisão de nome entre tenants) e `targetRevision: master`. Alinhado o git com o que já estava funcionando ao vivo.

**Efeito colateral corrigido**: a política do `corpshared-obs` (achado crítico #2 acima) tinha sido enumerada com os 10 namespaces de tenant que existiam no momento — incluindo os 8 fantasmas. Removidas essas 8 entradas da lista `&cross-ns-obs-sources`, deixando só os 2 tenants reais.

Tenants reais confirmados no cluster após o cleanup: `drr-tnt-swfabrik-latam-dev`, `drr-tnt-swfabrik-europe-dev`.

### Segunda onda do cleanup (2026-09-23, manhã seguinte): `darueira-operator`

Ao retomar a sessão, `drr-tnt-swfabrik-europe-marketplaces-dev` (um dos 8 namespaces apagados no dia anterior) tinha voltado sozinho, criado 65s antes da checagem. O cleanup de ontem não tinha mapeado essa fonte porque ela não é ArgoCD — é um **operator Kubernetes próprio da plataforma** (`darueira-operator`, Deployment em `drr-corpshared-mgmt`, imagem `localhost:8082/darueira-operator:v1alpha1`, com 3 CRDs: `tenants.darueira.io`, `projects.darueira.io`, `environments.darueira.io`).

**Como foi achado**: `kubectl get ns <namespace> -o yaml --show-managed-fields` mostrou `manager: darueira-operator` no lugar de `argocd-controller`/`kubectl-client-side-apply`. Os logs do operator (`kubectl logs -n drr-corpshared-mgmt deploy/darueira-operator`) confirmaram: o pod do operator reiniciou às 05:59:21 (tem histórico de 41 restarts em 34 dias — mesmo padrão crônico de I/O em disco já registrado neste runbook) e, no startup, reconcilia **todos** os `Environment` CRs existentes contra o estado atual do cluster — como o `Environment/swfabrik-europe-dev` (que referencia `Project/marketplaces` + `Tenant/swfabrik-europe`) ainda existia, o operator recriou o namespace que faltava.

**Diferença importante em relação ao achado de ontem**: isso não era lixo de demo — o `Environment` CR tinha dados de configuração reais (`adminEmail`, `deployers`/`operators` do OpenFGA, `enableSidecarPEP: true`). Antes de apagar de novo, confirmei com o usuário se era engano ter incluído esse na lista de ontem ou se o projeto "marketplaces" realmente devia ser decomissionado — resposta: decomissionar, mas pela via certa (CRs, não o namespace direto).

**Decomissionamento correto**:
1. `kubectl delete environments.darueira.io swfabrik-europe-dev` — o operator RBAC inclui `environments/finalizers`, mas **na prática não implementa cleanup automático**: o delete retornou na hora (sem o hang característico de um finalizer bloqueante) e os logs só registraram `"Environment resource deleted"`, sem nenhuma ação de limpeza em seguida. O namespace continuou existindo.
2. `kubectl delete namespace drr-tnt-swfabrik-europe-marketplaces-dev` — manual, já que o operator não faz.
3. Confirmado que nenhum outro `Environment` referenciava `Project/marketplaces` (`kubectl get environments.darueira.io -A -o jsonpath=...projectRef...`) antes de `kubectl delete projects.darueira.io marketplaces`.
4. `Tenant/swfabrik-europe` foi **mantido** — é o mesmo tenant real que já tem `drr-tnt-swfabrik-europe-dev` migrado; só o projeto "marketplaces" dentro dele foi removido.

**Verificado, não corrigido agora** (fora do escopo desta migração, mas registrado): `drr-tnt-swfabrik-latam-dev` foi confirmado como não gerenciado por este operator (criado via `kubectl-client-side-apply` + `argocd-controller`), então não corre o mesmo risco de recriação. Não foi checado se `swfabrik-europe-dev` (o ambiente real) também tem um `Environment` CR próprio no operator — provavelmente sim, dado o padrão, mas como não estamos apagando esse namespace, não há risco a mitigar agora.

**Lição de processo**: um cleanup baseado em apagar recursos do Kubernetes API direto (namespace, Application) só é permanente se a **fonte de reconciliação** for identificada primeiro — `kubectl get <resource> -o yaml --show-managed-fields` (campo `manager`) é a forma mais rápida de achar quem realmente é dono de um recurso quando não está óbvio, antes de assumir que é ArgoCD ou lixo manual.

Tenants/projects/environments reais confirmados após a segunda onda: `Tenant/swfabrik-europe` (namespace `drr-tnt-swfabrik-europe-dev`), namespace `drr-tnt-swfabrik-latam-dev` (fora do operator). Nenhum `Project`/`Environment` órfão restante.

---

## Fase 4 — Enforcement

Depois que **todos** os namespaces tiverem passado pela Fase 3 sem "would-drop" inesperado:

```bash
# NOTE (2026-09-23): a sintaxe abaixo, copiada de docs antigas do Cilium,
# dá `Error: Improper configuration format provided` nesta versão (v1.15.2).
# O `cilium-dbg config` desta versão usa a forma `<option>=(enable|disable)`.
CIL_POD=$(microk8s kubectl get pods -n kube-system -l k8s-app=cilium -o jsonpath='{.items[0].metadata.name}')
microk8s kubectl exec -n kube-system "$CIL_POD" -- cilium config PolicyAuditMode=Disable
microk8s kubectl exec -n kube-system "$CIL_POD" -- cilium config get PolicyAuditMode   # deve responder "Disabled"
```

Isso ativa o enforcement real (`default-deny` + regras) em todos os namespaces com política de uma vez. Na prática, neste cluster o audit mode já estava `Disabled` desde a Fase 1 (achado crítico da Fase 2) — rodar o comando aqui é só o passo formal/idempotente, o enforcement real já estava ativo o tempo todo.

**Executado em 2026-09-23**: comando rodado, confirmado `Disabled`. `cilium status` reportou `Controller Status: 932/932 healthy`. Zero drops numa janela de 60s em todos os 6 namespaces com política (4 corpshared + 2 tenant), antes e depois. Teste de DNS com pod novo em `drr-tnt-swfabrik-latam-dev` resolveu normalmente. `ArgoCD` com todas as 19 apps `Synced`/`Healthy`.

**Achado no meio do smoke test, não relacionado ao Cilium**: vários pods em `drr-corpshared-plat`/`drr-corpshared-mgmt` (`keycloak-server`, `stalwart-mail`, `clavex-server`, `jsreport`, `temporal-ui`, `apache-nifi`, `backstage`) estavam em `CrashLoopBackOff` e o ArgoCD com `SYNC: Unknown` em todas as apps. Causa: `central-postgres-0` e o `darueira-operator` reiniciaram no mesmo segundo (`05:59:21Z`) — mesmo padrão de cascata já documentado na Fase 1 (provável reinício do node/laptop de madrugada). Confirmado que o Postgres já estava saudável (`psql -U drr_admin -c "SELECT 1"` OK) antes de fazer qualquer coisa; os pods dependentes só estavam presos em backoff longo das tentativas durante o boot dele. `kubectl delete pod` nos 7 pods travados (mesma receita já documentada na Fase 1: "restart manual pra pular a espera") resolveu tudo — todos voltaram `Running 1/1` e o ArgoCD voltou a `Synced` em menos de 2 minutos.

Checklist:
- [x] Todos os namespaces revisados sem drops inesperados em audit
- [x] Audit mode desligado
- [x] Smoke test completo pós-enforcement (repetir os mesmos testes manuais da Fase 1)
- [x] Hubble continua mostrando fluxos normais como `FORWARDED`, não `DROPPED`

---

### 🔴 Achado crítico #3 (2026-09-23): interfaces administrativas nunca tinham porta liberada

Depois da Fase 4 concluída, o usuário reportou que interfaces administrativas não estavam acessíveis: serviços de tenant em geral, e o OpenSearch corporativo. Não era uma regressão da Fase 4 — o enforcement já estava live desde a Fase 1/3; essas portas simplesmente nunca tinham sido testadas antes.

**Causa raiz**: as políticas cobriam as portas de **API/dados** de cada serviço, mas o APISIX (`scripts/bootstrap_apisix_routes.py`) expõe as **interfaces administrativas** em portas diferentes, nunca incluídas nas políticas:

| Interface admin | Rota aponta para | Porta faltando | Política |
| :--- | :--- | :--- | :--- |
| OpenSearch Dashboards | `opensearch-dashboards.drr-corpshared-obs:5601` | `5601` | `corpshared-obs` (regra de ingress 1 tinha `9200` — a API — mas não `5601`, o Dashboard) |
| Tenant Keycloak (admin console) | `tenant-keycloak.<tenant>:8080` | `8080` | `tnt-tenant-base` (regra de ingress do `apisix-gateway` só tinha `8000`) |
| Tenant MinIO (console) | `tenant-minio.<tenant>:9001` | `9001` | idem |
| Tenant OpenBao (UI) | `tenant-openbao.<tenant>:8200` | `8200` | idem (corrigido preventivamente, mesma classe de bug, ainda não testado ao vivo) |

**Confirmado empiricamente** antes de corrigir: pod de teste com label `apisix-gateway` (mesma origem real do tráfego), `nc -zv` em cada porta → `Connection timed out`; Hubble confirmou `policy-verdict:none INGRESS DENIED` para os 3 primeiros alvos. Testados preventivamente ArgoCD (`:80`), Tekton Dashboard (`:9097`), Nexus (`:8082`) e Webmail (`:80`) — esses já funcionavam, cobertos pelas regras `fromEntities` de fallback de `corpshared-mgmt`/`corpshared-plat`.

**Fix**: adicionada a porta `5601/TCP` na regra de ingress 1 do `corpshared-obs`; adicionadas `8080/TCP`, `9001/TCP` e `8200/TCP` na regra de ingress do `apisix-gateway` no template de tenant (mantendo a `8000/TCP` já existente). Reaplicado em `corpshared-obs` e nos 2 namespaces de tenant. Revalidado: todas as 5 portas abrem (`nc -zv` → `open`) nos dois tenants, zero drops residuais.

**Lição de processo**: o smoke test da Fase 4 (Hubble sem drops + DNS + ArgoCD Synced) cobriu os caminhos que já tínhamos testado nas fases anteriores (egress de tenant, DNS, gateway→porta 8000), mas não testou **ingress em portas administrativas** — um caminho de tráfego diferente (browser → APISIX → serviço) que só apareceu quando o usuário testou de verdade. Ao validar uma política de rede, vale levantar o inventário completo de rotas/portas que **deveriam** funcionar (ex.: `scripts/bootstrap_apisix_routes.py` ou equivalente) antes de declarar "sem drops" como sinônimo de "tudo funciona" — ausência de drop numa amostra só prova que o que foi *exercitado* funciona.

---

### 🔴 Achado crítico #4 (2026-09-23): portas dos apps de negócio dos tenants bloqueadas para o APISIX

Mesmo depois do fix do achado #3, o usuário reportou que os serviços dos tenants continuavam inacessíveis. O frontend do `foodmarket` carregava, mas as chamadas `/api/food0X/...` retornavam 504/499. Os logs do APISIX mostravam `upstream timed out (110: Connection timed out) while connecting to upstream`.

**Causa raiz**: a regra de ingress do `apisix-gateway` no template de tenant partia do pressuposto de que o gateway só fala com o Envoy PEP (`8000`) mais os consoles admin (achado #3). Só que as rotas vivas do APISIX (`scripts/bootstrap_apisix_routes.py`) apontam direto para a porta de container de cada app de negócio. O Cilium avalia a porta **pós-DNAT** (a do container), não a do Service. Portas faltando:

| App (europe) | Porta do container |
| :--- | :--- |
| `food-market-01…06-service` | `8081`–`8086` |
| `bookanything-monolith-backend-01` | `8060` |
| `fake-legal-partners-agencies-app` | `8085` |

Os frontends/MFEs (Service `80` → container `8080`), o `caseforce` e os apps de latam funcionavam só porque o `8080` tinha sido liberado no achado #3 para o `tenant-keycloak`.

**Confirmado empiricamente** com um container efêmero (`kubectl debug --profile=restricted`, busybox `nc -z`) **dentro do pod do `apisix-gateway`**, ou seja, com a mesma identidade Cilium do tráfego real: `8081`, `8084`, `8060` e `8085` davam TIMEOUT; `8080`, `9001`, `8200` e `5601` davam OPEN.

**Fix**: a lista de portas da regra passou a ter `8000, 8060, 8080–8086, 9001, 8200`, com cada porta comentada com o app correspondente. A primeira tentativa foi usar a faixa `port: "8000"` + `endPort: 8099`, mas **o CRD do Cilium 1.15 não tem `endPort`** (o `--dry-run=server` retornou `strict decoding error: unknown field ...endPort`). Ficou um TODO para voltar à faixa quando o cluster estiver no Cilium ≥ 1.16. Aplicado nos 2 namespaces de tenant.

**Validado**:
- Novo probe com a identidade do gateway: todos os upstreams HTTP dos tenants (europe e latam) OPEN.
- Datastores continuam fechados para o gateway: `27017`, `3306`, `5432` e a API S3 do MinIO `9000` dão TIMEOUT, como esperado.
- HTTP ponta a ponta via APISIX: `foodmarket /api/food01|03|06/food-tradings` → 200, `bookanything-api` e `agency` `/swagger-ui` → 200. Os 404 de `api.food04 /` e `checkout /` vêm dos próprios apps (corpo FastAPI/Go, não o `Route Not Found` do APISIX).
- Hubble sem drops envolvendo `drr-tnt-*`/`apisix`.

**Lição de processo**: a lição do achado #3 (levantar o inventário de rotas antes de declarar "sem drops") foi aplicada só à metade: foram verificadas as rotas *administrativas*, não **todas** as rotas com upstream em namespace de tenant. O inventário tem que vir da Admin API do APISIX (`GET /apisix/admin/routes`), filtrando os upstreams `*.drr-tnt-*`, e não de uma leitura seletiva do script. Com lista explícita de portas, **todo app novo numa porta fora da lista vai falhar do mesmo jeito**, em silêncio. Esse probe agora está automatizado em `make smoke-apisix-upstreams` (`scripts/smoke_apisix_upstreams.py`). Ele lê todas as rotas da Admin API e testa, em paralelo, cada upstream a partir de um container efêmero dentro do pod do `apisix-gateway`; retorna exit 1 se algum não abrir. **Rode-o depois de qualquer mudança de `CiliumNetworkPolicy` ou de rota.** Na primeira execução (2026-09-23) ele achou mais 5 upstreams quebrados, nenhum deles de política de rede: 3 rotas órfãs para `drr-tnt-acme` (removidas) e 2 rotas com porta errada — `api.tenant` apontava para `:8080`, mas o `drr-tenant-svc` escuta na `8081`; `api.orchestrator` apontava para `:8080`, mas o `drr-env-orchestrator-svc` escuta na `8082`. Tudo corrigido em `scripts/bootstrap_apisix_routes.py`. Resultado final: 50/50 upstreams OPEN.

---

### 🔴 Achado crítico #5 (2026-09-23): NiFi (plataforma) → backend do tenant bloqueado

O workflow Temporal de import de GeoLocations (`GeoLocationIngestionWorkflow`) ficava ~25 min na activity `processCountryLocationViaNiFi` e nenhuma GeoLocation era criada no Postgres do tenant.

**Causa raiz**: o fluxo do NiFi "BookAnything - GeoLocation Ingestion Pipeline" roda em `drr-corpshared-plat`. O passo **"8. Ingest Backend & Summarize"** (ExecuteScript) faz POST **direto** em `bookanything-monolith-backend-01.drr-tnt-swfabrik-europe-dev:8060`, sem passar pelo APISIX. A política do tenant só aceitava entrada do próprio namespace, do `apisix-gateway` e do `host`. Hubble: `apache-nifi → backend:8060 · policy-verdict:none INGRESS DENIED`. O script usa `HttpURLConnection` sem timeout de conexão e a relação `failure` é auto-terminada, então a falha **sumia em silêncio**: nenhum evento em `geolocation.nifi-import.completed`, e o backend esperava o `future.get(25 min)` estourar. Em 21/09 o mesmo fluxo funcionou (import do Brasil) porque o enforcement só entrou em 22–23/09. Os passos 1–7 (Kafka, download do GADM, MinIO) funcionavam; os artefatos no MinIO eram a prova.

**Fix**: regra de ingress `apache-nifi` (`drr-corpshared-plat`) → porta `8060` no template de tenant, com `k8s:io.kubernetes.pod.namespace` explícito (mesmo padrão do achado #2). Aplicada nos 2 tenants. O Postgres do tenant continua fechado para o NiFi (validado).

**Validado**: `nifi → backend:8060` OPEN. No retry seguinte da activity, o NiFi processou `DEU` nível 1 em ~11 s (16 estados criados) e o workflow terminou `COMPLETED`, com PDF do JSReport e evento de fim publicados. O item `DEU` nível 0, que traz a fronteira do país, já tinha estourado o timeout antes do fix: a Alemanha ficou sem `ge_geographic_boundary` e precisa ser reimportada.

**Lição de processo**: o `make smoke-apisix-upstreams` cobre só browser → APISIX → serviço. Chamadas **serviço de plataforma → app de tenant** (NiFi, e potencialmente Temporal, Kafka Connect etc.) são outra classe de caminho e não aparecem em nenhum inventário de rotas. Precisam de levantamento próprio, por exemplo buscando `*.drr-tnt-*.svc` nas configs e flows dos serviços de plataforma.

*Contexto relacionado, não é causa de rede*: no mesmo teste, o worker Temporal do backend não estava registrado ("No Workers Running"). Ele tentou conectar às 06:08 UTC, antes de o `temporal-server` subir (06:12) depois do reboot do nó, e o `TemporalConfig.kt` desistia após uma única falha. Resolvido com restart do deployment; a correção de código (retry com backoff) está em `workspace/platf-bizz-apps` (GitOps).

---

### 🔴 Achado crítico #6 (2026-09-23): tenant sem saída para a internet (enriquecimento/Assets travados)

Depois do achado #5, as GeoLocations eram criadas, mas os Assets (SVGs de mapa, bandeira, PDF de detalhe) só saíam para o 1º estado. O consumer Kafka `geolocation-enricher` ficou com lag 16 e parado.

**Causa raiz**: o enriquecimento do `bookanything-monolith-backend-01` chama APIs externas: Gemini (`*.googleapis.com`), Wikimedia/Wikipedia, flagcdn, restcountries. O `tenant-isolation-policy` só libera saída para o próprio tenant, o DNS e os namespaces da plataforma. Hubble: `backend → 172.217.115.4:443 (world) · policy-verdict:none EGRESS DENIED`. A chamada ao Gemini ficava pendurada nos SYNs descartados, e como o consumer processa uma mensagem por vez, os demais estados ficaram parados na fila.

**Fix (escolha do usuário: opt-in por label)**: nova CNP `tenant-egress-internet` (`tnt-tenant-base/network-policy-egress-internet.yaml`) liberando `world:443` **só** para pods com `darueira.io/egress-internet: "true"`. A label foi adicionada ao pod template do backend no chart GitOps (`bookanything-platform-chart`, commit `04e146d` no Forgejo, sincronizado pelo ArgoCD). Bancos e demais pods do tenant continuam sem saída. Alternativas descartadas: liberar o namespace inteiro (dá saída a qualquer pod, inclusive bancos) e allowlist por FQDN (exige o proxy DNS L7, adiado).

**Validado**: sem drops de saída do backend. Wikimedia (ex.: bandeira de Hamburgo) e Gemini respondem, e os Assets voltaram a ser gerados (mapa local, mapa-múndi, bandeira e PDF por estado).

**Lentidão restante, que não é de rede**: as chamadas ao Gemini levam de 11 s a 460 s, padrão compatível com rate limit da chave (o client tenta de novo em 429). Parte das respostas cai em `JsonParseException` (JSON dentro de blocos markdown), e aí o app usa o `LOCAL_FALLBACK`. Os dois pontos são do app `bookanything-platform`.

**Para novos apps de tenant**: se o app chama APIs externas, precisa da label `darueira.io/egress-internet: "true"` no pod template. Sem ela, a saída para a internet é negada por padrão.

---

### 🔴 Achado crítico #7 (2026-09-24): vazamento de IPs do Cilium a cada reboot do nó (+ efeito colateral da limpeza)

**Sintoma**: depois de um reboot do nó, 67 pods ficaram presos em `ContainerCreating` (Forgejo, ArgoCD, Tekton, OpenSearch…) com `cilium-cni ... unable to allocate IP via local cilium agent: [POST /ipam][502] postIpamFailure range is full`.

**Causa raiz**: o agente Cilium 1.15 **restaura no boot os endpoints das sandboxes que morreram no reboot** (o reboot não dispara `CNI DEL`). O diretório `/var/run/cilium/state` persiste entre reboots nesse setup MicroK8s. Cada pod acumulou uma alocação `[restored]` por reboot, e os pods novos ainda pegavam IPs adicionais. Depois de uns 3 reboots: `IPv4: 254/254 allocated from 10.1.0.0/24` com só ~84 pods, ou seja, 238 IPs presos em endpoints órfãos (`cilium endpoint list` mostrava 254 endpoints, todos `ready`).

**Limpeza aplicada**:
1. Critério seguro: um endpoint é órfão se o IP dele está marcado `[restored]` no IPAM (`cilium status --verbose`) **e** não é o `podIP` de um pod `Running`. Endpoints criados depois do boot nunca têm `[restored]`, então pods subindo durante a limpeza ficam de fora.
2. `cilium endpoint disconnect <id>` em cada um. **No 1.15 não existe `cilium endpoint delete`**: o comando só imprime a ajuda e sai com rc=0, então um loop "bem-sucedido" não faz nada. Confira sempre o efeito, não o exit code.
3. IPAM 254 → 85; os pods presos subiram sozinhos. Postgres central levou ~4 min em fsync de recuperação no HDD, e o Forgejo esperou por ele.

**Efeito colateral e correção**: os endpoints órfãos têm **o mesmo `ns/pod`** dos pods vivos (são as sandboxes antigas deles). Desconectá-los apagou o `CiliumEndpoint` compartilhado e, com ele, a entrada de ipcache de 28 pods vivos (APISIX, Kafka, OpenSearch, Nexus, ArgoCD, Tekton…), que passaram a ser vistos como `world`. Sintoma: `cilium monitor --type drop` → `46590->world: ... -> 10.1.0.52:9200 Policy denied` (backend do tenant sem acesso ao OpenSearch). Correção: `kubectl -n kube-system rollout restart ds/cilium`. O agente reinicia com o diretório de estado já limpo e recria os CEPs e o ipcache (83/84 pods de volta; o que faltou era um pod efêmero do janitor).

**Procedimento correto da próxima vez**: limpeza (passos 1–2) e **logo em seguida** restart do agente.

**Causa de fundo (confirmada)**: o DaemonSet monta `/var/run/cilium` a partir do hostPath `/var/snap/microk8s/current/var/run/cilium`, que está **em disco**. No Cilium padrão esse diretório vem de `/var/run/cilium` do host, que é **tmpfs**: sobrevive a restarts do agente (o comportamento que se quer) e é apagado no reboot. Aqui ele sobrevive ao reboot, e os endpoints de sandboxes mortas são restaurados.

**Correção do diagnóstico (2026-09-24, tarde)**: o vazamento voltou (IPAM 85 → 168) **sem reboot**. O host estava de pé desde 22/09, e o gatilho foi o `microk8s stop`/`start` da noite anterior. O `microk8s stop` chama `kill_all_container_shims` (SIGKILL no containerd e no kubelite), e todas as sandboxes morrem sem `CNI DEL`, exatamente como num reboot. Portanto **qualquer stop/start do MicroK8s vaza cerca de 80 IPs**.

**Por que tmpfs não resolve**: o wrapper do containerd do MicroK8s (`/snap/microk8s/current/run-containerd-with-args`) faz `export CILIUM_SOCK="${SNAP_DATA}/var/run/cilium/cilium.sock"`. O plugin `cilium-cni` só encontra o agente nesse caminho, que é fixo no snap (read-only). Logo, o diretório não pode ser movido para `/run/cilium`. E um tmpfs só seria limpo no reboot, não no stop/start.

**Correção aplicada**: `scripts/setup_host_cilium_state_cleanup.sh` (rodar com `sudo`, idempotente, tem `--uninstall`) instala um `ExecStartPre` no `snap.microk8s.daemon-containerd.service`. Esse passo apaga os diretórios de endpoint em `.../var/run/cilium/state/<id>[_next|_stale|_next_fail]` **somente se nenhum shim de pod do MicroK8s estiver vivo**, ou seja, depois de um reboot ou de um `microk8s stop`. Num restart só do containerd (`KillMode=process` mantém os shims e os pods), o estado fica intacto e os endpoints vivos são restaurados normalmente. Templates e globals não são tocados. Log: `journalctl -t cilium-state-cleanup`.

**Validação pendente**: no próximo `microk8s stop`/`start`, conferir `journalctl -t cilium-state-cleanup` ("removed N stale Cilium endpoint state dirs") e `cilium status | grep IPAM` (deve ficar em torno do número de pods, sem `[restored]` órfãos). Se ainda vazar, o procedimento manual acima continua valendo.

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

- [x] `specs/01-initial-spec.md` §11 — Deviation #1 (network isolation) marcada como resolvida em 2026-09-23; Deviation #5 (namespace naming) também resolvida como efeito colateral do cleanup de tenants fantasma; status matrix (Cilium CNI, `darueira-operator`) atualizado.
- [x] Revisado ADR-0004 — nada nele referenciava o estado pendente de audit mode/enforcement, não precisou de mudança.
- [x] Runbook já registra a data real de execução de cada fase e todos os ajustes feitos nas políticas ao longo do processo (achados críticos #1 e #2, cleanup de tenants fantasma em duas ondas).
