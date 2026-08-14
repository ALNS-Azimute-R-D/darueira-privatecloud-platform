package k8s

import (
	"context"
	"fmt"

	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/domain"
)

type DirectK8sApplier struct{}

func NewDirectK8sApplier() *DirectK8sApplier {
	return &DirectK8sApplier{}
}

func (a *DirectK8sApplier) ApplyEnvironmentNamespace(ctx context.Context, env *domain.Environment) error {
	fmt.Printf("[K8S-APPLIER] Provisioning namespace: %s (Tenant: %s, Project: %s, Env: %s, PSS: restricted)\n",
		env.Namespace, env.TenantID, env.ProjectID, env.Type)
	return nil
}

func (a *DirectK8sApplier) DeleteEnvironmentNamespace(ctx context.Context, env *domain.Environment) error {
	fmt.Printf("[K8S-APPLIER] Deleting namespace: %s\n", env.Namespace)
	return nil
}
