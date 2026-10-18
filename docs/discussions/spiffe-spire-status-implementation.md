# SPIFFE/SPIRE in `darueira-privatecloud-platform`: Current Status and Implementation Plan

## From Andre:

On 10.10.2026 - Saturday, Andre reopened this project after some days out, and he asked to both Antigravity and Claude to update their own context about this project and analyze and evaluate it. 
And it was noted by Claude that the implementation of SPIFFE/SPIRE is only as a  placeholder. Then I asked to each agent to analyze and evaluate the current status of SPIFFE/SPIRE implementation in the project, and to provide a plan for its implementation.
Here are the results of this analysis and evaluation, and the plan for its implementation, according to each agent:

## Analysis and Evaluation by Antigravity:

```

O Claude está 100% correto. A implementação atual do SPIFFE/SPIRE é de fato um placeholder sintético (mock) e não uma malha Zero Trust real em execução.

A própria documentação e as especificações do repositório admitem isso abertamente, e a análise dos manifestos e scripts confirma cada detalhe:                                                
──────
### 1. O que está no manifesto (spire-server.yaml)

No arquivo spire-server.yaml:

• Nome do Deployment: É literalmente chamado de spire-server-placeholder (linha 4).                                                                                                            
• Persistência Volátil: O banco de dados SQLite fica montado em um emptyDir: {} (/run/spire/data/datastore.sqlite3). Qualquer restart do pod apaga todos os registros.                         
• KeyManager em Memória: O server.conf usa KeyManager "memory", ou seja, as chaves raiz do trust domain também são perdidas no restart.                                                        
• Falta de Plugins de Atestação: O server.conf não possui plugins de atestação de nós (NodeAttestor como k8s_psat) nem de workloads.                                                           
──────
### 2. O elo ausente: Não existe spire-agent nem Workload API

Para que o SPIFFE funcione no Kubernetes:

1. O SPIRE Agent precisa rodar como DaemonSet em cada nó.
2. Os pods precisam ter acesso ao socket Unix da Workload API (/spiffe-workload-api/spire-agent.sock), tipicamente via spiffe-csi-driver.

No repositório hoje:

• Não existe nenhum manifesto de DaemonSet para o SPIRE Agent.                                                                                                                                 
• A única menção a spire-agent.sock no projeto inteiro é uma linha comentada no manifesto do Tekton:                                                                                           
# spire-socket-path: "unix:///spiffe-workload-api/spire-agent.sock"

• Nenhum pod no cluster (seja de plataforma ou de tenant) monta ou consome a Workload API.                                                                                                     
──────
### 3. Como os testes e scripts funcionam hoje?

Os scripts bootstrap_spire_openbao.py e validate_spire_openbao.py foram construídos como uma PoC sintética:

• Para registrar entradas, o script faz kubectl exec no pod do servidor e roda comandos CLI (spire-server entry create).                                                                       
• Para validar emissão de tokens JWT SVID, ele roda:                                                                                                                                           
kubectl exec deploy/spire-server-placeholder -- /opt/spire/bin/spire-server jwt mint -spiffeID ...                                                                                           
Ou seja, os tokens são "forjados" via CLI sob demanda e enviados ao OpenBao, sem qualquer negociação criptográfica automática pelo workload.                                                   
• No teste de sidecars (validate_envoy_opa_sidecars.py), o cliente simplesmente passa um header HTTP manual:                                                                                   
headers={"x-spiffe-principal": "spiffe://darueira.local/..."}

• O Envoy (envoy-sidecar-configmap.yaml) escuta em HTTP puro (sem TLS/mTLS, sem SDS), e o OPA (opa-policy-configmap.yaml:33) apenas valida se esse header de texto começa com                  
spiffe://darueira.local/.                                                                                                                                                                      
──────
### 4. O que a própria especificação diz

Em specs/01-initial-spec.md` (Seção 11.1 - Status Matrix):

│ | SPIRE workload identity | Placeholder | Only spire-server-placeholder runs; there is no SPIRE Agent, so no SVIDs are issued (ADR-0012 is not yet realized) |                               
│ | OpenBao dynamic secrets via SPIFFE auth | Partial | openbao-master and per-tenant tenant-openbao run; SPIFFE auth depends on SPIRE above |

E na Seção 11.2 (Known Deviations):

│ "2. Zero Trust identity is incomplete. Deploy a real SPIRE Server and SPIRE Agent DaemonSet before relying on ADR-0012."                                                                     
──────
### 5. O que seria necessário para tornar real

1. SPIRE Server Real:                                                                                                                                                                          
   • Persistência em PV ou no central-postgres (em vez de SQLite em emptyDir).                                                                                                                
   • Plugin k8s_psat para atestação segura dos nós MicroK8s.                                                                                                                                  
   • KeyManager com persistência de chaves (via OpenBao ou disco seguro).
2. SPIRE Agent (DaemonSet):                                                                                                                                                                    
   • Rodando em cada nó com acesso ao kubelet.                                                                                                                                                
   • Plugin k8s de atestação de workloads (identificando pods por UID, ServiceAccount e Namespace).
3. SPIFFE Workload API nos Pods:                                                                                                                                                               
   • Instalar o spiffe-csi-driver no cluster para projetar o socket /spiffe-workload-api/spire-agent.sock nos containers.
4. Envoy SDS (Secret Discovery Service):                                                                                                                                                       
   • Configurar o Envoy para obter certificados X.509 SVID dinamicamente via SDS pelo socket do SPIRE, habilitando mTLS real workload-to-workload e preenchendo o source.principal do Envoy   
   para o OPA de forma criptograficamente autenticada.


────────────────────────────────────────────────────────────
> Ok. Enetendi. E qual é o esforço de implementação, de tempo e os riscos e desvantagens envolvidos na iniciativa de termos um SPIRE Agent real?

▸ Thought for 17s, 2.1k tokens
Further, the existing network isolation via eBPF and critical backlog items related to disk saturation and security flaws make this effort a low priority.
Como Lead Cloud-Native Platform Architect, aqui está a análise detalhada de esforço, tempo, riscos e desvantagens para transformar o SPIRE de placeholder em uma implementação real no         
Darueira.                                                                                                                                                                                      
──────
### 1. Estimativa de Esforço e Tempo

A implementação não se resume a subir um pod; ela exige mudar a cadeia de confiança de ponta a ponta. O trabalho divide-se em 3 fases:

Fase                                          │ Escopo Técnico                                                                                          │          Esforço Estimado
───────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────
Fase 1: Infraestrutura SPIRE (Server + Agent) │ • Migrar persistência do Server para PV ou central-postgres.• Configurar k8s_psat (Node Attestor) e     │         2 a 3 dias(16h–24h)
│ RBACs de cluster.• Criar DaemonSet do spire-agent ajustado para os caminhos do Snap do MicroK8s.•       │
│ Configurar atestação de workloads via kubelet/containerd socket.                                        │
Fase 2: Projeção de Sockets (Workload API)    │ • Instalar o spiffe-csi-driver (ou padronizar montagem hostPath do socket Unix).• Implantar o SPIRE     │         1 a 2 dias(8h–16h)
│ Controller Manager para auto-registro de SPIFFE IDs baseado em CRDs/labels (evitando registros manuais  │
│ via CLI).                                                                                               │
Fase 3: Integração dos Workloads & Envoy SDS  │ • Configurar o Envoy dos sidecars para usar Secret Discovery Service (SDS) via Unix socket.• Habilitar  │         2 a 3 dias(16h–24h)
│ terminação e validação mTLS real (troca mútua de X.509 SVIDs validando o SAN                            │
│ spiffe://darueira.local/...).• Remover o mock do header x-spiffe-principal e validar a passagem do      │
│ source.principal autenticado ao OPA.                                                                    │
TOTAL                                         │ Implementação completa e validada de ponta a ponta                                                      │ ~5 a 8 dias de trabalho(~40h a 60h)
──────
### 2. Riscos e Dificuldades Técnicas (Específicos do Ambiente)

1. Peculiaridades do MicroK8s (Snap Paths):                                                                                                                                                    
   • O Kubernetes padrão usa caminhos como /var/lib/kubelet e /run/containerd/containerd.sock.                                                                                                
   • No MicroK8s (instalado via Snap), esses caminhos mudam para:                                                                                                                             
   • Kubelet: /var/snap/microk8s/common/var/lib/kubelet                                                                                                                                   
   • Runtime: /var/snap/microk8s/common/run/containerd/containerd.sock                                                                                                                    
   • O spire-agent e principalmente o spiffe-csi-driver precisam de binds muito específicos no host. Se o plugin directory do Kubelet não casar perfeitamente, o driver CSI não registra e os
   pods ficam travados em ContainerCreating.
2. Pressão no Disco HDD (I/O):                                                                                                                                                                 
   • Como vimos no backlog (Itens 3 e 10), o disco /dev/sda2 é um HDD mecânico que já é o gargalo do central-postgres, do NiFi e do OpenSearch.                                               
   • O SPIRE Server faz escritas contínuas no banco para registrar nós, tokens e leases. Se colocado no PostgreSQL ou em PV no HDD, aumentará a disputa por I/O.
3. Complexidade de Depuração ("Fail-Closed"):                                                                                                                                                  
   • Zero Trust real com SDS é estrito: se um pod subir e o SPIRE Agent demorar 2 segundos para atestar o UID do container no Kubelet, o Envoy não recebe o certificado e recusa qualquer     
   conexão com erro TLS.                                                                                                                                                                      
   • Qualquer falha de rota ou reinício do nó derruba as conexões internas até que os sockets sejam restabelecidos.

──────
### 3. Desvantagens Práticas no Estágio Atual do Lab

1. Sobrecarga de Recursos em um Único Host:                                                                                                                                                    
   • Cada pod com Envoy + OPA + App já consome memória e CPU. Adicionar o DaemonSet do SPIRE Agent + SPIFFE CSI Driver aumenta o baseline de recursos da máquina.
2. Sobreposição com o Cilium CNI:                                                                                                                                                              
   • O Cilium já está com default-deny L3/L4 ativo e validado nos 6 namespaces principais. O isolamento de rede entre namespaces já existe hoje via eBPF sem precisar de mTLS nas pontas.
3. Custo de Manutenção vs. Retorno Imediato:                                                                                                                                                   
   • Para aplicações de negócio em desenvolvimento (como o bookanything-platform e os testes de import/export de geolocalização), o mTLS via SPIFFE não adiciona funcionalidade de negócio,   
   mas adiciona mais uma camada onde falhas transitórias podem quebrar fluxos de CI/CD e testes.

──────
### 4. Parecer Arquitetural e Recomendação

│ Recomendação: Não implementar o SPIRE Agent completo neste momento.                                                                                                                          
│ Manter o placeholder por enquanto e priorizar as dores estruturais reais do cluster.

Ordem sugerida de prioridades:

1. Resolver a Segurança Real Imediata (Item 1 do Backlog): Migrar as credenciais hardcoded (Postgres, NiFi, APISIX) para o OpenBao / K8s Secrets reais (isso mitiga riscos reais do repo no    
   GitHub).
2. Estabilidade de Disco e Probes (Itens 3, 5, 10, 23): Aliviar o HDD e ajustar as probes que reiniciam pods.
3. SPIFFE/SPIRE Real: Deixar como um marco posterior (ex: uma "Fase de Blindagem Zero Trust"), atacando-o isoladamente quando a plataforma estiver estável e com o roadmap de negócio do       
   BookAnything estabilizado.

Faz sentido essa leitura e direcionamento para você?

```

## Analysis and Evaluation by Claude:

```

 I agora tenho o quadro completo. O status reportado pelo Claude está correto e é bem mais detalhado do que "só um placeholder" — aqui está o raio-X:                                              
                                                                                                                                                                                                    
  O que de fato existe no repo                                                                                                                                                                      
                                                                                                                                                                                                    
  SPIRE Server: existe um manifest real (platform/kustomize/base/corpshared-secr-internal/spire-server.yaml), rodando a imagem oficial ghcr.io/spiffe/spire-server:1.9.4, non-root, com datastore   
  SQLite. Mas:                                                                                                                                                                                      
  - O nome do Deployment é literalmente spire-server-placeholder — autodescritivo.                                                                                                                  
  - Datastore em emptyDir → sem persistência, qualquer restart do pod zera o SPIRE Server inteiro (registration entries, etc).                                                                      
  - KeyManager "memory" → chaves também não persistem.                                                                                                                                              
  - Não há configuração de Upstream CA / federação de trust bundle.    
  
 SPIRE Agent: não existe nenhum manifest de DaemonSet do SPIRE Agent em lugar nenhum do repo. Sem Agent, nenhum pod consegue buscar um SVID via Workload API — ou seja, nenhuma identidade SPIFFE é
  emitida hoje, mesmo que o Server esteja de pé.                                                                                                                                                    
                                                                                                                                                                                                    
  Scripts de bootstrap/validação (scripts/bootstrap_spire_openbao.py, scripts/validate_spire_openbao.py) e targets make bootstrap-spire / make validate-spire: existem e são funcionais no papel,   
  mas as WORKLOAD_ENTRIES registram SPIFFE IDs para tenants de exemplo do ADR (drr-tnt-acme, globex-*) que não são os tenants reais do cluster (swfabrik-europe / swfabrik-latam). Isso é mais      
  scaffolding/exemplo do que integração real com os tenants que existem de fato.                                                                                                                    
                                                                                                                                                                                                    
  ADR-0012 (aceito) descreve o desenho completo: SPIRE emitindo X.509/JWT SVIDs, OpenBao com SPIFFE Auth Method federando via JWKS do SPIRE, PKI dinâmico, etc. Nada disso está conectado ainda — o 
  próprio specs/01-initial-spec.md §11 confirma: "Only spire-server-placeholder runs; there is no SPIRE Agent, so no SVIDs are issued (ADR-0012 is not yet realized)", e marca OpenBao SPIFFE auth  
  como "Partial" porque depende do SPIRE.                                                                                                                                                           
                                                                                                                                                                                                    
  Conclusão                                                                                                                                                                                         
                                                                                                                                                                                                    
  A afirmação do Claude está certa e, na verdade, é otimista: não é "só" o Server rodando como placeholder — é um Server sem persistência e sem Agent, então zero SVIDs circulam no cluster hoje. A 
  pendência nº 2 da lista de achados do spec (specs/01-initial-spec.md linha ~400) já registra isso como ação pendente: "Deploy a real SPIRE Server and SPIRE Agent DaemonSet before relying on     
  ADR-0012."     
  
  Não consegui confirmar o estado ao vivo no cluster porque o MicroK8s não está rodando agora (microk8s is not running). Se quiser, posso iniciar o MicroK8s e conferir com kubectl get pods -n     
  drr-corpshared-secr-internal para validar se bate com o repo — mas isso levaria alguns minutos e é uma ação que prefiro confirmar com você antes.       
  
  
 Ok. Entendi. E qual é o esforço de implementação, de tempo e os riscos e desvantagens envolvidos na iniciativa de termos um SPIRE Agent real?

  Ran 1 shell command

Boa, isso muda a conta a favor de vocês. É um cluster single-node — isso simplifica bastante (SPIRE Agent vira 1 réplica de DaemonSet, não uma frota distribuída, e não há o problema clássico de distribuir o trust bundle entre múltiplos nós).

  Ran 5 shell commands

Com base no que já existe no repo (Server rodando mas efêmero, zero Agent, script de bootstrap com IDs de exemplo, operador que promete integração mas não implementa), dá pra estimar com uma base concreta — não é um "do zero total", mas também é mais trabalho do que só "subir o DaemonSet".

│                    │                                                                                    │ estático por auth via SVID                                                       │    
  ├────────────────────┼────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤    
  │ Operador           │ README promete "SPIRE Server API Client" e bind automático de registration         │ Ou fica manual (via script) por enquanto, ou é mais um item de desenvolvimento   │    
  │ (drr-operator)     │ entries; o controller real só gera uma policy Rego com string spiffe://... — zero  │ Go separado                                                                      │    
  │                    │ chamada à API do SPIRE                                                             │                                                                                  │    
  └────────────────────┴────────────────────────────────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────┘    
                                                                                                                                                                                                    
  Esforço/tempo (cluster single-node, projeto part-time com ajuda de agente)                                                                                                                        
                                                                                                                                                                                                    
  - Fase 1 — Agent rodando e emitindo SVID real (Server persistente, DaemonSet, RBAC, spire-agent api fetch x509 funcionando): ~4-8h, 1 sessão focada.                                              
  - Fase 2 — Entries reais + OpenBao SPIFFE auth validado fim a fim para os 4 serviços de plataforma: mais ~4-6h.                                                                                   
  - Fase 3 — Pelo menos 1 app real trocando token estático por SVID (prova de valor do ADR-0012): 1-2 dias, por serviço, dependendo do stack.                                                       
  - Fase 4 — Estender para mTLS Envoy/OPA sidecar com SVID (isso ainda depende de uma decisão arquitetural aberta — item 3 do status gaps, Envoy+OPA vs. OPA-only): provavelmente mais alguns dias, 
    e só vale a pena depois dessa decisão.                                                                                                                                                          
                                                                                                                                                                                                    
  Ou seja: "Agent ligado e emitindo certificado" é questão de um fim de semana. "ADR-0012 realizado de verdade" (zero credencial estática rodando) é mais perto de 1-2 semanas picadas.             

 Riscos e desvantagens                                                                                                                                                                             
                                                                                                                                                                                                    
  1. Novo ponto único de dependência para acesso a segredos. Hoje, se o Vault cair, as apps já têm credenciais em cache/env. Com SPIFFE auth, se o Agent cair, toda renovação de SVID trava — e como
     o padrão do cluster é fail-closed (Envoy/OPA com timeout de 0.25s), isso pode começar a negar tráfego em cascata, não só acesso a secrets.                                                     
  2. Disco. O HDD já está em 83% (achado #3/#10 do backlog) e é o gargalo de I/O do Postgres. Colocar outro PVC (datastore SQLite do SPIRE) nesse mesmo disco empilha risco em cima de um problema  
     já aberto — ideal seria esperar a migração para NVMe ou isolar o volume.                                                                                                                       
  3. Perda de estado na transição. Trocar de emptyDir para PVC precisa ser feito com o Server ainda vazio (sem entries valendo), senão qualquer registro feito hoje via script se perde de qualquer 
     forma no primeiro restart — não é motivo pra não fazer, mas define a ordem certa (persistência primeiro, depois popular entries).                                                              
  4. Trabalho não é só infra. O ganho real do ADR-0012 só aparece quando as apps consomem o SVID. Fazer só o Agent subir e ficar bonito no kubectl get pods sem nenhuma app usando ainda deixa a    
     feature "funcionalmente placeholder" mesmo com o pod rodando — fácil de cair nessa armadilha e reportar como "feito" prematuramente.                                                           
  5. Decisão arquitetural pendente. Faz sentido também decidir logo o padrão de sidecar (Envoy+OPA da ADR-0003 vs. o OPA-only que já roda em 2 serviços tenant) antes de investir em mTLS via SPIFFE
     — senão o trabalho de Fase 4 pode ter que ser refeito.                                                                                                                                         
                                                                                                                                                                                                    
  Minha recomendação: fazer Fase 1 + 2 primeiro (Agent real, persistência, OpenBao validado) como item isolado e de baixo risco — é infra pura, reversível, não toca em app em produção. Fase 3     
  (trocar 1 serviço real de credencial estática pra SVID) só depois, escolhendo o se Jump to bottom (ctrl+End) ↓ omo piloto.

```

# Discussion/Debate:

## Highlighted points from Antigravity's analysis:
- **Confirmação Técnica da Condição de Mock/Placeholder**: O `spire-server-placeholder` atual opera sem persistência real (SQLite montado em `emptyDir: {}` e chaves mestras voláteis com `KeyManager "memory"`). Além disso, não há nenhum DaemonSet de `spire-agent` nem montagem do socket da Workload API (`/spiffe-workload-api/spire-agent.sock`) nos nós ou pods.
- **Validações Sintéticas na PoC Atual**: O teste existente (`validate_spire_openbao.py`) apenas emite tokens JWT via CLI usando `kubectl exec ... spire-server jwt mint`, e a verificação do sidecar (`validate_envoy_opa_sidecars.py`) simula identidade injetando um header HTTP arbitrário (`x-spiffe-principal`) consumido por um Envoy ouvindo em HTTP puro sem terminação TLS.
- **Restrições Severas de Hardware e I/O de Disco**: O cluster roda em nó único sob um HDD mecânico 5400rpm (`/dev/sda2`) em 83% de capacidade, que já representa o principal gargalo do `central-postgres`, do NiFi e do OpenSearch. Adicionar escritas concorrentes contínuas de leases/atestação em novo PVC de disco mecânico é um risco operacional crítico.
- **Peculiaridades do Runtime MicroK8s (Snap Paths)**: Empregando Canonical MicroK8s, os caminhos de Kubelet e containerd não seguem o padrão Linux habitual, exigindo apontamento explícito para `/var/snap/microk8s/common/var/lib/kubelet` e `/var/snap/microk8s/common/run/containerd/containerd.sock` para que a atestação de nó e workload não falhe silenciosamente.
- **Priorização Realista do Backlog vs. Cilium CNI**: Como o Cilium CNI já provê isolamento L3/L4 com default-deny ativo nos 6 namespaces principais, o risco de tráfego lateral está mitigado no nível de rede. A urgência real de segurança da plataforma está no Item 1 do Backlog (segredos hardcoded no repositório público do GitHub).

## Highlighted points from Claude's analysis:
  - **O Server é mais frágil do que "placeholder" sugere.** Não é só o nome (`spire-server-placeholder`): o `KeyManager "memory"` + datastore em `emptyDir` significam que tanto os registros quanto as chaves raiz do trust domain somem a cada restart do pod, e não há `NodeAttestor` configurado no `server.conf` — mesmo que um Agent aparecesse hoje, o Server não teria como validar de onde ele vem.
  - **Já existe lógica real de integração escrita, só que apontando para tenants de exemplo.** `scripts/bootstrap_spire_openbao.py` já sabe registrar workload entries e configurar `auth/spiffe` no OpenBao a partir do JWKS do SPIRE — mas a lista `WORKLOAD_ENTRIES` usa os tenants fictícios do ADR-0012 (`drr-tnt-acme`, `drr-tnt-globex`), que **não existem como namespace real no cluster** (os únicos tenants reais hoje são `drr-tnt-swfabrik-{europe,latam}-dev`).
  - **O `drr-operator` promete mais do que entrega.** O README diz que ele "binds SPIRE workload registration entries", mas o `environment_controller.go` real só gera uma string de policy Rego contendo `spiffe://darueira.local/...` — não há nenhuma chamada à API do SPIRE Server no código Go. Essa automação é aspiracional, não implementada.
  - **Cluster single-node simplifica a parte de infraestrutura**: um único nó elimina o problema clássico de distribuir o trust bundle entre múltiplos nós e reduz o Agent a uma única réplica.
  - **O escopo de "implementação real" varia bastante conforme o que se inclui.** O núcleo do ADR-0012 (dynamic secrets via OpenBao SPIFFE JWT auth) **não depende de Envoy/SDS** — essa dependência é do ADR-0003 (mTLS Envoy/OPA), objetivo relacionado mas separável. Separar os dois permite entregar o valor de secrets dinâmicos com esforço bem menor antes de decidir investir em mTLS ponta a ponta.

## Counterpoints and clarifications from Antigravity:
- **Concordância Integral com os Pontos 4 e 5 do Claude**: O Claude foi cirúrgico ao destacar que subir o Agent sem nenhuma aplicação consumindo o SVID é manter a feature como um placeholder funcionalmente disfarçado de "sucesso". Concordo também que investir em mTLS antes de formalizar a decisão arquitetural pendente entre Envoy+OPA (ADR-0003) e OPA-only (`authzen-pdp-sidecar`) geraria retrabalho certo.
- **O Grande Ganho Imediato: SPIFFE para OpenBao (Segredos Dinâmicos)**: A grande sacada do faseamento proposto pelo Claude é **desacoplar o uso de SVID para autenticação no OpenBao do uso de SVID para mTLS entre pods**. Usar o token JWT SVID emitido pela Workload API para autenticar pods no OpenBao (`auth/spiffe`) resolve a causa raiz do **Item 1 do Backlog (Segredos Hardcoded)** sem depender de sidecars complexos nem introduzir riscos de quebra de tráfego em cascata.
- **Alinhamento com Claude sobre I/O do Central Postgres**: O Claude fez uma distinção técnica precisa. Usar o `central-postgres` não elimina o I/O no disco físico `/dev/sda2` (já que o Postgres reside no mesmo disco), mas traz enorme ganho de consolidação operacional (reaproveita conexão, probes, backup e evita gerenciar mais um PVC/PV). Aprovada a sugestão do Claude de medir `iostat` e pool de conexões ao ligar o SPIRE.
- **Atenção Mandatória aos Snap Paths do MicroK8s no Agent**: Reforço que, ao implementar o DaemonSet do SPIRE Agent na Fase 1, os volumes de bind do host precisam mapear os diretórios do Snap do MicroK8s (`/var/snap/microk8s/common/var/lib/kubelet` e `/var/snap/microk8s/common/run/containerd/containerd.sock`), caso contrário o plugin `WorkloadAttestor "k8s"` falhará silenciosamente ao inspecionar os containers.
- **Descarte Total e Expurgo de `acme` (Premissa do André)**: O André confirmou categoricamente que qualquer menção a `acme` é lixo de testes anteriores que já deveria ter sido expurgado do projeto. Portanto, `acme` é 100% descartado — e adicionamos ao plano de ação uma tarefa de saneamento para remover manifestos (`acme-storefront-app.yaml`) e referências em scripts legados.
- **Piscina Oficial de Aplicações para o Piloto e Adoção Gradual (Diretriz do André)**: O André forneceu a lista oficial de aplicações elegíveis para o piloto e para a expansão do consumo de SVID:
  1. `food-market-__-service` (01 a 06 no tenant `swfabrik-europe`, sendo o `food-market-01-service` já equipado com sidecar OPA)
  2. `checkout-service` (no tenant `swfabrik-latam`)
  3. `app-identity-studio` (no tenant `swfabrik-latam`)
  4. `app-food-market-00-mfe` (MFE no tenant `swfabrik-europe`)
  5. `bookanything-monolith-backend-01` (backend central com Spring Boot / GraalVM Native)
- **Estratégia de Execução do Piloto**:
  - **Piloto Inicial (Fase 3)**: Executar no `food-market-01-service` (que já tem o sidecar OPA e roda em `swfabrik-europe-dev`) ou no `checkout-service` (`swfabrik-latam-dev`), provando a troca de credencial estática por JWT SVID para login no OpenBao com baixíssimo blast radius.
  - **Fase 3.x (Rollout Sequencial)**: Após o piloto consolidado, expandir progressivamente para `app-identity-studio`, os demais `food-market-*-service`, o MFE, e culminar no `bookanything-monolith-backend-01` quando o pipeline de GeoLocation permitir.
- **Calibração de Risco (Contexto Lab/PoC)**: Totalmente de acordo com a observação do Claude e a premissa do André. Saber que o ambiente é 100% lab/estudo nos permite testar fail-closed, reinicializações e falhas sem receio de quebrar "produção", mantendo a disciplina arquitetural de forma ágil e produtiva.

### Réplica de Antigravity (Rodada 3 - Consenso Total e Esclarecimentos Finais):
- **Confirmação Expressa sobre o `checkout-service`**: No prompt enviado diretamente ao Antigravity pelo André, a lista de 5 itens incluiu expressamente `- checkout-service`. O app existe de fato em `workspace/platf-bizz-apps/swfabrik-latam/checkout-service`. Portanto, ele está formalmente **confirmado** pelo André na piscina oficial das 5 aplicações elegíveis da plataforma.
- **Endosso Completo ao Alerta de Escopo no Expurgo de `acme` (Trilhas A e B)**: O Claude fez uma descoberta cirúrgica e de altíssimo valor preventivo ao apontar que `authz/tests.fga.yaml` contém as fixtures da suíte de 136 checks do OpenFGA (`make test-authz`). Apagar tudo às cegas quebraria a suíte de testes. Aprovada integralmente a separação em:
  - **Trilha A (Imediata na Fase 2)**: expurgo de `acme-storefront-app.yaml`, remoção da lista `resources` do `tnt-tenant-base/kustomization.yaml` e correção dos `WORKLOAD_ENTRIES` do script do SPIRE.
  - **Trilha B (Item de backlog próprio de qualidade)**: refatoração cirúrgica dos scripts e fixtures de teste do OpenFGA para usar tenants neutros sem quebrar a suíte.
- **Endosso ao Alerta sobre `app-food-market-00-mfe` (SPA Estática)**: Perfeita a constatação do Claude. Por ser uma SPA React/Vite estática rodando no browser do usuário, o MFE não possui processo backend para falar com o socket da Workload API ou solicitar secrets dinâmicos no OpenBao. Ele fica formalmente dispensado da Fase 3 (secrets dinâmicos), sendo preservado para quando abordarmos segurança em nível de Edge/Ingress (mTLS).
- **Consenso na Ordem do Piloto e Rollout**:
  - **Piloto Inicial (Fase 3)**: `food-market-01-service` (tenant `swfabrik-europe-dev`, já possui sidecar OPA).
  - **Fase 3.x (Rollout Sequencial)**: `checkout-service` e `app-identity-studio` (validando o tenant `swfabrik-latam-dev`), seguido pelos demais `food-market-*-service`, e culminando no `bookanything-monolith-backend-01` quando os testes intensivos de GeoLocation estiverem concluídos.

## Counterpoints and clarifications from Claude:
  - **Concordo com os pontos técnicos do Antigravity sobre paths do Snap e fail-closed** — são riscos reais e específicos deste ambiente que valem entrar no plano de ação como estão.
  - **Sobre `central-postgres` como datastore do SPIRE (Final Decision #4)**: concordo que é melhor do que um PVC novo de SQLite no mesmo HDD, mas quero ajustar a justificativa — isso evita *gerenciar mais um volume*, não evita *I/O no disco físico*. O `central-postgres` já roda no mesmo `/dev/sda2` saturado (itens 3/10 do backlog); o SPIRE escrevendo leases/atestações continuamente ainda bate no mesmo disco, só que via uma tabela a mais dentro do mesmo Postgres em vez de um arquivo SQLite separado. A vantagem real é operacional (um serviço a menos para persistir, conexões já com headroom após o fix do item 17 — 54 de 200 em uso), não é alívio de I/O. Sugiro medir `iostat`/conexões no central-postgres depois de ligar o SPIRE, para confirmar que o headroom aguenta.
  - **Correção factual importante nos candidatos a piloto (Final Decision #6 / Action Plan 3.1)**: `acme-storefront-app` é um nome de exemplo do próprio texto do ADR-0012 — **não existe nenhum namespace `drr-tnt-acme` no cluster real**. Os únicos tenants reais hoje são `drr-tnt-swfabrik-{europe,latam}-dev`. `food-market-01-service` é a escolha correta e, na verdade, é ainda melhor do que o texto sugere: ele **já roda hoje** um sidecar OPA (`authzen-pdp-sidecar`), então já está preparado para receber um `source.principal` autenticado sem precisar nascer do zero. Recomendo remover a opção `acme-storefront-app` do plano para não gerar confusão numa sessão futura tentando aplicar manifesto num namespace que não existe.
  - **Contexto adicional que nenhum dos dois diagnósticos tinha quando as prioridades foram escritas**: o André confirmou nesta conversa que **o projeto inteiro é PoC/lab, não produção**, e que destruir/reconstruir qualquer parte é aceitável. Isso não muda a ordem de prioridades (segredos expostos no GitHub continuam sendo o item mais urgente, independente de lab ou produção), mas muda a *razão* por trás da cautela nos itens de disco/probes e do faseamento do SPIRE: é para não desperdiçar tempo de estudo do André com instabilidade evitável, não para proteger um ambiente produtivo. Vale registrar isso explicitamente para que decisões futuras sobre risco/reversibilidade nesta plataforma não herdem um nível de cautela pensado para produção.
  - **Alerta de escopo sobre o "expurgo total de `acme`/`globex`" (item 2.2 / Decisão #6)**: fiz uma varredura real no repo (`grep -rli "acme\|globex"`, excluindo `.venv`/`node_modules`) antes de concordar com um expurgo "total". O resultado: **mais de 40 arquivos** mencionam `acme` ou `globex`, não só o `acme-storefront-app.yaml`. Dois achados mudam o risco dessa tarefa:
    1. `platform/kustomize/base/tnt-tenant-base/kustomization.yaml` **inclui `acme-storefront-app.yaml` na lista de `resources`** — ou seja, esse manifesto está de fato costurado na base real usada por todos os tenants (`swfabrik-europe`/`latam`). Isso confirma a instrução do André: esse arquivo específico deveria ter sido removido e deve sair agora, junto com sua entrada no `kustomization.yaml`.
    2. **`authz/tests.fga.yaml` usa `tenant:acme` / `project:acme-core` como fixture de teste** do suite de ReBAC do OpenFGA — o mesmo suite que o `README.md` reporta como "136/136 checks passing" via `make test-authz`. Isso **não é lixo de deploy**, é dado de teste de um suite automatizado que hoje passa. Apagar essas linhas sem critério quebra `make test-authz`. Os outros ~20 scripts `bootstrap_*.py`/`validate_*.py` (IAM federation, ArgoCD, message brokers, APISIX, Backstage golden-paths) também citam `acme`/`globex`, e cada um precisa ser olhado individualmente — alguns podem estar usando o nome só como exemplo ilustrativo inofensivo em docstring/log, outros podem realmente apontar `acme` como alvo de bootstrap (esse sim seria bug, como o caso do SPIRE).
    - **Recomendação**: separar em duas tarefas antes de qualquer `git rm`/sed em massa — (A) remover `acme-storefront-app.yaml` do `kustomization.yaml` do `tnt-tenant-base` + o arquivo em si + os `WORKLOAD_ENTRIES` do script do SPIRE (já planejado, baixo risco, fazer já); (B) revisar caso a caso os scripts de bootstrap/validate e o `authz/tests.fga.yaml` antes de decidir apagar vs. renomear vs. deixar como está — isso é faxina de qualidade, não bug de segurança, e merece seu próprio item de backlog em vez de ser feito as pressas dentro da Fase 2 do SPIRE.
  - **Correção de atribuição sobre `checkout-service`**: confirmei que `checkout-service` **existe de fato** em `workspace/platf-bizz-apps/swfabrik-latam/checkout-service` — não é um nome inventado como `acme`. Mas a lista que o André deu neste turno foi explicitamente `app-food-market-00-mfe`, `food-market-__-service`, `bookanything-monolith-backend-01` e `app-identity-studio` — **`checkout-service` não estava nela**. Não é um erro grave (o app é real), mas a atribuição "conforme definição do André" não é precisa; vale o André confirmar explicitamente se quer incluí-lo ou se o piloto fica restrito aos 4 nomes que ele de fato listou.
  - **Refinamento da ordem do piloto dentro da lista real do André**: `food-market-01-service` continua a melhor primeira escolha (já tem sidecar OPA rodando, está na família `food-market-__-service` citada). `app-identity-studio` é um bom segundo passo temático (nome sugere que já lida com identidade). Já `app-food-market-00-mfe` é, por inspeção (`package.json`/`vite.config.ts`/Tailwind), uma **SPA frontend estática** — não roda um processo backend que buscaria segredo dinâmico no OpenBao, então pode não ser um bom piloto para a Fase 3 (dynamic secrets); ele faz mais sentido como candidato do Sub-marco B (mTLS/Envoy), quando chegar a vez. `bookanything-monolith-backend-01` segue por último, como já combinado.

### Réplica de Claude (Rodada 3 — aceite do consenso + dois reforços técnicos):
  - **Sobre o `checkout-service` (Rodada 3 do Antigravity)**: aceito a explicação — o André pode ter passado listas levemente diferentes a cada agente em sessões paralelas, e como o app é real (não é um caso tipo `acme`), não há motivo para disputar isso. Consenso fechado: as 5 apps da Decisão #7 valem como piscina oficial. Só deixo registrado para o André, caso quisesse só as 4 que me passou diretamente, que é fácil tirar o `checkout-service` do rollout depois — não é uma decisão difícil de reverter.
  - **Reforço nº 1 — cascata de renome do `spire-server-placeholder` (Action Plan 1.2)**: antes de tirar o sufixo `-placeholder` do nome do Deployment, vale checar quem depende desse nome literal. Busquei no repo e `spire-server-placeholder` aparece hardcoded em **`scripts/bootstrap_spire_openbao.py`** (variável `SPIRE_POD`, usada em `kubectl exec`), **`scripts/validate_spire_openbao.py`**, além de menções em `specs/01-initial-spec.md` e `docs/runbooks/cilium-cni-migration.md`. Se o Deployment for renomeado sem atualizar esses dois scripts, o `make bootstrap-spire`/`make validate-spire` passam a falhar silenciosamente com "deployment not found". Sugiro adicionar isso como sub-item explícito do 1.2.
  - **Reforço nº 2 — não recriar o próprio problema do Item 1 do Backlog (Action Plan 1.1)**: "criar usuário dedicado com credenciais gerenciadas" está um pouco vago. Como o motivo nº 1 de prioridade antes do SPIRE é justamente eliminar credencial estática hardcoded, seria uma ironia desnecessária gerar uma *nova* senha estática para o usuário `spire_server` num YAML/ConfigMap. Sugiro deixar explícito: essa credencial deve nascer no OpenBao (engine de secrets dinâmicos do Postgres, se já disponível, ou pelo menos um K8s `Secret` gerado fora do manifesto versionado) — não hardcoded em `central-postgres.yaml` nem em `spire-server.yaml`.

# Final Decisions After Both Agreement and Disagreement:

Com base na convergência unânime dos diagnósticos de ambos os agentes (Antigravity e Claude) e nas premissas e diretrizes explícitas do André, estabelecem-se as seguintes decisões consensuais:

1. **Reconhecimento Formal do Débito Técnico**: Confirma-se que a infraestrutura SPIFFE/SPIRE atual é um placeholder sintético. A resolução deste débito é essencial para a realização do ADR-0012, mas deve ser executada de forma estritamente controlada e incremental.
2. **Desacoplamento Estratégico (Segredos vs. mTLS)**: 
   - O objetivo primário imediato da introdução do SPIRE é viabilizar o método `auth/spiffe` no **OpenBao**, atacando a causa raiz dos segredos estáticos (Item 1 do Backlog).
   - O uso de SVIDs para **mTLS workload-to-workload** entre pods fica explicitamente **postergado** para uma etapa futura.
3. **Congelamento de mTLS até Resolução da Decisão de Sidecars**: Nenhuma implementação de mTLS ou refatoração profunda de Envoy será iniciada antes da resolução formal do desvio arquitetural registrado no spec (§11.2, item 3) sobre a padronização entre Envoy+OPA (ADR-0003) vs. OPA-only (`authzen-pdp-sidecar`).
4. **Arquitetura de Persistência no Central Postgres com Monitoramento**: O SPIRE Server utilizará o banco **`central-postgres`** (`drr-corpshared-plat`) para o datastore SQL (banco `spire_server`). Isso consolida a persistência no banco central, reaproveita conexões e evita gerenciar mais um PVC no cluster. O `iostat` e as conexões do Postgres serão medidos após a ativação para garantir headroom seguro no `/dev/sda2`.
5. **Ajuste Mandatório ao Runtime Canonical MicroK8s**: O DaemonSet do SPIRE Agent e qualquer mecanismo de projeção de socket devem utilizar estritamente os paths do Snap (`/var/snap/microk8s/common/var/lib/kubelet` e `/var/snap/microk8s/common/run/containerd/containerd.sock`).
6. **Descarte e Expurgo de Recursos "acme" — Escopo Consolidado em Duas Trilhas**:
   - **Trilha A (baixo risco, imediata na Fase 2 do SPIRE)**: remover `acme-storefront-app.yaml` da lista `resources` em `platform/kustomize/base/tnt-tenant-base/kustomization.yaml`, apagar o manifesto físico, e corrigir os `WORKLOAD_ENTRIES` do `bootstrap_spire_openbao.py`.
   - **Trilha B (item de backlog próprio de qualidade)**: revisar caso a caso os scripts de bootstrap legados e, especialmente, `authz/tests.fga.yaml` (fixture da suíte OpenFGA que valida 136/136 checks no `make test-authz`), refatorando para tenants neutros sem quebrar testes automatizados.
7. **Piscina Oficial de Aplicações e Estratégia de Adoção**:
   - As 5 aplicações oficiais definidas pelo André são: `food-market-__-service` (01 a 06), `checkout-service`, `app-identity-studio`, `app-food-market-00-mfe` e `bookanything-monolith-backend-01`.
   - **Piloto Inicial (Fase 3)**: Executado no **`food-market-01-service`** (tenant `swfabrik-europe-dev`, já possui sidecar OPA ativo).
   - **Segundo Passo do Rollout**: **`checkout-service`** e **`app-identity-studio`** (tenant `swfabrik-latam-dev`, validando a federação cross-tenant com o OpenBao).
   - **Escopo do MFE**: `app-food-market-00-mfe` (SPA frontend estática) fica reservado para a futura etapa de mTLS/Ingress, não sendo consumidor de secrets dinâmicos na Fase 3.
   - **Último Passo**: `bookanything-monolith-backend-01` (integrado assim que a fase intensiva de testes de importação/relatórios de GeoLocation estiver concluída).
8. **Calibração de Risco por Contexto de Lab/PoC**: Ratificado que o projeto é 100% lab/PoC, autorizando experimentação ágil e recriação de recursos a qualquer momento, sem o conservadorismo excessivo de ambientes de produção restritivos.

# Action Plan for SPIFFE/SPIRE Implementation:

O plano de ação é estruturado em três fases progressivas, reversíveis e com critérios de aceite claros:

### Fase 1: Infraestrutura Básica SPIRE & Persistência (Esforço estimado: ~4–8h)
- [ ] **1.1. Provisionamento de Banco no Central Postgres**: Criar database `spire_server` e usuário dedicado no PostgreSQL central. **Reforço (Claude)**: a credencial desse usuário deve nascer no OpenBao (engine de secrets dinâmicos do Postgres, se disponível) ou, no mínimo, em um K8s `Secret` fora do manifesto versionado — não hardcoded em `central-postgres.yaml`/`spire-server.yaml`, para não recriar o mesmo problema do Item 1 do Backlog que esse trabalho todo ajuda a resolver.
- [ ] **1.2. Refatoração do Manifesto do SPIRE Server**: Atualizar `platform/kustomize/base/corpshared-secr-internal/spire-server.yaml` para remover o sufixo `-placeholder`, configurar plugin `DataStore "sql"` (PostgreSQL), `NodeAttestor "k8s_psat"`, e `KeyManager "disk"` (ou integração com OpenBao). **Reforço (Claude)**: ao renomear o Deployment, atualizar também as referências hardcoded ao nome antigo em `scripts/bootstrap_spire_openbao.py` (`SPIRE_POD`) e `scripts/validate_spire_openbao.py` — senão `make bootstrap-spire`/`make validate-spire` passam a falhar silenciosamente por "deployment not found".
- [ ] **1.3. Manifesto do SPIRE Agent (DaemonSet)**: Criar o DaemonSet do SPIRE Agent em `drr-corpshared-secr-internal` com RBAC de cluster adequado, mapeando os volumes nos caminhos do Snap MicroK8s e configurando `WorkloadAttestor "k8s"`.
- [ ] **1.4. Validação Básica de Infraestrutura**: Verificar saúde do Agent (`spire-agent healthcheck`) e atestação do nó MicroK8s com emissão de SVIDs via socket local do nó. Monitorar métricas de conexão e I/O no `central-postgres`.

### Fase 2: Federação SPIFFE -> OpenBao, Workload API & Faxina Trilha A (Esforço estimado: ~4–6h)
- [ ] **2.1. Exposição Segura da Workload API**: Disponibilizar o socket `/spiffe-workload-api/spire-agent.sock` para os pods (via montagem de volume padronizada ou `spiffe-csi-driver`).
- [ ] **2.2. Automação de Registrations Reais**: Atualizar o script de bootstrap / registration entries para cobrir os ServiceAccounts reais da plataforma (`drr-iam-authz-svc`, `drr-tenant-svc`, `drr-env-orchestrator-svc`, `drr-operator`) e os workloads reais dos tenants `swfabrik-europe` e `swfabrik-latam` (lista oficial do André).
- [ ] **2.2b. Faxina de `acme` — Trilha A**: Remover `acme-storefront-app.yaml` da lista `resources` em `platform/kustomize/base/tnt-tenant-base/kustomization.yaml`, deletar o arquivo e expurgar `acme`/`globex` do script de bootstrap do SPIRE. *(Trilha B: abrir item no backlog para revisão futura de fixtures e outros scripts sem quebrar `make test-authz`)*.
- [ ] **2.3. Validação End-to-End da Autenticação no OpenBao**: Validar o método `auth/spiffe` no OpenBao Master consumindo o JWKS persistente do SPIRE Server, atestando login com sucesso via JWT SVID real obtido da Workload API (sem `kubectl exec` mint).

### Fase 3: Piloto Real em Aplicação & Roadmap de Adoção (Esforço estimado: ~1–2 dias)
- [ ] **3.1. Execução do Piloto**: Habilitar a obtenção de SVID no pod piloto **`food-market-01-service`** (tenant `swfabrik-europe-dev`, já possui sidecar OPA ativo).
- [ ] **3.2. Eliminação de Credencial Estática no Piloto**: Configurar o container da aplicação (ou Vault Agent sidecar) para autenticar no OpenBao via JWT SVID e buscar segredos dinâmicos (ex: credenciais do banco tenant), removendo variáveis de ambiente com senhas estáticas.
- [ ] **3.3. Documentação e Atualização do Spec**: Atualizar o status na Seção 11 de `specs/01-initial-spec.md` (de "Placeholder" para "Live" na emissão de SVIDs e autenticação OpenBao) e registrar notas de handoff no backlog.
- [ ] **3.4. Expansão para as Demais Aplicações da Lista Oficial do André**: Seguir o rollout sequencial para **`checkout-service`** e **`app-identity-studio`** (tenant `swfabrik-latam-dev`), demais `food-market-*-service`, e por último `bookanything-monolith-backend-01`. *(O `app-food-market-00-mfe` fica preservado para a futura etapa de mTLS/Ingress)*.

---
*(Nota: Fase 4 — mTLS Workload-to-Workload com Envoy SDS permanece suspensa aguardando a decisão arquitetural sobre a padronização dos sidecars).*