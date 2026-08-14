package service

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/domain"
)

type MemberService struct {
	memberRepo domain.MemberRepository
	tenantRepo domain.TenantRepository
	publisher  domain.EventPublisher
	authz      domain.AuthzClient
}

func NewMemberService(memberRepo domain.MemberRepository, tenantRepo domain.TenantRepository, publisher domain.EventPublisher, authz domain.AuthzClient) *MemberService {
	return &MemberService{
		memberRepo: memberRepo,
		tenantRepo: tenantRepo,
		publisher:  publisher,
		authz:      authz,
	}
}

type AddMemberInput struct {
	TenantID string            `json:"tenantId"`
	UserID   string            `json:"userId"`
	Role     domain.TenantRole `json:"role"`
}

func (s *MemberService) AddMember(ctx context.Context, input AddMemberInput) (*domain.TenantMember, error) {
	// Verify tenant exists
	tenant, err := s.tenantRepo.GetByID(ctx, input.TenantID)
	if err != nil || tenant == nil {
		return nil, fmt.Errorf("tenant '%s' not found", input.TenantID)
	}

	member, err := domain.NewTenantMember(input.TenantID, input.UserID, input.Role)
	if err != nil {
		return nil, err
	}

	if err := s.memberRepo.Add(ctx, member); err != nil {
		return nil, fmt.Errorf("failed to persist tenant member: %w", err)
	}

	// Synchronize ReBAC tuple in OpenFGA: user:X [role] tenant:Y
	if s.authz != nil {
		userEntity := fmt.Sprintf("user:%s", input.UserID)
		tenantEntity := fmt.Sprintf("tenant:%s", input.TenantID)
		_ = s.authz.WriteTuple(ctx, userEntity, string(input.Role), tenantEntity)
	}

	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-member-add-%s-%s-%d", input.TenantID, input.UserID, time.Now().UnixNano()),
			Type:      domain.EventTypeMemberAssigned,
			TenantID:  input.TenantID,
			Payload:   member,
			Timestamp: time.Now().UTC(),
		})
	}

	return member, nil
}

func (s *MemberService) ListMembers(ctx context.Context, tenantID string) ([]*domain.TenantMember, error) {
	return s.memberRepo.ListByTenant(ctx, tenantID)
}

func (s *MemberService) RemoveMember(ctx context.Context, tenantID, userID string) error {
	existing, err := s.memberRepo.Get(ctx, tenantID, userID)
	if err != nil || existing == nil {
		return errors.New("member not found in tenant")
	}

	if err := s.memberRepo.Remove(ctx, tenantID, userID); err != nil {
		return fmt.Errorf("failed to remove member: %w", err)
	}

	// Remove OpenFGA tuple
	if s.authz != nil {
		userEntity := fmt.Sprintf("user:%s", userID)
		tenantEntity := fmt.Sprintf("tenant:%s", tenantID)
		_ = s.authz.DeleteTuple(ctx, userEntity, string(existing.Role), tenantEntity)
	}

	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-member-rm-%s-%s-%d", tenantID, userID, time.Now().UnixNano()),
			Type:      domain.EventTypeMemberRemoved,
			TenantID:  tenantID,
			Payload:   existing,
			Timestamp: time.Now().UTC(),
		})
	}

	return nil
}
