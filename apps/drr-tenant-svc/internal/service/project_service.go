package service

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/domain"
)

type ProjectService struct {
	projectRepo domain.ProjectRepository
	tenantRepo  domain.TenantRepository
	publisher   domain.EventPublisher
	authz       domain.AuthzClient
}

func NewProjectService(projectRepo domain.ProjectRepository, tenantRepo domain.TenantRepository, publisher domain.EventPublisher, authz domain.AuthzClient) *ProjectService {
	return &ProjectService{
		projectRepo: projectRepo,
		tenantRepo:  tenantRepo,
		publisher:   publisher,
		authz:       authz,
	}
}

type CreateProjectInput struct {
	ID          string            `json:"id"`
	TenantID    string            `json:"tenantId"`
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Labels      map[string]string `json:"labels,omitempty"`
	OwnerUserID string            `json:"ownerUserId,omitempty"`
}

func (s *ProjectService) CreateProject(ctx context.Context, input CreateProjectInput) (*domain.Project, error) {
	// 1. Verify parent tenant exists and is active
	tenant, err := s.tenantRepo.GetByID(ctx, input.TenantID)
	if err != nil || tenant == nil {
		return nil, fmt.Errorf("parent tenant '%s' not found", input.TenantID)
	}
	if tenant.Status != domain.TenantStatusActive {
		return nil, fmt.Errorf("parent tenant '%s' is not active (status: %s)", input.TenantID, tenant.Status)
	}

	// 2. Check quota limit for max projects
	existingProjects, _ := s.projectRepo.ListByTenant(ctx, input.TenantID)
	if len(existingProjects) >= tenant.Quotas.MaxProjects {
		return nil, fmt.Errorf("quota exceeded: tenant '%s' reached maximum allowed projects (%d)", input.TenantID, tenant.Quotas.MaxProjects)
	}

	// 3. Create project domain entity
	project, err := domain.NewProject(input.ID, input.TenantID, input.Name, input.Description, input.Labels)
	if err != nil {
		return nil, err
	}

	if err := s.projectRepo.Create(ctx, project); err != nil {
		return nil, fmt.Errorf("failed to persist project: %w", err)
	}

	// 4. Synchronize ReBAC hierarchy tuples in OpenFGA:
	// - tenant:X tenant project:Y
	// - user:Z owner project:Y (if owner provided)
	if s.authz != nil {
		tenantEntity := fmt.Sprintf("tenant:%s", input.TenantID)
		projectEntity := fmt.Sprintf("project:%s", project.ID)
		_ = s.authz.WriteTuple(ctx, tenantEntity, "tenant", projectEntity)

		if input.OwnerUserID != "" {
			userEntity := fmt.Sprintf("user:%s", input.OwnerUserID)
			_ = s.authz.WriteTuple(ctx, userEntity, "owner", projectEntity)
		}
	}

	// 5. Publish event
	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-proj-create-%s-%d", project.ID, time.Now().UnixNano()),
			Type:      domain.EventTypeProjectCreated,
			TenantID:  input.TenantID,
			Payload:   project,
			Timestamp: time.Now().UTC(),
		})
	}

	return project, nil
}

func (s *ProjectService) GetProject(ctx context.Context, tenantID, projectID string) (*domain.Project, error) {
	project, err := s.projectRepo.GetByID(ctx, tenantID, projectID)
	if err != nil {
		return nil, fmt.Errorf("project not found: %w", err)
	}
	return project, nil
}

func (s *ProjectService) ListProjects(ctx context.Context, tenantID string) ([]*domain.Project, error) {
	return s.projectRepo.ListByTenant(ctx, tenantID)
}

func (s *ProjectService) DeleteProject(ctx context.Context, tenantID, projectID string) error {
	project, err := s.projectRepo.GetByID(ctx, tenantID, projectID)
	if err != nil {
		return errors.New("project not found")
	}

	if err := s.projectRepo.Delete(ctx, tenantID, projectID); err != nil {
		return fmt.Errorf("failed to delete project: %w", err)
	}

	if s.authz != nil {
		tenantEntity := fmt.Sprintf("tenant:%s", tenantID)
		projectEntity := fmt.Sprintf("project:%s", projectID)
		_ = s.authz.DeleteTuple(ctx, tenantEntity, "tenant", projectEntity)
	}

	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-proj-delete-%s-%d", projectID, time.Now().UnixNano()),
			Type:      domain.EventTypeProjectDeleted,
			TenantID:  tenantID,
			Payload:   project,
			Timestamp: time.Now().UTC(),
		})
	}

	return nil
}
