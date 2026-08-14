package domain

import "context"

type TenantRepository interface {
	Create(ctx context.Context, tenant *Tenant) error
	GetByID(ctx context.Context, id string) (*Tenant, error)
	List(ctx context.Context) ([]*Tenant, error)
	Update(ctx context.Context, tenant *Tenant) error
	Delete(ctx context.Context, id string) error
}

type ProjectRepository interface {
	Create(ctx context.Context, project *Project) error
	GetByID(ctx context.Context, tenantID, projectID string) (*Project, error)
	ListByTenant(ctx context.Context, tenantID string) ([]*Project, error)
	Update(ctx context.Context, project *Project) error
	Delete(ctx context.Context, tenantID, projectID string) error
}

type MemberRepository interface {
	Add(ctx context.Context, member *TenantMember) error
	Get(ctx context.Context, tenantID, userID string) (*TenantMember, error)
	ListByTenant(ctx context.Context, tenantID string) ([]*TenantMember, error)
	Remove(ctx context.Context, tenantID, userID string) error
}

type AuthzClient interface {
	WriteTuple(ctx context.Context, user, relation, object string) error
	DeleteTuple(ctx context.Context, user, relation, object string) error
}
