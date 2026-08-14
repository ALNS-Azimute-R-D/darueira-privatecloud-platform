package service_test

import (
	"context"
	"errors"
	"testing"

	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/domain"
	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/service"
)

// MockOpenFGAAdapter mocks OpenFGA port
type MockOpenFGAAdapter struct {
	CheckFunc        func(ctx context.Context, req domain.PermissionCheckRequest) (bool, error)
	BatchCheckFunc   func(ctx context.Context, req domain.BatchCheckRequest) ([]domain.PermissionCheckResponse, error)
	WriteTuplesFunc  func(ctx context.Context, tuples []domain.Tuple) error
	DeleteTuplesFunc func(ctx context.Context, tuples []domain.Tuple) error
	ListObjectsFunc  func(ctx context.Context, user string, relation string, objectType string) ([]string, error)
}

func (m *MockOpenFGAAdapter) Check(ctx context.Context, req domain.PermissionCheckRequest) (bool, error) {
	if m.CheckFunc != nil {
		return m.CheckFunc(ctx, req)
	}
	return false, nil
}

func (m *MockOpenFGAAdapter) BatchCheck(ctx context.Context, req domain.BatchCheckRequest) ([]domain.PermissionCheckResponse, error) {
	if m.BatchCheckFunc != nil {
		return m.BatchCheckFunc(ctx, req)
	}
	return nil, nil
}

func (m *MockOpenFGAAdapter) WriteTuples(ctx context.Context, tuples []domain.Tuple) error {
	if m.WriteTuplesFunc != nil {
		return m.WriteTuplesFunc(ctx, tuples)
	}
	return nil
}

func (m *MockOpenFGAAdapter) DeleteTuples(ctx context.Context, tuples []domain.Tuple) error {
	if m.DeleteTuplesFunc != nil {
		return m.DeleteTuplesFunc(ctx, tuples)
	}
	return nil
}

func (m *MockOpenFGAAdapter) ListObjects(ctx context.Context, user string, relation string, objectType string) ([]string, error) {
	if m.ListObjectsFunc != nil {
		return m.ListObjectsFunc(ctx, user, relation, objectType)
	}
	return []string{}, nil
}

// MockTokenValidator mocks TokenValidatorPort
type MockTokenValidator struct {
	ValidateTokenFunc func(ctx context.Context, tokenString string) (*domain.TokenClaims, error)
}

func (m *MockTokenValidator) ValidateToken(ctx context.Context, tokenString string) (*domain.TokenClaims, error) {
	if m.ValidateTokenFunc != nil {
		return m.ValidateTokenFunc(ctx, tokenString)
	}
	return nil, errors.New("unimplemented")
}

func TestCheckPermission_Allowed(t *testing.T) {
	mockFGA := &MockOpenFGAAdapter{
		CheckFunc: func(ctx context.Context, req domain.PermissionCheckRequest) (bool, error) {
			if req.User == "user:alice" && req.Relation == "admin" && req.Object == "tenant:acme" {
				return true, nil
			}
			return false, nil
		},
	}
	mockOIDC := &MockTokenValidator{}

	svc := service.NewAuthzService(mockFGA, mockOIDC)
	ctx := context.Background()

	resp, err := svc.CheckPermission(ctx, domain.PermissionCheckRequest{
		User:     "user:alice",
		Relation: "admin",
		Object:   "tenant:acme",
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !resp.Allowed {
		t.Errorf("expected allowed=true, got false")
	}
}

func TestCheckPermission_Denied(t *testing.T) {
	mockFGA := &MockOpenFGAAdapter{
		CheckFunc: func(ctx context.Context, req domain.PermissionCheckRequest) (bool, error) {
			return false, nil
		},
	}
	mockOIDC := &MockTokenValidator{}

	svc := service.NewAuthzService(mockFGA, mockOIDC)
	ctx := context.Background()

	resp, err := svc.CheckPermission(ctx, domain.PermissionCheckRequest{
		User:     "user:mallory",
		Relation: "admin",
		Object:   "tenant:acme",
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.Allowed {
		t.Errorf("expected allowed=false, got true")
	}
}

func TestValidateAndCheck(t *testing.T) {
	mockFGA := &MockOpenFGAAdapter{
		CheckFunc: func(ctx context.Context, req domain.PermissionCheckRequest) (bool, error) {
			if req.User == "user:alice-id" && req.Relation == "can_deploy" && req.Object == "environment:acme-core-dev" {
				return true, nil
			}
			return false, nil
		},
	}
	mockOIDC := &MockTokenValidator{
		ValidateTokenFunc: func(ctx context.Context, tokenString string) (*domain.TokenClaims, error) {
			if tokenString == "valid-jwt-token" {
				return &domain.TokenClaims{
					Subject:  "alice-id",
					Email:    "alice@acme.corp",
					TenantID: "acme",
					Roles:    []string{"deployer"},
				}, nil
			}
			return nil, errors.New("invalid signature")
		},
	}

	svc := service.NewAuthzService(mockFGA, mockOIDC)
	ctx := context.Background()

	resp, claims, err := svc.ValidateAndCheck(ctx, "Bearer valid-jwt-token", "can_deploy", "environment:acme-core-dev")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !resp.Allowed {
		t.Errorf("expected allowed=true, got false")
	}
	if claims.Subject != "alice-id" {
		t.Errorf("expected subject alice-id, got %s", claims.Subject)
	}
}

func TestHandleTupleMutation_Insert(t *testing.T) {
	inserted := false
	mockFGA := &MockOpenFGAAdapter{
		WriteTuplesFunc: func(ctx context.Context, tuples []domain.Tuple) error {
			if len(tuples) == 1 && tuples[0].User == "user:bob" {
				inserted = true
			}
			return nil
		},
	}
	mockOIDC := &MockTokenValidator{}

	svc := service.NewAuthzService(mockFGA, mockOIDC)
	ctx := context.Background()

	err := svc.HandleTupleMutation(ctx, domain.TupleMutationEvent{
		Action: domain.ActionInsert,
		Tuple: domain.Tuple{
			User:     "user:bob",
			Relation: "maintainer",
			Object:   "project:acme-core",
		},
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !inserted {
		t.Errorf("expected WriteTuples to be called")
	}
}
