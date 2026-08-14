package service_test

import (
	"context"
	"testing"

	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/adapter/memory"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/domain"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/service"
)

func TestMemberLifecycleAndReBAC(t *testing.T) {
	ctx := context.Background()
	tenantRepo := memory.NewInMemoryTenantRepo()
	memberRepo := memory.NewInMemoryMemberRepo()
	publisher := &mockPublisher{}
	authz := &mockAuthzClient{}

	tenantSvc := service.NewTenantService(tenantRepo, publisher, authz)
	memberSvc := service.NewMemberService(memberRepo, tenantRepo, publisher, authz)

	_, err := tenantSvc.CreateTenant(ctx, service.CreateTenantInput{
		ID:   "tnt-fintech",
		Name: "tnt-fintech",
	})
	if err != nil {
		t.Fatalf("unexpected error creating tenant: %v", err)
	}

	// 1. Add Member as Admin
	member, err := memberSvc.AddMember(ctx, service.AddMemberInput{
		TenantID: "tnt-fintech",
		UserID:   "carol",
		Role:     domain.TenantRoleAdmin,
	})
	if err != nil {
		t.Fatalf("unexpected error adding member: %v", err)
	}
	if member.Role != domain.TenantRoleAdmin {
		t.Errorf("expected role admin, got %s", member.Role)
	}

	// 2. Add Member as Regular Member
	_, err = memberSvc.AddMember(ctx, service.AddMemberInput{
		TenantID: "tnt-fintech",
		UserID:   "david",
		Role:     domain.TenantRoleMember,
	})
	if err != nil {
		t.Fatalf("unexpected error adding member: %v", err)
	}

	// 3. List Members
	members, err := memberSvc.ListMembers(ctx, "tnt-fintech")
	if err != nil || len(members) != 2 {
		t.Fatalf("expected 2 members, got %d, err=%v", len(members), err)
	}

	// 4. Remove Member
	err = memberSvc.RemoveMember(ctx, "tnt-fintech", "carol")
	if err != nil {
		t.Fatalf("unexpected error removing member: %v", err)
	}

	members, _ = memberSvc.ListMembers(ctx, "tnt-fintech")
	if len(members) != 1 {
		t.Errorf("expected 1 member after removal, got %d", len(members))
	}
}
