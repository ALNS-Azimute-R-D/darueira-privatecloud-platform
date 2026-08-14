package memory

import (
	"context"
	"errors"
	"fmt"
	"sync"

	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/domain"
)

type InMemoryTenantRepo struct {
	mu      sync.RWMutex
	tenants map[string]*domain.Tenant
}

func NewInMemoryTenantRepo() *InMemoryTenantRepo {
	return &InMemoryTenantRepo{
		tenants: make(map[string]*domain.Tenant),
	}
}

func (r *InMemoryTenantRepo) Create(ctx context.Context, tenant *domain.Tenant) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.tenants[tenant.ID]; exists {
		return fmt.Errorf("tenant with ID '%s' already exists", tenant.ID)
	}
	r.tenants[tenant.ID] = tenant
	return nil
}

func (r *InMemoryTenantRepo) GetByID(ctx context.Context, id string) (*domain.Tenant, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	t, exists := r.tenants[id]
	if !exists {
		return nil, errors.New("tenant not found")
	}
	return t, nil
}

func (r *InMemoryTenantRepo) List(ctx context.Context) ([]*domain.Tenant, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	list := make([]*domain.Tenant, 0, len(r.tenants))
	for _, t := range r.tenants {
		list = append(list, t)
	}
	return list, nil
}

func (r *InMemoryTenantRepo) Update(ctx context.Context, tenant *domain.Tenant) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.tenants[tenant.ID]; !exists {
		return errors.New("tenant not found")
	}
	r.tenants[tenant.ID] = tenant
	return nil
}

func (r *InMemoryTenantRepo) Delete(ctx context.Context, id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.tenants[id]; !exists {
		return errors.New("tenant not found")
	}
	delete(r.tenants, id)
	return nil
}

type InMemoryProjectRepo struct {
	mu       sync.RWMutex
	projects map[string]*domain.Project // key: tenantID:projectID
}

func NewInMemoryProjectRepo() *InMemoryProjectRepo {
	return &InMemoryProjectRepo{
		projects: make(map[string]*domain.Project),
	}
}

func (r *InMemoryProjectRepo) Create(ctx context.Context, project *domain.Project) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	key := fmt.Sprintf("%s:%s", project.TenantID, project.ID)
	if _, exists := r.projects[key]; exists {
		return fmt.Errorf("project '%s' already exists in tenant '%s'", project.ID, project.TenantID)
	}
	r.projects[key] = project
	return nil
}

func (r *InMemoryProjectRepo) GetByID(ctx context.Context, tenantID, projectID string) (*domain.Project, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	key := fmt.Sprintf("%s:%s", tenantID, projectID)
	p, exists := r.projects[key]
	if !exists {
		return nil, errors.New("project not found")
	}
	return p, nil
}

func (r *InMemoryProjectRepo) ListByTenant(ctx context.Context, tenantID string) ([]*domain.Project, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	list := make([]*domain.Project, 0)
	for _, p := range r.projects {
		if p.TenantID == tenantID {
			list = append(list, p)
		}
	}
	return list, nil
}

func (r *InMemoryProjectRepo) Update(ctx context.Context, project *domain.Project) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	key := fmt.Sprintf("%s:%s", project.TenantID, project.ID)
	if _, exists := r.projects[key]; !exists {
		return errors.New("project not found")
	}
	r.projects[key] = project
	return nil
}

func (r *InMemoryProjectRepo) Delete(ctx context.Context, tenantID, projectID string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	key := fmt.Sprintf("%s:%s", tenantID, projectID)
	if _, exists := r.projects[key]; !exists {
		return errors.New("project not found")
	}
	delete(r.projects, key)
	return nil
}

type InMemoryMemberRepo struct {
	mu      sync.RWMutex
	members map[string]*domain.TenantMember // key: tenantID:userID
}

func NewInMemoryMemberRepo() *InMemoryMemberRepo {
	return &InMemoryMemberRepo{
		members: make(map[string]*domain.TenantMember),
	}
}

func (r *InMemoryMemberRepo) Add(ctx context.Context, member *domain.TenantMember) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	key := fmt.Sprintf("%s:%s", member.TenantID, member.UserID)
	r.members[key] = member
	return nil
}

func (r *InMemoryMemberRepo) Get(ctx context.Context, tenantID, userID string) (*domain.TenantMember, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	key := fmt.Sprintf("%s:%s", tenantID, userID)
	m, exists := r.members[key]
	if !exists {
		return nil, errors.New("member not found")
	}
	return m, nil
}

func (r *InMemoryMemberRepo) ListByTenant(ctx context.Context, tenantID string) ([]*domain.TenantMember, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	list := make([]*domain.TenantMember, 0)
	for _, m := range r.members {
		if m.TenantID == tenantID {
			list = append(list, m)
		}
	}
	return list, nil
}

func (r *InMemoryMemberRepo) Remove(ctx context.Context, tenantID, userID string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	key := fmt.Sprintf("%s:%s", tenantID, userID)
	if _, exists := r.members[key]; !exists {
		return errors.New("member not found")
	}
	delete(r.members, key)
	return nil
}
