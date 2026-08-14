package service

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/domain"
)

type AuthzService struct {
	fgaClient      domain.OpenFGAPort
	tokenValidator domain.TokenValidatorPort
}

func NewAuthzService(fgaClient domain.OpenFGAPort, tokenValidator domain.TokenValidatorPort) *AuthzService {
	return &AuthzService{
		fgaClient:      fgaClient,
		tokenValidator: tokenValidator,
	}
}

func (s *AuthzService) CheckPermission(ctx context.Context, req domain.PermissionCheckRequest) (domain.PermissionCheckResponse, error) {
	if req.User == "" || req.Relation == "" || req.Object == "" {
		return domain.PermissionCheckResponse{Allowed: false}, errors.New("user, relation, and object are required")
	}

	allowed, err := s.fgaClient.Check(ctx, req)
	if err != nil {
		return domain.PermissionCheckResponse{Allowed: false}, fmt.Errorf("openfga check error: %w", err)
	}

	return domain.PermissionCheckResponse{
		Allowed:    allowed,
		Resolution: fmt.Sprintf("evaluated relation %s on %s for %s", req.Relation, req.Object, req.User),
	}, nil
}

func (s *AuthzService) BatchCheckPermission(ctx context.Context, req domain.BatchCheckRequest) (domain.BatchCheckResponse, error) {
	if len(req.Checks) == 0 {
		return domain.BatchCheckResponse{Results: []domain.PermissionCheckResponse{}}, nil
	}

	results, err := s.fgaClient.BatchCheck(ctx, req)
	if err != nil {
		return domain.BatchCheckResponse{}, fmt.Errorf("openfga batch check error: %w", err)
	}

	return domain.BatchCheckResponse{Results: results}, nil
}

func (s *AuthzService) HandleTupleMutation(ctx context.Context, event domain.TupleMutationEvent) error {
	if event.Tuple.User == "" || event.Tuple.Relation == "" || event.Tuple.Object == "" {
		return errors.New("invalid tuple in mutation event: missing user, relation, or object")
	}

	switch event.Action {
	case domain.ActionInsert:
		return s.fgaClient.WriteTuples(ctx, []domain.Tuple{event.Tuple})
	case domain.ActionDelete:
		return s.fgaClient.DeleteTuples(ctx, []domain.Tuple{event.Tuple})
	default:
		return fmt.Errorf("unsupported mutation action: %s", event.Action)
	}
}

func (s *AuthzService) ValidateAndCheck(ctx context.Context, tokenString string, relation string, object string) (domain.PermissionCheckResponse, *domain.TokenClaims, error) {
	if tokenString == "" {
		return domain.PermissionCheckResponse{Allowed: false}, nil, errors.New("missing authorization token")
	}

	// Strip "Bearer " prefix if present
	token := strings.TrimPrefix(tokenString, "Bearer ")
	token = strings.TrimSpace(token)

	claims, err := s.tokenValidator.ValidateToken(ctx, token)
	if err != nil {
		return domain.PermissionCheckResponse{Allowed: false}, nil, fmt.Errorf("invalid token: %w", err)
	}

	fgaUser := fmt.Sprintf("user:%s", claims.Subject)
	if claims.Subject == "" && claims.Email != "" {
		fgaUser = fmt.Sprintf("user:%s", claims.Email)
	}

	resp, err := s.CheckPermission(ctx, domain.PermissionCheckRequest{
		User:     fgaUser,
		Relation: relation,
		Object:   object,
	})
	if err != nil {
		return domain.PermissionCheckResponse{Allowed: false}, claims, err
	}

	return resp, claims, nil
}
