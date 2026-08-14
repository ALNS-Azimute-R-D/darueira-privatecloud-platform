package service_test

import (
	"context"
	"testing"

	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/adapter/memory"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/domain"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/service"
)

type mockAuthzClient struct {
	tuples []string
}

func (m *mockAuthzClient) WriteTuple(ctx context.Context, user, relation, object string) error {
	m.tuples = append(m.tuples, user+":"+relation+":"+object)
	return nil
}

func (m *mockAuthzClient) DeleteTuple(ctx context.Context, user, relation, object string) error {
	return nil
}

type mockPublisher struct {
	events []domain.DomainEvent
}

func (p *mockPublisher) Publish(event domain.DomainEvent) error {
	p.events = append(p.events, event)
	return nil
}

func TestTenantLifecycle(t *testing.T) {
	ctx := context.Background()
	tenantRepo := memory.NewInMemoryTenantRepo()
	publisher := &mockPublisher{}
	authz := &mockAuthzClient{}

	svc := service.NewTenantService(tenantRepo, publisher, authz)

	// 1. Create Tenant
	tenant, err := svc.CreateTenant(ctx, service.CreateTenantInput{
		ID:          "acme-corp",
		Name:        "acme-corp",
		DisplayName: "Acme Corporation",
		Description: "Primary business unit",
		AdminUserID: "alice",
	})
	if err != nil {
		t.Fatalf("unexpected error creating tenant: %v", err)
	}
	if tenant.Status != domain.TenantStatusActive {
		t.Errorf("expected status ACTIVE, got %s", tenant.Status)
	}
	if len(authz.tuples) != 1 || authz.tuples[0] != "user:alice:admin:tenant:acme-corp" {
		t.Errorf("expected tuple user:alice:admin:tenant:acme-corp, got %v", authz.tuples)
	}

	// 2. Prevent Duplicate Tenant
	_, err = svc.CreateTenant(ctx, service.CreateTenantInput{
		ID:   "acme-corp",
		Name: "acme-corp",
	})
	if err == nil {
		t.Errorf("expected error creating duplicate tenant, got nil")
	}

	// 3. Suspend & Activate
	tenant, err = svc.SuspendTenant(ctx, "acme-corp")
	if err != nil || tenant.Status != domain.TenantStatusSuspended {
		t.Errorf("expected status SUSPENDED, got %v, err=%v", tenant.Status, err)
	}

	tenant, err = svc.ActivateTenant(ctx, "acme-corp")
	if err != nil || tenant.Status != domain.TenantStatusActive {
		t.Errorf("expected status ACTIVE, got %v, err=%v", tenant.Status, err)
	}

	// 4. Update Quotas
	customQuotas := domain.ResourceQuotas{
		MaxCPUCores:     64,
		MaxMemoryGiB:    128,
		MaxStorageGiB:   1000,
		MaxEnvironments: 20,
		MaxProjects:     10,
	}
	tenant, err = svc.UpdateQuotas(ctx, "acme-corp", customQuotas)
	if err != nil || tenant.Quotas.MaxCPUCores != 64 {
		t.Errorf("expected max CPU 64, got %v, err=%v", tenant.Quotas.MaxCPUCores, err)
	}

	// 5. Delete Tenant
	err = svc.DeleteTenant(ctx, "acme-corp")
	if err != nil {
		t.Fatalf("unexpected error deleting tenant: %v", err)
	}
	_, err = svc.GetTenant(ctx, "acme-corp")
	if err == nil {
		t.Errorf("expected error retrieving deleted tenant, got nil")
	}
}
