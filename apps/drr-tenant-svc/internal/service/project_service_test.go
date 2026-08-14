package service_test

import (
	"context"
	"testing"

	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/adapter/memory"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/domain"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/service"
)

func TestProjectLifecycleAndQuotas(t *testing.T) {
	ctx := context.Background()
	tenantRepo := memory.NewInMemoryTenantRepo()
	projectRepo := memory.NewInMemoryProjectRepo()
	publisher := &mockPublisher{}
	authz := &mockAuthzClient{}

	tenantSvc := service.NewTenantService(tenantRepo, publisher, authz)
	projectSvc := service.NewProjectService(projectRepo, tenantRepo, publisher, authz)

	// Create Tenant with MaxProjects = 2
	quotas := domain.ResourceQuotas{MaxProjects: 2}
	_, err := tenantSvc.CreateTenant(ctx, service.CreateTenantInput{
		ID:     "tnt-demo",
		Name:   "tnt-demo",
		Quotas: &quotas,
	})
	if err != nil {
		t.Fatalf("unexpected error creating tenant: %v", err)
	}

	// 1. Create Project 1
	p1, err := projectSvc.CreateProject(ctx, service.CreateProjectInput{
		ID:          "proj-1",
		TenantID:    "tnt-demo",
		Name:        "proj-1",
		Description: "First Project",
		OwnerUserID: "bob",
	})
	if err != nil {
		t.Fatalf("unexpected error creating project 1: %v", err)
	}
	if p1.Status != domain.ProjectStatusActive {
		t.Errorf("expected ACTIVE, got %s", p1.Status)
	}

	// 2. Create Project 2
	_, err = projectSvc.CreateProject(ctx, service.CreateProjectInput{
		ID:       "proj-2",
		TenantID: "tnt-demo",
		Name:     "proj-2",
	})
	if err != nil {
		t.Fatalf("unexpected error creating project 2: %v", err)
	}

	// 3. Create Project 3 - Must fail due to Quotas MaxProjects=2
	_, err = projectSvc.CreateProject(ctx, service.CreateProjectInput{
		ID:       "proj-3",
		TenantID: "tnt-demo",
		Name:     "proj-3",
	})
	if err == nil {
		t.Errorf("expected error exceeding project quotas, got nil")
	}

	// 4. Delete Project
	err = projectSvc.DeleteProject(ctx, "tnt-demo", "proj-1")
	if err != nil {
		t.Fatalf("unexpected error deleting project: %v", err)
	}

	// Now creating Project 3 succeeds because count is 1 < 2
	_, err = projectSvc.CreateProject(ctx, service.CreateProjectInput{
		ID:       "proj-3",
		TenantID: "tnt-demo",
		Name:     "proj-3",
	})
	if err != nil {
		t.Fatalf("expected project 3 to succeed after deletion, got %v", err)
	}
}
