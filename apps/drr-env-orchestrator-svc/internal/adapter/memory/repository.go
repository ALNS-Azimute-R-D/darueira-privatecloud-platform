package memory

import (
	"context"
	"errors"
	"fmt"
	"sync"

	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/domain"
)

type InMemoryEnvRepo struct {
	mu   sync.RWMutex
	envs map[string]*domain.Environment
}

func NewInMemoryEnvRepo() *InMemoryEnvRepo {
	return &InMemoryEnvRepo{
		envs: make(map[string]*domain.Environment),
	}
}

func (r *InMemoryEnvRepo) Create(ctx context.Context, env *domain.Environment) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.envs[env.ID]; exists {
		return fmt.Errorf("environment '%s' already exists", env.ID)
	}
	r.envs[env.ID] = env
	return nil
}

func (r *InMemoryEnvRepo) GetByID(ctx context.Context, id string) (*domain.Environment, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	env, exists := r.envs[id]
	if !exists {
		return nil, errors.New("environment not found")
	}
	return env, nil
}

func (r *InMemoryEnvRepo) List(ctx context.Context, tenantID, projectID string) ([]*domain.Environment, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	list := make([]*domain.Environment, 0)
	for _, env := range r.envs {
		matchTenant := tenantID == "" || env.TenantID == tenantID
		matchProject := projectID == "" || env.ProjectID == projectID
		if matchTenant && matchProject {
			list = append(list, env)
		}
	}
	return list, nil
}

func (r *InMemoryEnvRepo) Update(ctx context.Context, env *domain.Environment) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.envs[env.ID]; !exists {
		return errors.New("environment not found")
	}
	r.envs[env.ID] = env
	return nil
}

func (r *InMemoryEnvRepo) Delete(ctx context.Context, id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.envs[id]; !exists {
		return errors.New("environment not found")
	}
	delete(r.envs, id)
	return nil
}
