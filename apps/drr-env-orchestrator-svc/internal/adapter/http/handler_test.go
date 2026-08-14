package http_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	httpAdapter "github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/adapter/http"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/adapter/k8s"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/adapter/memory"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/domain"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/service"
)

func setupTestRouter() *httpAdapter.Router {
	envRepo := memory.NewInMemoryEnvRepo()
	k8sApplier := k8s.NewDirectK8sApplier()
	orchSvc := service.NewOrchestratorService(envRepo, k8sApplier, nil, nil)
	return httpAdapter.NewRouter(orchSvc)
}

func TestHealthEndpoints(t *testing.T) {
	router := setupTestRouter()
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("expected 200 OK, got %d", rec.Code)
	}
}

func TestEnvironmentHTTPFlow(t *testing.T) {
	router := setupTestRouter()

	// 1. Create Environment
	createBody := map[string]interface{}{
		"tenantId":  "tenant-alpha",
		"projectId": "proj-auth",
		"name":      "staging",
		"type":      "staging",
	}
	bodyBytes, _ := json.Marshal(createBody)
	req := httptest.NewRequest(http.MethodPost, "/api/v1/environments", bytes.NewBuffer(bodyBytes))
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("expected 201 Created, got %d (body: %s)", rec.Code, rec.Body.String())
	}

	// 2. Get Environment
	envID := "tenant-alpha-proj-auth-staging"
	req = httptest.NewRequest(http.MethodGet, "/api/v1/environments/"+envID, nil)
	rec = httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", rec.Code)
	}

	// 3. List Environments
	req = httptest.NewRequest(http.MethodGet, "/api/v1/environments?tenantId=tenant-alpha", nil)
	rec = httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", rec.Code)
	}

	var envs []*domain.Environment
	_ = json.Unmarshal(rec.Body.Bytes(), &envs)
	if len(envs) != 1 {
		t.Errorf("expected 1 environment, got %d", len(envs))
	}

	// 4. Deploy Environment
	deployBody := map[string]interface{}{
		"components": []map[string]interface{}{
			{
				"name":     "auth-service",
				"image":    "auth:v1.0",
				"port":     8080,
				"replicas": 1,
			},
		},
		"triggeredBy": "developer-bob",
	}
	bodyBytes, _ = json.Marshal(deployBody)
	req = httptest.NewRequest(http.MethodPost, "/api/v1/environments/"+envID+"/deploy", bytes.NewBuffer(bodyBytes))
	rec = httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d (body: %s)", rec.Code, rec.Body.String())
	}

	// 5. Delete Environment
	req = httptest.NewRequest(http.MethodDelete, "/api/v1/environments/"+envID, nil)
	rec = httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", rec.Code)
	}
}
