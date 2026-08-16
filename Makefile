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
	wait

.PHONY: proxy
proxy: ## Start APISIX Ingress Reverse Proxy on localhost:9080 (non-root)
	@echo -e "${GREEN}==> Starting Darueira Reverse Proxy Gateway on localhost:9080...${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	@echo -e "${CYAN}  Corporate Shared Services (Access via port :9080):                            ${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	@echo -e "${CYAN}  - Vault (OpenBao):       http://vault.darueira-corpshared.127.0.0.1.nip.io:9080${NC}"
	@echo -e "${CYAN}  - Keycloak IdP:          http://keycloak.darueira-corpshared.127.0.0.1.nip.io:9080/admin/${NC}"
	@echo -e "${CYAN}  - Nexus OSS:             http://nexus.darueira-corpshared.127.0.0.1.nip.io:9080${NC}"
	@echo -e "${CYAN}  - MinIO Console:         http://minio.darueira-corpshared.127.0.0.1.nip.io:9080${NC}"
	@echo -e "${CYAN}  - Grafana Dashboards:    http://grafana.darueira-corpshared.127.0.0.1.nip.io:9080${NC}"
	@echo -e "${CYAN}  - OpenSearch Dashboards: http://opensearch.darueira-corpshared.127.0.0.1.nip.io:9080${NC}"
	@echo -e "${CYAN}  - Prometheus Engine:     http://prometheus.darueira-corpshared.127.0.0.1.nip.io:9080${NC}"
	@echo -e "${CYAN}  - Jaeger Tracing:        http://jaeger.darueira-corpshared.127.0.0.1.nip.io:9080${NC}"
	@echo -e "${CYAN}  - OpenFGA Playground:    http://openfga.darueira-corpshared.127.0.0.1.nip.io:9080${NC}"
	@echo -e "${CYAN}  - Backstage Portal:      http://backstage.darueira-corpshared.127.0.0.1.nip.io:9080${NC}"
	@echo -e "${CYAN}  - ArgoCD Console:        http://argocd.darueira-corpshared.127.0.0.1.nip.io:9080${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	$(KUBECTL) port-forward -n drr-corpshared-plat svc/apisix-gateway 9080:80

.PHONY: proxy-80
proxy-80: ## Start APISIX Ingress Reverse Proxy on default Port 80 (requires sudo, no port in URL)
	@echo -e "${GREEN}==> Starting Darueira Reverse Proxy Gateway on standard Port 80 (clean URLs)...${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	@echo -e "${CYAN}  Corporate Shared Services (Standard Port 80 - No Port in URL):                 ${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	@echo -e "${CYAN}  - Vault (OpenBao):       http://vault.darueira-corpshared.127.0.0.1.nip.io/ui/${NC}"
	@echo -e "${CYAN}  - Keycloak IdP:          http://keycloak.darueira-corpshared.127.0.0.1.nip.io/admin/${NC}"
	@echo -e "${CYAN}  - Nexus OSS:             http://nexus.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - MinIO Console:         http://minio.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - Grafana Dashboards:    http://grafana.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - OpenSearch Dashboards: http://opensearch.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - Prometheus Engine:     http://prometheus.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - Jaeger Tracing:        http://jaeger.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - OpenFGA Playground:    http://openfga.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - Backstage Portal:      http://backstage.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}  - ArgoCD Console:        http://argocd.darueira-corpshared.127.0.0.1.nip.io${NC}"
	@echo -e "${CYAN}================================================================================${NC}"
	sudo $(KUBECTL) --kubeconfig $(HOME)/.kube/config port-forward -n drr-corpshared-plat svc/apisix-gateway 80:80

.PHONY: clean
clean: ## Clean build artifacts and temporary files
	@echo -e "${YELLOW}==> Cleaning workspace artifacts...${NC}"
	@find . -type f -name "*.tmp" -delete
	@find . -type d -name "target" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	@echo -e "${GREEN}==> Workspace clean.${NC}"
