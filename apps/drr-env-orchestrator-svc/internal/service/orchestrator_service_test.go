package service_test

import (
	"context"
	"testing"

	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/adapter/k8s"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/adapter/memory"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/domain"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/service"
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

func TestEnvironmentLifecycleAndDeployment(t *testing.T) {
	ctx := context.Background()
	envRepo := memory.NewInMemoryEnvRepo()
	k8sApplier := k8s.NewDirectK8sApplier()
	publisher := &mockPublisher{}
	authz := &mockAuthzClient{}

	svc := service.NewOrchestratorService(envRepo, k8sApplier, publisher, authz)

	// 1. Create Environment
	env, err := svc.CreateEnvironment(ctx, service.CreateEnvironmentInput{
		TenantID:       "acme",
		ProjectID:      "storefront",
		Name:           "dev",
		Type:           domain.EnvTypeDev,
		OperatorUserID: "dave",
	})
	if err != nil {
		t.Fatalf("unexpected error creating environment: %v", err)
	}
	if env.Status != domain.EnvStatusProvisioned {
		t.Errorf("expected PROVISIONED, got %s", env.Status)
	}
	if env.Namespace != "drr-tnt-acme-storefront-dev" {
		t.Errorf("expected namespace drr-tnt-acme-storefront-dev, got %s", env.Namespace)
	}

	// Verify ReBAC hierarchy tuple was written
	if len(authz.tuples) < 2 {
		t.Errorf("expected at least 2 tuples, got %v", authz.tuples)
	}

	// 2. Deploy Environment with Components
	result, err := svc.DeployEnvironment(ctx, service.DeployEnvironmentInput{
		EnvID: env.ID,
		Components: []service.DeployComponentInput{
			{
				Name:     "frontend-web",
				Image:    "nginx:1.27-alpine",
				Port:     80,
				Replicas: 2,
			},
		},
		TriggeredBy: "ci-bot",
	})
	if err != nil {
		t.Fatalf("unexpected error deploying environment: %v", err)
	}
	if result.Environment.Status != domain.EnvStatusActive {
		t.Errorf("expected ACTIVE, got %s", result.Environment.Status)
	}
	if len(result.Environment.Components) != 1 {
		t.Errorf("expected 1 component, got %d", len(result.Environment.Components))
	}
	if result.PipelineRun == nil || result.PipelineRun.Status != "Succeeded" {
		t.Errorf("expected Succeeded pipeline run, got %v", result.PipelineRun)
	}
	if result.GitOpsSync == nil || result.GitOpsSync.SyncStatus != "Synced" {
		t.Errorf("expected Synced GitOps status, got %v", result.GitOpsSync)
	}

	// 3. Delete Environment
	err = svc.DeleteEnvironment(ctx, env.ID)
	if err != nil {
		t.Fatalf("unexpected error deleting environment: %v", err)
	}
	_, err = svc.GetEnvironment(ctx, env.ID)
	if err == nil {
		t.Errorf("expected error getting deleted environment, got nil")
	}
}
