package openfga

import (
	"context"
	"fmt"
	"sync"

	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/domain"
	"github.com/openfga/go-sdk/client"
)

type OpenFGAAdapter struct {
	apiClient *client.OpenFgaClient
	storeID   string
	modelID   string

	// Local in-memory fallback cache for development/testing when external store is offline
	mu        sync.RWMutex
	memTuples map[string]bool
}

func NewOpenFGAAdapter(apiUrl string, storeID string, modelID string) (*OpenFGAAdapter, error) {
	var fgaClient *client.OpenFgaClient
	var err error

	if apiUrl != "" && storeID != "" {
		cfg := &client.ClientConfiguration{
			ApiUrl:               apiUrl,
			StoreId:              storeID,
			AuthorizationModelId: modelID,
		}
		fgaClient, err = client.NewSdkClient(cfg)
		if err != nil {
			return nil, fmt.Errorf("failed to initialize OpenFGA SDK client: %w", err)
		}
	}

	return &OpenFGAAdapter{
		apiClient: fgaClient,
		storeID:   storeID,
		modelID:   modelID,
		memTuples: make(map[string]bool),
	}, nil
}

func (a *OpenFGAAdapter) Check(ctx context.Context, req domain.PermissionCheckRequest) (bool, error) {
	if a.apiClient != nil {
		var contextualTuples []client.ClientContextualTupleKey
		for _, t := range req.ContextualTuples {
			contextualTuples = append(contextualTuples, client.ClientContextualTupleKey{
				User:     t.User,
				Relation: t.Relation,
				Object:   t.Object,
			})
		}

		body := client.ClientCheckRequest{
			User:             req.User,
			Relation:         req.Relation,
			Object:           req.Object,
			ContextualTuples: contextualTuples,
		}

		resp, err := a.apiClient.Check(ctx).Body(body).Execute()
		if err != nil {
			return false, fmt.Errorf("OpenFGA SDK check failed: %w", err)
		}

		return resp.GetAllowed(), nil
	}

	// Fallback to in-memory evaluation
	a.mu.RLock()
	defer a.mu.RUnlock()
	key := fmt.Sprintf("%s#%s@%s", req.Object, req.Relation, req.User)
	return a.memTuples[key], nil
}

func (a *OpenFGAAdapter) BatchCheck(ctx context.Context, req domain.BatchCheckRequest) ([]domain.PermissionCheckResponse, error) {
	results := make([]domain.PermissionCheckResponse, len(req.Checks))
	for i, chk := range req.Checks {
		allowed, err := a.Check(ctx, chk)
		if err != nil {
			results[i] = domain.PermissionCheckResponse{Allowed: false, Resolution: err.Error()}
		} else {
			results[i] = domain.PermissionCheckResponse{Allowed: allowed}
		}
	}
	return results, nil
}

func (a *OpenFGAAdapter) WriteTuples(ctx context.Context, tuples []domain.Tuple) error {
	if a.apiClient != nil {
		var writes []client.ClientTupleKey
		for _, t := range tuples {
			writes = append(writes, client.ClientTupleKey{
				User:     t.User,
				Relation: t.Relation,
				Object:   t.Object,
			})
		}

		body := client.ClientWriteRequest{
			Writes: writes,
		}

		_, err := a.apiClient.Write(ctx).Body(body).Execute()
		if err != nil {
			return fmt.Errorf("OpenFGA SDK write tuples failed: %w", err)
		}
		return nil
	}

	a.mu.Lock()
	defer a.mu.Unlock()
	for _, t := range tuples {
		key := fmt.Sprintf("%s#%s@%s", t.Object, t.Relation, t.User)
		a.memTuples[key] = true
	}
	return nil
}

func (a *OpenFGAAdapter) DeleteTuples(ctx context.Context, tuples []domain.Tuple) error {
	if a.apiClient != nil {
		var deletes []client.ClientTupleKeyWithoutCondition
		for _, t := range tuples {
			deletes = append(deletes, client.ClientTupleKeyWithoutCondition{
				User:     t.User,
				Relation: t.Relation,
				Object:   t.Object,
			})
		}

		body := client.ClientWriteRequest{
			Deletes: deletes,
		}

		_, err := a.apiClient.Write(ctx).Body(body).Execute()
		if err != nil {
			return fmt.Errorf("OpenFGA SDK delete tuples failed: %w", err)
		}
		return nil
	}

	a.mu.Lock()
	defer a.mu.Unlock()
	for _, t := range tuples {
		key := fmt.Sprintf("%s#%s@%s", t.Object, t.Relation, t.User)
		delete(a.memTuples, key)
	}
	return nil
}

func (a *OpenFGAAdapter) ListObjects(ctx context.Context, user string, relation string, objectType string) ([]string, error) {
	if a.apiClient != nil {
		body := client.ClientListObjectsRequest{
			User:     user,
			Relation: relation,
			Type:     objectType,
		}

		resp, err := a.apiClient.ListObjects(ctx).Body(body).Execute()
		if err != nil {
			return nil, fmt.Errorf("OpenFGA SDK list objects failed: %w", err)
		}

		return resp.GetObjects(), nil
	}

	return []string{}, nil
}

// Helper to seed memory tuples for testing
func (a *OpenFGAAdapter) SetLocalTuple(object, relation, user string, allowed bool) {
	a.mu.Lock()
	defer a.mu.Unlock()
	key := fmt.Sprintf("%s#%s@%s", object, relation, user)
	if allowed {
		a.memTuples[key] = true
	} else {
		delete(a.memTuples, key)
	}
}
