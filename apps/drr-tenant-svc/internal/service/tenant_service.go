package service

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/domain"
)

type TenantService struct {
	tenantRepo domain.TenantRepository
	publisher  domain.EventPublisher
	authz      domain.AuthzClient
}

func NewTenantService(tenantRepo domain.TenantRepository, publisher domain.EventPublisher, authz domain.AuthzClient) *TenantService {
	return &TenantService{
		tenantRepo: tenantRepo,
		publisher:  publisher,
		authz:      authz,
	}
}

type CreateTenantInput struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	DisplayName string                 `json:"displayName"`
	Description string                 `json:"description"`
	Quotas      *domain.ResourceQuotas `json:"quotas,omitempty"`
	Labels      map[string]string      `json:"labels,omitempty"`
	AdminUserID string                 `json:"adminUserId,omitempty"`
}

func (s *TenantService) CreateTenant(ctx context.Context, input CreateTenantInput) (*domain.Tenant, error) {
	existing, err := s.tenantRepo.GetByID(ctx, input.ID)
	if err == nil && existing != nil {
		return nil, fmt.Errorf("tenant with id '%s' already exists", input.ID)
	}

	tenant, err := domain.NewTenant(input.ID, input.Name, input.DisplayName, input.Description, input.Quotas, input.Labels)
	if err != nil {
		return nil, err
	}

	if err := s.tenantRepo.Create(ctx, tenant); err != nil {
		return nil, fmt.Errorf("failed to persist tenant: %w", err)
	}

	// Synchronize Admin ReBAC tuple in OpenFGA if admin user provided
	if input.AdminUserID != "" && s.authz != nil {
		userEntity := fmt.Sprintf("user:%s", input.AdminUserID)
		tenantEntity := fmt.Sprintf("tenant:%s", tenant.ID)
		_ = s.authz.WriteTuple(ctx, userEntity, "admin", tenantEntity)
	}

	// Publish domain event
	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-tenant-create-%s-%d", tenant.ID, time.Now().UnixNano()),
			Type:      domain.EventTypeTenantCreated,
			TenantID:  tenant.ID,
			Payload:   tenant,
			Timestamp: time.Now().UTC(),
		})
	}

	return tenant, nil
}

func (s *TenantService) GetTenant(ctx context.Context, id string) (*domain.Tenant, error) {
	tenant, err := s.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("tenant not found: %w", err)
	}
	return tenant, nil
}

func (s *TenantService) ListTenants(ctx context.Context) ([]*domain.Tenant, error) {
	return s.tenantRepo.List(ctx)
}

func (s *TenantService) UpdateQuotas(ctx context.Context, id string, quotas domain.ResourceQuotas) (*domain.Tenant, error) {
	tenant, err := s.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("tenant not found: %w", err)
	}

	tenant.UpdateQuotas(quotas)
	if err := s.tenantRepo.Update(ctx, tenant); err != nil {
		return nil, fmt.Errorf("failed to update tenant quotas: %w", err)
	}

	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-tenant-quota-%s-%d", tenant.ID, time.Now().UnixNano()),
			Type:      domain.EventTypeTenantUpdated,
			TenantID:  tenant.ID,
			Payload:   tenant,
			Timestamp: time.Now().UTC(),
		})
	}

	return tenant, nil
}

func (s *TenantService) SuspendTenant(ctx context.Context, id string) (*domain.Tenant, error) {
	tenant, err := s.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("tenant not found: %w", err)
	}

	tenant.Suspend()
	if err := s.tenantRepo.Update(ctx, tenant); err != nil {
		return nil, fmt.Errorf("failed to suspend tenant: %w", err)
	}

	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-tenant-status-%s-%d", tenant.ID, time.Now().UnixNano()),
			Type:      domain.EventTypeTenantStatusChanged,
			TenantID:  tenant.ID,
			Payload:   tenant,
			Timestamp: time.Now().UTC(),
		})
	}

	return tenant, nil
}

func (s *TenantService) ActivateTenant(ctx context.Context, id string) (*domain.Tenant, error) {
	tenant, err := s.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("tenant not found: %w", err)
	}

	tenant.Activate()
	if err := s.tenantRepo.Update(ctx, tenant); err != nil {
		return nil, fmt.Errorf("failed to activate tenant: %w", err)
	}

	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-tenant-status-%s-%d", tenant.ID, time.Now().UnixNano()),
			Type:      domain.EventTypeTenantStatusChanged,
			TenantID:  tenant.ID,
			Payload:   tenant,
			Timestamp: time.Now().UTC(),
		})
	}

	return tenant, nil
}

func (s *TenantService) DeleteTenant(ctx context.Context, id string) error {
	tenant, err := s.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return errors.New("tenant not found")
	}

	if err := s.tenantRepo.Delete(ctx, id); err != nil {
		return fmt.Errorf("failed to delete tenant: %w", err)
	}

	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-tenant-delete-%s-%d", id, time.Now().UnixNano()),
			Type:      domain.EventTypeTenantDeleted,
			TenantID:  id,
			Payload:   tenant,
			Timestamp: time.Now().UTC(),
		})
	}

	return nil
}
