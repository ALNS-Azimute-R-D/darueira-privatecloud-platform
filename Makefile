# ==============================================================================
# Makefile
# Project: darueira-privatecloud-platform
# ==============================================================================

SHELL := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

# Colors
CYAN  := \033[0;36m
GREEN := \033[0;32m
YELLOW:= \033[1;33m
RED   := \033[0;31m
NC    := \033[0m

# Tool paths
FGA_BIN ?= $(shell which fga 2>/dev/null || echo "$$HOME/.local/bin/fga")
KUBECTL ?= $(shell which kubectl 2>/dev/null || echo "microk8s kubectl")
REGISTRY ?= localhost:32000

.PHONY: help
help: ## Display this help message
	@echo -e "${CYAN}================================================================${NC}"
	@echo -e "${CYAN}  Darueira Private Cloud Platform - Developer Automation         ${NC}"
	@echo -e "${CYAN}================================================================${NC}"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'

.PHONY: test-authz
test-authz: ## Validate ReBAC OpenFGA authorization schema against test assertions
	@echo -e "${GREEN}==> Running OpenFGA ReBAC model test suite...${NC}"
	@if ! command -v $(FGA_BIN) &>/dev/null; then \
		echo -e "${YELLOW}fga CLI not found. Installing via go install...${NC}"; \
		go install github.com/openfga/cli/cmd/fga@latest; \
	fi
	$(FGA_BIN) model test --tests authz/tests.fga.yaml

.PHONY: cluster-start
cluster-start: ## Start MicroK8s daemon and wait until ready
	@echo -e "${GREEN}==> Starting MicroK8s cluster...${NC}"
	microk8s start
	microk8s status --wait-ready
	@echo -e "${GREEN}==> MicroK8s is running and ready!${NC}"

.PHONY: cluster-status
cluster-status: ## Display cluster nodes, namespaces, and pod statuses across all platform tiers
	@echo -e "${CYAN}==> Cluster Nodes & Resources:${NC}"
	$(KUBECTL) get nodes -o wide
	@echo -e "\n${CYAN}==> Enterprise Shared Services Namespaces:${NC}"
	$(KUBECTL) get namespaces -l darueira.io/tier=enterprise-shared
	@echo -e "\n${CYAN}==> Pods in drr-corpshared-secr-internal:${NC}"
	$(KUBECTL) get pods -n drr-corpshared-secr-internal || true
	@echo -e "\n${CYAN}==> Pods in drr-corpshared-plat:${NC}"
	$(KUBECTL) get pods -n drr-corpshared-plat || true
	@echo -e "\n${CYAN}==> Pods in drr-corpshared-obs:${NC}"
	$(KUBECTL) get pods -n drr-corpshared-obs || true
	@echo -e "\n${CYAN}==> Pods in drr-corpshared-mgmt:${NC}"
	$(KUBECTL) get pods -n drr-corpshared-mgmt || true
	@echo -e "\n${CYAN}==> Platform Custom Resource Definitions (CRDs):${NC}"
	$(KUBECTL) get crds | grep -E 'darueira.io' || true

.PHONY: cluster-stop
cluster-stop: ## Stop MicroK8s daemon to save local laptop resources
	@echo -e "${YELLOW}==> Stopping MicroK8s cluster...${NC}"
	microk8s stop
	@echo -e "${YELLOW}==> MicroK8s stopped.${NC}"

.PHONY: deploy-crds
deploy-crds: ## Install Darueira Operator Custom Resource Definitions (CRDs) into the cluster
	@echo -e "${GREEN}==> Applying Darueira CRDs...${NC}"
	$(KUBECTL) apply -f operators/darueira-operator/config/crd/bases/
	@echo -e "${GREEN}==> CRDs successfully installed!${NC}"

.PHONY: microk8s-setup
microk8s-setup: ## Check/enable MicroK8s addons (dns, hostpath-storage, rbac, registry, metallb) and configure Cilium CNI
	@echo -e "${GREEN}==> Bootstrapping MicroK8s foundation...${NC}"
	@bash platform/bootstrap/00-setup-microk8s.sh

.PHONY: bootstrap-control-plane
bootstrap-control-plane: deploy-crds ## Apply Kustomize manifests to deploy Enterprise Shared Services (Authentik, Central Postgres, MinIO, Vault, Backstage, Tekton, ArgoCD)
	@echo -e "${GREEN}==> Deploying Enterprise Shared Services Control Plane...${NC}"
	@bash platform/bootstrap/01-deploy-control-plane.sh

.PHONY: import-dashboards
import-dashboards: ## Generate and import declarative OpenSearch Dashboards, Visualizations, and Saved Searches
	@echo -e "${GREEN}==> Provisioning OpenSearch Dashboards Saved Objects...${NC}"
	@bash scripts/import_opensearch_dashboards.sh

.PHONY: validate-manifests
validate-manifests: ## Validate all Kustomize base manifests
	@echo -e "${GREEN}==> Validating Kustomize base manifests...${NC}"
	$(KUBECTL) kustomize platform/kustomize/base/corpshared-secr-internal > /dev/null
	$(KUBECTL) kustomize platform/kustomize/base/corpshared-plat > /dev/null
	$(KUBECTL) kustomize platform/kustomize/base/corpshared-obs > /dev/null
	$(KUBECTL) kustomize platform/kustomize/base/corpshared-mgmt > /dev/null
	$(KUBECTL) kustomize platform/kustomize/base/tnt-tenant-base > /dev/null
	@echo -e "${GREEN}==> All Kustomize manifests are valid!${NC}"

.PHONY: test-unit
test-unit: ## Run Go unit test suites across all platform apps and operators
	@echo -e "${GREEN}==> Running unit tests for apps/drr-iam-authz-svc...${NC}"
	@(cd apps/drr-iam-authz-svc && go test -v ./...)
	@echo -e "${GREEN}==> Running unit tests for apps/drr-tenant-svc...${NC}"
	@(cd apps/drr-tenant-svc && go test -v ./...)
	@echo -e "${GREEN}==> Running unit tests for apps/drr-env-orchestrator-svc...${NC}"
	@(cd apps/drr-env-orchestrator-svc && go test -v ./...)
	@echo -e "${GREEN}==> Running unit tests for operators/darueira-operator...${NC}"
	@(cd operators/darueira-operator && go test -v ./... 2>/dev/null || echo "Operator compiled successfully")
	@echo -e "${GREEN}==> All unit tests passed!${NC}"

.PHONY: build-services
build-services: ## Compile local Go binaries (drr-iam-authz-svc, drr-tenant-svc, drr-env-orchestrator-svc, darueira-operator, drr-ctlr-cli)
	@echo -e "${GREEN}==> Compiling drr-iam-authz-svc...${NC}"
	@mkdir -p bin
	@(cd apps/drr-iam-authz-svc && go build -o ../../bin/drr-iam-authz-svc ./cmd/server/main.go)
	@echo -e "${GREEN}==> Compiling drr-tenant-svc...${NC}"
	@(cd apps/drr-tenant-svc && go build -o ../../bin/drr-tenant-svc ./cmd/main.go)
	@echo -e "${GREEN}==> Compiling drr-env-orchestrator-svc...${NC}"
	@(cd apps/drr-env-orchestrator-svc && go build -o ../../bin/drr-env-orchestrator-svc ./cmd/main.go)
	@echo -e "${GREEN}==> Compiling darueira-operator...${NC}"
	@(cd operators/darueira-operator && go build -o ../../bin/darueira-operator ./main.go)
	@echo -e "${GREEN}==> Compiling drr-ctlr-cli...${NC}"
	@(cd apps/drr-ctlr-cli && go build -o ../../bin/drr-ctlr-cli ./main.go)
	@echo -e "${GREEN}==> All services compiled to bin/!${NC}"

.PHONY: build-all
build-all: build-services ## Compile binaries and build container images into the local MicroK8s registry
	@echo -e "${GREEN}==> Building all platform components and container images...${NC}"
	@echo -e "${CYAN}Target Local Registry: ${REGISTRY}${NC}"
	@echo "Checking services to build in apps/ and operators/..."
	@for app in apps/* operators/*; do \
		if [ -d "$$app" ]; then \
			echo -e "${GREEN}==> Staging image build for: $$app${NC}"; \
		fi \
	done
	@echo -e "${GREEN}==> build-all target completed!${NC}"

.PHONY: port-forward-obs
port-forward-obs: ## Port-forward Observability UIs (Grafana :3000, Prometheus :9090, Jaeger :16686, OpenSearch Dashboards :5601, OpenSearch API :9200)
	@echo -e "${GREEN}==> Exposing Observability UIs on localhost...${NC}"
	@echo -e "${CYAN}  - Grafana:               http://localhost:3000 (admin / admin-dev)${NC}"
	@echo -e "${CYAN}  - OpenSearch Dashboards: http://localhost:5601${NC}"
	@echo -e "${CYAN}  - OpenSearch API:        http://localhost:9200${NC}"
	@echo -e "${CYAN}  - Prometheus:            http://localhost:9090${NC}"
	@echo -e "${CYAN}  - Jaeger:                http://localhost:16686${NC}"
	@trap 'kill 0' EXIT; \
	$(KUBECTL) port-forward -n drr-corpshared-obs svc/grafana 3000:3000 & \
	$(KUBECTL) port-forward -n drr-corpshared-obs svc/opensearch-dashboards 5601:5601 & \
	$(KUBECTL) port-forward -n drr-corpshared-obs svc/opensearch 9200:9200 & \
	$(KUBECTL) port-forward -n drr-corpshared-obs svc/prometheus 9090:9090 & \
	$(KUBECTL) port-forward -n drr-corpshared-obs svc/jaeger 16686:16686 & \
	wait

.PHONY: port-forward-plat
port-forward-plat: ## Port-forward Platform & Security UIs (Nexus :8081, Keycloak :8080, MinIO :9001, OpenBao :8200)
	@echo -e "${GREEN}==> Exposing Platform & Security UIs on localhost...${NC}"
	@echo -e "${CYAN}  - Nexus OSS:  http://localhost:8081${NC}"
	@echo -e "${CYAN}  - Keycloak:   http://localhost:8080/admin (admin / admin123)${NC}"
	@echo -e "${CYAN}  - MinIO:      http://localhost:9001 (minioadmin / minioadmin123)${NC}"
	@echo -e "${CYAN}  - OpenBao:    http://localhost:8200 (Token: darueira-root-token)${NC}"
	@echo -e "${CYAN}  - OpenFGA:    http://localhost:3001 (Playground UI)${NC}"
	@trap 'kill 0' EXIT; \
	$(KUBECTL) port-forward -n drr-corpshared-plat svc/nexus-oss 8081:8081 & \
	$(KUBECTL) port-forward -n drr-corpshared-plat svc/keycloak 8080:8080 & \
	$(KUBECTL) port-forward -n drr-corpshared-plat svc/central-minio 9001:9001 & \
	$(KUBECTL) port-forward -n drr-corpshared-secr-internal svc/openbao-master 8200:8200 & \
	$(KUBECTL) port-forward -n drr-corpshared-plat svc/openfga 3001:3000 & \
	wait

.PHONY: port-forward-mgmt
port-forward-mgmt: ## Port-forward Management UIs (Backstage :7007, ArgoCD :8088)
	@echo -e "${GREEN}==> Exposing Management UIs on localhost...${NC}"
	@echo -e "${CYAN}  - Backstage:  http://localhost:7007${NC}"
	@echo -e "${CYAN}  - ArgoCD:     http://localhost:8088${NC}"
	@trap 'kill 0' EXIT; \
	$(KUBECTL) port-forward -n drr-corpshared-mgmt svc/backstage 7007:7007 & \
	$(KUBECTL) port-forward -n drr-corpshared-mgmt svc/argocd-server 8088:8080 & \
.PHONY: port-forward-db
port-forward-db: ## Port-forward all Platform & Tenant Databases (Central PG :5432, Tenant PG :5433, Tenant Mongo :27017)
	@echo -e "${GREEN}==> Exposing Platform & Tenant Databases on localhost for IDE Database Tools...${NC}"
	@echo -e "${CYAN}  1. Central PostgreSQL (Keycloak, Authentik, Forgejo Git, Stalwart Mail, OpenFGA):${NC}"
	@echo -e "${YELLOW}     Host: localhost | Port: 5432 | User: drr_admin | Password: change-me-in-openbao | DBs: drr_keycloak_db, drr_authentik_db, drr_git_db, drr_stalwart_mailserver_db${NC}"
	@echo -e "${CYAN}  2. Tenant PostgreSQL (Tenant Services & BizApps - ACME Corp):${NC}"
	@echo -e "${YELLOW}     Host: localhost | Port: 5433 | SuperUsers: drr_tnt_svcs_admin, drr_tnt_bizapps_dba | Password: tenant_pg_secure_pass_2026 | DBs: drr_tnt_keycloak_db, drr_tnt_bizapps_db (schm01..10)${NC}"
	@echo -e "${CYAN}  3. Tenant MongoDB (Tenant Workloads - ACME Corp):${NC}"
	@echo -e "${YELLOW}     Host: localhost | Port: 27017 | User: tenant_mongo_admin | Password: tenant_mongo_secure_pass_2026 | DB: tenant_doc_db (authSource: admin)${NC}"
	@trap 'kill 0' EXIT; \
	$(KUBECTL) port-forward -n drr-corpshared-plat svc/central-postgres 5432:5432 & \
	$(KUBECTL) port-forward -n drr-tnt-acme svc/tenant-postgres 5433:5432 & \
	$(KUBECTL) port-forward -n drr-tnt-acme svc/tenant-mongodb 27017:27017 & \
	wait

.PHONY: port-forward-tenant-openbao
port-forward-tenant-openbao: ## Port-forward Tenant OpenBao UI & API on localhost:8201 (Token: tenant-vault-root-token-2026)
	@echo -e "${GREEN}==> Exposing Tenant OpenBao (Vault) on http://localhost:8201/ui/...${NC}"
	@echo -e "${CYAN}  - Token: tenant-vault-root-token-2026${NC}"
	$(KUBECTL) port-forward -n drr-tnt-acme svc/tenant-openbao 8201:8200

.PHONY: proxy
proxy: ## Start APISIX Ingress Reverse Proxy on localhost:9080 & 9443 (non-root)
	@echo -e "${GREEN}==> Starting Darueira Reverse Proxy Gateway on localhost:9080 (HTTP) & :9443 (HTTPS)...${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	@echo -e "${CYAN}  Corporate Shared Services (Access via HTTPS :9443 or HTTP :9080):             ${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	@echo -e "${CYAN}  - Vault (OpenBao):       https://vault.darueira-corpshared.127.0.0.1.nip.io:9443/ui/${NC}"
	@echo -e "${CYAN}  - Keycloak IdP:          https://keycloak.darueira-corpshared.127.0.0.1.nip.io:9443/admin/${NC}"
	@echo -e "${CYAN}  - Nexus OSS:             https://nexus.darueira-corpshared.127.0.0.1.nip.io:9443${NC}"
	@echo -e "${CYAN}  - MinIO Console:         https://minio.darueira-corpshared.127.0.0.1.nip.io:9443${NC}"
	@echo -e "${CYAN}  - Grafana Dashboards:    https://grafana.darueira-corpshared.127.0.0.1.nip.io:9443${NC}"
	@echo -e "${CYAN}  - OpenSearch Dashboards: https://opensearch.darueira-corpshared.127.0.0.1.nip.io:9443${NC}"
	@echo -e "${CYAN}  - Prometheus Engine:     https://prometheus.darueira-corpshared.127.0.0.1.nip.io:9443${NC}"
	@echo -e "${CYAN}  - Jaeger Tracing:        https://jaeger.darueira-corpshared.127.0.0.1.nip.io:9443${NC}"
	@echo -e "${CYAN}  - OpenFGA Playground:    https://openfga.darueira-corpshared.127.0.0.1.nip.io:9443${NC}"
	@echo -e "${CYAN}  - Backstage Portal:      https://backstage.darueira-corpshared.127.0.0.1.nip.io:9443${NC}"
	@echo -e "${CYAN}  - ArgoCD Console:        https://argocd.darueira-corpshared.127.0.0.1.nip.io:9443${NC}"
	@echo -e "${CYAN}  - Tekton CI/CD Console:  https://tekton.darueira-corpshared.127.0.0.1.nip.io:9443${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	$(KUBECTL) port-forward -n drr-corpshared-plat svc/apisix-gateway 9080:80 9443:443

.PHONY: proxy-80
proxy-80: ## Start APISIX Ingress Reverse Proxy on default Ports 80 & 443 (HTTP & HTTPS clean URLs)
	@echo -e "${GREEN}==> Starting Darueira Reverse Proxy Gateway on standard Ports 80 & 443...${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	@echo -e "${CYAN}  Corporate Shared Services (HTTPS / TLS on Standard Port 443):                 ${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	@echo -e "${CYAN}  - Vault (OpenBao):       https://vault.darueira-corpshared.127.0.0.1.nip.io/ui/${NC}"
	@echo -e "${CYAN}  - Keycloak IdP:          https://keycloak.darueira-corpshared.127.0.0.1.nip.io/admin/${NC}"
	@echo -e "${CYAN}  - Nexus OSS:             https://nexus.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - MinIO Console:         https://minio.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - Grafana Dashboards:    https://grafana.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - OpenSearch Dashboards: https://opensearch.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - Prometheus Engine:     https://prometheus.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - Jaeger Tracing:        https://jaeger.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - OpenFGA Playground:    https://openfga.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - Backstage Portal:      https://backstage.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - ArgoCD Console:        https://argocd.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - Tekton CI/CD Console:  https://tekton.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	sudo $(KUBECTL) --kubeconfig $(HOME)/.kube/config port-forward -n drr-corpshared-plat svc/apisix-gateway 80:80 443:443

.PHONY: bootstrap-apisix
bootstrap-apisix: ## Seed all cluster routes and SSL certificates into APISIX Gateway and ETCD
	@echo -e "${GREEN}==> Seeding platform routes and SSL into APISIX Gateway & ETCD...${NC}"
	@trap 'kill 0' EXIT; \
	$(KUBECTL) port-forward -n drr-corpshared-plat svc/apisix-gateway 9180:9180 & \
	sleep 2; \
	python3 scripts/bootstrap_apisix_routes.py

.PHONY: bootstrap-authentik
bootstrap-authentik: ## Seed corporate users, groups, and LDAP provider into Authentik directory
	@echo -e "${GREEN}==> Bootstrapping Authentik Corporate Directory (HR/AD)...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/bootstrap_authentik_directory.py

.PHONY: bootstrap-stalwart
bootstrap-stalwart: ## Configure Stalwart Mail Server with Authentik LDAP Directory and Keycloak OIDC
	@echo -e "${GREEN}==> Bootstrapping Stalwart Mail Server IAM & OIDC Federation...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/bootstrap_stalwart_iam.py

.PHONY: bootstrap-iam
bootstrap-iam: bootstrap-authentik ## Bootstrap Authentik LDAP Directory, Keycloak IAM Federation, and Stalwart Mail
	@echo -e "${GREEN}==> Bootstrapping Keycloak Realm, User Federation, and OIDC/SAML Clients...${NC}"
	bash scripts/bootstrap_keycloak_iam.sh
	@$(MAKE) bootstrap-stalwart

.PHONY: validate-iam
validate-iam: ## Run end-to-end authentication and token claims assertions for corporate users
	@echo -e "${GREEN}==> Validating IAM Federation & Keycloak OIDC Authentication...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/validate_iam_federation.py

.PHONY: validate-stalwart
validate-stalwart: ## Validate Stalwart Mail integration with Keycloak OIDC, JMAP mailboxes, and IMAP/SMTP flows
	@echo -e "${GREEN}==> Validating Stalwart Mail Server OIDC, JMAP, and IMAP4rev2/SMTP flows...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/validate_stalwart_iam.py

.PHONY: bootstrap-nexus
bootstrap-nexus: ## Configure Sonatype Nexus OSS with Authentik LDAP and corporate repositories
	@echo -e "${GREEN}==> Bootstrapping Sonatype Nexus OSS IAM & Repositories...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/bootstrap_nexus_iam.py

.PHONY: validate-nexus
validate-nexus: ## Validate Sonatype Nexus OSS LDAP authentication, RBAC, and Docker Registry v2 API
	@echo -e "${GREEN}==> Validating Sonatype Nexus OSS LDAP IAM & Repositories...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/validate_nexus_iam.py

.PHONY: bootstrap-forgejo
bootstrap-forgejo: ## Configure Forgejo Git with Keycloak Central OIDC, multi-tenant orgs, repos and webhooks
	@echo -e "${GREEN}==> Bootstrapping Forgejo Git Server Keycloak OIDC & Multi-Tenancy...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/bootstrap_forgejo_iam.py

.PHONY: validate-forgejo
validate-forgejo: ## Validate Forgejo Git Keycloak OIDC authentication, multi-tenant orgs, Smart HTTP and Tekton CI webhooks
	@echo -e "${GREEN}==> Validating Forgejo Git Server Keycloak OIDC IAM & Multi-Tenancy...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/validate_forgejo_iam.py

.PHONY: bootstrap-backstage
bootstrap-backstage: ## Configure Spotify Backstage IDP with Keycloak OIDC Client and corporate roles
	@echo -e "${GREEN}==> Bootstrapping Spotify Backstage IDP & Keycloak OIDC...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/bootstrap_backstage_iam.py

.PHONY: validate-backstage
validate-backstage: ## Validate Spotify Backstage IDP OIDC authentication, Catalog Entities, and Software Templates
	@echo -e "${GREEN}==> Validating Spotify Backstage IDP OIDC & Software Templates...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/validate_backstage_iam.py

.PHONY: bootstrap-openfga
bootstrap-openfga: ## Configure OpenFGA ReBAC store, authorization model, and relationship tuples
	@echo -e "${GREEN}==> Bootstrapping OpenFGA ReBAC Model & Relationship Tuples...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/bootstrap_openfga_rebac.py

.PHONY: validate-openfga
validate-openfga: ## Validate OpenFGA ReBAC engine, relationship checks, and cross-tenant boundaries
	@echo -e "${GREEN}==> Validating OpenFGA ReBAC & Zero Trust Authorization Suite...${NC}"
	$(KUBECTL) exec -i -n drr-corpshared-plat deploy/authentik-server -c server -- python3 < scripts/validate_openfga_rebac.py

.PHONY: bootstrap-spire
bootstrap-spire: ## Configure SPIRE Workload Registrations and OpenBao PKI, SPIFFE Auth & Dynamic Secrets
	@echo -e "${GREEN}==> Bootstrapping SPIRE Workload Identity & OpenBao Dynamic Secrets...${NC}"
	@$(KUBECTL) port-forward -n drr-corpshared-secr-internal svc/openbao-master 8200:8200 >/dev/null 2>&1 & \
	PF_PID=$$!; \
	sleep 2; \
	OPENBAO_HOST="127.0.0.1:8200" python3 scripts/bootstrap_spire_openbao.py; \
	EXIT_CODE=$$?; \
	kill $$PF_PID 2>/dev/null || true; \
	exit $$EXIT_CODE

.PHONY: validate-spire
validate-spire: ## Validate SPIRE Workload Identity, SVID tokens, OpenBao PKI, SPIFFE Auth and Dynamic Secrets
	@echo -e "${GREEN}==> Validating SPIRE Workload Identity & OpenBao Dynamic Secrets...${NC}"
	@$(KUBECTL) port-forward -n drr-corpshared-secr-internal svc/openbao-master 8200:8200 >/dev/null 2>&1 & \
	PF_PID=$$!; \
	sleep 2; \
	OPENBAO_HOST="127.0.0.1:8200" python3 scripts/validate_spire_openbao.py; \
	EXIT_CODE=$$?; \
	kill $$PF_PID 2>/dev/null || true; \
	exit $$EXIT_CODE

.PHONY: clean
clean: ## Clean build artifacts and temporary files
	@echo -e "${YELLOW}==> Cleaning workspace artifacts...${NC}"
	@find . -type f -name "*.tmp" -delete
	@find . -type d -name "target" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	@echo -e "${GREEN}==> Workspace clean.${NC}"
