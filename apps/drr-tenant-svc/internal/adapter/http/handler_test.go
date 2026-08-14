package http_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	httpAdapter "github.com/dexterity/darueira/apps/drr-tenant-svc/internal/adapter/http"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/adapter/memory"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/domain"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/service"
)

func setupTestRouter() *httpAdapter.Router {
	tenantRepo := memory.NewInMemoryTenantRepo()
	projectRepo := memory.NewInMemoryProjectRepo()
	memberRepo := memory.NewInMemoryMemberRepo()

	tenantSvc := service.NewTenantService(tenantRepo, nil, nil)
	projectSvc := service.NewProjectService(projectRepo, tenantRepo, nil, nil)
	memberSvc := service.NewMemberService(memberRepo, tenantRepo, nil, nil)

	return httpAdapter.NewRouter(tenantSvc, projectSvc, memberSvc)
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

func TestTenantHTTPFlow(t *testing.T) {
	router := setupTestRouter()

	// 1. Create Tenant
	createBody := map[string]interface{}{
		"id":          "tenant-beta",
		"name":        "tenant-beta",
		"displayName": "Beta Testing Tenant",
	}
	bodyBytes, _ := json.Marshal(createBody)
	req := httptest.NewRequest(http.MethodPost, "/api/v1/tenants", bytes.NewBuffer(bodyBytes))
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("expected 201 Created, got %d (body: %s)", rec.Code, rec.Body.String())
	}

	// 2. Get Tenant
	req = httptest.NewRequest(http.MethodGet, "/api/v1/tenants/tenant-beta", nil)
	rec = httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", rec.Code)
	}

	// 3. Create Project
	projBody := map[string]interface{}{
		"id":          "proj-core",
		"name":        "proj-core",
		"description": "Core Project",
	}
	bodyBytes, _ = json.Marshal(projBody)
	req = httptest.NewRequest(http.MethodPost, "/api/v1/tenants/tenant-beta/projects", bytes.NewBuffer(bodyBytes))
	rec = httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusCreated {
		t.Fatalf("expected 201 Created, got %d (body: %s)", rec.Code, rec.Body.String())
	}

	// 4. List Projects
	req = httptest.NewRequest(http.MethodGet, "/api/v1/tenants/tenant-beta/projects", nil)
	rec = httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", rec.Code)
	}

	var projects []*domain.Project
	_ = json.Unmarshal(rec.Body.Bytes(), &projects)
	if len(projects) != 1 {
		t.Errorf("expected 1 project, got %d", len(projects))
	}

	// 5. Add Member
	memberBody := map[string]interface{}{
		"userId": "usr-123",
		"role":   "admin",
	}
	bodyBytes, _ = json.Marshal(memberBody)
	req = httptest.NewRequest(http.MethodPost, "/api/v1/tenants/tenant-beta/members", bytes.NewBuffer(bodyBytes))
	rec = httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusCreated {
		t.Fatalf("expected 201 Created, got %d (body: %s)", rec.Code, rec.Body.String())
	}

	// 6. Delete Tenant
	req = httptest.NewRequest(http.MethodDelete, "/api/v1/tenants/tenant-beta", nil)
	rec = httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", rec.Code)
	}
}
