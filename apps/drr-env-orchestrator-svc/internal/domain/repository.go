package domain

import "context"

type EnvironmentRepository interface {
	Create(ctx context.Context, env *Environment) error
	GetByID(ctx context.Context, id string) (*Environment, error)
	List(ctx context.Context, tenantID, projectID string) ([]*Environment, error)
	Update(ctx context.Context, env *Environment) error
	Delete(ctx context.Context, id string) error
}

type AuthzClient interface {
	WriteTuple(ctx context.Context, user, relation, object string) error
	DeleteTuple(ctx context.Context, user, relation, object string) error
}

type K8sManifestApplier interface {
	ApplyEnvironmentNamespace(ctx context.Context, env *Environment) error
	DeleteEnvironmentNamespace(ctx context.Context, env *Environment) error
}
