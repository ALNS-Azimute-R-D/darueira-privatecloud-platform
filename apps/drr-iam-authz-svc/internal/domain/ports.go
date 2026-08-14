package domain

import (
	"context"
)

// OpenFGAPort defines outbound operations against OpenFGA engine
type OpenFGAPort interface {
	Check(ctx context.Context, req PermissionCheckRequest) (bool, error)
	BatchCheck(ctx context.Context, req BatchCheckRequest) ([]PermissionCheckResponse, error)
	WriteTuples(ctx context.Context, tuples []Tuple) error
	DeleteTuples(ctx context.Context, tuples []Tuple) error
	ListObjects(ctx context.Context, user string, relation string, objectType string) ([]string, error)
}

// TokenValidatorPort defines outbound JWT / OIDC token verification
type TokenValidatorPort interface {
	ValidateToken(ctx context.Context, tokenString string) (*TokenClaims, error)
}

// AuthzServicePort defines inbound business logic interface
type AuthzServicePort interface {
	CheckPermission(ctx context.Context, req PermissionCheckRequest) (PermissionCheckResponse, error)
	BatchCheckPermission(ctx context.Context, req BatchCheckRequest) (BatchCheckResponse, error)
	HandleTupleMutation(ctx context.Context, event TupleMutationEvent) error
	ValidateAndCheck(ctx context.Context, tokenString string, relation string, object string) (PermissionCheckResponse, *TokenClaims, error)
}
