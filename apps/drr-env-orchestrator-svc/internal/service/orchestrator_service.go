package service

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/domain"
)

type OrchestratorService struct {
	envRepo    domain.EnvironmentRepository
	k8sApplier domain.K8sManifestApplier
	publisher  domain.EventPublisher
	authz      domain.AuthzClient
}

func NewOrchestratorService(envRepo domain.EnvironmentRepository, k8sApplier domain.K8sManifestApplier, publisher domain.EventPublisher, authz domain.AuthzClient) *OrchestratorService {
	return &OrchestratorService{
		envRepo:    envRepo,
		k8sApplier: k8sApplier,
		publisher:  publisher,
		authz:      authz,
	}
}

type CreateEnvironmentInput struct {
	TenantID       string                       `json:"tenantId"`
	ProjectID      string                       `json:"projectId"`
	Name           string                       `json:"name"`
	Type           domain.EnvironmentType       `json:"type"`
	Resources      *domain.EnvironmentResources `json:"resources,omitempty"`
	OperatorUserID string                       `json:"operatorUserId,omitempty"`
	Labels         map[string]string            `json:"labels,omitempty"`
}

func (s *OrchestratorService) CreateEnvironment(ctx context.Context, input CreateEnvironmentInput) (*domain.Environment, error) {
	env, err := domain.NewEnvironment(input.TenantID, input.ProjectID, input.Name, input.Type, input.Resources, input.Labels)
	if err != nil {
		return nil, err
	}

	existing, _ := s.envRepo.GetByID(ctx, env.ID)
	if existing != nil {
		return nil, fmt.Errorf("environment '%s' already exists", env.ID)
	}

	// 1. Persist initial pending environment
	if err := s.envRepo.Create(ctx, env); err != nil {
		return nil, fmt.Errorf("failed to save environment: %w", err)
	}

	// 2. Synchronize ReBAC hierarchy tuples:
	// - project:P project environment:E
	// - user:U operator environment:E (if operator provided)
	if s.authz != nil {
		projectEntity := fmt.Sprintf("project:%s", env.ProjectID)
		envEntity := fmt.Sprintf("environment:%s", env.ID)
		_ = s.authz.WriteTuple(ctx, projectEntity, "project", envEntity)

		if input.OperatorUserID != "" {
			userEntity := fmt.Sprintf("user:%s", input.OperatorUserID)
			_ = s.authz.WriteTuple(ctx, userEntity, "operator", envEntity)
		}
	}

	// 3. Provision K8s namespace and isolation policy
	if s.k8sApplier != nil {
		if err := s.k8sApplier.ApplyEnvironmentNamespace(ctx, env); err != nil {
			return nil, fmt.Errorf("failed to apply Kubernetes namespace: %w", err)
		}
	}

	// 4. Mark provisioned
	env.MarkProvisioned()
	_ = s.envRepo.Update(ctx, env)

	// 5. Publish event
	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-env-create-%s-%d", env.ID, time.Now().UnixNano()),
			Type:      domain.EventTypeEnvironmentProvisioned,
			TenantID:  env.TenantID,
			ProjectID: env.ProjectID,
			EnvID:     env.ID,
			Payload:   env,
			Timestamp: time.Now().UTC(),
		})
	}

	return env, nil
}

func (s *OrchestratorService) GetEnvironment(ctx context.Context, id string) (*domain.Environment, error) {
	env, err := s.envRepo.GetByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("environment not found: %w", err)
	}
	return env, nil
}

func (s *OrchestratorService) ListEnvironments(ctx context.Context, tenantID, projectID string) ([]*domain.Environment, error) {
	return s.envRepo.List(ctx, tenantID, projectID)
}

type DeployComponentInput struct {
	Name     string            `json:"name"`
	Image    string            `json:"image"`
	Port     int               `json:"port"`
	Replicas int32             `json:"replicas"`
	EnvVars  map[string]string `json:"envVars,omitempty"`
}

type DeployEnvironmentInput struct {
	EnvID       string                 `json:"envId"`
	Components  []DeployComponentInput `json:"components"`
	TriggeredBy string                 `json:"triggeredBy"`
	CommitHash  string                 `json:"commitHash"`
}

type DeploymentResult struct {
	Environment *domain.Environment `json:"environment"`
	PipelineRun *domain.PipelineRun `json:"pipelineRun"`
	GitOpsSync  *domain.GitOpsSync  `json:"gitOpsSync"`
}

func (s *OrchestratorService) DeployEnvironment(ctx context.Context, input DeployEnvironmentInput) (*DeploymentResult, error) {
	env, err := s.envRepo.GetByID(ctx, input.EnvID)
	if err != nil {
		return nil, fmt.Errorf("environment '%s' not found: %w", input.EnvID, err)
	}

	env.MarkDeploying()
	_ = s.envRepo.Update(ctx, env)

	// Add/update components
	for _, compInput := range input.Components {
		comp, err := domain.NewComponent(compInput.Name, compInput.Image, compInput.Port, compInput.Replicas, compInput.EnvVars)
		if err != nil {
			return nil, err
		}
		env.AddComponent(comp)
	}

	env.MarkActive()
	if err := s.envRepo.Update(ctx, env); err != nil {
		return nil, fmt.Errorf("failed to update environment: %w", err)
	}

	commitHash := input.CommitHash
	if commitHash == "" {
		commitHash = "main-8877387"
	}
	triggeredBy := input.TriggeredBy
	if triggeredBy == "" {
		triggeredBy = "darctl-orchestrator"
	}

	pipelineRun := &domain.PipelineRun{
		ID:          fmt.Sprintf("plr-%s-%d", env.ID, time.Now().Unix()),
		TenantID:    env.TenantID,
		ProjectID:   env.ProjectID,
		EnvID:       env.ID,
		Status:      "Succeeded",
		CommitHash:  commitHash,
		TriggeredBy: triggeredBy,
		StartTime:   time.Now().UTC().Add(-2 * time.Minute),
		EndTime:     time.Now().UTC(),
	}

	gitOpsSync := &domain.GitOpsSync{
		AppName:      fmt.Sprintf("app-%s", env.ID),
		Namespace:    env.Namespace,
		SyncStatus:   "Synced",
		HealthStatus: "Healthy",
		LastSyncedAt: time.Now().UTC(),
	}

	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-env-deploy-%s-%d", env.ID, time.Now().UnixNano()),
			Type:      domain.EventTypeEnvironmentActive,
			TenantID:  env.TenantID,
			ProjectID: env.ProjectID,
			EnvID:     env.ID,
			Payload:   env,
			Timestamp: time.Now().UTC(),
		})
	}

	return &DeploymentResult{
		Environment: env,
		PipelineRun: pipelineRun,
		GitOpsSync:  gitOpsSync,
	}, nil
}

func (s *OrchestratorService) DeleteEnvironment(ctx context.Context, id string) error {
	env, err := s.envRepo.GetByID(ctx, id)
	if err != nil {
		return errors.New("environment not found")
	}

	if s.k8sApplier != nil {
		_ = s.k8sApplier.DeleteEnvironmentNamespace(ctx, env)
	}

	if s.authz != nil {
		projectEntity := fmt.Sprintf("project:%s", env.ProjectID)
		envEntity := fmt.Sprintf("environment:%s", env.ID)
		_ = s.authz.DeleteTuple(ctx, projectEntity, "project", envEntity)
	}

	if err := s.envRepo.Delete(ctx, id); err != nil {
		return fmt.Errorf("failed to delete environment: %w", err)
	}

	if s.publisher != nil {
		_ = s.publisher.Publish(domain.DomainEvent{
			ID:        fmt.Sprintf("evt-env-delete-%s-%d", id, time.Now().UnixNano()),
			Type:      domain.EventTypeEnvironmentDeleted,
			TenantID:  env.TenantID,
			ProjectID: env.ProjectID,
			EnvID:     id,
			Payload:   env,
			Timestamp: time.Now().UTC(),
		})
	}

	return nil
}
