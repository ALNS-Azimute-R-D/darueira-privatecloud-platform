package http_test

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	adapterHttp "github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/adapter/http"
	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/domain"
)

type MockAuthzService struct {
	CheckPermissionFunc     func(ctx context.Context, req domain.PermissionCheckRequest) (domain.PermissionCheckResponse, error)
	BatchCheckFunc          func(ctx context.Context, req domain.BatchCheckRequest) (domain.BatchCheckResponse, error)
	HandleTupleMutationFunc func(ctx context.Context, event domain.TupleMutationEvent) error
	ValidateAndCheckFunc    func(ctx context.Context, tokenString string, relation string, object string) (domain.PermissionCheckResponse, *domain.TokenClaims, error)
}

func (m *MockAuthzService) CheckPermission(ctx context.Context, req domain.PermissionCheckRequest) (domain.PermissionCheckResponse, error) {
	if m.CheckPermissionFunc != nil {
		return m.CheckPermissionFunc(ctx, req)
	}
	return domain.PermissionCheckResponse{Allowed: false}, nil
}

func (m *MockAuthzService) BatchCheckPermission(ctx context.Context, req domain.BatchCheckRequest) (domain.BatchCheckResponse, error) {
	if m.BatchCheckFunc != nil {
		return m.BatchCheckFunc(ctx, req)
	}
	return domain.BatchCheckResponse{}, nil
}

func (m *MockAuthzService) HandleTupleMutation(ctx context.Context, event domain.TupleMutationEvent) error {
	if m.HandleTupleMutationFunc != nil {
		return m.HandleTupleMutationFunc(ctx, event)
	}
	return nil
}

func (m *MockAuthzService) ValidateAndCheck(ctx context.Context, tokenString string, relation string, object string) (domain.PermissionCheckResponse, *domain.TokenClaims, error) {
	if m.ValidateAndCheckFunc != nil {
		return m.ValidateAndCheckFunc(ctx, tokenString, relation, object)
	}
	return domain.PermissionCheckResponse{Allowed: false}, nil, nil
}

func TestHandler_Healthz(t *testing.T) {
	mockSvc := &MockAuthzService{}
	h := adapterHttp.NewAuthzHandler(mockSvc)
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}
}

func TestHandler_Check_Allowed(t *testing.T) {
	mockSvc := &MockAuthzService{
		CheckPermissionFunc: func(ctx context.Context, req domain.PermissionCheckRequest) (domain.PermissionCheckResponse, error) {
			if req.User == "user:alice" && req.Relation == "admin" {
				return domain.PermissionCheckResponse{Allowed: true, Resolution: "ok"}, nil
			}
			return domain.PermissionCheckResponse{Allowed: false}, nil
		},
	}

	h := adapterHttp.NewAuthzHandler(mockSvc)
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	payload := domain.PermissionCheckRequest{
		User:     "user:alice",
		Relation: "admin",
		Object:   "tenant:acme",
	}
	body, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPost, "/api/v1/authz/check", bytes.NewReader(body))
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var resp domain.PermissionCheckResponse
	_ = json.NewDecoder(w.Body).Decode(&resp)
	if !resp.Allowed {
		t.Errorf("expected allowed=true, got false")
	}
}

func TestHandler_ForwardAuth(t *testing.T) {
	mockSvc := &MockAuthzService{
		ValidateAndCheckFunc: func(ctx context.Context, tokenString string, relation string, object string) (domain.PermissionCheckResponse, *domain.TokenClaims, error) {
			if tokenString == "Bearer test-token" && relation == "deployer" {
				return domain.PermissionCheckResponse{Allowed: true}, &domain.TokenClaims{
					Subject:  "bob-123",
					Email:    "bob@acme.corp",
					TenantID: "acme",
				}, nil
			}
			return domain.PermissionCheckResponse{Allowed: false}, nil, nil
		},
	}

	h := adapterHttp.NewAuthzHandler(mockSvc)
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/authz/forward-auth?relation=deployer&object=environment:acme-dev", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}
	if w.Header().Get("X-Auth-Subject") != "bob-123" {
		t.Errorf("expected X-Auth-Subject bob-123, got %s", w.Header().Get("X-Auth-Subject"))
	}
}
